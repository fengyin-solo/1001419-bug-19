"""隧道设施业务规则：状态流转、班组权限、经办台账与筛选口径都收在这里。

权限口径：
- 隧道登记后处于「待移交」，尚未明确责任班组，可由任一养护班组办理移交并承接；
- 只有该隧道的责任班组能安排检修、停用隧道，其他岗位一律只读，越权提交会被拦下；
- 「已停用」为终态，停用的隧道不能再回到正常养护或其他任何状态。

台账口径：同一条隧道、同一个动作重复提交时，只保留最后一次结果，
经办班组与经办人以请求携带的登录身份为准，提交体里夹带的经办信息一律不采信。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.identity import Operator
from app.store import store

MODULE = "tunnel"
REQUIRED_FIELDS = ["隧道编码", "隧道名称", "隧道长度"]
# 隧道原有展示字段，登记与台账改造均不得增删这些字段。
ORIGINAL_FIELDS = [
    "隧道编码", "隧道名称", "隧道长度", "断面形式",
    "照明方式", "通风方式", "管养单位", "隧道状态",
]
TEAM_FIELD = "责任班组"
STATUS_ORDER = ["待移交", "正常养护", "检修封闭", "已停用"]
TERMINAL_STATUS = "已停用"

# 每个动作允许从哪些状态发起；「已停用」不在任何动作的允许来源里，即终态不可逆。
ACTION_FLOW: dict[str, dict[str, Any]] = {
    "办理移交": {"target": "正常养护", "from": ["待移交"]},
    "安排检修": {"target": "检修封闭", "from": ["正常养护", "检修封闭"]},
    "停用隧道": {"target": "已停用", "from": ["待移交", "正常养护", "检修封闭"]},
}
# 台账中按动作归集的记录键（同键重复提交只留最后一次）。
RECORD_KEYS = {"办理移交": "办理移交", "安排检修": "检修记录", "停用隧道": "停用记录"}


class PermissionError(Exception):
    """越权操作：当前岗位不是该隧道的责任班组。"""


class ConflictError(Exception):
    """状态冲突：当前状态不允许该动作（如已停用隧道试图恢复养护）。"""


class TunnelService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("隧道编码", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = rows[start:start + size]
        return [self._serialize(row) for row in page_rows], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._serialize(row, include_records=True) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        # 原有字段照旧保留，缺哪个补哪个，不改字段名也不丢字段。
        for field in ORIGINAL_FIELDS:
            entry[field] = values.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry[TEAM_FIELD] = None
        entry["records"] = {}
        rows.append(entry)
        return self._serialize(entry), []

    def run_action(
        self,
        entry_id: int,
        action: str,
        operator: Operator,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"隧道设施 {entry_id} 不存在或已归档"
        if action not in ACTION_FLOW:
            return None, f"动作「{action}」不属于隧道设施可执行范围"

        current = str(entry.get("status") or "")
        if current == TERMINAL_STATUS:
            raise ConflictError(
                f"该隧道已停用，不能再回到正常养护或继续安排检修，任何改动均不被允许"
            )

        flow = ACTION_FLOW[action]
        if not operator.is_crew:
            raise PermissionError(
                f"当前岗位「{operator.team}」不是隧道「{entry.get('隧道名称', '')}」的责任班组，"
                f"仅可查看，不能{action}"
            )

        owner = entry.get(TEAM_FIELD)
        if action != "办理移交" and owner != operator.team:
            raise PermissionError(
                f"隧道「{entry.get('隧道名称', '')}」的责任班组是「{owner or '未移交'}」，"
                f"当前班组「{operator.team}」无权{action}；仅责任班组可操作，其他岗位只能查看"
            )
        if action == "办理移交":
            if owner is not None:
                raise PermissionError(
                    f"隧道「{entry.get('隧道名称', '')}」已由「{owner}」承接，"
                    f"当前班组「{operator.team}」不能重复办理移交"
                )
            if current not in flow["from"]:
                raise ConflictError(f"隧道当前为「{current}」，不允许{action}")
        elif current not in flow["from"]:
            raise ConflictError(f"隧道当前为「{current}」，不允许{action}")

        target = flow["target"]
        entry["status"] = target
        entry["pending"] = target != TERMINAL_STATUS
        entry["abnormal"] = target == TERMINAL_STATUS
        if action == "办理移交":
            # 承接移交的班组即成为该隧道的责任班组。
            entry[TEAM_FIELD] = operator.team

        # 经办痕迹只记登录身份；同动作重复提交覆盖同一条记录，只留最后一次结果。
        # 必须按条目独立建台账字典，避免缺键时多条隧道共享同一个 dict 造成串记。
        record_key = RECORD_KEYS[action]
        records = dict(entry.get("records") or {})
        records[record_key] = {
            "动作": action,
            "结果状态": target,
            "责任班组": operator.team,
            "经办人": operator.name,
            "经办时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        entry["records"] = records
        return self._serialize(entry, include_records=True), f"隧道设施已{action}"

    def _serialize(self, entry: dict[str, Any], *, include_records: bool = False) -> dict[str, Any]:
        """统一出口：列表与详情都从这里出，保证班组、状态口径一致。

        「隧道状态」对外一律展示内部流转状态，避免台账状态与页面显示两样；
        责任班组未定时显示「未移交」。
        """
        data = {"id": entry["id"]}
        for field in ORIGINAL_FIELDS:
            data[field] = entry.get(field)
        data["隧道状态"] = entry.get("status")
        data[TEAM_FIELD] = entry.get(TEAM_FIELD) or "未移交"
        data["status"] = entry.get("status")
        if include_records:
            records = entry.get("records") or {}
            # 按办理移交、检修记录、停用记录的固定顺序给出，便于详情页直接展示。
            data["检修记录"] = [records[key] for key in RECORD_KEYS.values() if key in records]
        return data

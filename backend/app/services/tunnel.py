"""隧道设施业务规则：责任班组鉴权、状态流转、检修留痕与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "tunnel"
REQUIRED_FIELDS = ["隧道编码", "隧道名称", "隧道长度"]
TEAM_FIELD = "责任班组"
STATUS_FIELD = "隧道状态"
LEDGER_FIELD = "检修记录"
STATUS_ORDER = ["待移交", "正常养护", "检修封闭", "已停用"]
ACTION_RULES = {"办理移交": "正常养护", "安排检修": "检修封闭", "停用隧道": "已停用"}
NEGATIVE_ACTIONS = ["停用隧道"]
# 允许的状态流转：只给出路，已停用不在任何键里，即终态不可回退。
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "待移交": {"正常养护"},
    "正常养护": {"检修封闭", "已停用"},
    "检修封闭": {"已停用"},
}
# 每个动作只保留最后一次结果，重复提交覆盖同一动作的台账记录。
LEDGER_ACTIONS = ["办理移交", "安排检修", "停用隧道"]


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
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._present(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry[TEAM_FIELD] = str(values.get(TEAM_FIELD) or "").strip()
        entry[LEDGER_FIELD] = {}
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), []

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        operator: str | None = None,
        team: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"隧道设施 {entry_id} 不存在或已归档"
        operator = str(operator or "").strip()
        team = str(team or "").strip()
        if not operator or not team:
            return None, "无法识别当前操作岗位，请以责任班组身份登录后再提交"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于隧道设施可执行范围"

        owner_team = str(entry.get(TEAM_FIELD) or "").strip()
        if not owner_team:
            return None, "该隧道尚未指定责任班组，暂不能安排检修或停用，请先完成移交建档"
        if team != owner_team:
            return (
                None,
                f"越权操作被阻断：隧道「{entry.get('隧道名称', entry_id)}」的责任班组是"
                f"「{owner_team}」，当前岗位「{team}」只能查看，不能执行「{action}」",
            )

        current = str(entry.get("status") or "")
        target = ACTION_RULES[action]
        if current == STATUS_ORDER[-1]:
            return None, f"隧道已处于「{current}」终态，不能再回到正常养护或安排任何作业"
        if current == target:
            # 同一动作重复提交：状态不再变化，仅覆盖该动作的经办痕迹，只留最后一次结果。
            self._write_ledger(entry, action, target, operator, team)
            return self._present(entry), f"隧道设施已{action}（重复提交已覆盖旧记录），经办已记为{team}·{operator}"
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            return None, f"隧道当前为「{current}」，不允许直接「{action}」到「{target}」"

        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        self._write_ledger(entry, action, target, operator, team)
        return self._present(entry), f"隧道设施已{action}，经办已记为{team}·{operator}"

    def _write_ledger(
        self,
        entry: dict[str, Any],
        action: str,
        target: str,
        operator: str,
        team: str,
    ) -> None:
        # 经办痕迹只信服务端从请求身份取到的操作人与班组；同动作重复提交覆盖旧记录。
        ledger = entry.setdefault(LEDGER_FIELD, {})
        ledger[action] = {
            "结果状态": target,
            "操作人": operator,
            "责任班组": team,
            "操作时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _present(self, entry: dict[str, Any]) -> dict[str, Any]:
        """出参统一：台账字段与隧道状态以内部状态为准，列表与详情同源不会两样。"""
        data = dict(entry)
        status = str(data.get("status") or "")
        if status in STATUS_ORDER:
            data[STATUS_FIELD] = status
        data.setdefault(TEAM_FIELD, "")
        data.setdefault(LEDGER_FIELD, {})
        return data

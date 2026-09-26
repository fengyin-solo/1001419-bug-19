"""不依赖 fastapi/pydantic 的业务规则自检：用桩模块加载真实 service/store/seed。"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def install_stubs() -> None:
    fastapi = types.ModuleType("fastapi")

    def _missing(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("stub 不应被服务层调用")

    class _Raiser:
        def __init__(self, *args, **kwargs) -> None:
            _missing()

    fastapi.APIRouter = _Raiser
    fastapi.HTTPException = _Raiser
    fastapi.Query = _missing
    fastapi.Depends = _missing
    fastapi.Header = lambda *args, **kwargs: None
    sys.modules["fastapi"] = fastapi

    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, **_kwargs):  # noqa: ANN001
        return default

    pydantic.BaseModel = BaseModel
    pydantic.Field = Field
    sys.modules["pydantic"] = pydantic

    schemas = types.ModuleType("app.schemas")
    sys.modules["app.schemas"] = schemas


install_stubs()

from app.identity import Operator  # noqa: E402
from app.services.tunnel import (  # noqa: E402
    ACTION_FLOW,
    ConflictError,
    PermissionError as TunnelPermissionError,
    TunnelService,
)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILED += 1
        print(f"  ✗ {name} {detail}")


crew1 = Operator("一班经办人", "隧道养护一班")
crew2 = Operator("二班经办人", "隧道养护二班")
crew3 = Operator("三班经办人", "隧道养护三班")
viewer = Operator("值班管理员", "监控值班岗")


def fresh_service() -> TunnelService:
    # store 是单例，每个场景重置一次内存数据
    from app.store import store

    for module in list(store._tables):
        del store._tables[module]
    from app.seed import SEED_ROWS

    store._tables.update({name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()})
    return TunnelService()


print("场景1：越权班组不能安排/停用他人隧道")
svc = fresh_service()
try:
    svc.run_action(2, "安排检修", crew2)
    check("二班操作一班隧道被阻断", False)
except TunnelPermissionError as exc:
    check("二班操作一班隧道被阻断", "责任班组是「隧道养护一班」" in str(exc), str(exc))

try:
    svc.run_action(2, "停用隧道", crew3)
    check("三班停用一班隧道被阻断", False)
except TunnelPermissionError as exc:
    check("三班停用一班隧道被阻断", "无权停用隧道" in str(exc), str(exc))

try:
    svc.run_action(2, "安排检修", viewer)
    check("只读岗位操作被阻断", False)
except TunnelPermissionError as exc:
    check("只读岗位操作被阻断", "仅可查看" in str(exc), str(exc))
entry, _ = svc.run_action(2, "安排检修", crew1)
check("责任班组自己操作成功", entry is not None and entry["status"] == "检修封闭")
check("责任班组列显示一致", entry["责任班组"] == "隧道养护一班")

print("场景2：已停用隧道不能回到正常养护，任何后续动作都拒绝")
svc = fresh_service()
entry, _ = svc.run_action(2, "停用隧道", crew1)
from app.store import store as _store  # noqa: E402
raw = _store.find("tunnel", 2)
check("责任班组可停用", entry["status"] == "已停用" and raw["abnormal"] is True and raw["pending"] is False)
for actor in (crew1, crew2, viewer):
    try:
        svc.run_action(2, "安排检修", actor)
        check(f"停用后 {actor.team} 再操作被拒", False)
    except ConflictError as exc:
        check(f"停用后 {actor.team} 再操作被拒", "已停用" in str(exc), str(exc))
    except TunnelPermissionError:
        check(f"停用后 {actor.team} 再操作被拒", False, "应返回终态冲突而非权限错误")

print("场景3：同动作重复提交只留最后一次，经办人跟对登录身份")
svc = fresh_service()
# 伪造提交体里夹带经办人，服务签名不接收该字段，天然无法影响痕迹
svc.run_action(2, "安排检修", crew1)
entry, _ = svc.run_action(2, "安排检修", crew1)
raw = _store.find("tunnel", 2)
check("台账中检修记录键只有一份（未重复堆积）", list(raw["records"]).count("检修记录") == 1)
check("详情台账包含移交+检修两条不同动作", len(entry["检修记录"]) == 2)
records = {r["动作"]: r for r in entry["检修记录"]}
check("检修经办人是登录身份", records["安排检修"]["经办人"] == "一班经办人")
check("经办班组是责任班组", records["安排检修"]["责任班组"] == "隧道养护一班")
# 同一隧道再次安排检修（封闭期内重复提交），覆盖旧记录、经办人更新为最新登录人
crew1b = Operator("一班替班人员", "隧道养护一班")
entry, _ = svc.run_action(2, "安排检修", crew1b)
records = {r["动作"]: r for r in entry["检修记录"]}
check("重复提交后检修记录仍是一条", list(_store.find("tunnel", 2)["records"]).count("检修记录") == 1)
check("最后一次经办人为最新登录人", records["安排检修"]["经办人"] == "一班替班人员")
check("状态保持检修封闭，未出现两条互相矛盾的结果", records["安排检修"]["结果状态"] == "检修封闭")
# 台账隔离：操作 2 号隧道不能在 1 号隧道台账里留下任何记录
check("台账不串隧道：1 号隧道记录仍为空", _store.find("tunnel", 1)["records"] == {})
check("台账不串隧道：3 号隧道记录不受影响",
      list(_store.find("tunnel", 3)["records"]) == ["办理移交", "检修记录"])

print("场景4：移交承接逻辑——未移交隧道任何养护班组可承接，承接后归属该班组")
svc = fresh_service()
try:
    svc.run_action(1, "办理移交", viewer)
    check("只读岗不能承接移交", False)
except TunnelPermissionError:
    check("只读岗不能承接移交", True)
entry, _ = svc.run_action(1, "办理移交", crew3)
check("三班承接成功并归属三班", entry["责任班组"] == "隧道养护三班" and entry["status"] == "正常养护")
try:
    svc.run_action(1, "办理移交", crew1)
    check("已承接隧道不能被别班重复移交", False)
except TunnelPermissionError as exc:
    check("已承接隧道不能被别班重复移交", "已由「隧道养护三班」承接" in str(exc), str(exc))
try:
    svc.run_action(1, "安排检修", crew1)
    check("非责任班组不能安排检修", False)
except TunnelPermissionError:
    check("非责任班组不能安排检修", True)
entry, _ = svc.run_action(1, "安排检修", crew3)
check("承接班组可安排检修", entry["status"] == "检修封闭")

print("场景5：非法状态流转被拒（如待移交直接安排检修）")
svc = fresh_service()
try:
    svc.run_action(1, "安排检修", crew1)
    check("待移交隧道不能直接安排检修", False)
except TunnelPermissionError as exc:
    # id=1 未移交，非归属判断会先触发权限错误，信息同样清楚
    check("待移交且未归属时外班组被权限拦下", "未移交" in str(exc), str(exc))
try:
    svc.run_action(1, "停用隧道", crew1)
    check("待移交隧道责任未定，停用被权限拦截", False)
except TunnelPermissionError:
    check("待移交隧道责任未定，停用被权限拦截", True)
check("状态机配置不含从已停用出发的流转",
      all(TERMINAL not in rule["from"] for rule in ACTION_FLOW.values()
          for TERMINAL in ("已停用",)))

print("场景6：列表与详情口径一致")
svc = fresh_service()
items, total = svc.list_entries(page=1, size=20)
detail = svc.get_entry(2)
list_row = next(item for item in items if item["id"] == 2)
check("列表/详情状态一致", list_row["status"] == detail["status"] == "正常养护")
check("列表/详情责任班组一致", list_row["责任班组"] == detail["责任班组"] == "隧道养护一班")
check("隧道状态对外等于内部状态", list_row["隧道状态"] == list_row["status"])
check("列表不携带检修记录", "检修记录" not in list_row)
check("详情携带检修记录", "检修记录" in detail)
unassigned = next(item for item in items if item["id"] == 1)
check("未移交隧道责任班组显示未移交", unassigned["责任班组"] == "未移交")

print("场景7：原有字段照旧保留")
svc = fresh_service()
detail = svc.get_entry(1)
for field in ["隧道编码", "隧道名称", "隧道长度", "断面形式", "照明方式", "通风方式", "管养单位", "隧道状态"]:
    check(f"字段「{field}」仍在", field in detail)

print("场景8：登记新隧道默认待移交、无责任班组")
svc = fresh_service()
entry, missing = svc.create_entry({"隧道编码": "TUNN-9001", "隧道名称": "新建隧道", "隧道长度": "1200m"})
check("登记成功", not missing and entry["status"] == "待移交")
check("新隧道未移交", entry["责任班组"] == "未移交")

print(f"\n通过 {PASSED} 项，失败 {FAILED} 项")
sys.exit(1 if FAILED else 0)

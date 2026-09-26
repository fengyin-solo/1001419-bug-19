"""隧道设施接口：维护隧道设施，覆盖办理移交、安排检修、停用隧道等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.tunnel import TunnelService

router = APIRouter(prefix="/api/tunnel", tags=["隧道设施"])

service = TunnelService()

LIST_FIELDS = ["隧道编码", "隧道名称", "隧道长度", "断面形式", "照明方式", "通风方式", "管养单位", "责任班组", "隧道状态"]
STATUSES = ["待移交", "正常养护", "检修封闭", "已停用"]


def _decode_header(value: str | None) -> str | None:
    """还原中文请求头。

    HTTP 头按 latin-1 解码，而浏览器 fetch 会直接发送 UTF-8 字节；这里把被
    误解码的字符串还原为 UTF-8。纯 ASCII 的身份名保持不变。
    """
    if value is None:
        return None
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def current_operator(
    x_operator: str | None = Header(default=None, alias="X-Operator"),
    x_team: str | None = Header(default=None, alias="X-Team"),
) -> tuple[str | None, str | None]:
    """从请求头认定当前操作岗位；身份由登录会话签发，不接受请求体里夹带的他人姓名。"""
    return _decode_header(x_operator), _decode_header(x_team)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按隧道编码检索"),
    status: str | None = Query(default=None, description="待移交、正常养护、检修封闭、已停用"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按隧道编码与状态过滤隧道设施列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出隧道设施清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "tunnel", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条隧道设施明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"隧道设施 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条隧道设施，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="隧道设施已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    identity: tuple[str | None, str | None] = Depends(current_operator),
) -> ActionResult:
    """对单条隧道设施执行办理移交、安排检修、停用隧道。

    只有该隧道的责任班组可以改动；越权提交、已停用隧道回退、非法状态流转都会被拦下，
    并在 message 里说明具体是哪里不被允许。
    """
    action = str(payload.values.get("action") or "").strip()
    operator, team = identity
    entry, message = service.run_action(entry_id, action, operator=operator, team=team)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

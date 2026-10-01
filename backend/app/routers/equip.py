"""养护机械接口：维护养护机械，覆盖安排保养、确认可用、报废机械等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, EquipPageResult
from app.services.equip import (
    DEFAULT_SIZE,
    DEFAULT_SORT,
    SORT_BY_CODE,
    SORT_BY_NEXT_MAINT,
    SORT_OPTIONS,
    EquipService,
)

router = APIRouter(prefix="/api/equip", tags=["养护机械"])

service = EquipService()

LIST_FIELDS = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]
STATUSES = ["待保养", "可用", "保养中", "已报废"]


def _query(
    keyword: str | None,
    status: str | None,
    sort: str,
    page: int,
    size: int,
) -> dict[str, Any]:
    if sort not in SORT_OPTIONS:
        raise HTTPException(status_code=400, detail="排序方式仅支持按机械编号或按下次保养日")
    if page < 1:
        raise HTTPException(status_code=400, detail="页码必须从 1 开始")
    if size < 1:
        raise HTTPException(status_code=400, detail="每页条数不能小于 1")
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    return service.query_entries(keyword=keyword, status=status, sort=sort, page=page, size=size)


@router.get("", response_model=EquipPageResult)
def list_entries(
    keyword: str | None = Query(default=None, description="按机械编号、名称、型号检索"),
    status: str | None = Query(default=None, description="待保养、可用、保养中、已报废"),
    sort: str = Query(default=DEFAULT_SORT, description=f"{SORT_BY_CODE}=按机械编号；{SORT_BY_NEXT_MAINT}=按下次保养日由近到远"),
    page: int = 1,
    size: int = DEFAULT_SIZE,
) -> dict[str, Any]:
    """养护机械台账：排序、报废拆分与分页规则全部来自 EquipService.query_entries。"""
    return _query(keyword, status, sort, page, size)


@router.get("/reminders", response_model=EquipPageResult)
def list_reminders(
    keyword: str | None = Query(default=None, description="按机械编号、名称、型号检索"),
    status: str | None = Query(default=None, description="待保养、可用、保养中、已报废"),
    sort: str = Query(default=DEFAULT_SORT, description=f"{SORT_BY_CODE}=按机械编号；{SORT_BY_NEXT_MAINT}=按下次保养日由近到远"),
    page: int = 1,
    size: int = DEFAULT_SIZE,
) -> dict[str, Any]:
    """保养提醒清单：与台账共用同一套排序、收起与分页口径，只额外标注提醒分级。"""
    payload = _query(keyword, status, sort, page, size)
    return service.with_reminders(payload)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出养护机械清单：在统一取数口径上合并在册与已报废机械，导出全量数据。"""
    payload = service.query_entries(page=1, size=10000)
    items = list(payload["items"]) + list(payload["retired_items"])
    return {"module": "equip", "total": payload["total"] + payload["retired_total"], "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict[str, Any]:
    """读取单条养护机械明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"养护机械 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条养护机械，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="养护机械已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条养护机械执行安排保养、确认可用、报废机械；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

"""养护机械接口：维护养护机械，覆盖安排保养、确认可用、报废机械等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.equip import DEFAULT_SORT, SORT_MODES, EquipService

router = APIRouter(prefix="/api/equip", tags=["养护机械"])

service = EquipService()

LIST_FIELDS = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]
STATUSES = ["待保养", "可用", "保养中", "已报废"]


def _list_page(
    keyword: str | None,
    name: str | None,
    model: str | None,
    status: str | None,
    sort: str,
    include_scrapped: bool,
    page: int,
    size: int,
    *,
    reminder: bool,
) -> PageResult[dict]:
    """台账与保养提醒清单共用的取数入口：同一套排序、收起与分页口径。"""
    if size < 1 or size > 200:
        raise HTTPException(status_code=400, detail="每页条数需在 1 到 200 之间，请调整分页范围")
    if sort not in SORT_MODES:
        raise HTTPException(status_code=400, detail=f"未知排序方式「{sort}」，可选：{'、'.join(SORT_MODES)}")
    list_method = service.list_reminders if reminder else service.list_entries
    items, total = list_method(
        keyword=keyword,
        name=name,
        model=model,
        status=status,
        sort=sort,
        include_scrapped=include_scrapped,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按机械编号检索"),
    name: str | None = Query(default=None, description="按机械名称检索"),
    model: str | None = Query(default=None, description="按机械型号检索"),
    status: str | None = Query(default=None, description="待保养、可用、保养中、已报废"),
    sort: str = Query(default=DEFAULT_SORT, description="code 按机械编号；next_maintenance 按下次保养日由近到远"),
    include_scrapped: bool = Query(default=False, description="已报废机械默认收起，传 true 主动展开"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按条件过滤养护机械台账；没有数据时返回空页，不报错。"""
    return _list_page(keyword, name, model, status, sort, include_scrapped, page, size, reminder=False)


@router.get("/reminders", response_model=PageResult[dict])
def list_reminders(
    keyword: str | None = Query(default=None, description="按机械编号检索"),
    name: str | None = Query(default=None, description="按机械名称检索"),
    model: str | None = Query(default=None, description="按机械型号检索"),
    status: str | None = Query(default=None, description="待保养、可用、保养中、已报废"),
    sort: str = Query(default=DEFAULT_SORT, description="code 按机械编号；next_maintenance 按下次保养日由近到远"),
    include_scrapped: bool = Query(default=False, description="已报废机械默认收起，传 true 主动展开"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """保养提醒清单：与台账共用同一套排序与收起规则，次序与条数保持一致。"""
    return _list_page(keyword, name, model, status, sort, include_scrapped, page, size, reminder=True)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出养护机械清单：返回当前过滤条件下的全量数据，已报废机械一并导出。"""
    items, total = service.list_entries(page=1, size=10000, include_scrapped=True)
    return {"module": "equip", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
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

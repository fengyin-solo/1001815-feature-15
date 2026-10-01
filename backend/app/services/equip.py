"""养护机械业务规则：状态流转、字段校验与筛选口径都收在这里。

台账列表与保养提醒清单共用 query_entries 这一个取数口径：
排序方式、已报废机械的拆分、分页条数都只有这一份实现，保证两处读到的
机械次序与条数完全一致。
"""
from __future__ import annotations

from datetime import date
from math import ceil
from typing import Any

from app.store import store

MODULE = "equip"
REQUIRED_FIELDS = ["机械编号", "机械名称", "机械型号"]
STATUS_ORDER = ["待保养", "可用", "保养中", "已报废"]
ACTION_RULES = {"安排保养": "保养中", "确认可用": "可用", "报废机械": "已报废"}
NEGATIVE_ACTIONS = []

SORT_BY_CODE = "code"
SORT_BY_NEXT_MAINT = "next_maintain"
SORT_OPTIONS = (SORT_BY_CODE, SORT_BY_NEXT_MAINT)
DEFAULT_SORT = SORT_BY_CODE
DEFAULT_SIZE = 10

_REMINDER_SOON_DAYS = 7
# 无法识别的保养日期按最晚处理，排序时沉到最后，不参与提醒分级
_DATE_FAR = date.max


class EquipService:
    def query_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        sort: str = DEFAULT_SORT,
        page: int = 1,
        size: int = DEFAULT_SIZE,
    ) -> dict[str, Any]:
        """台账与保养提醒清单的统一取数入口。

        返回在册（未报废）机械的当前页，以及完整的已报废机械清单：
        报废机械默认收起，由前端决定何时展开，因此不分页但走同一套排序。
        """
        if sort not in SORT_OPTIONS:
            sort = DEFAULT_SORT
        size = max(size, 1)
        page = max(page, 1)

        rows = store.rows(MODULE)
        if keyword:
            keyword = keyword.strip()
            if keyword:
                rows = [
                    row for row in rows
                    if keyword in str(row.get("机械编号", ""))
                    or keyword in str(row.get("机械名称", ""))
                    or keyword in str(row.get("机械型号", ""))
                ]
        if status:
            rows = [row for row in rows if row.get("status") == status]

        active = [row for row in rows if row.get("status") != STATUS_ORDER[-1]]
        retired = [row for row in rows if row.get("status") == STATUS_ORDER[-1]]
        active.sort(key=lambda row: self._sort_key(row, sort))
        retired.sort(key=lambda row: self._sort_key(row, sort))

        total = len(active)
        total_pages = max(1, ceil(total / size)) if total else 0
        # 请求页超出范围时夹到最后一页，避免筛选后停在空页
        page = min(page, total_pages) if total_pages else 1
        start = (page - 1) * size
        page_items = active[start:start + size]

        status_counts = {label: 0 for label in STATUS_ORDER}
        for row in rows:
            label = row.get("status")
            if label in status_counts:
                status_counts[label] += 1

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "sort": sort,
            "retired_items": retired,
            "retired_total": len(retired),
            "status_counts": status_counts,
        }

    @staticmethod
    def _sort_key(row: dict[str, Any], sort: str) -> tuple[Any, ...]:
        # 排序只看排序字段本身，停放场地等其它字段一律不参与，
        # 保证机械停在哪个场地都不影响它的名次
        code = str(row.get("机械编号", ""))
        if sort == SORT_BY_NEXT_MAINT:
            return (EquipService._parse_date(row.get("下次保养日")), code)
        return (code,)

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if not text:
            return _DATE_FAR
        try:
            return date.fromisoformat(text)
        except ValueError:
            return _DATE_FAR

    def with_reminders(self, payload: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
        """在统一取数结果上补保养提醒分级；不动原始取数口径与条数。"""
        today = today or date.today()

        def annotate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            annotated: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                level, days = self._reminder_level(row, today)
                item["reminder_level"] = level
                item["reminder_days"] = days
                annotated.append(item)
            return annotated

        result = dict(payload)
        result["items"] = annotate(list(payload["items"]))
        result["retired_items"] = annotate(list(payload["retired_items"]))
        return result

    def _reminder_level(self, row: dict[str, Any], today: date) -> tuple[str, int | None]:
        if row.get("status") == STATUS_ORDER[-1]:
            return "retired", None
        text = str(row.get("下次保养日") or "").strip()
        if not text:
            return "unscheduled", None
        try:
            next_day = date.fromisoformat(text)
        except ValueError:
            return "unscheduled", None
        days = (next_day - today).days
        if days < 0:
            return "overdue", days
        if days == 0:
            return "today", days
        if days <= _REMINDER_SOON_DAYS:
            return "soon", days
        return "normal", days

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护机械 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护机械可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"养护机械已{action}"

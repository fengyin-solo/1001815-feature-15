"""养护机械业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "equip"
REQUIRED_FIELDS = ["机械编号", "机械名称", "机械型号"]
STATUS_ORDER = ["待保养", "可用", "保养中", "已报废"]
ACTION_RULES = {"安排保养": "保养中", "确认可用": "可用", "报废机械": "已报废"}
NEGATIVE_ACTIONS = []

SCRAPPED_STATUS = "已报废"

# 排序与收起规则只在这里定义一份，台账列表与保养提醒清单都按它取数。
SORT_BY_CODE = "code"
SORT_BY_NEXT_MAINTENANCE = "next_maintenance"
SORT_MODES = (SORT_BY_CODE, SORT_BY_NEXT_MAINTENANCE)
DEFAULT_SORT = SORT_BY_CODE


def _maintenance_day(row: dict[str, Any]) -> date:
    """解析下次保养日；缺失或无法识别的排在最后，不挤占其他机械的名次。"""
    raw = str(row.get("下次保养日") or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.max


class EquipService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        sort: str = DEFAULT_SORT,
        include_scrapped: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("机械编号", ""))]
        if name:
            rows = [row for row in rows if name in str(row.get("机械名称", ""))]
        if model:
            rows = [row for row in rows if model in str(row.get("机械型号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        # 已报废机械默认收起；主动展开、或明确按已报废状态筛选时才并入清单
        if not include_scrapped and status != SCRAPPED_STATUS:
            rows = [row for row in rows if row.get("status") != SCRAPPED_STATUS]
        rows = self._sort_rows(rows, sort)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_reminders(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        sort: str = DEFAULT_SORT,
        include_scrapped: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """保养提醒清单：与台账走同一条取数路径，两处读到的次序与条数才一致。"""
        return self.list_entries(
            keyword=keyword,
            name=name,
            model=model,
            status=status,
            sort=sort,
            include_scrapped=include_scrapped,
            page=page,
            size=size,
        )

    @staticmethod
    def _sort_rows(rows: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
        # 排序作用在筛选后的整张清单上，与机械停放在哪个场地无关
        if sort == SORT_BY_NEXT_MAINTENANCE:
            return sorted(rows, key=lambda row: (_maintenance_day(row), str(row.get("机械编号") or "")))
        return sorted(rows, key=lambda row: str(row.get("机械编号") or ""))

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

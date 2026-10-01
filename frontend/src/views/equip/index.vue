<template>
  <section class="page" data-module="equip">
    <header class="page-head">
      <div>
        <h2>养护机械管理</h2>
        <p class="page-desc">维护养护机械，围绕机械编号、机械名称、机械型号、停放场地做登记、排序、分段浏览与保养提醒。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记养护机械</button>
        <button class="btn" type="button" @click="exportRows">导出养护机械清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">在册机械</span>
        <strong class="stat-value">{{ store.total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待保养机械</span>
        <strong class="stat-value">{{ store.statusCounts['待保养'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">保养中机械</span>
        <strong class="stat-value">{{ store.statusCounts['保养中'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已报废机械</span>
        <strong class="stat-value">{{ store.retiredTotal }}</strong>
      </article>
    </div>

    <div class="tab-bar" role="tablist">
      <button
        class="tab-item"
        :class="{ active: activeTab === 'ledger' }"
        type="button"
        role="tab"
        @click="activeTab = 'ledger'"
      >
        机械台账
      </button>
      <button
        class="tab-item"
        :class="{ active: activeTab === 'reminder' }"
        type="button"
        role="tab"
        @click="activeTab = 'reminder'"
      >
        保养提醒清单
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="store.search()">
      <label class="filter-item">
        <span>机械检索</span>
        <input
          :value="store.keyword"
          placeholder="按机械编号 / 名称 / 型号检索"
          @input="store.setKeyword(($event.target as HTMLInputElement).value)"
        />
      </label>
      <label class="filter-item">
        <span>机械状态</span>
        <select :value="store.statusFilter" @change="store.setStatusFilter(($event.target as HTMLSelectElement).value)">
          <option value="">全部在册状态</option>
          <option v-for="status in activeStatuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit" :disabled="store.loading">查询</button>
      <button class="btn ghost" type="button" @click="store.resetFilters()">重置条件</button>

      <label class="filter-item">
        <span>排序方式</span>
        <select :value="store.sortMode" @change="store.setSortMode(($event.target as HTMLSelectElement).value as SortMode)">
          <option value="code">按机械编号排序</option>
          <option value="next_maintain">按下次保养日由近到远</option>
        </select>
      </label>
      <label class="filter-item">
        <span>每页条数</span>
        <select :value="store.size" @change="store.setSize(Number(($event.target as HTMLSelectElement).value))">
          <option v-for="option in PAGE_SIZE_OPTIONS" :key="option" :value="option">{{ option }} 条/页</option>
        </select>
      </label>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in ledgerColumns" :key="column">{{ column }}</th>
          <th v-if="activeTab === 'reminder'">保养提醒</th>
          <th v-if="activeTab === 'ledger'">可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in activeRows" :key="String(row.id)">
          <td v-for="column in ledgerColumns" :key="column">{{ row[column] ?? '—' }}</td>
          <td v-if="activeTab === 'reminder'" class="reminder-cell">
            <span class="reminder-tag" :class="`tag-${row.reminder_level}`">{{ reminderText(row) }}</span>
          </td>
          <td v-if="activeTab === 'ledger'" class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!activeRows.length">
          <td :colspan="ledgerColumns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <section v-if="store.retiredTotal > 0" class="retired-block">
      <button class="retired-toggle" type="button" @click="store.showRetired = !store.showRetired">
        {{ store.showRetired ? '▼' : '▶' }} 已报废机械（{{ store.retiredTotal }} 台，默认收起）
      </button>
      <table v-if="store.showRetired" class="data-table retired-table">
        <thead>
          <tr>
            <th v-for="column in ledgerColumns" :key="column">{{ column }}</th>
            <th v-if="activeTab === 'reminder'">保养提醒</th>
            <th v-if="activeTab === 'ledger'">可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in activeRetiredRows" :key="String(row.id)" class="retired-row">
            <td v-for="column in ledgerColumns" :key="column">{{ row[column] ?? '—' }}</td>
            <td v-if="activeTab === 'reminder'" class="reminder-cell">
              <span class="reminder-tag tag-retired">已报废</span>
            </td>
            <td v-if="activeTab === 'ledger'" class="row-actions">
              <span class="muted-text">已报废，无可用动作</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot equip-foot">
      <span>第 {{ store.page }} / {{ store.totalPages || 1 }} 页，共 {{ store.total }} 台在册机械</span>
      <span class="pager">
        <button class="btn" type="button" :disabled="store.page <= 1 || store.loading" @click="store.setPage(store.page - 1)">上一页</button>
        <button
          class="btn"
          type="button"
          :disabled="store.page >= store.totalPages || store.loading"
          @click="store.setPage(store.page + 1)"
        >
          下一页
        </button>
      </span>
      <span v-if="store.errorMessage" class="error-text">{{ store.errorMessage }}（已保留上次的排序与分页条件）</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { PAGE_SIZE_OPTIONS, useEquipStore, type EquipRow, type SortMode } from '@/stores/equip'

const ENDPOINT = '/api/equip'
const ledgerColumns = ['机械编号', '机械名称', '机械型号', '停放场地', '上次保养日', '下次保养日', '责任人', '机械状态']
const actions = ['安排保养', '确认可用', '报废机械']
const activeStatuses = ['待保养', '可用', '保养中']

const store = useEquipStore()
const activeTab = ref<'ledger' | 'reminder'>('ledger')

const activeRows = computed(() => (activeTab.value === 'reminder' ? store.reminderRows : store.rows))
const activeRetiredRows = computed(() => (activeTab.value === 'reminder' ? store.retiredReminderRows : store.retiredRows))

const emptyText = computed(() => {
  if (store.keyword.trim() || store.statusFilter) {
    return '没有符合检索条件的在册养护机械，可调整关键词或重置条件后再试'
  }
  if (activeTab.value === 'reminder') {
    return '暂无需要保养提醒的在册养护机械'
  }
  return '暂无在册养护机械数据，可先登记养护机械'
})

function reminderText(row: EquipRow): string {
  switch (row.reminder_level) {
    case 'overdue':
      return `已逾期 ${Math.abs(row.reminder_days ?? 0)} 天`
    case 'today':
      return '今天到期保养'
    case 'soon':
      return `${row.reminder_days} 天后保养`
    case 'normal':
      return `${row.reminder_days} 天后保养`
    case 'unscheduled':
      return '未安排保养日期'
    case 'retired':
      return '已报废'
    default:
      return '—'
  }
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  store.errorMessage = '养护机械登记入口尚未接入审批流'
}

async function runAction(action: string, row: EquipRow) {
  store.errorMessage = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('养护机械动作未生效，请稍后重试')
    }
    await store.reload()
  } catch (error) {
    store.errorMessage = error instanceof Error ? error.message : '养护机械操作失败'
  }
}

onMounted(() => {
  void store.reload()
})
</script>

<style scoped>
.tab-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.tab-item {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 6px 6px 0 0;
  padding: 8px 18px;
  cursor: pointer;
  font-size: 14px;
}
.tab-item.active { background: var(--brand); border-color: var(--brand); color: #fff; }
.filter-bar select { padding: 5px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 13px; }
.reminder-tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; white-space: nowrap; }
.tag-overdue { background: #fee4e2; color: #b42318; }
.tag-today { background: #fff4d6; color: #b54708; }
.tag-soon { background: #fef0c7; color: #93370d; }
.tag-normal { background: #e8f1ff; color: #1f6feb; }
.tag-retired { background: #e5e7eb; color: #475467; }
.tag-unscheduled { background: #f2f4f7; color: #667085; }
.retired-block { margin-top: 12px; }
.retired-toggle {
  width: 100%;
  text-align: left;
  border: 1px dashed var(--border);
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: var(--muted);
}
.retired-table { margin-top: 6px; opacity: 0.85; }
.retired-row { background: #fafafa; }
.muted-text { color: var(--muted); font-size: 12px; }
.equip-foot { align-items: center; }
.pager { display: flex; gap: 6px; }
.pager .btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>

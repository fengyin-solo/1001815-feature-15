<template>
  <section class="page" data-module="equip">
    <header class="page-head">
      <div>
        <h2>养护机械管理</h2>
        <p class="page-desc">维护养护机械，围绕机械编号、机械名称、机械型号、停放场地做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记养护机械</button>
        <button class="btn" type="button" @click="exportRows">导出养护机械清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>机械编号</span>
        <input v-model="filters['机械编号']" placeholder="按机械编号检索" />
      </label>
      <label class="filter-item">
        <span>机械名称</span>
        <input v-model="filters['机械名称']" placeholder="按机械名称检索" />
      </label>
      <label class="filter-item">
        <span>机械型号</span>
        <input v-model="filters['机械型号']" placeholder="按机械型号检索" />
      </label>
      <label class="filter-item">
        <span>机械状态</span>
        <select v-model="filters['机械状态']">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div class="toolbar">
      <div class="sort-toggle" role="group" aria-label="排序方式">
        <span class="toolbar-label">排序方式</span>
        <button
          v-for="option in sortOptions"
          :key="option.value"
          class="btn"
          :class="{ primary: sortMode === option.value }"
          type="button"
          @click="setSort(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
      <label class="scrap-toggle">
        <input v-model="includeScrapped" type="checkbox" @change="resetPageAndReload" />
        展开已报废机械
      </label>
      <label class="size-picker">
        每页
        <select v-model.number="size" @change="resetPageAndReload">
          <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
        </select>
        条
      </label>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
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
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条养护机械记录</span>
      <div class="pager">
        <button class="btn ghost" type="button" :disabled="page <= 1" @click="goToPage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ pageCount }} 页</span>
        <button class="btn ghost" type="button" :disabled="page >= pageCount" @click="goToPage(page + 1)">下一页</button>
      </div>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <section class="reminder-panel">
      <header class="reminder-head">
        <h3>保养提醒清单</h3>
        <p class="reminder-desc">与台账共用同一套排序与收起规则，按当前筛选、排序与分页条件一起取数。</p>
      </header>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in reminderColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in reminders" :key="String(row.id)">
            <td v-for="column in reminderColumns" :key="column">{{ row[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!reminders.length">
            <td :colspan="reminderColumns.length" class="empty-state">当前条件下没有需要提醒的保养机械</td>
          </tr>
        </tbody>
      </table>
      <footer class="reminder-foot">
        <span>共 {{ reminderTotal }} 条保养提醒，与台账第 {{ page }} 页同序</span>
      </footer>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type PageResult = { items: Row[]; total: number; page: number; size: number }
type SortMode = 'code' | 'next_maintenance'
type ListConditions = { sort: SortMode; includeScrapped: boolean; page: number; size: number }

const ENDPOINT = '/api/equip'
const columns = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]
const reminderColumns = ["机械编号", "机械名称", "下次保养日", "机械状态"]
const actions = ["安排保养", "确认可用", "报废机械"]
const statuses = ["待保养", "可用", "保养中", "已报废"]
const stats = [{"label": "在册机械", "value": 0}, {"label": "待保养机械", "value": 0}, {"label": "保养中机械", "value": 0}]
const sortOptions: { value: SortMode; label: string }[] = [
  { value: 'code', label: '按机械编号' },
  { value: 'next_maintenance', label: '按下次保养日由近到远' },
]
const sizeOptions = [5, 10, 20, 50]

const rows = ref<Row[]>([])
const total = ref(0)
const reminders = ref<Row[]>([])
const reminderTotal = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ 机械编号: '', 机械名称: '', 机械型号: '', 机械状态: '' })

const sortMode = ref<SortMode>('code')
const includeScrapped = ref(false)
const page = ref(1)
const size = ref(10)
// 上一次成功取数时的排序与分页条件；取数失败时回退到它，避免清单和条件对不上
const applied = ref<ListConditions>({ sort: 'code', includeScrapped: false, page: 1, size: 10 })

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const hasActiveFilter = computed(() => Object.values(filters.value).some((value) => value.trim() !== ''))
const emptyHint = computed(() => {
  if (hasActiveFilter.value) {
    return '没有符合条件的养护机械，请调整筛选条件后重试'
  }
  if (!includeScrapped.value) {
    return '没有符合条件的养护机械，已报废机械默认收起，可主动展开查看'
  }
  return '暂无养护机械数据，可先登记养护机械'
})

function buildQuery(): string {
  const params = new URLSearchParams()
  const keyword = filters.value['机械编号'].trim()
  const name = filters.value['机械名称'].trim()
  const model = filters.value['机械型号'].trim()
  const status = filters.value['机械状态']
  if (keyword) params.set('keyword', keyword)
  if (name) params.set('name', name)
  if (model) params.set('model', model)
  if (status) params.set('status', status)
  params.set('sort', sortMode.value)
  params.set('include_scrapped', String(includeScrapped.value))
  params.set('page', String(page.value))
  params.set('size', String(size.value))
  return params.toString()
}

async function fetchPage(path: string): Promise<PageResult> {
  const response = await request(path)
  if (!response.ok) {
    let detail = `接口返回 ${response.status}`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // 保留状态码说明即可
    }
    throw new Error(detail)
  }
  return (await response.json()) as PageResult
}

function setSort(mode: SortMode) {
  if (sortMode.value === mode) {
    return
  }
  sortMode.value = mode
  // 翻页以后改动排序方式要回到第一页
  page.value = 1
  void reload()
}

function resetPageAndReload() {
  page.value = 1
  void reload()
}

function goToPage(target: number) {
  if (target < 1 || target > pageCount.value || target === page.value) {
    return
  }
  page.value = target
  void reload()
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = { 机械编号: '', 机械名称: '', 机械型号: '', 机械状态: '' }
  page.value = 1
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '养护机械登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('养护机械动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = buildQuery()
  try {
    const [ledger, reminder] = await Promise.all([
      fetchPage(`${ENDPOINT}?${query}`),
      fetchPage(`${ENDPOINT}/reminders?${query}`),
    ])
    if (!ledger.items.length && ledger.total > 0 && page.value > 1) {
      // 数据变少后当前页已越界，回到最后一页再取一次
      page.value = Math.max(1, Math.ceil(ledger.total / size.value))
      return reload()
    }
    rows.value = ledger.items
    total.value = ledger.total
    reminders.value = reminder.items
    reminderTotal.value = reminder.total
    applied.value = {
      sort: sortMode.value,
      includeScrapped: includeScrapped.value,
      page: page.value,
      size: size.value,
    }
  } catch (error) {
    // 取数失败：保留上次的排序与分页条件，已展示的清单不清空
    sortMode.value = applied.value.sort
    includeScrapped.value = applied.value.includeScrapped
    page.value = applied.value.page
    size.value = applied.value.size
    errorMessage.value = error instanceof Error ? error.message : '养护机械列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
}
.toolbar-label {
  color: var(--muted);
  font-size: 12px;
}
.sort-toggle {
  display: flex;
  gap: 6px;
  align-items: center;
}
.scrap-toggle,
.size-picker {
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--muted);
}
.pager {
  display: flex;
  gap: 8px;
  align-items: center;
}
.reminder-panel {
  margin-top: 20px;
}
.reminder-head h3 {
  margin: 0 0 4px;
  font-size: 15px;
}
.reminder-desc {
  color: var(--muted);
  font-size: 12px;
  margin: 0 0 8px;
}
.reminder-foot {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}
</style>

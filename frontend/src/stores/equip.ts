import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { request } from '@/api/client'

export type SortMode = 'code' | 'next_maintain'

export interface EquipRow {
  id: number
  status?: string
  机械编号?: string
  机械名称?: string
  机械型号?: string
  停放场地?: string
  上次保养日?: string
  下次保养日?: string
  责任人?: string
  机械状态?: string
  reminder_level?: 'overdue' | 'today' | 'soon' | 'normal' | 'retired' | 'unscheduled'
  reminder_days?: number | null
  [key: string]: string | number | null | undefined
}

export interface EquipPayload {
  items: EquipRow[]
  total: number
  page: number
  size: number
  total_pages: number
  sort: SortMode
  retired_items: EquipRow[]
  retired_total: number
  status_counts: Record<string, number>
}

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

const ENDPOINT = '/api/equip'

/**
 * 台账与保养提醒清单共用的唯一查询状态：
 * 排序方式、页码、每页条数、检索条件与报废展开状态都只存这一份，
 * 两个页面各自取数但传入相同条件，保证机械次序与条数一致。
 */
export const useEquipStore = defineStore('equip', () => {
  const sortMode = ref<SortMode>('code')
  const page = ref(1)
  const size = ref(PAGE_SIZE_OPTIONS[0])
  const keyword = ref('')
  const statusFilter = ref('')
  const showRetired = ref(false)
  const loading = ref(false)
  const errorMessage = ref('')

  const ledger = ref<EquipPayload | null>(null)
  const reminders = ref<EquipPayload | null>(null)

  // 上一次取数成功时的排序与分页；取数失败时回到它，保留上次的条件
  const lastApplied = ref({ sort: 'code' as SortMode, page: 1, size: PAGE_SIZE_OPTIONS[0] })

  const rows = computed<EquipRow[]>(() => ledger.value?.items ?? [])
  const retiredRows = computed<EquipRow[]>(() => ledger.value?.retired_items ?? [])
  const total = computed(() => ledger.value?.total ?? 0)
  const retiredTotal = computed(() => ledger.value?.retired_total ?? 0)
  const totalPages = computed(() => ledger.value?.total_pages ?? 0)
  const statusCounts = computed<Record<string, number>>(() => ledger.value?.status_counts ?? {})
  // 两处读到的机械次序与条数一致：提醒清单直接复台账的次序
  const reminderRows = computed<EquipRow[]>(() => reminders.value?.items ?? [])
  const retiredReminderRows = computed<EquipRow[]>(() => reminders.value?.retired_items ?? [])

  function buildQuery() {
    const params = new URLSearchParams()
    params.set('sort', sortMode.value)
    params.set('page', String(page.value))
    params.set('size', String(size.value))
    if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
    if (statusFilter.value) params.set('status', statusFilter.value)
    return params.toString()
  }

  /** 改动排序方式后回到第一页 */
  function setSortMode(mode: SortMode) {
    if (mode === sortMode.value) return Promise.resolve()
    sortMode.value = mode
    page.value = 1
    return reload()
  }

  /** 调整每页条数后同样回到第一页 */
  function setSize(next: number) {
    if (next === size.value) return Promise.resolve()
    size.value = next
    page.value = 1
    return reload()
  }

  function setPage(next: number) {
    const target = Math.min(Math.max(next, 1), Math.max(totalPages.value || 1, 1))
    if (target === page.value) return Promise.resolve()
    page.value = target
    return reload()
  }

  function setKeyword(value: string) {
    keyword.value = value
  }

  function setStatusFilter(value: string) {
    statusFilter.value = value
  }

  function search() {
    page.value = 1
    return reload()
  }

  function resetFilters() {
    keyword.value = ''
    statusFilter.value = ''
    page.value = 1
    return reload()
  }

  function rollbackControls() {
    // 取数失败只回滚排序与分页条件，检索框里用户刚输入的内容保留
    sortMode.value = lastApplied.value.sort
    page.value = lastApplied.value.page
    size.value = lastApplied.value.size
  }

  async function reload() {
    loading.value = true
    errorMessage.value = ''
    try {
      const query = buildQuery()
      const [ledgerResponse, reminderResponse] = await Promise.all([
        request(`${ENDPOINT}?${query}`),
        request(`${ENDPOINT}/reminders?${query}`),
      ])
      if (!ledgerResponse.ok || !reminderResponse.ok) {
        throw new Error('养护机械列表读取失败')
      }
      const [ledgerPayload, reminderPayload] = await Promise.all([
        ledgerResponse.json() as Promise<EquipPayload>,
        reminderResponse.json() as Promise<EquipPayload>,
      ])
      ledger.value = ledgerPayload
      reminders.value = reminderPayload
      // 服务端可能把越界页码夹到最后一页，控件跟随服务端结果
      sortMode.value = ledgerPayload.sort
      page.value = ledgerPayload.page
      size.value = ledgerPayload.size
      lastApplied.value = {
        sort: ledgerPayload.sort,
        page: ledgerPayload.page,
        size: ledgerPayload.size,
      }
    } catch (error) {
      rollbackControls()
      errorMessage.value = error instanceof Error ? error.message : '养护机械列表读取失败'
    } finally {
      loading.value = false
    }
  }

  return {
    sortMode,
    page,
    size,
    keyword,
    statusFilter,
    showRetired,
    loading,
    errorMessage,
    ledger,
    reminders,
    rows,
    retiredRows,
    total,
    retiredTotal,
    totalPages,
    statusCounts,
    reminderRows,
    retiredReminderRows,
    reload,
    setSortMode,
    setSize,
    setPage,
    setKeyword,
    setStatusFilter,
    search,
    resetFilters,
  }
})

import { ref, computed } from 'vue'
import { startOfDay, endOfDay, startOfWeek, startOfMonth, isWithinInterval } from 'date-fns'
import type { QaItem } from '@/types'

export type PeriodPreset = 'today' | 'week' | 'month' | 'custom'

export function useFilters(items: () => QaItem[]) {
  const manager = ref('')
  const product = ref('')
  const periodPreset = ref<PeriodPreset>('month')
  const dateFrom = ref<Date | null>(null)
  const dateTo = ref<Date | null>(null)

  const dateRange = computed<{ from: Date; to: Date }>(() => {
    if (periodPreset.value === 'custom' && dateFrom.value && dateTo.value) {
      return { from: startOfDay(dateFrom.value), to: endOfDay(dateTo.value) }
    }

    const now = new Date()
    const to = endOfDay(now)

    switch (periodPreset.value) {
      case 'today':
        return { from: startOfDay(now), to }
      case 'week':
        return { from: startOfWeek(now, { weekStartsOn: 1 }), to }
      case 'month':
      default:
        return { from: startOfMonth(now), to }
    }
  })

  const filtered = computed(() => {
    return items().filter(item => {
      if (manager.value && item.manager !== manager.value) return false
      if (product.value && item.product !== product.value) return false

      const itemDate = new Date(item.createdTime)
      if (!isWithinInterval(itemDate, { start: dateRange.value.from, end: dateRange.value.to })) {
        return false
      }

      return true
    })
  })

  const managers = computed(() => {
    const set = new Set(items().map(i => i.manager).filter(Boolean))
    return Array.from(set).sort()
  })

  const products = computed(() => {
    const set = new Set(items().map(i => i.product).filter(Boolean))
    return Array.from(set).sort()
  })

  const isMultiDay = computed(() => {
    return periodPreset.value !== 'today'
  })

  return {
    manager,
    product,
    periodPreset,
    dateFrom,
    dateTo,
    dateRange,
    filtered,
    managers,
    products,
    isMultiDay,
  }
}

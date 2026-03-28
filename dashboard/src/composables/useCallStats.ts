import { ref } from 'vue'
import type { CallStatsResponse } from '@/types'

const API_BASE = import.meta.env.VITE_API_URL || ''

export function useCallStats() {
  const stats = ref<CallStatsResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchStats(days = 30): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${API_BASE}/api/stats?days=${days}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      stats.value = await res.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Ошибка загрузки статистики'
    } finally {
      loading.value = false
    }
  }

  return { stats, loading, error, fetchStats }
}

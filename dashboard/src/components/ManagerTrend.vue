<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Tooltip, Legend,
} from 'chart.js'
import type { QaItem } from '@/types'
import { CHART_COLORS } from '@/utils/colors'
import { format } from 'date-fns'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

const props = defineProps<{ items: QaItem[] }>()

const MANAGER_COLORS = [
  'rgba(47, 198, 246, 0.9)',
  'rgba(157, 207, 0, 0.9)',
  'rgba(255, 169, 0, 0.9)',
  'rgba(153, 133, 243, 0.9)',
  'rgba(255, 87, 82, 0.9)',
  'rgba(0, 178, 169, 0.9)',
]

const chartData = computed(() => {
  // Group by date then by manager
  const byDate = new Map<string, Map<string, number[]>>()
  const managers = new Set<string>()

  for (const item of props.items) {
    const date = format(new Date(item.createdTime), 'dd.MM')
    const mgr = item.manager || 'Неизвестный'
    managers.add(mgr)

    if (!byDate.has(date)) byDate.set(date, new Map())
    const dateMap = byDate.get(date)!
    if (!dateMap.has(mgr)) dateMap.set(mgr, [])
    dateMap.get(mgr)!.push(item.scoreTotal)
  }

  const dates = [...byDate.keys()]
  const mgrList = [...managers]

  return {
    labels: dates,
    datasets: mgrList.map((mgr, i) => ({
      label: mgr,
      data: dates.map(d => {
        const scores = byDate.get(d)?.get(mgr)
        if (!scores || scores.length === 0) return null
        return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10
      }),
      borderColor: MANAGER_COLORS[i % MANAGER_COLORS.length],
      backgroundColor: MANAGER_COLORS[i % MANAGER_COLORS.length],
      tension: 0.3,
      pointRadius: 4,
      spanGaps: true,
    })),
  }
})

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { color: CHART_COLORS.text, boxWidth: 12 } },
    tooltip: {
      callbacks: {
        label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
          `${ctx.dataset.label ?? ''}: ${(ctx.parsed.y ?? 0).toFixed(1)}`,
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: CHART_COLORS.text, font: { size: 11 } } },
    y: {
      min: 0, max: 10,
      grid: { color: CHART_COLORS.gridLine },
      ticks: { color: CHART_COLORS.text, stepSize: 2 },
    },
  },
}
</script>

<template>
  <div class="b24-card">
    <h3 class="text-sm font-semibold text-b24-text mb-4">Динамика по менеджерам</h3>
    <div v-if="items.length > 0" class="h-64">
      <Line :data="chartData" :options="options" />
    </div>
    <p v-else class="text-sm text-b24-text-secondary py-8 text-center">Нет данных</p>
  </div>
</template>

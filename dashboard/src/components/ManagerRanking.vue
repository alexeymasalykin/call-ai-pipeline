<script setup lang="ts">
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  Tooltip,
} from 'chart.js'
import type { ManagerRow } from '@/types'
import { CHART_COLORS } from '@/utils/colors'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip)

const props = defineProps<{ rows: ManagerRow[] }>()

const chartData = computed(() => {
  const sorted = [...props.rows].sort((a, b) => a.avgScore - b.avgScore)
  return {
    labels: sorted.map(r => r.manager),
    datasets: [{
      data: sorted.map(r => r.avgScore),
      backgroundColor: sorted.map(r => {
        if (r.avgScore <= 3) return 'rgba(255, 87, 82, 0.75)'
        if (r.avgScore <= 6) return 'rgba(255, 169, 0, 0.75)'
        return 'rgba(157, 207, 0, 0.75)'
      }),
      borderRadius: 4,
    }],
  }
})

const options = {
  indexAxis: 'y' as const,
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx: { parsed: { x: number | null } }) => `Средняя: ${(ctx.parsed.x ?? 0).toFixed(1)}`,
      },
    },
  },
  scales: {
    x: {
      min: 0,
      max: 10,
      grid: { color: CHART_COLORS.gridLine },
      ticks: { color: CHART_COLORS.text, stepSize: 2 },
    },
    y: {
      grid: { display: false },
      ticks: { color: '#333333', font: { size: 12 } },
    },
  },
}
</script>

<template>
  <div class="b24-card">
    <h3 class="text-sm font-semibold text-b24-text mb-4">Рейтинг менеджеров</h3>
    <div v-if="rows.length > 0" :style="{ height: `${Math.max(rows.length * 40, 120)}px` }">
      <Bar :data="chartData" :options="options" />
    </div>
    <p v-else class="text-sm text-b24-text-secondary py-8 text-center">Нет данных</p>
  </div>
</template>

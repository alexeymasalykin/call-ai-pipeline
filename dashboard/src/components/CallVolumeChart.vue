<script setup lang="ts">
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  Tooltip, Legend,
} from 'chart.js'
import type { CallStatsResponse } from '@/types'
import { CHART_COLORS } from '@/utils/colors'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const props = defineProps<{ stats: CallStatsResponse }>()

const chartData = computed(() => {
  const entries = Object.entries(props.stats.daily).sort(([a], [b]) => a.localeCompare(b))
  const labels = entries.map(([d]) => d.slice(5))
  return {
    labels,
    datasets: [
      {
        label: 'Исходящие',
        data: entries.map(([, s]) => s.outgoing ?? 0),
        backgroundColor: CHART_COLORS.primary,
        borderRadius: 4,
      },
      {
        label: 'Входящие',
        data: entries.map(([, s]) => s.incoming ?? 0),
        backgroundColor: 'rgba(153, 133, 243, 0.7)',
        borderRadius: 4,
      },
    ],
  }
})

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { color: CHART_COLORS.text, boxWidth: 12 } },
  },
  scales: {
    x: { stacked: true, grid: { display: false }, ticks: { color: CHART_COLORS.text, font: { size: 11 } } },
    y: {
      stacked: true,
      beginAtZero: true,
      grid: { color: CHART_COLORS.gridLine },
      ticks: { color: CHART_COLORS.text, stepSize: 1 },
    },
  },
}
</script>

<template>
  <div class="b24-card">
    <h3 class="text-sm font-semibold text-b24-text mb-4">Звонки по дням</h3>
    <div v-if="Object.keys(stats.daily).length > 0" class="h-64">
      <Bar :data="chartData" :options="options" />
    </div>
    <p v-else class="text-sm text-b24-text-secondary py-8 text-center">Нет данных</p>
  </div>
</template>

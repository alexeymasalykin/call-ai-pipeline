<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
} from 'chart.js'
import type { QaItem } from '@/types'
import { CHART_COLORS } from '@/utils/colors'
import { format } from 'date-fns'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip)

const props = defineProps<{ items: QaItem[] }>()

const sorted = computed(() =>
  [...props.items].sort(
    (a, b) => new Date(a.createdTime).getTime() - new Date(b.createdTime).getTime(),
  ),
)

const chartData = computed(() => ({
  labels: sorted.value.map(i => format(new Date(i.createdTime), 'dd.MM HH:mm')),
  datasets: [
    {
      label: 'Общая оценка',
      data: sorted.value.map(i => i.scoreTotal),
      borderColor: CHART_COLORS.primary,
      backgroundColor: CHART_COLORS.primaryBg,
      tension: 0.3,
      fill: true,
      pointRadius: 4,
      pointBackgroundColor: CHART_COLORS.primary,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      min: 0,
      max: 10,
      ticks: { stepSize: 2, color: CHART_COLORS.text },
      grid: { color: CHART_COLORS.gridLine },
    },
    x: {
      ticks: { maxRotation: 45, font: { size: 10 }, color: CHART_COLORS.text },
      grid: { color: CHART_COLORS.gridLine },
    },
  },
  plugins: {
    tooltip: {
      callbacks: {
        label: (ctx: { parsed: { y: number | null } }) => `Оценка: ${(ctx.parsed.y ?? 0).toFixed(1)}`,
      },
    },
  },
}
</script>

<template>
  <div class="b24-card">
    <h3 class="text-sm font-semibold text-b24-text-secondary mb-3">Динамика качества</h3>
    <div class="h-[300px]">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

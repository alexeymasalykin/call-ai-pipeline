<script setup lang="ts">
import { computed } from 'vue'
import { Radar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js'
import type { StageAverages } from '@/types'
import { STAGE_LABELS } from '@/utils/fields'
import { CHART_COLORS } from '@/utils/colors'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

const props = defineProps<{ averages: StageAverages }>()

const chartData = computed(() => ({
  labels: Object.values(STAGE_LABELS),
  datasets: [
    {
      label: 'Средняя оценка',
      data: [
        props.averages.exitToDm,
        props.averages.opening,
        props.averages.development,
        props.averages.closing,
        props.averages.objections,
      ],
      backgroundColor: CHART_COLORS.primaryBg,
      borderColor: CHART_COLORS.primary,
      borderWidth: 2,
      pointBackgroundColor: CHART_COLORS.primary,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      min: 0,
      max: 10,
      ticks: { stepSize: 2, color: CHART_COLORS.text, backdropColor: 'white' },
      grid: { color: CHART_COLORS.gridLine },
      angleLines: { color: CHART_COLORS.gridLine },
      pointLabels: { font: { size: 12 }, color: '#333333' },
    },
  },
  plugins: {
    tooltip: {
      callbacks: {
        label: (ctx: { parsed: { r: number } }) => `${ctx.parsed.r.toFixed(1)} / 10`,
      },
    },
  },
}
</script>

<template>
  <div class="b24-card p-4">
    <h3 class="text-sm font-semibold text-b24-text-secondary mb-3">Средние оценки по этапам</h3>
    <div class="h-[300px]">
      <Radar :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

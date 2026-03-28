<script setup lang="ts">
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import type { CallStatsResponse } from '@/types'
import { CHART_COLORS } from '@/utils/colors'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps<{ stats: CallStatsResponse }>()

const QUAL_LABELS: Record<string, string> = {
  hot: 'Горячий',
  warm: 'Тёплый',
  cold: 'Холодный',
  rejected: 'Отказ',
  spam: 'Спам',
}

const QUAL_COLORS: Record<string, string> = {
  hot: 'rgba(255, 87, 82, 0.85)',
  warm: 'rgba(255, 169, 0, 0.85)',
  cold: 'rgba(47, 198, 246, 0.85)',
  rejected: 'rgba(168, 173, 180, 0.85)',
  spam: 'rgba(153, 133, 243, 0.85)',
}

const chartData = computed(() => {
  const t = props.stats.totals
  const quals = Object.keys(QUAL_LABELS)
    .map(q => ({
      key: q,
      value: (t[`qual:${q}` as keyof typeof t] as number) ?? 0,
    }))
    .filter(q => q.value > 0)

  return {
    labels: quals.map(q => QUAL_LABELS[q.key]),
    datasets: [{
      data: quals.map(q => q.value),
      backgroundColor: quals.map(q => QUAL_COLORS[q.key]),
      borderWidth: 0,
    }],
  }
})

const hasData = computed(() => {
  const t = props.stats.totals
  return Object.keys(QUAL_LABELS).some(q => ((t[`qual:${q}` as keyof typeof t] as number) ?? 0) > 0)
})

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { color: CHART_COLORS.text, boxWidth: 12 } },
  },
}
</script>

<template>
  <div class="b24-card">
    <h3 class="text-sm font-semibold text-b24-text mb-4">Квалификация звонков</h3>
    <div v-if="hasData" class="h-56">
      <Doughnut :data="chartData" :options="options" />
    </div>
    <p v-else class="text-sm text-b24-text-secondary py-8 text-center">Нет данных</p>
  </div>
</template>

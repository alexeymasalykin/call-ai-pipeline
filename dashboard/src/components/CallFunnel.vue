<script setup lang="ts">
import { computed } from 'vue'
import type { CallStatsResponse } from '@/types'

const props = defineProps<{ stats: CallStatsResponse }>()

interface FunnelStep {
  label: string
  value: number
  color: string
  bgColor: string
}

const funnel = computed<FunnelStep[]>(() => {
  const t = props.stats.totals
  const total = t.total ?? 0
  const avgDuration = total > 0 ? Math.round((t.duration_sum ?? 0) / total) : 0
  const durationLabel = avgDuration >= 60
    ? `${Math.floor(avgDuration / 60)}м ${avgDuration % 60}с`
    : `${avgDuration}с`

  return [
    { label: 'Всего звонков', value: total, color: 'text-b24-text', bgColor: 'bg-b24-border' },
    { label: 'Исходящие', value: t.outgoing ?? 0, color: 'text-b24-blue-dark', bgColor: 'bg-b24-blue-bg' },
    { label: 'Входящие', value: t.incoming ?? 0, color: 'text-b24-violet', bgColor: 'bg-purple-50' },
    { label: `Короткие (< мин. длит.)`, value: t.short ?? 0, color: 'text-b24-yellow', bgColor: 'bg-b24-yellow-bg' },
    { label: 'Не распознаны (STT)', value: t.no_transcript ?? 0, color: 'text-b24-red', bgColor: 'bg-b24-red-bg' },
    { label: 'Проанализированы', value: t.analyzed ?? 0, color: 'text-b24-green', bgColor: 'bg-b24-green-bg' },
    { label: 'Оценены (QA)', value: t.qa_assessed ?? 0, color: 'text-b24-blue-dark', bgColor: 'bg-b24-blue-bg' },
    { label: 'Ошибки обработки', value: t.errors ?? 0, color: 'text-b24-red', bgColor: 'bg-b24-red-bg' },
  ]
})

const avgDuration = computed(() => {
  const t = props.stats.totals
  const total = t.total ?? 0
  if (!total) return '—'
  const avg = Math.round((t.duration_sum ?? 0) / total)
  return avg >= 60 ? `${Math.floor(avg / 60)}м ${avg % 60}с` : `${avg}с`
})

const successRate = computed(() => {
  const t = props.stats.totals
  const total = t.total ?? 0
  if (!total) return '—'
  return `${Math.round(((t.analyzed ?? 0) / total) * 100)}%`
})
</script>

<template>
  <div class="b24-card">
    <h3 class="text-sm font-semibold text-b24-text mb-4">Воронка обработки</h3>
    <div class="space-y-2 mb-4">
      <div
        v-for="step in funnel"
        :key="step.label"
        class="flex items-center justify-between py-2 px-3 rounded-lg"
        :class="step.bgColor"
      >
        <span class="text-sm" :class="step.color">{{ step.label }}</span>
        <span class="text-sm font-bold" :class="step.color">{{ step.value }}</span>
      </div>
    </div>
    <div class="flex justify-around pt-3 border-t border-b24-border">
      <div class="text-center">
        <p class="text-lg font-bold text-b24-text">{{ avgDuration }}</p>
        <p class="text-xs text-b24-text-secondary">Ср. длительность</p>
      </div>
      <div class="text-center">
        <p class="text-lg font-bold text-b24-green">{{ successRate }}</p>
        <p class="text-xs text-b24-text-secondary">Обработано</p>
      </div>
    </div>
  </div>
</template>

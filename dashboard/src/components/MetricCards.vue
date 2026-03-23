<script setup lang="ts">
import type { Metrics } from '@/types'

defineProps<{ metrics: Metrics }>()

function formatScore(score: number): string {
  return `${score.toFixed(1)} / 10`
}
</script>

<template>
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
    <div class="b24-card p-4">
      <p class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide mb-1.5">Всего звонков</p>
      <p class="text-2xl font-bold text-b24-text">{{ metrics.totalCalls }}</p>
    </div>
    <div class="b24-card p-4">
      <p class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide mb-1.5">Средняя оценка</p>
      <p class="text-2xl font-bold text-b24-blue-dark">{{ formatScore(metrics.avgScore) }}</p>
    </div>
    <div class="b24-card p-4">
      <p class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide mb-1.5">Критических ошибок</p>
      <p class="text-2xl font-bold" :class="metrics.criticalErrorsCount > 0 ? 'text-b24-red' : 'text-b24-text'">
        {{ metrics.criticalErrorsCount }}
      </p>
    </div>
    <div class="b24-card p-4">
      <p class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide mb-1.5">Лучший звонок</p>
      <p class="text-2xl font-bold text-b24-green">{{ metrics.bestScore }} / 10</p>
    </div>
  </div>
</template>

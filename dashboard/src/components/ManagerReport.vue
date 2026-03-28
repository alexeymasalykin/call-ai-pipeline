<script setup lang="ts">
import { computed } from 'vue'
import type { QaItem } from '@/types'
import { getScoreColor } from '@/utils/colors'
import { STAGE_LABELS } from '@/utils/fields'

const props = defineProps<{ items: QaItem[]; manager: string }>()

const scores = computed(() => props.items.map(i => i.scoreTotal))
const avgScore = computed(() => {
  if (!scores.value.length) return 0
  return Math.round(scores.value.reduce((a, b) => a + b, 0) / scores.value.length * 10) / 10
})

const goodCount = computed(() => scores.value.filter(s => s >= 7).length)
const goodRate = computed(() => scores.value.length ? Math.round(goodCount.value / scores.value.length * 100) : 0)
const badCount = computed(() => scores.value.filter(s => s < 5).length)
const badRate = computed(() => scores.value.length ? Math.round(badCount.value / scores.value.length * 100) : 0)
const errorCount = computed(() => props.items.filter(i => i.criticalErrors.trim()).length)
const errorRate = computed(() => props.items.length ? Math.round(errorCount.value / props.items.length * 100) : 0)

const stages = computed(() => {
  const keys = [
    { key: 'scoreExitToDm' as const, label: STAGE_LABELS.exitToDm },
    { key: 'scoreOpening' as const, label: STAGE_LABELS.opening },
    { key: 'scoreDevelopment' as const, label: STAGE_LABELS.development },
    { key: 'scoreClosing' as const, label: STAGE_LABELS.closing },
    { key: 'scoreObjections' as const, label: STAGE_LABELS.objections },
  ]
  return keys.map(({ key, label }) => {
    const vals = props.items.map(i => i[key])
    const avg = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10 : 0
    return { label, avg }
  })
})

const worstStage = computed(() => {
  const sorted = [...stages.value].sort((a, b) => a.avg - b.avg)
  return sorted[0]
})

const bestStage = computed(() => {
  const sorted = [...stages.value].sort((a, b) => b.avg - a.avg)
  return sorted[0]
})

// Score distribution
const distribution = computed(() => {
  const dist = new Map<number, number>()
  for (let i = 1; i <= 10; i++) dist.set(i, 0)
  for (const s of scores.value) dist.set(s, (dist.get(s) ?? 0) + 1)
  return Array.from(dist.entries()).map(([score, count]) => ({ score, count }))
})
const maxDistCount = computed(() => Math.max(...distribution.value.map(d => d.count), 1))

// Daily breakdown
const dailyData = computed(() => {
  const grouped = new Map<string, number[]>()
  for (const item of props.items) {
    const d = item.createdTime.slice(0, 10)
    const list = grouped.get(d) ?? []
    list.push(item.scoreTotal)
    grouped.set(d, list)
  }
  return Array.from(grouped.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, vals]) => ({
      date: date.slice(5), // MM-DD
      count: vals.length,
      avg: Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10,
    }))
})

// Top critical errors
const topErrors = computed(() => {
  const counter = new Map<string, number>()
  for (const item of props.items) {
    const errs = item.criticalErrors.trim()
    if (!errs) continue
    for (const line of errs.split('\n')) {
      const clean = line.trim().replace(/\.$/, '')
      if (clean.length > 5) counter.set(clean, (counter.get(clean) ?? 0) + 1)
    }
  }
  return Array.from(counter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
})

// Top recommendations
const topRecs = computed(() => {
  const counter = new Map<string, number>()
  for (const item of props.items) {
    const recs = item.recommendations.trim()
    if (!recs) continue
    for (const line of recs.split('\n')) {
      const clean = line.trim().replace(/\.$/, '')
      if (clean.length > 10) counter.set(clean, (counter.get(clean) ?? 0) + 1)
    }
  }
  return Array.from(counter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
})

function stageBarWidth(avg: number): string {
  return `${Math.max(avg * 10, 2)}%`
}

function stageColor(avg: number): string {
  if (avg >= 5) return 'bg-b24-green'
  if (avg >= 3) return 'bg-b24-yellow'
  return 'bg-b24-red'
}

function distBarColor(score: number): string {
  if (score >= 7) return 'bg-b24-green'
  if (score >= 5) return 'bg-b24-yellow'
  return 'bg-b24-red'
}
</script>

<template>
  <div class="space-y-4 mb-5">
    <div class="b24-card">
      <h2 class="text-lg font-semibold text-b24-text mb-4">
        Отчёт: {{ manager }}
        <span class="text-sm font-normal text-b24-text-secondary ml-2">{{ items.length }} звонков с оценкой</span>
      </h2>

      <!-- Summary cards -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
        <div class="rounded-lg p-3 bg-b24-bg text-center">
          <p class="text-xs text-b24-text-secondary mb-1">Средний балл</p>
          <p class="text-2xl font-bold" :class="avgScore >= 7 ? 'text-b24-green' : avgScore >= 5 ? 'text-b24-yellow' : 'text-b24-red'">
            {{ avgScore }}
          </p>
        </div>
        <div class="rounded-lg p-3 bg-b24-bg text-center">
          <p class="text-xs text-b24-text-secondary mb-1">Качественных (≥7)</p>
          <p class="text-2xl font-bold" :class="goodRate >= 20 ? 'text-b24-green' : 'text-b24-red'">
            {{ goodRate }}%
          </p>
        </div>
        <div class="rounded-lg p-3 bg-b24-bg text-center">
          <p class="text-xs text-b24-text-secondary mb-1">Плохих (&lt;5)</p>
          <p class="text-2xl font-bold" :class="badRate <= 10 ? 'text-b24-green' : 'text-b24-red'">
            {{ badRate }}%
          </p>
        </div>
        <div class="rounded-lg p-3 bg-b24-bg text-center">
          <p class="text-xs text-b24-text-secondary mb-1">Крит. ошибки</p>
          <p class="text-2xl font-bold" :class="errorRate <= 10 ? 'text-b24-green' : 'text-b24-red'">
            {{ errorRate }}%
          </p>
        </div>
        <div class="rounded-lg p-3 bg-b24-bg text-center">
          <p class="text-xs text-b24-text-secondary mb-1">Лучший / Худший</p>
          <p class="text-2xl font-bold text-b24-text">
            {{ scores.length ? Math.max(...scores) : 0 }} / {{ scores.length ? Math.min(...scores) : 0 }}
          </p>
        </div>
      </div>

      <!-- Stages -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div>
          <h3 class="text-sm font-semibold text-b24-text-secondary uppercase tracking-wide mb-3">Навыки по этапам</h3>
          <div class="space-y-2.5">
            <div v-for="stage in stages" :key="stage.label" class="flex items-center gap-3">
              <span class="text-sm text-b24-text w-28 shrink-0">{{ stage.label }}</span>
              <div class="flex-1 h-6 bg-b24-bg rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500 flex items-center justify-end pr-2"
                  :class="stageColor(stage.avg)"
                  :style="{ width: stageBarWidth(stage.avg) }"
                >
                  <span class="text-xs font-bold text-white drop-shadow">{{ stage.avg }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="mt-3 flex gap-4 text-xs">
            <span class="text-b24-green">✓ Сильный: {{ bestStage?.label }} ({{ bestStage?.avg }})</span>
            <span class="text-b24-red">✗ Слабый: {{ worstStage?.label }} ({{ worstStage?.avg }})</span>
          </div>
        </div>

        <!-- Score distribution -->
        <div>
          <h3 class="text-sm font-semibold text-b24-text-secondary uppercase tracking-wide mb-3">Распределение оценок</h3>
          <div class="space-y-1.5">
            <div v-for="d in distribution" :key="d.score" class="flex items-center gap-2">
              <span class="text-xs text-b24-text-secondary w-5 text-right">{{ d.score }}</span>
              <div class="flex-1 h-5 bg-b24-bg rounded overflow-hidden">
                <div
                  v-if="d.count > 0"
                  class="h-full rounded transition-all duration-500"
                  :class="distBarColor(d.score)"
                  :style="{ width: `${(d.count / maxDistCount) * 100}%` }"
                />
              </div>
              <span class="text-xs text-b24-text-secondary w-6">{{ d.count || '' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Daily + Errors + Recommendations -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Daily -->
      <div class="b24-card">
        <h3 class="text-sm font-semibold text-b24-text-secondary uppercase tracking-wide mb-3">Динамика по дням</h3>
        <div class="space-y-2">
          <div v-for="d in dailyData" :key="d.date" class="flex items-center gap-2">
            <span class="text-xs text-b24-text-secondary w-12">{{ d.date }}</span>
            <span class="text-xs text-b24-text-secondary w-8 text-right">{{ d.count }}зв.</span>
            <div class="flex-1 h-5 bg-b24-bg rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :class="d.avg >= 7 ? 'bg-b24-green' : d.avg >= 5 ? 'bg-b24-blue' : 'bg-b24-red'"
                :style="{ width: `${d.avg * 10}%` }"
              />
            </div>
            <span class="text-xs font-bold w-6" :class="d.avg >= 7 ? 'text-b24-green' : d.avg >= 5 ? 'text-b24-text' : 'text-b24-red'">
              {{ d.avg }}
            </span>
          </div>
        </div>
      </div>

      <!-- Critical errors -->
      <div class="b24-card">
        <h3 class="text-sm font-semibold text-b24-red uppercase tracking-wide mb-3">Типичные ошибки</h3>
        <div v-if="topErrors.length" class="space-y-2">
          <div v-for="[err, cnt] in topErrors" :key="err" class="flex gap-2">
            <span class="text-xs font-bold text-b24-red shrink-0 w-8 text-right">{{ cnt }}×</span>
            <span class="text-sm text-b24-text">{{ err }}</span>
          </div>
        </div>
        <p v-else class="text-sm text-b24-text-secondary">Нет критических ошибок</p>
      </div>

      <!-- Recommendations -->
      <div class="b24-card">
        <h3 class="text-sm font-semibold text-b24-blue-dark uppercase tracking-wide mb-3">Рекомендации</h3>
        <div v-if="topRecs.length" class="space-y-2">
          <div v-for="[rec, cnt] in topRecs" :key="rec" class="flex gap-2">
            <span class="text-xs font-bold text-b24-blue-dark shrink-0 w-8 text-right">{{ cnt }}×</span>
            <span class="text-sm text-b24-text">{{ rec }}</span>
          </div>
        </div>
        <p v-else class="text-sm text-b24-text-secondary">Нет рекомендаций</p>
      </div>
    </div>
  </div>
</template>

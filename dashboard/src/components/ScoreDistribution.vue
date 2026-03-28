<script setup lang="ts">
import { computed } from 'vue'
import type { QaItem } from '@/types'

const props = defineProps<{ items: QaItem[] }>()

const buckets = computed(() => {
  const red = props.items.filter(i => i.scoreTotal <= 3).length
  const yellow = props.items.filter(i => i.scoreTotal >= 4 && i.scoreTotal <= 6).length
  const green = props.items.filter(i => i.scoreTotal >= 7).length
  const total = props.items.length || 1
  return [
    { label: '1–3', count: red, pct: Math.round(red / total * 100), color: 'bg-b24-red', bgColor: 'bg-b24-red-bg', textColor: 'text-b24-red' },
    { label: '4–6', count: yellow, pct: Math.round(yellow / total * 100), color: 'bg-b24-yellow', bgColor: 'bg-b24-yellow-bg', textColor: 'text-b24-yellow' },
    { label: '7–10', count: green, pct: Math.round(green / total * 100), color: 'bg-b24-green', bgColor: 'bg-b24-green-bg', textColor: 'text-b24-green' },
  ]
})

const goodRate = computed(() => {
  if (props.items.length === 0) return 0
  const good = props.items.filter(i => i.scoreTotal >= 7).length
  return Math.round(good / props.items.length * 100)
})
</script>

<template>
  <div class="b24-card">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-b24-text">Распределение оценок</h3>
      <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="goodRate >= 50 ? 'bg-b24-green-bg text-b24-green' : 'bg-b24-red-bg text-b24-red'">
        {{ goodRate }}% качественных
      </span>
    </div>
    <div class="space-y-3">
      <div v-for="b in buckets" :key="b.label">
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-medium text-b24-text-secondary">{{ b.label }} баллов</span>
          <span class="text-xs font-bold" :class="b.textColor">{{ b.count }} ({{ b.pct }}%)</span>
        </div>
        <div class="h-2.5 rounded-full bg-b24-bg overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="b.color"
            :style="{ width: `${b.pct}%` }"
          />
        </div>
      </div>
    </div>
  </div>
</template>

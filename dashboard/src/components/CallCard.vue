<script setup lang="ts">
import { ref } from 'vue'
import type { QaItem } from '@/types'
import { getScoreColor } from '@/utils/colors'
import { getItemUrl, STAGE_LABELS } from '@/utils/fields'
import { format } from 'date-fns'

const props = defineProps<{ item: QaItem }>()
const expanded = ref(false)

const stages = [
  { key: 'scoreExitToDm' as const, label: STAGE_LABELS.exitToDm },
  { key: 'scoreOpening' as const, label: STAGE_LABELS.opening },
  { key: 'scoreDevelopment' as const, label: STAGE_LABELS.development },
  { key: 'scoreClosing' as const, label: STAGE_LABELS.closing },
  { key: 'scoreObjections' as const, label: STAGE_LABELS.objections },
]

function getStageScore(key: (typeof stages)[number]['key']): number {
  return props.item[key]
}
</script>

<template>
  <div class="b24-card overflow-hidden transition-all duration-200">
    <div
      class="flex items-center gap-3 p-4 cursor-pointer hover:bg-b24-surface-hover transition-colors"
      @click="expanded = !expanded"
    >
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-sm font-medium text-b24-text">#{{ item.id }}</span>
          <span class="text-xs text-b24-text-secondary">
            {{ format(new Date(item.createdTime), 'dd.MM.yyyy HH:mm') }}
          </span>
          <span
            v-if="item.product"
            class="px-2 py-0.5 rounded-full text-xs font-medium bg-b24-blue-bg text-b24-blue-dark"
          >
            {{ item.product }}
          </span>
        </div>
        <p v-if="item.summary" class="text-sm text-b24-text-secondary leading-relaxed">{{ item.summary }}</p>
        <p v-else class="text-sm text-b24-text-secondary">{{ item.manager }}</p>
      </div>

      <div
        class="w-14 h-14 rounded-xl flex items-center justify-center text-lg font-bold shrink-0"
        :class="getScoreColor(item.scoreTotal)"
      >
        {{ item.scoreTotal }}
      </div>

      <svg
        class="w-5 h-5 text-b24-text-light transition-transform shrink-0"
        :class="{ 'rotate-180': expanded }"
        fill="none" stroke="currentColor" viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </div>

    <div v-if="expanded" class="border-t border-b24-border p-4 space-y-3 bg-b24-bg/50">
      <div class="flex items-center gap-2 flex-wrap">
        <div
          v-for="stage in stages"
          :key="stage.key"
          class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium"
          :class="getScoreColor(getStageScore(stage.key))"
        >
          <span class="opacity-70">{{ stage.label }}</span>
          <span class="font-bold">{{ getStageScore(stage.key) }}</span>
        </div>
      </div>
      <div v-if="item.summary">
        <p class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide mb-1">Саммари</p>
        <p class="text-sm text-b24-text whitespace-pre-line">{{ item.summary }}</p>
      </div>
      <div v-if="item.criticalErrors">
        <p class="text-xs font-semibold text-b24-red uppercase tracking-wide mb-1">Критические ошибки</p>
        <p class="text-sm text-b24-text whitespace-pre-line">{{ item.criticalErrors }}</p>
      </div>
      <div v-if="item.strengths">
        <p class="text-xs font-semibold text-b24-green uppercase tracking-wide mb-1">Сильные стороны</p>
        <p class="text-sm text-b24-text whitespace-pre-line">{{ item.strengths }}</p>
      </div>
      <div v-if="item.recommendations">
        <p class="text-xs font-semibold text-b24-blue-dark uppercase tracking-wide mb-1">Рекомендации</p>
        <p class="text-sm text-b24-text whitespace-pre-line">{{ item.recommendations }}</p>
      </div>
      <a
        :href="getItemUrl(item.id)"
        target="_blank"
        class="inline-flex items-center gap-1 text-sm text-b24-blue-dark hover:text-b24-blue transition-colors"
      >
        Открыть карточку
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
      </a>
    </div>
  </div>
</template>

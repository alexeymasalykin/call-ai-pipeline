<script setup lang="ts">
import { computed } from 'vue'
import type { QaItem } from '@/types'
import { STAGE_LABELS } from '@/utils/fields'

const props = defineProps<{ items: QaItem[] }>()

const stageKeys = ['scoreExitToDm', 'scoreOpening', 'scoreDevelopment', 'scoreClosing', 'scoreObjections'] as const
const stageLabels = [STAGE_LABELS.exitToDm, STAGE_LABELS.opening, STAGE_LABELS.development, STAGE_LABELS.closing, STAGE_LABELS.objections]

interface HeatmapRow {
  manager: string
  scores: number[]
}

const rows = computed<HeatmapRow[]>(() => {
  const grouped = new Map<string, QaItem[]>()
  for (const item of props.items) {
    const name = item.manager || 'Неизвестный'
    const list = grouped.get(name) ?? []
    list.push(item)
    grouped.set(name, list)
  }

  return [...grouped.entries()]
    .map(([manager, managerItems]) => ({
      manager,
      scores: stageKeys.map(key =>
        Math.round(managerItems.reduce((s, i) => s + i[key], 0) / managerItems.length * 10) / 10,
      ),
    }))
    .sort((a, b) => {
      const avgA = a.scores.reduce((s, v) => s + v, 0) / a.scores.length
      const avgB = b.scores.reduce((s, v) => s + v, 0) / b.scores.length
      return avgB - avgA
    })
})

function cellColor(score: number): string {
  if (score <= 3) return 'bg-red-100 text-red-700'
  if (score <= 5) return 'bg-orange-100 text-orange-700'
  if (score <= 7) return 'bg-yellow-50 text-yellow-700'
  return 'bg-green-100 text-green-700'
}
</script>

<template>
  <div class="b24-card overflow-hidden">
    <h3 class="text-sm font-semibold text-b24-text p-5 pb-3">Тепловая карта по этапам</h3>
    <div v-if="rows.length > 0" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-b24-border">
            <th class="text-left px-4 py-2 text-xs font-semibold text-b24-text-secondary uppercase">Менеджер</th>
            <th
              v-for="label in stageLabels"
              :key="label"
              class="text-center px-3 py-2 text-xs font-semibold text-b24-text-secondary uppercase"
            >
              {{ label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.manager"
            class="border-b border-b24-border/50 last:border-0"
          >
            <td class="px-4 py-2.5 font-medium text-b24-text whitespace-nowrap">{{ row.manager }}</td>
            <td
              v-for="(score, idx) in row.scores"
              :key="idx"
              class="px-3 py-2.5 text-center"
            >
              <span
                class="inline-block w-10 py-0.5 rounded text-xs font-bold"
                :class="cellColor(score)"
              >
                {{ score.toFixed(1) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="text-sm text-b24-text-secondary py-8 text-center">Нет данных</p>
  </div>
</template>

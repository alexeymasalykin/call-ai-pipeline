<script setup lang="ts">
import type { ManagerRow } from '@/types'
import { getScoreColor } from '@/utils/colors'

defineProps<{ rows: ManagerRow[] }>()
</script>

<template>
  <div v-if="rows.length > 0" class="b24-card overflow-hidden">
    <h3 class="text-lg font-semibold text-b24-text p-5 pb-0">Сводка по менеджерам</h3>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-b24-border">
            <th class="text-left px-5 py-3 text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Менеджер</th>
            <th class="text-center px-5 py-3 text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Звонков</th>
            <th class="text-center px-5 py-3 text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Ср. оценка</th>
            <th class="text-center px-5 py-3 text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">≥ 7 баллов</th>
            <th class="text-center px-5 py-3 text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Худший этап</th>
            <th class="text-center px-5 py-3 text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Крит. ошибок</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.manager"
            class="border-b border-b24-border/50 last:border-0 hover:bg-b24-surface-hover transition-colors"
          >
            <td class="px-5 py-3 font-medium text-b24-text">{{ row.manager }}</td>
            <td class="px-5 py-3 text-center text-b24-text-secondary">{{ row.callCount }}</td>
            <td class="px-5 py-3 text-center">
              <span
                class="inline-flex px-2.5 py-0.5 rounded-lg text-xs font-bold"
                :class="getScoreColor(row.avgScore)"
              >
                {{ row.avgScore.toFixed(1) }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold" :class="row.goodRate >= 50 ? 'text-b24-green' : 'text-b24-red'">
                {{ row.goodRate }}%
              </span>
            </td>
            <td class="px-5 py-3 text-center text-b24-text-secondary">{{ row.worstStage }}</td>
            <td class="px-5 py-3 text-center">
              <span :class="row.criticalErrorsCount > 0 ? 'text-b24-red font-bold' : 'text-b24-text-secondary'">
                {{ row.criticalErrorsCount }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

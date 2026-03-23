<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useB24 } from '@/composables/useB24'
import { useQaData } from '@/composables/useQaData'
import { useFilters } from '@/composables/useFilters'
import { computeMetrics, computeStageAverages, computeManagerTable } from '@/utils/metrics'
import DashboardFilters from '@/components/DashboardFilters.vue'
import MetricCards from '@/components/MetricCards.vue'
import RadarChart from '@/components/RadarChart.vue'
import TrendChart from '@/components/TrendChart.vue'
import CallList from '@/components/CallList.vue'
import ManagerTable from '@/components/ManagerTable.vue'
import EmptyState from '@/components/EmptyState.vue'

const { init, error: b24Error } = useB24()
const { items, loading, error: dataError, fetchAll } = useQaData()
const {
  manager, product, periodPreset, dateFrom, dateTo,
  filtered, managers, products, isMultiDay,
} = useFilters(() => items.value)

const metrics = computed(() => computeMetrics(filtered.value))
const stageAverages = computed(() => computeStageAverages(filtered.value))
const managerRows = computed(() => computeManagerTable(filtered.value))
const error = computed(() => b24Error.value || dataError.value)

onMounted(async () => {
  try {
    await init()
    await fetchAll()
  } catch {
    // errors captured in refs
  }
})

async function refresh() {
  await fetchAll()
}
</script>

<template>
  <div class="min-h-screen p-5 max-w-[1400px] mx-auto">
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-semibold text-b24-text">Оценка качества звонков</h1>
    </div>

    <div v-if="error" class="b24-card p-4 mb-5 border-l-4 border-b24-red">
      <p class="text-b24-red text-sm">{{ error }}</p>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-32">
      <div class="text-center">
        <div class="w-8 h-8 border-3 border-b24-blue border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p class="text-b24-text-secondary text-sm">Загрузка данных...</p>
      </div>
    </div>

    <template v-else-if="!error">
      <DashboardFilters
        :managers="managers"
        :products="products"
        v-model:manager="manager"
        v-model:product="product"
        v-model:period-preset="periodPreset"
        v-model:date-from="dateFrom"
        v-model:date-to="dateTo"
        @refresh="refresh"
      />

      <template v-if="filtered.length > 0">
        <MetricCards :metrics="metrics" />

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
          <RadarChart :averages="stageAverages" />
          <TrendChart :items="filtered" />
        </div>

        <div v-if="isMultiDay" class="mb-5">
          <ManagerTable :rows="managerRows" />
        </div>

        <CallList :items="filtered" />
      </template>

      <EmptyState v-else />
    </template>
  </div>
</template>

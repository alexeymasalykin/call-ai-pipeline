<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useB24 } from '@/composables/useB24'
import { useQaData } from '@/composables/useQaData'
import { useFilters } from '@/composables/useFilters'
import { useCallStats } from '@/composables/useCallStats'
import { computeMetrics, computeStageAverages, computeManagerTable } from '@/utils/metrics'
import DashboardFilters from '@/components/DashboardFilters.vue'
import MetricCards from '@/components/MetricCards.vue'
import RadarChart from '@/components/RadarChart.vue'
import TrendChart from '@/components/TrendChart.vue'
import CallList from '@/components/CallList.vue'
import ManagerTable from '@/components/ManagerTable.vue'
import ManagerRanking from '@/components/ManagerRanking.vue'
import StageHeatmap from '@/components/StageHeatmap.vue'
import ScoreDistribution from '@/components/ScoreDistribution.vue'
import ManagerTrend from '@/components/ManagerTrend.vue'
import CallFunnel from '@/components/CallFunnel.vue'
import CallVolumeChart from '@/components/CallVolumeChart.vue'
import QualificationPie from '@/components/QualificationPie.vue'
import ManagerReport from '@/components/ManagerReport.vue'
import EmptyState from '@/components/EmptyState.vue'

const { init, error: b24Error } = useB24()
const { items, loading, error: dataError, fetchAll } = useQaData()
const { stats, fetchStats } = useCallStats()
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
    await Promise.all([fetchAll(), fetchStats(30)])
  } catch {
    // errors captured in refs
  }
})

async function refresh() {
  await Promise.all([fetchAll(), fetchStats(30)])
}
</script>

<template>
  <B24App>
    <div class="min-h-screen p-5 max-w-[1400px] mx-auto">
      <div class="flex items-center justify-between mb-5">
        <h1 class="text-xl font-semibold text-b24-text">Оценка качества звонков</h1>
      </div>

      <B24Alert v-if="error" color="red" variant="subtle" :description="error" class="mb-5" />

      <div v-if="loading" class="flex items-center justify-center py-32">
        <B24Skeleton class="w-full h-48 rounded-xl" />
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

      <!-- Call Processing Stats -->
      <div v-if="stats && (stats.totals.total ?? 0) > 0" class="mb-5">
        <h2 class="text-lg font-semibold text-b24-text mb-3">Статистика обработки</h2>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <CallFunnel :stats="stats" />
          <CallVolumeChart :stats="stats" />
          <QualificationPie :stats="stats" />
        </div>
      </div>

      <template v-if="filtered.length > 0">
        <!-- Manager detail report -->
        <ManagerReport v-if="manager" :items="filtered" :manager="manager" />

        <MetricCards :metrics="metrics" :total-outgoing="stats?.totals?.outgoing" />

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
          <ManagerRanking :rows="managerRows" />
          <ScoreDistribution :items="filtered" />
          <RadarChart :averages="stageAverages" />
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
          <ManagerTrend :items="filtered" />
          <TrendChart :items="filtered" />
        </div>

        <div class="mb-5">
          <StageHeatmap :items="filtered" />
        </div>

        <div v-if="isMultiDay" class="mb-5">
          <ManagerTable :rows="managerRows" />
        </div>

        <CallList :items="filtered" />
      </template>

      <EmptyState v-else />
    </template>
    </div>
  </B24App>
</template>

<script setup lang="ts">
import type { PeriodPreset } from '@/composables/useFilters'

const props = defineProps<{
  managers: string[]
  products: string[]
  manager: string
  product: string
  periodPreset: PeriodPreset
  dateFrom: Date | null
  dateTo: Date | null
}>()

const emit = defineEmits<{
  'update:manager': [value: string]
  'update:product': [value: string]
  'update:periodPreset': [value: PeriodPreset]
  'update:dateFrom': [value: Date | null]
  'update:dateTo': [value: Date | null]
  refresh: []
}>()

const periods: { value: PeriodPreset; label: string }[] = [
  { value: 'today', label: 'Сегодня' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'custom', label: 'Период' },
]

function onDateFromInput(e: Event) {
  const val = (e.target as HTMLInputElement).value
  emit('update:dateFrom', val ? new Date(val) : null)
}

function onDateToInput(e: Event) {
  const val = (e.target as HTMLInputElement).value
  emit('update:dateTo', val ? new Date(val) : null)
}
</script>

<template>
  <div class="b24-card p-4 mb-5">
    <div class="flex flex-wrap items-end gap-3">
      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Менеджер</label>
        <select
          :value="props.manager"
          class="border border-b24-border rounded-md px-3 py-1.5 text-sm bg-white text-b24-text min-w-[160px] cursor-pointer focus:border-b24-blue focus:outline-none transition-colors"
          @change="emit('update:manager', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">Все</option>
          <option v-for="m in props.managers" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Продукт</label>
        <select
          :value="props.product"
          class="border border-b24-border rounded-md px-3 py-1.5 text-sm bg-white text-b24-text min-w-[160px] cursor-pointer focus:border-b24-blue focus:outline-none transition-colors"
          @change="emit('update:product', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">Все</option>
          <option v-for="p in props.products" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">Период</label>
        <div class="flex rounded-md border border-b24-border overflow-hidden">
          <button
            v-for="p in periods"
            :key="p.value"
            class="px-3 py-1.5 text-sm transition-colors cursor-pointer"
            :class="props.periodPreset === p.value
              ? 'bg-b24-blue text-white'
              : 'bg-white text-b24-text-secondary hover:bg-b24-surface-hover hover:text-b24-text'"
            @click="emit('update:periodPreset', p.value)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <template v-if="props.periodPreset === 'custom'">
        <div class="flex flex-col gap-1">
          <label class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">С</label>
          <input
            type="date"
            class="border border-b24-border rounded-md px-3 py-1.5 text-sm bg-white text-b24-text focus:border-b24-blue focus:outline-none transition-colors"
            :value="props.dateFrom?.toISOString().split('T')[0] ?? ''"
            @input="onDateFromInput"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-semibold text-b24-text-secondary uppercase tracking-wide">По</label>
          <input
            type="date"
            class="border border-b24-border rounded-md px-3 py-1.5 text-sm bg-white text-b24-text focus:border-b24-blue focus:outline-none transition-colors"
            :value="props.dateTo?.toISOString().split('T')[0] ?? ''"
            @input="onDateToInput"
          />
        </div>
      </template>

      <button
        class="px-4 py-1.5 bg-b24-blue text-white text-sm font-medium rounded-md hover:bg-b24-blue-dark transition-colors cursor-pointer"
        @click="emit('refresh')"
      >
        Обновить
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { QaItem } from '@/types'
import CallCard from './CallCard.vue'
import EmptyState from './EmptyState.vue'

defineProps<{ items: QaItem[] }>()
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-lg font-semibold text-gray-900">Список звонков</h3>
    <EmptyState v-if="items.length === 0" />
    <CallCard v-for="item in items" :key="item.id" :item="item" />
  </div>
</template>

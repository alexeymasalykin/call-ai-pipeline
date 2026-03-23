import { ref } from 'vue'
import { useB24 } from './useB24'
import { QA_ENTITY_TYPE_ID, FIELD_MAP } from '@/utils/fields'
import type { QaItem } from '@/types'

export function useQaData() {
  const items = ref<QaItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  function mapRawItem(raw: Record<string, unknown>): QaItem {
    return {
      id: Number(raw.id),
      title: String(raw.title ?? ''),
      createdTime: String(raw.createdTime ?? ''),
      assignedById: Number(raw.assignedById ?? 0),
      parentId2: raw.parentId2 ? Number(raw.parentId2) : null,
      product: String(raw[FIELD_MAP.product] ?? ''),
      segment: String(raw[FIELD_MAP.segment] ?? ''),
      manager: String(raw[FIELD_MAP.manager] ?? ''),
      scoreTotal: Number(raw[FIELD_MAP.scoreTotal] ?? 0),
      scoreExitToDm: Number(raw[FIELD_MAP.scoreExitToDm] ?? 0),
      scoreOpening: Number(raw[FIELD_MAP.scoreOpening] ?? 0),
      scoreDevelopment: Number(raw[FIELD_MAP.scoreDevelopment] ?? 0),
      scoreClosing: Number(raw[FIELD_MAP.scoreClosing] ?? 0),
      scoreObjections: Number(raw[FIELD_MAP.scoreObjections] ?? 0),
      criticalErrors: String(raw[FIELD_MAP.criticalErrors] ?? ''),
      strengths: String(raw[FIELD_MAP.strengths] ?? ''),
      recommendations: String(raw[FIELD_MAP.recommendations] ?? ''),
      summary: String(raw[FIELD_MAP.summary] ?? ''),
    }
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null
    const allItems: QaItem[] = []

    try {
      const { getB24 } = useB24()
      const b24 = getB24()
      let start = 0

      while (true) {
        const response = await b24.callMethod('crm.item.list', {
          entityTypeId: QA_ENTITY_TYPE_ID,
          select: ['*', 'uf_*'],
          order: { id: 'DESC' },
          start,
        })

        const data = response.getData() as Record<string, unknown>
        const resultObj = (data.result ?? data) as Record<string, unknown>
        const result = (resultObj.items ?? []) as Record<string, unknown>[]

        for (const raw of result) {
          allItems.push(mapRawItem(raw))
        }

        const next = (resultObj.next ?? data.next) as number | undefined
        if (!next || result.length === 0) break
        start = next
      }

      items.value = allItems
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Ошибка загрузки данных'
    } finally {
      loading.value = false
    }
  }

  return { items, loading, error, fetchAll }
}

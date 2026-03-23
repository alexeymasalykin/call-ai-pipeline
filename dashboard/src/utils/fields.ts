export const QA_ENTITY_TYPE_ID = 1040

export const FIELD_MAP = {
  product: 'ufCrm7_1773830213138',
  segment: 'ufCrm7_1773830225528',
  manager: 'ufCrm7_1773830235292',
  scoreTotal: 'ufCrm7_1773830256948',
  scoreExitToDm: 'ufCrm7_1773830277240',
  scoreOpening: 'ufCrm7_1773830520349',
  scoreDevelopment: 'ufCrm7_1773830290854',
  scoreClosing: 'ufCrm7_1773830304889',
  scoreObjections: 'ufCrm7_1773830318819',
  criticalErrors: 'ufCrm7_1773830330597',
  strengths: 'ufCrm7_1773830345725',
  recommendations: 'ufCrm7_1773830355517',
  summary: 'ufCrm7_1773830365526',
} as const

export const STAGE_LABELS: Record<string, string> = {
  exitToDm: 'Выход на ЛПР',
  opening: 'Открытие',
  development: 'Развитие',
  closing: 'Закрытие',
  objections: 'Возражения',
}

export const B24_DOMAIN = 'https://b24-d5wkxm.bitrix24.ru'

export function getItemUrl(itemId: number): string {
  return `${B24_DOMAIN}/crm/type/${QA_ENTITY_TYPE_ID}/details/${itemId}/`
}

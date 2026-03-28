export interface QaItem {
  id: number
  title: string
  createdTime: string
  assignedById: number
  parentId2: number | null
  product: string
  segment: string
  manager: string
  scoreTotal: number
  scoreExitToDm: number
  scoreOpening: number
  scoreDevelopment: number
  scoreClosing: number
  scoreObjections: number
  criticalErrors: string
  strengths: string
  recommendations: string
  summary: string
}

export interface Filters {
  manager: string
  dateFrom: Date | null
  dateTo: Date | null
  product: string
}

export interface Metrics {
  totalCalls: number
  avgScore: number
  criticalErrorsCount: number
  bestScore: number
  goodRate: number
}

export interface ManagerRow {
  manager: string
  callCount: number
  avgScore: number
  goodRate: number
  worstStage: string
  criticalErrorsCount: number
}

export interface DailyStats {
  total: number
  incoming: number
  outgoing: number
  short: number
  no_transcript: number
  analyzed: number
  qa_assessed: number
  errors: number
  duration_sum: number
  [key: `qual:${string}`]: number
}

export interface CallStatsResponse {
  days: number
  daily: Record<string, Partial<DailyStats>>
  totals: Partial<DailyStats>
}

export interface StageAverages {
  exitToDm: number
  opening: number
  development: number
  closing: number
  objections: number
}

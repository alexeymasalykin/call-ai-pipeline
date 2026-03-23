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
}

export interface ManagerRow {
  manager: string
  callCount: number
  avgScore: number
  worstStage: string
  criticalErrorsCount: number
}

export interface StageAverages {
  exitToDm: number
  opening: number
  development: number
  closing: number
  objections: number
}

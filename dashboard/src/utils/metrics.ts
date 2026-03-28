import type { QaItem, Metrics, StageAverages, ManagerRow } from '@/types'
import { STAGE_LABELS } from './fields'

export function computeMetrics(items: QaItem[]): Metrics {
  if (items.length === 0) {
    return { totalCalls: 0, avgScore: 0, criticalErrorsCount: 0, bestScore: 0, goodRate: 0 }
  }

  const scores = items.map(i => i.scoreTotal)
  const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length
  const criticalErrorsCount = items.filter(i => i.criticalErrors.trim().length > 0).length
  const bestScore = Math.max(...scores)
  const goodRate = Math.round(scores.filter(s => s >= 7).length / scores.length * 100)

  return {
    totalCalls: items.length,
    avgScore: Math.round(avgScore * 10) / 10,
    criticalErrorsCount,
    bestScore,
    goodRate,
  }
}

export function computeStageAverages(items: QaItem[]): StageAverages {
  if (items.length === 0) {
    return { exitToDm: 0, opening: 0, development: 0, closing: 0, objections: 0 }
  }

  const len = items.length
  return {
    exitToDm: Math.round(items.reduce((s, i) => s + i.scoreExitToDm, 0) / len * 10) / 10,
    opening: Math.round(items.reduce((s, i) => s + i.scoreOpening, 0) / len * 10) / 10,
    development: Math.round(items.reduce((s, i) => s + i.scoreDevelopment, 0) / len * 10) / 10,
    closing: Math.round(items.reduce((s, i) => s + i.scoreClosing, 0) / len * 10) / 10,
    objections: Math.round(items.reduce((s, i) => s + i.scoreObjections, 0) / len * 10) / 10,
  }
}

export function computeManagerTable(items: QaItem[]): ManagerRow[] {
  const grouped = new Map<string, QaItem[]>()

  for (const item of items) {
    const name = item.manager || 'Неизвестный'
    const list = grouped.get(name) ?? []
    list.push(item)
    grouped.set(name, list)
  }

  const rows: ManagerRow[] = []

  for (const [manager, managerItems] of grouped) {
    const avgScore = Math.round(
      managerItems.reduce((s, i) => s + i.scoreTotal, 0) / managerItems.length * 10,
    ) / 10

    const stageAvgs: Record<string, number> = {
      exitToDm: managerItems.reduce((s, i) => s + i.scoreExitToDm, 0) / managerItems.length,
      opening: managerItems.reduce((s, i) => s + i.scoreOpening, 0) / managerItems.length,
      development: managerItems.reduce((s, i) => s + i.scoreDevelopment, 0) / managerItems.length,
      closing: managerItems.reduce((s, i) => s + i.scoreClosing, 0) / managerItems.length,
      objections: managerItems.reduce((s, i) => s + i.scoreObjections, 0) / managerItems.length,
    }

    const worstStageKey = Object.entries(stageAvgs).reduce(
      (min, [k, v]) => (v < min[1] ? [k, v] : min),
      ['', Infinity] as [string, number],
    )[0]

    const goodCount = managerItems.filter(i => i.scoreTotal >= 7).length
    rows.push({
      manager,
      callCount: managerItems.length,
      avgScore,
      goodRate: Math.round(goodCount / managerItems.length * 100),
      worstStage: STAGE_LABELS[worstStageKey] ?? worstStageKey,
      criticalErrorsCount: managerItems.filter(i => i.criticalErrors.trim().length > 0).length,
    })
  }

  return rows.sort((a, b) => b.avgScore - a.avgScore)
}

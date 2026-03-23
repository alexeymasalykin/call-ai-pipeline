export function getScoreColor(score: number): string {
  if (score <= 3) return 'text-b24-red bg-b24-red-bg'
  if (score <= 6) return 'text-b24-yellow bg-b24-yellow-bg'
  return 'text-b24-green bg-b24-green-bg'
}

export function getScoreBorderColor(score: number): string {
  if (score <= 3) return 'border-b24-red/30'
  if (score <= 6) return 'border-b24-yellow/30'
  return 'border-b24-green/30'
}

export const CHART_COLORS = {
  primary: 'rgba(47, 198, 246, 0.9)',
  primaryBg: 'rgba(47, 198, 246, 0.12)',
  gridLine: 'rgba(0, 0, 0, 0.06)',
  text: '#959ca4',
} as const

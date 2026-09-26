import { readActionResult, request } from '@/api/client'

/** 隧道台账行：原有字段照旧，另带责任班组与规范状态。 */
export type TunnelRow = {
  id: number | string
  [key: string]: string | number | null | Array<Record<string, string>>
}

export const ENDPOINT = '/api/tunnel'
export const columns = [
  '隧道编码', '隧道名称', '隧道长度', '断面形式',
  '照明方式', '通风方式', '管养单位', '责任班组', '隧道状态',
]
export const actions = ['办理移交', '安排检修', '停用隧道']
export const statuses = ['待移交', '正常养护', '检修封闭', '已停用']
export const stats = [
  { label: '在养隧道', value: 0 },
  { label: '检修中隧道', value: 0 },
  { label: '隧道总长', value: 0 },
]

/** 当前状态下该动作是否符合流转规则；已停用是终态，任何动作都不再放行。 */
function flowAllows(action: string, status: string): boolean {
  if (status === '已停用') {
    return false
  }
  const allowed: Record<string, string[]> = {
    办理移交: ['待移交'],
    安排检修: ['正常养护', '检修封闭'],
    停用隧道: ['待移交', '正常养护', '检修封闭'],
  }
  return (allowed[action] ?? []).includes(status)
}

export interface ActionState {
  enabled: boolean
  reason: string
}

/**
 * 前端收口：非责任班组的动作按钮直接禁用并说明原因；
 * 后端仍会再做一次强制校验，绕过页面直接调接口同样会被阻断。
 */
export function actionState(action: string, row: TunnelRow, team: string, isCrew: boolean): ActionState {
  const status = String(row.status ?? '')
  const owner = String(row['责任班组'] ?? '未移交')
  if (status === '已停用') {
    return { enabled: false, reason: '隧道已停用，不能再回到正常养护' }
  }
  if (!isCrew) {
    return { enabled: false, reason: '当前岗位只能查看，不能改动隧道' }
  }
  if (action === '办理移交') {
    if (owner !== '未移交') {
      return { enabled: false, reason: `已由${owner}承接，不能重复移交` }
    }
  } else if (owner !== team) {
    return { enabled: false, reason: `仅责任班组「${owner}」可操作，当前班组无权改动` }
  }
  if (!flowAllows(action, status)) {
    return { enabled: false, reason: `当前状态「${status}」不允许${action}` }
  }
  return { enabled: true, reason: '' }
}

export async function submitAction(action: string, row: TunnelRow): Promise<void> {
  const response = await request(`${ENDPOINT}/${row.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  await readActionResult(response, '隧道设施动作未生效，请稍后重试')
}

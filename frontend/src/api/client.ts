/** 统一请求封装：拼后端地址、携带当前值班身份、抛网络错误、给页脚留一句可读的说明。 */
import { useSessionStore } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const session = useSessionStore()
  return fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Operator-Name': session.operator,
      'X-Operator-Team': session.team,
      ...init?.headers,
    },
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

/** 解析动作类接口：HTTP 错误和后端 ok:false 都转成带具体原因的异常。 */
export async function readActionResult(
  response: Response,
  fallback = '操作未生效，请稍后重试',
): Promise<void> {
  if (!response.ok) {
    let detail = ''
    try {
      detail = (await response.json())?.detail ?? ''
    } catch {
      detail = ''
    }
    throw new Error(detail || fallback)
  }
  const payload = (await response.json()) as { ok?: boolean; message?: string }
  if (payload.ok === false) {
    throw new Error(payload.message || fallback)
  }
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

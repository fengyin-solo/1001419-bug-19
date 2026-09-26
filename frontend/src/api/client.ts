/** 统一请求封装：拼后端地址、随登录会话携带操作人/班组、抛网络错误。 */
import { useSessionStore } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const session = useSessionStore()
  // 操作身份只从登录会话取，页面不能在请求体里冒充别人；后端按 X-Team 做责任班组鉴权。
  const headers = new Headers(init?.headers ?? { 'Content-Type': 'application/json' })
  headers.set('X-Operator', session.operator)
  headers.set('X-Team', session.team)
  return fetch(url, {
    ...init,
    headers,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

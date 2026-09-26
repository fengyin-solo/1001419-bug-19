import { defineStore } from 'pinia'

export interface Identity {
  operator: string
  team: string
  label: string
}

/** 可切换的值班岗位：前三个是隧道养护班组，可承接/操作归属本班组的隧道；监控值班岗只读。 */
export const IDENTITIES: Identity[] = [
  { operator: '一班经办人', team: '隧道养护一班', label: '隧道养护一班 · 一班经办人' },
  { operator: '二班经办人', team: '隧道养护二班', label: '隧道养护二班 · 二班经办人' },
  { operator: '三班经办人', team: '隧道养护三班', label: '隧道养护三班 · 三班经办人' },
  { operator: '值班管理员', team: '监控值班岗', label: '监控值班岗 · 值班管理员（只读）' },
]

const STORAGE_KEY = 'tunnel-duty-identity'

function restoreIdentity(): Identity {
  if (typeof localStorage !== 'undefined') {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const found = IDENTITIES.find((item) => item.label === raw)
      if (found) {
        return found
      }
    }
  }
  return IDENTITIES[3]
}

export const useSessionStore = defineStore('session', {
  state: () => {
    const identity = restoreIdentity()
    return {
      operator: identity.operator,
      team: identity.team,
      shiftLabel: '白班 08:00-20:00',
      scope: '市政道路桥梁养护平台',
    }
  },
  getters: {
    canOperate: (state) => state.operator.length > 0,
    isCrew: (state) => IDENTITIES.slice(0, 3).some((item) => item.team === state.team),
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setIdentity(identity: Identity) {
      this.operator = identity.operator
      this.team = identity.team
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, identity.label)
      }
    },
  },
})

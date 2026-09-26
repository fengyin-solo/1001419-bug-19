import { defineStore } from 'pinia'

/** 可切换的值班岗位：班组决定能否改动对应责任班组的设施。 */
export interface OperatorPreset {
  operator: string
  team: string
}

export const OPERATOR_PRESETS: OperatorPreset[] = [
  { operator: '周工', team: '隧道养护一班' },
  { operator: '吴敏', team: '隧道养护二班' },
  { operator: '值班管理员', team: '综合管理岗' },
]

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: OPERATOR_PRESETS[0].operator,
    team: OPERATOR_PRESETS[0].team,
    shiftLabel: '白班 08:00-20:00',
    scope: '市政道路桥梁养护平台',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    switchRole(preset: OperatorPreset) {
      this.operator = preset.operator
      this.team = preset.team
    },
  },
})

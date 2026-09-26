<template>
  <section class="page" data-module="tunnel">
    <header class="page-head">
      <div>
        <h2>隧道设施管理</h2>
        <p class="page-desc">维护隧道设施，围绕隧道编码、隧道名称、隧道长度、断面形式做登记、筛选与状态流转；仅责任班组可安排检修与停用。</p>
      </div>
      <div class="page-actions">
        <label class="role-switch">
          <span>当前岗位</span>
          <select :value="session.team" @change="switchRole(($event.target as HTMLSelectElement).value)">
            <option v-for="preset in rolePresets" :key="preset.team" :value="preset.team">
              {{ preset.team }} · {{ preset.operator }}
            </option>
          </select>
        </label>
        <button class="btn primary" type="button" @click="openCreate">登记隧道设施</button>
        <button class="btn" type="button" @click="exportRows">导出隧道设施清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>隧道状态</span>
        <select v-model="filters['隧道状态']">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <template v-if="canManage(row)">
              <button
                v-for="action in actionsFor(row)"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <span v-else class="readonly-hint">仅查看</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无隧道设施数据，可先登记隧道设施</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条隧道设施记录，当前岗位：{{ session.team }} · {{ session.operator }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'
import { OPERATOR_PRESETS, useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/tunnel'
const columns = ["隧道编码", "隧道名称", "隧道长度", "断面形式", "照明方式", "通风方式", "管养单位", "责任班组", "隧道状态"]
const actions = ["办理移交", "安排检修", "停用隧道"]
const statuses = ["待移交", "正常养护", "检修封闭", "已停用"]
const stats = [{"label": "在养隧道", "value": 0}, {"label": "检修中隧道", "value": 0}, {"label": "隧道总长", "value": 0}]

const router = useRouter()
const session = useSessionStore()
const rolePresets = OPERATOR_PRESETS

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function switchRole(team: string) {
  const preset = rolePresets.find((item) => item.team === team)
  if (preset) {
    session.switchRole(preset)
  }
}

function canManage(row: Row) {
  return String(row['责任班组'] ?? '') === session.team
}

function actionsFor(row: Row) {
  // 已停用是终态，前端不再给出任何改动入口；其余非法流转交给后端阻断并说明原因。
  if (row['隧道状态'] === '已停用') {
    return []
  }
  if (row['隧道状态'] === '待移交') {
    return ["办理移交"]
  }
  if (row['隧道状态'] === '检修封闭') {
    return ["停用隧道"]
  }
  return actions.filter((action) => action !== '办理移交')
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '隧道设施登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push({ name: 'tunnel-detail', params: { id: String(row.id) } })
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean, message?: string } | null
    // 业务拦截（越权、终态、非法流转）统一由后端 message 讲清是哪里不被允许。
    if (!response.ok || !payload || payload.ok === false) {
      throw new Error(payload?.message || '隧道设施动作未生效，请稍后重试')
    }
    successMessage.value = payload.message || '操作已生效'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '隧道设施操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  successMessage.value = ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) {
      // 隧道状态过滤对应后端内部 status 字段
      params.set(key === '隧道状态' ? 'status' : key, value)
    }
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('隧道设施列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '隧道设施列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.role-switch { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--muted); }
.role-switch select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.readonly-hint { color: var(--muted); font-size: 12px; }
.success-text { color: #067647; }
</style>

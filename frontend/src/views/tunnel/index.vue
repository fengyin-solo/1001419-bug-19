<template>
  <section class="page" data-module="tunnel">
    <header class="page-head">
      <div>
        <h2>隧道设施管理</h2>
        <p class="page-desc">维护隧道设施，围绕隧道编码、隧道名称、隧道长度、断面形式做登记、筛选与状态流转；仅责任班组可安排检修与停用。</p>
      </div>
      <div class="page-actions">
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

    <p class="page-desc">
      当前值班：{{ store.operator }}（{{ store.team }}）；
      非责任班组只能查看，越权提交会被后端阻断并提示具体原因。
    </p>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
          <td v-for="column in columns" :key="column">
            <RouterLink v-if="column === '隧道名称'" class="tunnel-name" :to="`/tunnel/${row.id}`">
              {{ row[column] ?? '—' }}
            </RouterLink>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <template v-for="action in actions" :key="action">
              <button
                class="link"
                :class="{ muted: !actionState(action, row, store.team, store.isCrew).enabled }"
                type="button"
                :title="actionState(action, row, store.team, store.isCrew).reason"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <RouterLink class="link detail-link" :to="`/tunnel/${row.id}`">详情</RouterLink>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无隧道设施数据，可先登记隧道设施</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条隧道设施记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import {
  actions,
  actionState,
  columns,
  ENDPOINT,
  stats,
  submitAction,
  type TunnelRow,
} from './shared'

const store = useSessionStore()

const rows = ref<TunnelRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

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

async function runAction(action: string, row: TunnelRow) {
  const state = actionState(action, row, store.team, store.isCrew)
  if (!state.enabled) {
    errorMessage.value = state.reason
    return
  }
  errorMessage.value = ''
  try {
    await submitAction(action, row)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '隧道设施操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
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
.tunnel-name { color: var(--brand); text-decoration: none; }
.tunnel-name:hover { text-decoration: underline; }
.detail-link { margin-left: 4px; }
</style>

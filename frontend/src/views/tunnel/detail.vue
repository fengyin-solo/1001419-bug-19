<template>
  <section class="page" data-module="tunnel-detail">
    <header class="page-head">
      <div>
        <h2>隧道设施详情</h2>
        <p class="page-desc">
          隧道字段与状态和列表页同一口径；责任班组、检修记录均取自台账，
          同动作重复提交只留最后一次结果。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/tunnel">返回列表</RouterLink>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <p class="page-desc">
        当前值班：{{ store.operator }}（{{ store.team }}）；
        非责任班组只能查看，不能安排检修或停用。
      </p>

      <div class="detail-grid">
        <div v-for="field in detailFields" :key="field" class="detail-item">
          <span class="detail-key">{{ field }}</span>
          <span>{{ (entry[field] ?? '—') || '—' }}</span>
        </div>
      </div>

      <div class="detail-panel">
        <h3>可执行动作</h3>
        <div class="row-actions">
          <button
            v-for="action in actions"
            :key="action"
            class="link"
            :class="{ muted: !actionState(action, entry, store.team, store.isCrew).enabled }"
            type="button"
            :title="actionState(action, entry, store.team, store.isCrew).reason"
            @click="runAction(action)"
          >
            {{ action }}
          </button>
        </div>
      </div>

      <div class="detail-panel">
        <h3>检修记录（经办台账）</h3>
        <table v-if="records.length" class="data-table">
          <thead>
            <tr>
              <th>动作</th>
              <th>结果状态</th>
              <th>经办班组</th>
              <th>经办人</th>
              <th>经办时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(record, index) in records" :key="index">
              <td>{{ record['动作'] }}</td>
              <td>{{ record['结果状态'] }}</td>
              <td>{{ record['责任班组'] }}</td>
              <td>{{ record['经办人'] }}</td>
              <td>{{ record['经办时间'] }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="page-desc">暂无检修记录。</p>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { actions, actionState, ENDPOINT, submitAction, type TunnelRow } from './shared'

type MaintenanceRecord = Record<string, string>

type TunnelDetail = TunnelRow & {
  检修记录?: MaintenanceRecord[]
}

const store = useSessionStore()
const route = useRoute()
const router = useRouter()

const entry = ref<TunnelDetail | null>(null)
const errorMessage = ref('')

const detailFields = [
  '隧道编码', '隧道名称', '隧道长度', '断面形式',
  '照明方式', '通风方式', '管养单位', '责任班组', '隧道状态',
]
const records = ref<Array<Record<string, string>>>([])

async function runAction(action: string) {
  if (!entry.value) {
    return
  }
  const state = actionState(action, entry.value, store.team, store.isCrew)
  if (!state.enabled) {
    errorMessage.value = state.reason
    return
  }
  errorMessage.value = ''
  try {
    await submitAction(action, entry.value)
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '隧道设施操作失败'
  }
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}`)
    if (response.status === 404) {
      errorMessage.value = '隧道设施不存在或已归档，即将返回列表'
      window.setTimeout(() => {
        void router.push('/tunnel')
      }, 1500)
      return
    }
    if (!response.ok) {
      throw new Error('隧道详情读取失败')
    }
    entry.value = await response.json()
    records.value = entry.value?.检修记录 ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '隧道详情读取失败'
  }
}

onMounted(load)
</script>

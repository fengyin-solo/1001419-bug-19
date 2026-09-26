<template>
  <section class="page" data-module="tunnel-detail">
    <header class="page-head">
      <div>
        <h2>隧道设施详情</h2>
        <p class="page-desc">台账信息与列表同源；仅本隧道责任班组可在此安排检修与停用，经办痕迹按操作人如实留档。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <div v-if="errorMessage" class="detail-error">
      <span class="error-text">{{ errorMessage }}</span>
      <button class="btn" type="button" @click="goBack">返回列表</button>
    </div>

    <template v-else-if="entry">
      <article class="detail-card">
        <h3>基本信息</h3>
        <dl class="detail-grid">
          <template v-for="field in fields" :key="field">
            <dt>{{ field }}</dt>
            <dd :class="field === '隧道状态' ? `status-tag status-${entry[field]}` : ''">
              {{ entry[field] ?? '—' }}
            </dd>
          </template>
          <dt>内部台账状态</dt>
          <dd>{{ entry.status ?? '—' }}</dd>
        </dl>
      </article>

      <article class="detail-card">
        <h3>检修与流转记录</h3>
        <p class="page-desc">同一动作重复提交只保留最后一次结果，经办人以服务端认定的登录身份为准。</p>
        <table v-if="ledgerRows.length" class="data-table">
          <thead>
            <tr>
              <th>动作</th>
              <th>结果状态</th>
              <th>操作人</th>
              <th>责任班组</th>
              <th>操作时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in ledgerRows" :key="row.action">
              <td>{{ row.action }}</td>
              <td>{{ row.record['结果状态'] }}</td>
              <td>{{ row.record['操作人'] }}</td>
              <td>{{ row.record['责任班组'] }}</td>
              <td>{{ row.record['操作时间'] }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty-state">暂无检修与流转记录</p>
      </article>

      <article class="detail-card">
        <h3>可执行操作</h3>
        <p v-if="!canManage" class="page-desc">
          当前岗位「{{ session.team }} · {{ session.operator }}」不是本隧道责任班组，只能查看，不能改动。
        </p>
        <p v-else-if="!allowedActions.length" class="page-desc">
          隧道已处于「{{ entry['隧道状态'] }}」终态，不能再回到正常养护或安排任何作业。
        </p>
        <div v-else class="action-bar">
          <button
            v-for="action in allowedActions"
            :key="action"
            class="btn"
            :class="{ primary: action === '安排检修' }"
            type="button"
            @click="runAction(action)"
          >
            {{ action }}
          </button>
        </div>
        <p v-if="actionError" class="error-text">{{ actionError }}</p>
        <p v-if="actionSuccess" class="success-text">{{ actionSuccess }}</p>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type LedgerRecord = Record<string, string>
type Entry = Record<string, string | number | null | LedgerRecord>

const ENDPOINT = '/api/tunnel'
const fields = ["隧道编码", "隧道名称", "隧道长度", "断面形式", "照明方式", "通风方式", "管养单位", "责任班组", "隧道状态"]
const ALL_ACTIONS = ["办理移交", "安排检修", "停用隧道"]

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const entry = ref<Entry | null>(null)
const errorMessage = ref('')
const actionError = ref('')
const actionSuccess = ref('')

const ledgerRows = computed(() => {
  const ledger = (entry.value?.['检修记录'] ?? {}) as unknown as Record<string, LedgerRecord>
  return ALL_ACTIONS.filter((action) => ledger[action]).map((action) => ({
    action,
    record: ledger[action],
  }))
})

const canManage = computed(() =>
  entry.value !== null && String(entry.value['责任班组'] ?? '') === session.team,
)

const allowedActions = computed(() => {
  if (!entry.value || !canManage.value) {
    return []
  }
  const status = String(entry.value['隧道状态'] ?? '')
  if (status === '待移交') {
    return ['办理移交']
  }
  if (status === '正常养护') {
    return ['安排检修', '停用隧道']
  }
  if (status === '检修封闭') {
    return ['停用隧道']
  }
  return []
})

function goBack() {
  void router.push({ name: 'tunnel' })
}

async function runAction(action: string) {
  actionError.value = ''
  actionSuccess.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean, message?: string } | null
    if (!response.ok || !payload || payload.ok === false) {
      throw new Error(payload?.message || '隧道设施动作未生效，请稍后重试')
    }
    actionSuccess.value = payload.message || '操作已生效'
    await load()
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : '隧道设施操作失败'
  }
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}`)
    if (!response.ok) {
      throw new Error('隧道详情读取失败')
    }
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '隧道详情读取失败'
  }
}

onMounted(load)
</script>

<style scoped>
.detail-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; }
.detail-card h3 { margin: 0 0 10px; font-size: 15px; }
.detail-grid { display: grid; grid-template-columns: 120px 1fr 120px 1fr; gap: 6px 12px; margin: 0; }
.detail-grid dt { color: var(--muted); font-size: 13px; }
.detail-grid dd { margin: 0; font-size: 13px; }
.detail-error { display: flex; justify-content: space-between; align-items: center; background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.action-bar { display: flex; gap: 8px; }
.success-text { color: #067647; }
</style>

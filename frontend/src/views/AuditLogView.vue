<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { request } from "../api/client";
import { formatDateTime } from "../constants";

const filters = reactive({
  operator_user_id: "",
  start_time: "",
  end_time: "",
  method: "",
  request_path: "",
});

const logs = ref([]);
const loading = ref(false);
const errorMessage = ref("");
const selectedLog = ref(null);
const limit = 200;

const methodOptions = ["POST", "PUT", "PATCH", "DELETE"];

const selectedPayload = computed(() =>
  selectedLog.value ? prettyPayload(selectedLog.value.payload) : ""
);

function prettyPayload(payload) {
  if (!payload) {
    return "无请求载荷";
  }
  try {
    return JSON.stringify(JSON.parse(payload), null, 2);
  } catch {
    return payload;
  }
}

function payloadPreview(payload) {
  if (!payload) {
    return "-";
  }
  const compact = String(payload).replace(/\s+/g, " ").trim();
  return compact.length > 90 ? `${compact.slice(0, 90)}...` : compact;
}

function methodClass(method) {
  if (method === "POST") {
    return "badge badge-blue";
  }
  if (method === "PUT" || method === "PATCH") {
    return "badge badge-amber";
  }
  if (method === "DELETE") {
    return "badge badge-red";
  }
  return "badge badge-gray";
}

function statusClass(statusCode) {
  if (statusCode >= 200 && statusCode < 300) {
    return "badge badge-green";
  }
  if (statusCode >= 400 && statusCode < 500) {
    return "badge badge-amber";
  }
  if (statusCode >= 500) {
    return "badge badge-red";
  }
  return "badge badge-gray";
}

function friendlyError(error) {
  if (error?.status === 403) {
    return "仅系统管理员可以查询审计日志";
  }
  if (error?.status === 401) {
    return "登录状态已过期，请重新登录";
  }
  return error?.message || "审计日志查询失败";
}

async function queryLogs() {
  loading.value = true;
  errorMessage.value = "";

  try {
    const data = await request("/api/audit-logs", {
      params: {
        operator_user_id: filters.operator_user_id,
        start_time: filters.start_time,
        end_time: filters.end_time,
        method: filters.method,
        request_path: filters.request_path.trim(),
        limit,
      },
    });
    logs.value = Array.isArray(data) ? data : [];
  } catch (error) {
    logs.value = [];
    errorMessage.value = friendlyError(error);
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.operator_user_id = "";
  filters.start_time = "";
  filters.end_time = "";
  filters.method = "";
  filters.request_path = "";
  queryLogs();
}

function openPayload(log) {
  selectedLog.value = log;
}

function closePayload() {
  selectedLog.value = null;
}

onMounted(queryLogs);
</script>

<template>
  <section class="audit-page">
    <article class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">审计日志查询</h2>
          <p class="card-subtitle">
            管理员查看全局写操作审计记录。可按操作人、操作时间、请求方法和路径筛选。
          </p>
        </div>
        <span class="badge badge-gray">{{ logs.length }} 条</span>
      </div>

      <div class="filter-grid">
        <label class="field">
          <span class="field-label">操作人 ID</span>
          <input
            v-model="filters.operator_user_id"
            class="input"
            type="number"
            min="1"
            placeholder="例如 1"
          />
        </label>

        <label class="field">
          <span class="field-label">开始时间</span>
          <input
            v-model="filters.start_time"
            class="input"
            type="datetime-local"
            step="1"
          />
        </label>

        <label class="field">
          <span class="field-label">结束时间</span>
          <input
            v-model="filters.end_time"
            class="input"
            type="datetime-local"
            step="1"
          />
        </label>

        <label class="field">
          <span class="field-label">请求方法</span>
          <select v-model="filters.method" class="select">
            <option value="">全部方法</option>
            <option v-for="method in methodOptions" :key="method" :value="method">
              {{ method }}
            </option>
          </select>
        </label>

        <label class="field path-field">
          <span class="field-label">请求路径</span>
          <input
            v-model="filters.request_path"
            class="input"
            type="search"
            placeholder="例如 /api/dispenses"
          />
        </label>

        <div class="filter-actions">
          <button
            class="btn btn-primary"
            type="button"
            :disabled="loading"
            @click="queryLogs"
          >
            <span v-if="loading" class="spinner" aria-hidden="true"></span>
            {{ loading ? "查询中..." : "查询" }}
          </button>
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="loading"
            @click="resetFilters"
          >
            重置
          </button>
        </div>
      </div>

      <p v-if="errorMessage" class="alert alert-error list-alert" role="alert">
        {{ errorMessage }}
      </p>

      <div v-else-if="loading" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        正在加载审计日志...
      </div>

      <div v-else-if="logs.length === 0" class="empty-state">
        当前筛选条件下没有审计记录。
      </div>

      <div v-else class="table-wrap">
        <table class="data-table audit-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>操作人</th>
              <th>操作时间</th>
              <th>请求方法</th>
              <th>请求路径</th>
              <th>状态码</th>
              <th>载荷</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td class="mono">#{{ log.id }}</td>
              <td>
                <strong>#{{ log.operator_user_id ?? "-" }}</strong>
                <div class="sub-text">{{ log.operator_username || "-" }}</div>
              </td>
              <td>{{ formatDateTime(log.operate_time) }}</td>
              <td>
                <span :class="methodClass(log.method)">{{ log.method }}</span>
              </td>
              <td class="mono path-cell" :title="log.request_path">
                {{ log.request_path }}
              </td>
              <td>
                <span :class="statusClass(log.status_code)">
                  {{ log.status_code }}
                </span>
              </td>
              <td>
                <div v-if="log.payload" class="payload-cell">
                  <span class="payload-preview">{{ payloadPreview(log.payload) }}</span>
                  <button
                    class="btn btn-ghost btn-sm"
                    type="button"
                    @click="openPayload(log)"
                  >
                    查看
                  </button>
                </div>
                <span v-else class="muted">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="foot-note">
        默认展示最近 {{ limit }} 条记录；时间范围按操作时间筛选。
      </p>
    </article>

    <div
      v-if="selectedLog"
      class="modal-backdrop"
      @click.self="closePayload"
    >
      <div
        class="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="payload-title"
      >
        <div class="modal-head">
          <div>
            <h3 id="payload-title">审计载荷</h3>
            <p class="modal-subtitle">
              #{{ selectedLog.id }} · {{ selectedLog.method }}
              {{ selectedLog.request_path }}
            </p>
          </div>
          <button class="btn btn-secondary btn-sm" type="button" @click="closePayload">
            关闭
          </button>
        </div>
        <pre class="payload-pre">{{ selectedPayload }}</pre>
      </div>
    </div>
  </section>
</template>

<style scoped>
.audit-page {
  display: grid;
  gap: 20px;
}

.filter-grid {
  padding: 18px 22px;
  display: grid;
  grid-template-columns: 140px 210px 210px 150px minmax(180px, 1fr) auto;
  align-items: end;
  gap: 12px;
  border-bottom: 1px solid #edf1f7;
}

.filter-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.path-field {
  min-width: 0;
}

.list-alert {
  margin: 18px 22px;
}

.sub-text {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 11px;
}

.path-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.payload-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 180px;
}

.payload-preview {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #64748b;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 11px;
}

.foot-note {
  margin: 0;
  padding: 14px 22px 18px;
  border-top: 1px solid #edf1f7;
  color: #94a3b8;
  font-size: 11px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(3px);
}

.modal-card {
  width: min(100%, 760px);
  max-height: 84vh;
  display: flex;
  flex-direction: column;
  border: 1px solid #dbe3ee;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.25);
  overflow: hidden;
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #edf1f7;
}

.modal-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
}

.modal-subtitle {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 12px;
  font-family: "Cascadia Code", Consolas, monospace;
}

.payload-pre {
  margin: 0;
  padding: 18px 20px 22px;
  overflow: auto;
  color: #1e293b;
  background: #f8fafc;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1100px) {
  .filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .path-field {
    grid-column: span 2;
  }
}

@media (max-width: 720px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .path-field {
    grid-column: auto;
  }

  .filter-actions {
    align-items: stretch;
  }

  .filter-actions .btn {
    flex: 1;
  }

  .modal-head {
    flex-direction: column;
  }
}
</style>

<script setup>
import { onMounted, ref } from "vue";

import { request } from "../api/client";
import { formatDateTime } from "../constants";

const stats = ref(null);
const loading = ref(false);
const errorMessage = ref("");
const refreshedAt = ref("");

function formatMoney(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function friendlyError(error) {
  if (error?.status === 403) {
    return "仅系统管理员可以查看统计报表";
  }
  if (error?.status === 401) {
    return "登录状态已过期，请重新登录";
  }
  return error?.message || "统计报表加载失败";
}

async function loadStatistics() {
  loading.value = true;
  errorMessage.value = "";

  try {
    stats.value = await request("/api/statistics/today");
    refreshedAt.value = formatDateTime(new Date().toISOString());
  } catch (error) {
    stats.value = null;
    errorMessage.value = friendlyError(error);
  } finally {
    loading.value = false;
  }
}

onMounted(loadStatistics);
</script>

<template>
  <section class="statistics-page">
    <article class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">今日统计报表</h2>
          <p class="card-subtitle">
            展示今日挂号总数量与今日收费总金额。统计口径为服务器本地日期当天
            00:00:00 至次日 00:00:00。
          </p>
        </div>
        <button
          class="btn btn-primary"
          type="button"
          :disabled="loading"
          @click="loadStatistics"
        >
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
          {{ loading ? "刷新中..." : "刷新数据" }}
        </button>
      </div>

      <p v-if="errorMessage" class="alert alert-error report-alert" role="alert">
        {{ errorMessage }}
      </p>

      <div v-else-if="loading && !stats" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        正在加载今日统计数据...
      </div>

      <div v-else-if="stats" class="table-wrap">
        <table class="data-table report-table">
          <thead>
            <tr>
              <th>统计项目</th>
              <th>统计结果</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>统计日期</td>
              <td class="mono">{{ stats.date }}</td>
            </tr>
            <tr>
              <td>今日挂号总数量</td>
              <td>
                <strong class="metric-number">
                  {{ stats.registration_count }}
                </strong>
                <span class="metric-unit">人次</span>
              </td>
            </tr>
            <tr>
              <td>今日收费总金额</td>
              <td>
                <strong class="amount-number">
                  ¥{{ formatMoney(stats.charge_total_amount) }}
                </strong>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="empty-state">
        暂无统计数据。
      </div>

      <p v-if="refreshedAt" class="foot-note">
        最近刷新时间：{{ refreshedAt }}
      </p>
    </article>

    <article class="card note-card">
      <div class="card-body note-body">
        <div>
          <p class="note-title">统计说明</p>
          <p class="note-text">
            挂号数量按今日新建的挂号记录统计；收费金额按今日生成的收费单金额汇总。
          </p>
        </div>
        <span class="badge badge-blue">只读报表</span>
      </div>
    </article>
  </section>
</template>

<style scoped>
.statistics-page {
  display: grid;
  gap: 20px;
}

.report-alert {
  margin: 18px 22px;
}

.report-table {
  font-size: 14px;
}

.report-table th,
.report-table td {
  padding: 18px 22px;
}

.report-table td:first-child {
  width: 40%;
  color: #475569;
  font-weight: 700;
}

.metric-number {
  color: #0f172a;
  font-size: 26px;
  line-height: 1;
}

.metric-unit {
  margin-left: 8px;
  color: #64748b;
  font-size: 13px;
}

.amount-number {
  color: #b45309;
  font-size: 26px;
  line-height: 1;
}

.foot-note {
  margin: 0;
  padding: 14px 22px 18px;
  border-top: 1px solid #edf1f7;
  color: #94a3b8;
  font-size: 11px;
}

.note-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.note-title {
  margin: 0;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.note-text {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 640px) {
  .report-table th,
  .report-table td {
    padding: 14px;
  }

  .note-body {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

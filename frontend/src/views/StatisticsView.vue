<script setup>
import { computed, onMounted, ref } from "vue";

import { request } from "../api/client";
import { formatDateTime } from "../constants";

const dashboard = ref(null);
const loading = ref(false);
const errorMessage = ref("");
const refreshedAt = ref("");

const metrics = computed(
  () =>
    dashboard.value?.metrics || {
      registration_count: 0,
      charge_total_amount: 0,
      dispense_count: 0,
      low_stock_count: 0,
    }
);

const trend = computed(() => dashboard.value?.registration_trend || []);
const departmentDistribution = computed(
  () => dashboard.value?.department_distribution || []
);
const topDrugs = computed(() => dashboard.value?.top_drugs || []);
const lowStockDrugs = computed(() => dashboard.value?.low_stock_drugs || []);

const trendChart = computed(() => {
  const data = trend.value;
  const width = 680;
  const height = 240;
  const paddingX = 46;
  const paddingY = 34;
  const max = Math.max(1, ...data.map((item) => Number(item.count) || 0));
  const step =
    data.length > 1
      ? (width - paddingX * 2) / (data.length - 1)
      : 0;

  const points = data.map((item, index) => {
    const count = Number(item.count) || 0;
    return {
      ...item,
      count,
      x: paddingX + index * step,
      y: height - paddingY - (count / max) * (height - paddingY * 2),
    };
  });

  return {
    width,
    height,
    paddingX,
    paddingY,
    max,
    points,
    polyline: points.map((point) => `${point.x},${point.y}`).join(" "),
    gridLines: [0, 1, 2, 3, 4].map((index) => ({
      y: paddingY + (index * (height - paddingY * 2)) / 4,
      label: Math.round(max - (max * index) / 4),
    })),
  };
});

const departmentMax = computed(() =>
  Math.max(1, ...departmentDistribution.value.map((item) => Number(item.count) || 0))
);

const topDrugMax = computed(() =>
  Math.max(1, ...topDrugs.value.map((item) => Number(item.count) || 0))
);

function formatMoney(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function formatShortDate(value) {
  return String(value || "").slice(5);
}

function departmentBarHeight(count) {
  const value = Number(count) || 0;
  if (value <= 0) {
    return "4px";
  }
  return `${Math.max(10, (value / departmentMax.value) * 150)}px`;
}

function topDrugWidth(count) {
  const value = Number(count) || 0;
  if (value <= 0) {
    return "4%";
  }
  return `${Math.max(8, (value / topDrugMax.value) * 100)}%`;
}

function stockBadgeClass(stock) {
  return Number(stock) < 10 ? "badge badge-red" : "badge badge-amber";
}

function friendlyError(error) {
  if (error?.status === 403) {
    return "仅系统管理员可以查看统计看板";
  }
  if (error?.status === 401) {
    return "登录状态已过期，请重新登录";
  }
  return error?.message || "统计看板加载失败";
}

async function loadDashboard() {
  loading.value = true;
  errorMessage.value = "";

  try {
    dashboard.value = await request("/api/stats/dashboard");
    refreshedAt.value = formatDateTime(new Date().toISOString());
  } catch (error) {
    dashboard.value = null;
    errorMessage.value = friendlyError(error);
  } finally {
    loading.value = false;
  }
}

onMounted(loadDashboard);
</script>

<template>
  <section class="statistics-page">
    <article class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">门诊数据看板</h2>
          <p class="card-subtitle">
            今日核心指标、近 7 天挂号趋势、科室分布、热门药品与库存预警。
            统计口径为服务器本地日期当天 00:00:00 至次日 00:00:00。
          </p>
        </div>
        <button
          class="btn btn-primary"
          type="button"
          :disabled="loading"
          @click="loadDashboard"
        >
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
          {{ loading ? "刷新中..." : "刷新数据" }}
        </button>
      </div>

      <p v-if="errorMessage" class="alert alert-error report-alert" role="alert">
        {{ errorMessage }}
      </p>

      <div v-else-if="loading && !dashboard" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        正在加载统计看板...
      </div>

      <div v-else-if="dashboard" class="dashboard-body">
        <section class="metric-grid" aria-label="今日核心指标">
          <article class="metric-card metric-blue">
            <span class="metric-label">今日挂号总数</span>
            <strong>{{ metrics.registration_count }}</strong>
            <small>今日新建挂号记录</small>
          </article>
          <article class="metric-card metric-amber">
            <span class="metric-label">今日收费总金额</span>
            <strong>¥{{ formatMoney(metrics.charge_total_amount) }}</strong>
            <small>今日收费单金额合计</small>
          </article>
          <article class="metric-card metric-green">
            <span class="metric-label">今日发药处方数</span>
            <strong>{{ metrics.dispense_count }}</strong>
            <small>今日完成发药的处方</small>
          </article>
          <article class="metric-card metric-red">
            <span class="metric-label">库存预警药品数</span>
            <strong>{{ metrics.low_stock_count }}</strong>
            <small>库存低于 20 的药品</small>
          </article>
        </section>

        <section class="chart-grid">
          <article class="card chart-card">
            <div class="chart-head">
              <div>
                <h3>近 7 天挂号趋势</h3>
                <p>每日新建挂号数量</p>
              </div>
              <span class="badge badge-blue">近 7 天</span>
            </div>

            <div v-if="trend.length === 0" class="empty-state">
              暂无趋势数据。
            </div>

            <div v-else class="trend-chart">
              <svg
                :viewBox="`0 0 ${trendChart.width} ${trendChart.height}`"
                class="trend-svg"
                role="img"
                aria-label="近 7 天挂号趋势折线图"
              >
                <title>近 7 天挂号趋势</title>

                <line
                  v-for="line in trendChart.gridLines"
                  :key="`grid-${line.y}`"
                  :x1="trendChart.paddingX"
                  :x2="trendChart.width - trendChart.paddingX"
                  :y1="line.y"
                  :y2="line.y"
                  class="grid-line"
                />

                <text
                  v-for="line in trendChart.gridLines"
                  :key="`label-${line.y}`"
                  :x="trendChart.paddingX - 10"
                  :y="line.y + 4"
                  text-anchor="end"
                  class="axis-text"
                >
                  {{ line.label }}
                </text>

                <polyline
                  v-if="trendChart.points.length > 1"
                  :points="trendChart.polyline"
                  class="trend-line"
                />

                <g
                  v-for="point in trendChart.points"
                  :key="point.date"
                  class="trend-point-group"
                >
                  <circle
                    :cx="point.x"
                    :cy="point.y"
                    r="5"
                    class="trend-point"
                  />
                  <text
                    :x="point.x"
                    :y="point.y - 12"
                    text-anchor="middle"
                    class="point-value"
                  >
                    {{ point.count }}
                  </text>
                  <text
                    :x="point.x"
                    :y="trendChart.height - 10"
                    text-anchor="middle"
                    class="axis-text"
                  >
                    {{ formatShortDate(point.date) }}
                  </text>
                </g>
              </svg>
            </div>
          </article>

          <article class="card chart-card">
            <div class="chart-head">
              <div>
                <h3>今日科室挂号分布</h3>
                <p>按排班科室分组统计</p>
              </div>
              <span class="badge badge-green">今日</span>
            </div>

            <div
              v-if="departmentDistribution.length === 0"
              class="empty-state"
            >
              今日暂无挂号数据。
            </div>

            <div v-else class="department-chart">
              <div
                v-for="item in departmentDistribution"
                :key="item.department"
                class="department-column"
              >
                <span class="department-value">{{ item.count }}</span>
                <div class="department-track">
                  <div
                    class="department-fill"
                    :style="{ height: departmentBarHeight(item.count) }"
                  ></div>
                </div>
                <span class="department-label">{{ item.department }}</span>
              </div>
            </div>
          </article>
        </section>

        <section class="bottom-grid">
          <article class="card chart-card">
            <div class="chart-head">
              <div>
                <h3>热门药品 TOP5</h3>
                <p>按处方明细出现次数排序</p>
              </div>
              <span class="badge badge-amber">累计</span>
            </div>

            <div v-if="topDrugs.length === 0" class="empty-state">
              暂无处方药品数据。
            </div>

            <div v-else class="top-drugs">
              <div
                v-for="(drug, index) in topDrugs"
                :key="drug.drug_id"
                class="top-drug-row"
              >
                <div class="top-drug-head">
                  <span class="top-drug-name">
                    <span class="rank">{{ index + 1 }}</span>
                    {{ drug.drug_name }}
                  </span>
                  <span class="top-drug-count">{{ drug.count }} 次</span>
                </div>
                <div class="top-drug-track">
                  <div
                    class="top-drug-fill"
                    :style="{ width: topDrugWidth(drug.count) }"
                  ></div>
                </div>
              </div>
            </div>
          </article>

          <article class="card chart-card">
            <div class="chart-head">
              <div>
                <h3>库存预警</h3>
                <p>库存低于 20 的药品，低于 10 标红</p>
              </div>
              <span class="badge badge-red">
                {{ lowStockDrugs.length }} 项
              </span>
            </div>

            <div v-if="lowStockDrugs.length === 0" class="empty-state">
              暂无库存预警药品。
            </div>

            <div v-else class="table-wrap warning-table">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>药品名</th>
                    <th>规格</th>
                    <th>当前库存</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="drug in lowStockDrugs" :key="drug.id">
                    <td>
                      <strong>{{ drug.generic_name }}</strong>
                    </td>
                    <td>{{ drug.spec }}</td>
                    <td>
                      <span :class="stockBadgeClass(drug.stock)">
                        {{ drug.stock }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </section>
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
            挂号、收费、发药按今日统计；热门药品按处方明细累计出现次数统计；
            库存预警阈值为 stock &lt; 20。
          </p>
        </div>
        <span class="badge badge-blue">只读看板</span>
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

.dashboard-body {
  padding: 20px 22px 22px;
  display: grid;
  gap: 18px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.metric-card {
  position: relative;
  overflow: hidden;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
}

.metric-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: currentColor;
}

.metric-blue {
  color: #2563eb;
}

.metric-amber {
  color: #b45309;
}

.metric-green {
  color: #15803d;
}

.metric-red {
  color: #b91c1c;
}

.metric-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.metric-card strong {
  color: #0f172a;
  font-size: 28px;
  line-height: 1.15;
}

.metric-card small {
  color: #94a3b8;
  font-size: 11px;
}

.chart-grid,
.bottom-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  align-items: stretch;
}

.chart-card {
  padding: 18px;
  min-width: 0;
}

.chart-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.chart-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
}

.chart-head p {
  margin: 4px 0 0;
  color: #94a3b8;
  font-size: 11px;
}

.trend-chart {
  width: 100%;
  overflow-x: auto;
}

.trend-svg {
  width: 100%;
  min-width: 480px;
  height: auto;
  display: block;
}

.grid-line {
  stroke: #e2e8f0;
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.axis-text {
  fill: #94a3b8;
  font-size: 10px;
}

.point-value {
  fill: #1d4ed8;
  font-size: 10px;
  font-weight: 700;
}

.trend-line {
  fill: none;
  stroke: #2563eb;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trend-point {
  fill: #fff;
  stroke: #2563eb;
  stroke-width: 3;
}

.department-chart {
  height: 220px;
  padding: 0 4px;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 12px;
  overflow-x: auto;
}

.department-column {
  min-width: 46px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.department-value {
  color: #15803d;
  font-size: 11px;
  font-weight: 700;
}

.department-track {
  width: 30px;
  height: 160px;
  display: flex;
  align-items: flex-end;
  border-radius: 8px 8px 4px 4px;
  background: #f1f5f9;
}

.department-fill {
  width: 100%;
  border-radius: 8px 8px 4px 4px;
  background: linear-gradient(180deg, #22c55e, #15803d);
  transition: height 0.3s ease;
}

.department-label {
  max-width: 64px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #64748b;
  font-size: 11px;
}

.top-drugs {
  display: grid;
  gap: 14px;
}

.top-drug-row {
  display: grid;
  gap: 7px;
}

.top-drug-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #334155;
  font-size: 12px;
}

.top-drug-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
}

.rank {
  width: 20px;
  height: 20px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 10px;
  font-weight: 800;
}

.top-drug-count {
  flex: 0 0 auto;
  color: #b45309;
  font-weight: 700;
}

.top-drug-track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #f1f5f9;
}

.top-drug-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #f59e0b, #f97316);
  transition: width 0.3s ease;
}

.warning-table {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
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

@media (max-width: 1100px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chart-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dashboard-body {
    padding: 14px;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .chart-card {
    padding: 14px;
  }

  .note-body {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

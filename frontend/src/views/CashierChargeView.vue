<script setup>
import { computed, onMounted, ref } from "vue";

import { request } from "../api/client";
import { formatDate, formatDateTime } from "../constants";

const prescriptions = ref([]);
const loadingPrescriptions = ref(false);
const prescriptionsError = ref("");
const keyword = ref("");

const selectedId = ref(null);
const preview = ref(null);
const previewLoading = ref(false);
const previewError = ref("");
const charging = ref(false);
const chargeError = ref("");
const successMessage = ref("");
const lastCharge = ref(null);

const chargeOrders = ref([]);
const loadingOrders = ref(false);
const ordersError = ref("");
const orderDate = ref("");

const filteredPrescriptions = computed(() => {
  const search = keyword.value.trim().toLowerCase();
  if (!search) {
    return prescriptions.value;
  }
  return prescriptions.value.filter((prescription) => {
    return [
      prescription.id,
      prescription.patient_name,
      prescription.patient_phone,
      prescription.department,
      prescription.doctor_username,
      prescription.icd10_code,
      prescription.diagnosis_name,
    ].some((value) => String(value || "").toLowerCase().includes(search));
  });
});

const recentTotal = computed(() =>
  chargeOrders.value.reduce(
    (sum, order) => sum + Number(order.total_amount || 0),
    0
  )
);

function formatMoney(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function friendlyError(error) {
  const message = error?.message || "操作失败，请稍后重试";
  if (error?.status === 409) {
    if (/already paid/i.test(message)) {
      return "该处方已收费，请刷新未收费处方列表";
    }
    return "操作冲突，请刷新页面后重试";
  }
  if (error?.status === 400 && /drug/i.test(message)) {
    return "处方中存在未维护的药品，无法计算收费金额";
  }
  if (error?.status === 400 && /quantity/i.test(message)) {
    return "处方明细数量异常，无法收费";
  }
  if (error?.status === 404) {
    return "处方不存在或已被删除";
  }
  if (error?.status === 403) {
    return "仅收费员可以执行收费操作";
  }
  if (error?.status === 422) {
    return "请求参数不正确，请刷新后重试";
  }
  if (error?.status === 401) {
    return "登录状态已过期，请重新登录";
  }
  return message;
}

function clearSelection() {
  selectedId.value = null;
  preview.value = null;
  previewError.value = "";
  chargeError.value = "";
}

async function loadPrescriptions() {
  loadingPrescriptions.value = true;
  prescriptionsError.value = "";

  try {
    const data = await request("/api/prescriptions", {
      params: { paid: false, limit: 100 },
    });
    prescriptions.value = Array.isArray(data) ? data : [];

    if (
      selectedId.value &&
      !prescriptions.value.some(
        (prescription) => prescription.id === selectedId.value
      )
    ) {
      clearSelection();
    }
  } catch (error) {
    prescriptions.value = [];
    clearSelection();
    prescriptionsError.value = friendlyError(error);
  } finally {
    loadingPrescriptions.value = false;
  }
}

async function loadPreview(prescriptionId) {
  previewLoading.value = true;
  previewError.value = "";
  preview.value = null;

  try {
    preview.value = await request(
      `/api/prescriptions/${prescriptionId}/charge-preview`
    );
  } catch (error) {
    previewError.value = friendlyError(error);
    if ([404, 409].includes(error?.status)) {
      await loadPrescriptions();
    }
  } finally {
    previewLoading.value = false;
  }
}

function selectPrescription(prescription) {
  if (selectedId.value === prescription.id) {
    return;
  }
  selectedId.value = prescription.id;
  preview.value = null;
  previewError.value = "";
  chargeError.value = "";
  successMessage.value = "";
  lastCharge.value = null;
  loadPreview(prescription.id);
}

async function confirmCharge() {
  if (!preview.value || charging.value) {
    return;
  }

  charging.value = true;
  chargeError.value = "";
  successMessage.value = "";

  try {
    const order = await request("/api/charge-orders", {
      method: "POST",
      body: { prescription_id: preview.value.prescription_id },
    });

    lastCharge.value = order;
    successMessage.value = `收费成功，收费单号 #${order.id}，实收 ¥${formatMoney(
      order.total_amount
    )}`;
    selectedId.value = null;
    preview.value = null;
    previewError.value = "";

    await Promise.all([loadPrescriptions(), loadChargeOrders()]);
  } catch (error) {
    chargeError.value = friendlyError(error);
    if ([404, 409].includes(error?.status)) {
      await loadPrescriptions();
    }
  } finally {
    charging.value = false;
  }
}

async function loadChargeOrders() {
  loadingOrders.value = true;
  ordersError.value = "";

  try {
    const data = await request("/api/charge-orders", {
      params: { date: orderDate.value, limit: 50 },
    });
    chargeOrders.value = Array.isArray(data) ? data : [];
  } catch (error) {
    chargeOrders.value = [];
    ordersError.value = friendlyError(error);
  } finally {
    loadingOrders.value = false;
  }
}

function resetOrderDate() {
  orderDate.value = "";
  loadChargeOrders();
}

onMounted(() => {
  loadPrescriptions();
  loadChargeOrders();
});
</script>

<template>
  <section class="cashier-page">
    <div class="metric-grid">
      <article class="card metric-card">
        <span class="metric-label">未收费处方</span>
        <strong>{{ prescriptions.length }}</strong>
        <small>当前可执行收费</small>
      </article>
      <article class="card metric-card">
        <span class="metric-label">最近收费单</span>
        <strong>{{ chargeOrders.length }}</strong>
        <small>当前筛选结果</small>
      </article>
      <article class="card metric-card">
        <span class="metric-label">最近收费金额</span>
        <strong>¥{{ formatMoney(recentTotal) }}</strong>
        <small>当前筛选结果合计</small>
      </article>
    </div>

    <div class="cashier-grid">
      <article class="card unpaid-panel">
        <div class="card-head">
          <div>
            <h2 class="card-title">未收费处方</h2>
            <p class="card-subtitle">
              选择一张未收费处方，查看后端计算的药品明细和应收金额。
            </p>
          </div>
          <span class="badge badge-amber">待收费</span>
        </div>

        <div class="toolbar">
          <input
            v-model="keyword"
            class="input"
            type="search"
            placeholder="搜索患者、手机号、诊断、医生或处方号"
          />
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="loadingPrescriptions"
            @click="loadPrescriptions"
          >
            刷新
          </button>
        </div>

        <p
          v-if="prescriptionsError"
          class="alert alert-error list-alert"
          role="alert"
        >
          {{ prescriptionsError }}
        </p>

        <div v-else-if="loadingPrescriptions" class="empty-state">
          <span class="spinner" aria-hidden="true"></span>
          正在加载未收费处方...
        </div>

        <div
          v-else-if="filteredPrescriptions.length === 0"
          class="empty-state"
        >
          暂无未收费处方。<br />
          医生开具处方后会自动出现在这里。
        </div>

        <ul v-else class="rx-list">
          <li v-for="prescription in filteredPrescriptions" :key="prescription.id">
            <button
              type="button"
              class="rx-item"
              :class="{ selected: selectedId === prescription.id }"
              @click="selectPrescription(prescription)"
            >
              <span class="rx-head">
                <span class="rx-title">
                  #{{ prescription.id }} {{ prescription.patient_name }}
                </span>
                <span class="badge badge-amber">未收费</span>
              </span>

              <span class="rx-meta">
                {{ prescription.patient_phone || "-" }} ·
                {{ prescription.department || "-" }} ·
                {{ prescription.doctor_username || "-" }}
              </span>

              <span class="rx-meta">
                就诊 {{ formatDate(prescription.schedule_date) }} ·
                {{ prescription.icd10_code }} ·
                {{ prescription.diagnosis_name }}
              </span>

              <span class="rx-foot">
                药品 {{ prescription.items?.length || 0 }} 项
              </span>
            </button>
          </li>
        </ul>
      </article>

      <article class="card charge-panel">
        <div class="card-head">
          <div>
            <h2 class="card-title">收费确认</h2>
            <p class="card-subtitle">
              应收金额完全由后端读取药品档案单价计算，前端不提交价格参数。
            </p>
          </div>
          <span v-if="preview" class="badge badge-blue">待确认</span>
        </div>

        <div class="card-body charge-body">
          <p v-if="successMessage" class="alert alert-success" role="status">
            {{ successMessage }}
          </p>

          <div v-if="lastCharge" class="last-charge">
            <div class="last-charge-head">
              <div>
                <p class="summary-label">最近完成收费</p>
                <p class="summary-title">
                  收费单 #{{ lastCharge.id }} · ¥{{
                    formatMoney(lastCharge.total_amount)
                  }}
                </p>
                <p class="summary-meta">
                  {{ lastCharge.patient_name || "-" }} ·
                  {{ lastCharge.department || "-" }} ·
                  {{ formatDateTime(lastCharge.charged_at) }}
                </p>
              </div>
              <span class="badge badge-green">已收费</span>
            </div>
          </div>

          <p v-if="previewError" class="alert alert-error" role="alert">
            {{ previewError }}
          </p>

          <div v-else-if="previewLoading" class="empty-state">
            <span class="spinner" aria-hidden="true"></span>
            正在计算应收金额...
          </div>

          <p v-else-if="!preview" class="alert alert-info">
            请从左侧选择一张未收费处方，系统将展示药品明细与应收金额。
          </p>

          <template v-else>
            <div class="preview-summary">
              <div>
                <p class="summary-label">患者信息</p>
                <p class="summary-title">
                  {{ preview.patient_name }}
                  <span class="summary-phone">
                    {{ preview.patient_phone || "-" }}
                  </span>
                </p>
                <p class="summary-meta">
                  {{ preview.department || "-" }} ·
                  {{ preview.doctor_username || "-" }} ·
                  就诊 {{ formatDate(preview.schedule_date) }}
                </p>
                <p class="summary-meta">
                  {{ preview.icd10_code }} · {{ preview.diagnosis_name }}
                </p>
              </div>
              <span class="badge badge-blue">
                处方 #{{ preview.prescription_id }}
              </span>
            </div>

            <div class="table-wrap preview-table">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>药品</th>
                    <th>规格</th>
                    <th>医保</th>
                    <th>单价</th>
                    <th>数量</th>
                    <th>小计</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in preview.items" :key="item.drug_id">
                    <td>
                      <strong>{{ item.generic_name }}</strong>
                      <span v-if="item.trade_name" class="drug-trade">
                        （{{ item.trade_name }}）
                      </span>
                      <div class="drug-form">{{ item.dosage_form }}</div>
                    </td>
                    <td>{{ item.spec }}</td>
                    <td>
                      <span class="badge badge-gray">
                        {{ item.insurance_type }}
                      </span>
                    </td>
                    <td class="mono">¥{{ formatMoney(item.unit_price) }}</td>
                    <td>{{ item.qty }}</td>
                    <td class="mono line-total">
                      ¥{{ formatMoney(item.line_total) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="total-bar">
              <span>应收金额</span>
              <strong>¥{{ formatMoney(preview.total_amount) }}</strong>
            </div>

            <p class="price-note">
              该金额由后端按药品档案单价 × 明细数量计算，不使用前端传入的任何价格。
            </p>

            <p v-if="chargeError" class="alert alert-error" role="alert">
              {{ chargeError }}
            </p>

            <div class="charge-actions">
              <button
                class="btn btn-primary"
                type="button"
                :disabled="charging"
                @click="confirmCharge"
              >
                <span
                  v-if="charging"
                  class="spinner"
                  aria-hidden="true"
                ></span>
                {{ charging ? "收费中..." : "确认收费" }}
              </button>
              <button
                class="btn btn-secondary"
                type="button"
                :disabled="charging"
                @click="clearSelection"
              >
                取消选择
              </button>
            </div>
          </template>
        </div>
      </article>
    </div>

    <article class="card orders-panel">
      <div class="card-head">
        <div>
          <h2 class="card-title">收费记录</h2>
          <p class="card-subtitle">
            展示最近收费单，可按收费日期筛选；金额均来自收费时的后端计算结果。
          </p>
        </div>
        <span class="badge badge-gray">{{ chargeOrders.length }} 条</span>
      </div>

      <div class="toolbar">
        <div class="toolbar-group">
          <label class="field order-date-field">
            <span class="field-label">收费日期</span>
            <input v-model="orderDate" class="input" type="date" />
          </label>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="loadingOrders"
            @click="loadChargeOrders"
          >
            查询
          </button>
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="loadingOrders"
            @click="resetOrderDate"
          >
            重置
          </button>
        </div>
      </div>

      <p v-if="ordersError" class="alert alert-error orders-alert" role="alert">
        {{ ordersError }}
      </p>

      <div v-else-if="loadingOrders" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        正在加载收费记录...
      </div>

      <div v-else-if="chargeOrders.length === 0" class="empty-state">
        暂无收费记录。
      </div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>收费单号</th>
              <th>处方号</th>
              <th>患者</th>
              <th>科室</th>
              <th>医生</th>
              <th>金额</th>
              <th>收费员</th>
              <th>收费时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="order in chargeOrders" :key="order.id">
              <td class="mono">#{{ order.id }}</td>
              <td class="mono">#{{ order.prescription_id }}</td>
              <td>{{ order.patient_name || "-" }}</td>
              <td>{{ order.department || "-" }}</td>
              <td>{{ order.doctor_username || "-" }}</td>
              <td class="mono amount-cell">
                ¥{{ formatMoney(order.total_amount) }}
              </td>
              <td>{{ order.cashier_username || "-" }}</td>
              <td>{{ formatDateTime(order.charged_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<style scoped>
.cashier-page {
  display: grid;
  gap: 20px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.metric-card {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.metric-card strong {
  color: #0f172a;
  font-size: 24px;
  line-height: 1.2;
}

.metric-card small {
  color: #94a3b8;
  font-size: 11px;
}

.cashier-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.3fr);
  align-items: start;
  gap: 20px;
}

.unpaid-panel,
.charge-panel {
  min-width: 0;
}

.list-alert {
  margin: 14px;
}

.rx-list {
  max-height: 64vh;
  margin: 0;
  padding: 14px;
  display: grid;
  gap: 10px;
  overflow-y: auto;
  list-style: none;
}

.rx-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 13px;
  background: #fff;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    box-shadow 0.18s ease;
}

.rx-item:hover {
  border-color: #fcd34d;
  background: #fffbeb;
}

.rx-item.selected {
  border-color: #f59e0b;
  background: #fffbeb;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.12);
}

.rx-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.rx-title {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}

.rx-meta {
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.45;
}

.rx-foot {
  color: #b45309;
  font-size: 11px;
  font-weight: 700;
}

.charge-body {
  display: grid;
  gap: 14px;
}

.last-charge {
  padding: 14px 16px;
  border: 1px solid #bbf7d0;
  border-radius: 13px;
  background: #f0fdf4;
}

.last-charge-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.last-charge .summary-title {
  color: #166534;
}

.preview-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid #bfdbfe;
  border-radius: 13px;
  background: #eff6ff;
}

.summary-label {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.summary-title {
  margin: 0;
  color: #1e3a8a;
  font-size: 15px;
  font-weight: 800;
}

.summary-phone {
  margin-left: 8px;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.summary-meta {
  margin: 4px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
}

.preview-table {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}

.drug-trade {
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
}

.drug-form {
  color: #94a3b8;
  font-size: 11px;
}

.line-total {
  color: #0f172a;
  font-weight: 800;
}

.total-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 13px;
  background: #0f172a;
  color: #fff;
}

.total-bar span {
  font-size: 13px;
  font-weight: 700;
}

.total-bar strong {
  font-size: 24px;
  letter-spacing: 0.02em;
}

.price-note {
  margin: 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.5;
}

.charge-actions {
  display: flex;
  gap: 10px;
}

.order-date-field {
  width: 170px;
}

.orders-alert {
  margin: 18px 22px;
}

.amount-cell {
  color: #b45309;
  font-weight: 800;
}

@media (max-width: 960px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .cashier-grid {
    grid-template-columns: 1fr;
  }

  .rx-list {
    max-height: 340px;
  }
}

@media (max-width: 640px) {
  .order-date-field {
    width: 100%;
  }

  .charge-actions {
    flex-direction: column;
  }

  .last-charge-head,
  .preview-summary {
    flex-direction: column;
  }
}
</style>

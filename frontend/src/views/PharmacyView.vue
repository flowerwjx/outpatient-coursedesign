<script setup>
import { computed, onMounted, ref } from "vue";

import { request } from "../api/client";
import { formatDate, formatDateTime } from "../constants";

const activeTab = ref("dispense");

const drugs = ref([]);
const loadingDrugs = ref(false);
const drugsError = ref("");
const drugKeyword = ref("");

const fileInput = ref(null);
const selectedFile = ref(null);
const importing = ref(false);
const importResult = ref(null);
const importError = ref("");

const prescriptions = ref([]);
const loadingPrescriptions = ref(false);
const prescriptionsError = ref("");
const prescriptionKeyword = ref("");
const dispenseFilter = ref("pending");
const selectedId = ref(null);
const dispensing = ref(false);
const dispenseError = ref("");
const successMessage = ref("");
const lastDispense = ref(null);

const drugMap = computed(
  () => new Map(drugs.value.map((drug) => [drug.id, drug]))
);

const filteredDrugs = computed(() => {
  const keyword = drugKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return drugs.value;
  }
  return drugs.value.filter((drug) => {
    return [drug.generic_name, drug.trade_name, drug.spec, drug.dosage_form]
      .some((value) => String(value || "").toLowerCase().includes(keyword));
  });
});

const lowStockCount = computed(
  () => drugs.value.filter((drug) => drug.stock <= 10).length
);

const pendingCount = computed(
  () => prescriptions.value.filter((item) => !item.dispensed).length
);

const dispensedCount = computed(
  () => prescriptions.value.filter((item) => item.dispensed).length
);

const selectedPrescription = computed(
  () =>
    prescriptions.value.find(
      (prescription) => prescription.id === selectedId.value
    ) || null
);

const filteredPrescriptions = computed(() => {
  let list = prescriptions.value.filter((item) => item.paid);

  if (dispenseFilter.value === "pending") {
    list = list.filter((item) => !item.dispensed);
  } else if (dispenseFilter.value === "dispensed") {
    list = list.filter((item) => item.dispensed);
  }

  const keyword = prescriptionKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return list;
  }
  return list.filter((prescription) => {
    return [
      prescription.id,
      prescription.patient_name,
      prescription.patient_phone,
      prescription.department,
      prescription.doctor_username,
      prescription.icd10_code,
      prescription.diagnosis_name,
    ].some((value) => String(value || "").toLowerCase().includes(keyword));
  });
});

const selectedItems = computed(() =>
  (selectedPrescription.value?.items || []).map((item) => ({
    ...item,
    drug: drugMap.value.get(item.drug_id) || null,
  }))
);

const hasStockShortage = computed(() =>
  selectedItems.value.some(
    (item) => !item.drug || Number(item.drug.stock) < Number(item.qty)
  )
);

function formatMoney(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function stockClass(drug) {
  if (drug.stock <= 0) {
    return "badge badge-red";
  }
  if (drug.stock <= 10) {
    return "badge badge-amber";
  }
  return "badge badge-green";
}

function friendlyError(error) {
  const message = error?.message || "操作失败，请稍后重试";
  if (error?.status === 400 && /paid/i.test(message)) {
    return "该处方尚未收费，不能发药";
  }
  if (error?.status === 400 && /stock/i.test(message)) {
    return "药品库存不足，发药失败，库存未发生变化";
  }
  if (error?.status === 400 && /drug/i.test(message)) {
    return "处方中存在未维护的药品，无法发药";
  }
  if (error?.status === 409) {
    return "该处方已经发药，请刷新已收费处方列表";
  }
  if (error?.status === 403) {
    return "仅药师可以执行发药操作";
  }
  if (error?.status === 404) {
    return "处方不存在或已被删除";
  }
  if (error?.status === 422) {
    return "请求参数不正确，请刷新后重试";
  }
  if (error?.status === 401) {
    return "登录状态已过期，请重新登录";
  }
  return message;
}

async function loadDrugs() {
  loadingDrugs.value = true;
  drugsError.value = "";

  try {
    const data = await request("/api/drugs", { params: { limit: 500 } });
    drugs.value = Array.isArray(data) ? data : [];
  } catch (error) {
    drugs.value = [];
    drugsError.value = friendlyError(error);
  } finally {
    loadingDrugs.value = false;
  }
}

async function loadPrescriptions() {
  loadingPrescriptions.value = true;
  prescriptionsError.value = "";

  try {
    const data = await request("/api/prescriptions", {
      params: { paid: true, limit: 200 },
    });
    prescriptions.value = Array.isArray(data) ? data : [];
    if (
      selectedId.value &&
      !prescriptions.value.some(
        (prescription) => prescription.id === selectedId.value
      )
    ) {
      selectedId.value = null;
    }
  } catch (error) {
    prescriptions.value = [];
    prescriptionsError.value = friendlyError(error);
  } finally {
    loadingPrescriptions.value = false;
  }
}

function onFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null;
  importError.value = "";
  importResult.value = null;
}

function resetFileInput() {
  selectedFile.value = null;
  if (fileInput.value) {
    fileInput.value.value = "";
  }
}

async function uploadCsv() {
  if (!selectedFile.value || importing.value) {
    return;
  }

  importing.value = true;
  importError.value = "";
  importResult.value = null;

  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    const result = await request("/api/drugs/import", {
      method: "POST",
      body: formData,
    });
    importResult.value = result;
    resetFileInput();
    await loadDrugs();
  } catch (error) {
    importError.value = friendlyError(error);
  } finally {
    importing.value = false;
  }
}

function downloadTemplate() {
  const header =
    "generic_name,trade_name,spec,dosage_form,insurance_type,unit_price,stock";
  const example = "阿莫西林胶囊,阿莫仙,0.25g×24粒,胶囊剂,甲类,18.50,100";
  const blob = new Blob([`\uFEFF${header}\n${example}\n`], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "drugs_template.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function selectPrescription(prescription) {
  if (!prescription.paid) {
    return;
  }
  selectedId.value = prescription.id;
  dispenseError.value = "";
  successMessage.value = "";
  lastDispense.value = null;
}

async function confirmDispense() {
  if (
    !selectedPrescription.value ||
    selectedPrescription.value.dispensed ||
    dispensing.value
  ) {
    return;
  }

  dispensing.value = true;
  dispenseError.value = "";
  successMessage.value = "";

  try {
    const record = await request("/api/dispenses", {
      method: "POST",
      body: { prescription_id: selectedPrescription.value.id },
    });

    lastDispense.value = record;
    successMessage.value = `发药成功，发药单号 #${record.id}。`;
    selectedId.value = null;
    await Promise.all([loadPrescriptions(), loadDrugs()]);
  } catch (error) {
    dispenseError.value = friendlyError(error);
    if ([404, 409].includes(error?.status)) {
      await loadPrescriptions();
    }
  } finally {
    dispensing.value = false;
  }
}

onMounted(() => {
  loadDrugs();
  loadPrescriptions();
});
</script>

<template>
  <section class="pharmacy-page">
    <div class="page-tabs card">
      <button
        type="button"
        class="tab-button"
        :class="{ active: activeTab === 'dispense' }"
        @click="activeTab = 'dispense'"
      >
        发药工作台
      </button>
      <button
        type="button"
        class="tab-button"
        :class="{ active: activeTab === 'drugs' }"
        @click="activeTab = 'drugs'"
      >
        药品档案与导入
      </button>
      <span class="tab-note">当前角色：药房药师</span>
    </div>

    <template v-if="activeTab === 'drugs'">
      <div class="metric-grid">
        <article class="card metric-card">
          <span class="metric-label">药品档案</span>
          <strong>{{ drugs.length }}</strong>
          <small>当前药品目录总数</small>
        </article>
        <article class="card metric-card">
          <span class="metric-label">库存紧张</span>
          <strong>{{ lowStockCount }}</strong>
          <small>库存 ≤ 10 的药品</small>
        </article>
        <article class="card metric-card">
          <span class="metric-label">最近导入</span>
          <strong v-if="importResult">
            {{ importResult.success }} / {{ importResult.fail }}
          </strong>
          <strong v-else>-</strong>
          <small>成功 / 失败行数</small>
        </article>
      </div>

      <article class="card import-card">
        <div class="card-head">
          <div>
            <h2 class="card-title">CSV 批量导入药品</h2>
            <p class="card-subtitle">
              服务端逐行校验；错误行不会影响合法行入库。支持 UTF-8 / GB18030
              编码，也兼容中英文表头。
            </p>
          </div>
          <button
            class="btn btn-secondary btn-sm"
            type="button"
            @click="downloadTemplate"
          >
            下载模板
          </button>
        </div>

        <div class="card-body import-body">
          <div class="file-row">
            <input
              ref="fileInput"
              class="input file-input"
              type="file"
              accept=".csv,text/csv"
              :disabled="importing"
              @change="onFileChange"
            />
            <button
              class="btn btn-primary"
              type="button"
              :disabled="!selectedFile || importing"
              @click="uploadCsv"
            >
              <span v-if="importing" class="spinner" aria-hidden="true"></span>
              {{ importing ? "导入中..." : "上传并导入" }}
            </button>
          </div>

          <p class="field-note">
            必填列：generic_name、trade_name、spec、dosage_form、
            insurance_type、unit_price、stock。商品名允许为空。
          </p>

          <p v-if="importError" class="alert alert-error" role="alert">
            {{ importError }}
          </p>

          <div v-if="importResult" class="import-result">
            <div class="import-stats">
              <span class="badge badge-green">
                成功 {{ importResult.success }} 行
              </span>
              <span class="badge badge-red">
                失败 {{ importResult.fail }} 行
              </span>
            </div>

            <div
              v-if="importResult.errors.length > 0"
              class="table-wrap import-errors"
            >
              <table class="data-table">
                <thead>
                  <tr>
                    <th>CSV 行号</th>
                    <th>错误原因</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, index) in importResult.errors" :key="index">
                    <td class="mono">第 {{ item.row }} 行</td>
                    <td>{{ item.error }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p v-else class="alert alert-success">
              全部合法药品均已导入，无错误行。
            </p>
          </div>
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <div>
            <h2 class="card-title">药品档案</h2>
            <p class="card-subtitle">
              查看通用名、商品名、规格、剂型、医保类别、单价和库存。
            </p>
          </div>
          <span class="badge badge-gray">{{ filteredDrugs.length }} 条</span>
        </div>

        <div class="toolbar">
          <input
            v-model="drugKeyword"
            class="input"
            type="search"
            placeholder="搜索通用名、商品名、规格或剂型"
          />
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="loadingDrugs"
            @click="loadDrugs"
          >
            刷新
          </button>
        </div>

        <p v-if="drugsError" class="alert alert-error list-alert" role="alert">
          {{ drugsError }}
        </p>

        <div v-else-if="loadingDrugs" class="empty-state">
          <span class="spinner" aria-hidden="true"></span>
          正在加载药品档案...
        </div>

        <div v-else-if="filteredDrugs.length === 0" class="empty-state">
          暂无药品数据。可通过上方 CSV 批量导入。
        </div>

        <div v-else class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>通用名 / 商品名</th>
                <th>规格 / 剂型</th>
                <th>医保类别</th>
                <th>单价</th>
                <th>库存</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="drug in filteredDrugs" :key="drug.id">
                <td class="mono">#{{ drug.id }}</td>
                <td>
                  <strong>{{ drug.generic_name }}</strong>
                  <div class="sub-text">
                    {{ drug.trade_name || "无商品名" }}
                  </div>
                </td>
                <td>
                  {{ drug.spec }}
                  <div class="sub-text">{{ drug.dosage_form }}</div>
                </td>
                <td>
                  <span class="badge badge-gray">{{ drug.insurance_type }}</span>
                </td>
                <td class="mono">¥{{ formatMoney(drug.unit_price) }}</td>
                <td>
                  <span :class="stockClass(drug)">库存 {{ drug.stock }}</span>
                </td>
                <td>{{ formatDateTime(drug.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </template>

    <template v-else>
      <div class="metric-grid">
        <article class="card metric-card">
          <span class="metric-label">待发药处方</span>
          <strong>{{ pendingCount }}</strong>
          <small>已收费且未发药</small>
        </article>
        <article class="card metric-card">
          <span class="metric-label">已发药处方</span>
          <strong>{{ dispensedCount }}</strong>
          <small>已完成发药</small>
        </article>
        <article class="card metric-card">
          <span class="metric-label">药品档案</span>
          <strong>{{ drugs.length }}</strong>
          <small>当前药品目录总数</small>
        </article>
      </div>

      <div class="dispense-grid">
        <article class="card paid-panel">
          <div class="card-head">
            <div>
              <h2 class="card-title">已收费处方</h2>
              <p class="card-subtitle">
                仅展示已收费处方；未收费处方不会出现在发药列表中。
              </p>
            </div>
            <span class="badge badge-amber">{{ pendingCount }} 待发药</span>
          </div>

          <div class="toolbar">
            <input
              v-model="prescriptionKeyword"
              class="input"
              type="search"
              placeholder="搜索患者、手机号、诊断、医生或处方号"
            />
            <select v-model="dispenseFilter" class="select filter-select">
              <option value="pending">待发药</option>
              <option value="dispensed">已发药</option>
              <option value="all">全部已收费</option>
            </select>
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
            正在加载已收费处方...
          </div>

          <div
            v-else-if="filteredPrescriptions.length === 0"
            class="empty-state"
          >
            当前筛选条件下没有已收费处方。
          </div>

          <ul v-else class="rx-list">
            <li v-for="prescription in filteredPrescriptions" :key="prescription.id">
              <button
                type="button"
                class="rx-item"
                :class="{
                  selected: selectedId === prescription.id,
                  dispensed: prescription.dispensed,
                }"
                @click="selectPrescription(prescription)"
              >
                <span class="rx-head">
                  <span class="rx-title">
                    #{{ prescription.id }} {{ prescription.patient_name }}
                  </span>
                  <span
                    class="badge"
                    :class="
                      prescription.dispensed ? 'badge-gray' : 'badge-green'
                    "
                  >
                    {{ prescription.dispensed ? "已发药" : "待发药" }}
                  </span>
                </span>

                <span class="rx-meta">
                  {{ prescription.patient_phone || "-" }} ·
                  {{ prescription.department || "-" }} ·
                  {{ prescription.doctor_username || "-" }}
                </span>

                <span class="rx-meta">
                  {{ prescription.icd10_code }} ·
                  {{ prescription.diagnosis_name }}
                </span>

                <span class="rx-foot">
                  {{ prescription.items?.length || 0 }} 项药品 · 已收费
                </span>
              </button>
            </li>
          </ul>
        </article>

        <article class="card dispense-panel">
          <div class="card-head">
            <div>
              <h2 class="card-title">发药确认</h2>
              <p class="card-subtitle">
                发药会按处方明细扣减药品库存，库存不足时整单回滚。
              </p>
            </div>
            <span
              v-if="selectedPrescription"
              class="badge"
              :class="
                selectedPrescription.dispensed
                  ? 'badge-gray'
                  : 'badge-green'
              "
            >
              {{ selectedPrescription.dispensed ? "已发药" : "待发药" }}
            </span>
          </div>

          <div class="card-body dispense-body">
            <p v-if="successMessage" class="alert alert-success" role="status">
              {{ successMessage }}
            </p>

            <div v-if="lastDispense" class="last-dispense">
              <div class="last-dispense-head">
                <div>
                  <p class="summary-label">最近完成发药</p>
                  <p class="summary-title">
                    发药单 #{{ lastDispense.id }} ·
                    {{ lastDispense.patient_name || "-" }}
                  </p>
                  <p class="summary-meta">
                    {{ lastDispense.department || "-" }} ·
                    {{ formatDateTime(lastDispense.dispensed_at) }}
                  </p>
                </div>
                <span class="badge badge-green">已完成</span>
              </div>
              <ul class="last-dispense-items">
                <li v-for="item in lastDispense.items" :key="item.drug_id">
                  <span>{{ item.generic_name }}</span>
                  <span class="mono">
                    × {{ item.qty }}，剩余 {{ item.remaining_stock }}
                  </span>
                </li>
              </ul>
            </div>

            <p v-if="dispenseError" class="alert alert-error" role="alert">
              {{ dispenseError }}
            </p>

            <p v-else-if="!selectedPrescription" class="alert alert-info">
              请从左侧选择一张已收费处方查看明细并发药。
            </p>

            <template v-else>
              <div class="preview-summary">
                <div>
                  <p class="summary-label">患者信息</p>
                  <p class="summary-title">
                    {{ selectedPrescription.patient_name }}
                    <span class="summary-phone">
                      {{ selectedPrescription.patient_phone || "-" }}
                    </span>
                  </p>
                  <p class="summary-meta">
                    {{ selectedPrescription.department || "-" }} ·
                    {{ selectedPrescription.doctor_username || "-" }} ·
                    就诊 {{ formatDate(selectedPrescription.schedule_date) }}
                  </p>
                  <p class="summary-meta">
                    {{ selectedPrescription.icd10_code }} ·
                    {{ selectedPrescription.diagnosis_name }}
                  </p>
                </div>
                <span class="badge badge-blue">
                  处方 #{{ selectedPrescription.id }}
                </span>
              </div>

              <div class="table-wrap preview-table">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>药品</th>
                      <th>规格</th>
                      <th>医保</th>
                      <th>当前库存</th>
                      <th>需发数量</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in selectedItems" :key="item.drug_id">
                      <td>
                        <strong>
                          {{ item.drug?.generic_name || `药品 #${item.drug_id}` }}
                        </strong>
                        <div class="sub-text">
                          {{ item.drug?.dosage_form || "-" }}
                        </div>
                      </td>
                      <td>{{ item.drug?.spec || "-" }}</td>
                      <td>
                        <span class="badge badge-gray">
                          {{ item.drug?.insurance_type || "-" }}
                        </span>
                      </td>
                      <td class="mono">{{ item.drug?.stock ?? "-" }}</td>
                      <td>{{ item.qty }}</td>
                      <td>
                        <span
                          class="badge"
                          :class="
                            !item.drug || item.drug.stock < item.qty
                              ? 'badge-red'
                              : 'badge-green'
                          "
                        >
                          {{
                            !item.drug
                              ? "药品缺失"
                              : item.drug.stock < item.qty
                                ? "库存不足"
                                : "可发药"
                          }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <p
                v-if="selectedPrescription.dispensed"
                class="alert alert-info"
              >
                该处方已完成发药，发药单号
                #{{ selectedPrescription.dispense_id }}，不可重复发药。
              </p>

              <p v-else-if="hasStockShortage" class="alert alert-error">
                存在药品库存不足或药品档案缺失，当前处方无法发药。
              </p>

              <div
                v-else
                class="dispense-actions"
              >
                <button
                  class="btn btn-primary"
                  type="button"
                  :disabled="dispensing"
                  @click="confirmDispense"
                >
                  <span
                    v-if="dispensing"
                    class="spinner"
                    aria-hidden="true"
                  ></span>
                  {{ dispensing ? "发药中..." : "确认发药" }}
                </button>
              </div>
            </template>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.pharmacy-page {
  display: grid;
  gap: 20px;
}

.page-tabs {
  padding: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-button {
  min-height: 38px;
  padding: 0 16px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition:
    background 0.18s ease,
    color 0.18s ease,
    box-shadow 0.18s ease;
}

.tab-button:hover {
  color: #1d4ed8;
}

.tab-button.active {
  background: #eff6ff;
  color: #1d4ed8;
  box-shadow: inset 0 0 0 1px #bfdbfe;
}

.tab-note {
  margin-left: auto;
  padding-right: 8px;
  color: #94a3b8;
  font-size: 12px;
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

.import-body {
  display: grid;
  gap: 12px;
}

.file-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.file-input {
  max-width: 440px;
  padding: 7px 10px;
}

.field-note {
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.55;
}

.import-result {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 13px;
  background: #f8fafc;
}

.import-stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.import-errors {
  border: 1px solid #fecaca;
  border-radius: 10px;
  background: #fff;
}

.list-alert {
  margin: 14px;
}

.sub-text {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 11px;
}

.dispense-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.3fr);
  align-items: start;
  gap: 20px;
}

.paid-panel,
.dispense-panel {
  min-width: 0;
}

.filter-select {
  width: 130px;
  flex: 0 0 auto;
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
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.rx-item.selected {
  border-color: #22c55e;
  background: #f0fdf4;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.12);
}

.rx-item.dispensed {
  background: #f8fafc;
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
  color: #15803d;
  font-size: 11px;
  font-weight: 700;
}

.dispense-body {
  display: grid;
  gap: 14px;
}

.last-dispense {
  padding: 14px 16px;
  border: 1px solid #bbf7d0;
  border-radius: 13px;
  background: #f0fdf4;
}

.last-dispense-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.last-dispense .summary-title {
  color: #166534;
}

.last-dispense-items {
  margin: 10px 0 0;
  padding: 10px 0 0;
  border-top: 1px dashed #bbf7d0;
  list-style: none;
  display: grid;
  gap: 5px;
  color: #166534;
  font-size: 12px;
}

.last-dispense-items li {
  display: flex;
  justify-content: space-between;
  gap: 14px;
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

.dispense-actions {
  display: flex;
  gap: 10px;
}

.orders-alert {
  margin: 18px 22px;
}

@media (max-width: 960px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .dispense-grid {
    grid-template-columns: 1fr;
  }

  .rx-list {
    max-height: 340px;
  }
}

@media (max-width: 640px) {
  .page-tabs {
    flex-wrap: wrap;
  }

  .tab-note {
    width: 100%;
    margin-left: 0;
    padding: 4px 6px;
  }

  .filter-select {
    width: 100%;
  }

  .file-row {
    align-items: stretch;
  }

  .file-input {
    max-width: none;
  }

  .last-dispense-head,
  .preview-summary {
    flex-direction: column;
  }
}
</style>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { request } from "../api/client";
import { formatDate, formatDateTime } from "../constants";

const ICD10_PATTERN = /^[A-Z][0-9]{2}(\.[0-9A-Z]{1,4})?$/;

// 课程演示药品目录。后端处方接口当前只保存 drug_id，
// 待药品档案模块完成后，应替换为 GET /api/drugs 返回的真实药品目录。
const DEMO_DRUGS = Object.freeze([
  {
    id: 1,
    generic_name: "阿莫西林胶囊",
    trade_name: "阿莫仙",
    spec: "0.25g×24粒",
    dosage_form: "胶囊剂",
    insurance_type: "甲类",
  },
  {
    id: 2,
    generic_name: "布洛芬缓释胶囊",
    trade_name: "芬必得",
    spec: "0.3g×20粒",
    dosage_form: "胶囊剂",
    insurance_type: "乙类",
  },
  {
    id: 3,
    generic_name: "对乙酰氨基酚片",
    trade_name: "扑热息痛",
    spec: "0.5g×20片",
    dosage_form: "片剂",
    insurance_type: "甲类",
  },
  {
    id: 4,
    generic_name: "头孢克肟分散片",
    trade_name: "世福素",
    spec: "0.1g×12片",
    dosage_form: "分散片",
    insurance_type: "乙类",
  },
  {
    id: 5,
    generic_name: "氯雷他定片",
    trade_name: "开瑞坦",
    spec: "10mg×6片",
    dosage_form: "片剂",
    insurance_type: "乙类",
  },
  {
    id: 6,
    generic_name: "奥美拉唑肠溶胶囊",
    trade_name: "洛赛克",
    spec: "20mg×14粒",
    dosage_form: "肠溶胶囊",
    insurance_type: "甲类",
  },
  {
    id: 7,
    generic_name: "蒙脱石散",
    trade_name: "思密达",
    spec: "3g×10袋",
    dosage_form: "散剂",
    insurance_type: "甲类",
  },
  {
    id: 8,
    generic_name: "氨溴索口服溶液",
    trade_name: "沐舒坦",
    spec: "100ml",
    dosage_form: "口服溶液",
    insurance_type: "乙类",
  },
  {
    id: 9,
    generic_name: "复方甘草片",
    trade_name: "",
    spec: "100片",
    dosage_form: "片剂",
    insurance_type: "甲类",
  },
  {
    id: 10,
    generic_name: "维生素C片",
    trade_name: "",
    spec: "0.1g×100片",
    dosage_form: "片剂",
    insurance_type: "甲类",
  },
  {
    id: 11,
    generic_name: "硝苯地平控释片",
    trade_name: "拜新同",
    spec: "30mg×7片",
    dosage_form: "控释片",
    insurance_type: "甲类",
  },
  {
    id: 12,
    generic_name: "二甲双胍缓释片",
    trade_name: "格华止",
    spec: "0.5g×30片",
    dosage_form: "缓释片",
    insurance_type: "甲类",
  },
]);

const ICD10_SUGGESTIONS = Object.freeze([
  { code: "J06.9", name: "急性上呼吸道感染" },
  { code: "J18.9", name: "肺炎" },
  { code: "J45.9", name: "支气管哮喘" },
  { code: "K29.7", name: "慢性胃炎" },
  { code: "I10", name: "原发性高血压" },
  { code: "E11.9", name: "2型糖尿病" },
  { code: "N39.0", name: "泌尿道感染" },
  { code: "M54.5", name: "腰痛" },
  { code: "R51", name: "头痛" },
  { code: "A09.9", name: "感染性腹泻" },
]);

const registrations = ref([]);
const loadingPatients = ref(false);
const loadError = ref("");
const patientKeyword = ref("");
const selectedId = ref(null);

const form = reactive({
  icd10_code: "",
  diagnosis_name: "",
});
const selectedItems = ref([]);
const drugKeyword = ref("");
const submitting = ref(false);
const formError = ref("");
const successMessage = ref("");
const lastCreated = ref(null);

const drugMap = computed(
  () => new Map(DEMO_DRUGS.map((drug) => [drug.id, drug]))
);

const selectedRegistration = computed(
  () =>
    registrations.value.find(
      (registration) => registration.id === selectedId.value
    ) || null
);

const visibleRegistrations = computed(() => {
  const keyword = patientKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return registrations.value;
  }
  return registrations.value.filter((registration) => {
    return [
      registration.patient_name,
      registration.phone,
      registration.department,
      String(registration.id),
    ].some((value) => String(value || "").toLowerCase().includes(keyword));
  });
});

const filteredDrugs = computed(() => {
  const keyword = drugKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return DEMO_DRUGS;
  }
  return DEMO_DRUGS.filter((drug) => {
    return [drug.generic_name, drug.trade_name, drug.spec].some((value) =>
      String(value || "").toLowerCase().includes(keyword)
    );
  });
});

const selectedDrugIds = computed(
  () => new Set(selectedItems.value.map((item) => item.drug_id))
);

const selectedDrugDetails = computed(() =>
  selectedItems.value.map((item) => ({
    ...item,
    drug: drugMap.value.get(item.drug_id) || null,
  }))
);

function friendlyError(error) {
  const message = error?.message || "操作失败，请稍后重试";
  if (error?.status === 409) {
    return "该患者已创建过处方，请刷新待接诊列表";
  }
  if (error?.status === 403) {
    return "无权为该患者开具处方，只能处理本人名下待接诊患者";
  }
  if (error?.status === 404) {
    return "挂号记录不存在，请刷新待接诊列表";
  }
  if (error?.status === 422) {
    return "处方参数校验失败，请检查 ICD-10 编码、诊断名称或药品数量";
  }
  if (error?.status === 400 && /pending|registered/i.test(message)) {
    return "该挂号已不处于待接诊状态，请刷新列表";
  }
  return message;
}

async function loadPending() {
  loadingPatients.value = true;
  loadError.value = "";

  try {
    const data = await request("/api/doctor/pending-registrations");
    registrations.value = Array.isArray(data) ? data : [];
    if (
      selectedId.value &&
      !registrations.value.some(
        (registration) => registration.id === selectedId.value
      )
    ) {
      selectedId.value = null;
    }
  } catch (error) {
    registrations.value = [];
    selectedId.value = null;
    loadError.value = friendlyError(error);
  } finally {
    loadingPatients.value = false;
  }
}

function selectRegistration(registration) {
  if (selectedId.value !== registration.id) {
    resetForm();
    lastCreated.value = null;
  }
  selectedId.value = registration.id;
}

function resetForm() {
  form.icd10_code = "";
  form.diagnosis_name = "";
  selectedItems.value = [];
  drugKeyword.value = "";
  formError.value = "";
  successMessage.value = "";
}

function addDrug(drug) {
  if (!selectedRegistration.value || selectedDrugIds.value.has(drug.id)) {
    return;
  }
  selectedItems.value.push({ drug_id: drug.id, qty: 1 });
}

function removeDrug(drugId) {
  selectedItems.value = selectedItems.value.filter(
    (item) => item.drug_id !== drugId
  );
}

function stepQty(item, delta) {
  const current = Number(item.qty) || 1;
  const next = Math.min(100000, Math.max(1, current + delta));
  item.qty = next;
}

function onIcdChange() {
  const code = form.icd10_code.trim().toUpperCase();
  const matched = ICD10_SUGGESTIONS.find((item) => item.code === code);
  if (matched) {
    form.icd10_code = matched.code;
    if (!form.diagnosis_name.trim()) {
      form.diagnosis_name = matched.name;
    }
  }
}

function drugName(drugId) {
  return drugMap.value.get(drugId)?.generic_name || `药品 #${drugId}`;
}

function validateForm() {
  if (!selectedRegistration.value) {
    return "请先选择待接诊患者";
  }

  const icd10 = form.icd10_code.trim().toUpperCase();
  if (!ICD10_PATTERN.test(icd10)) {
    return "ICD-10 编码格式不正确，例如 J06.9";
  }

  const diagnosis = form.diagnosis_name.trim();
  if (!diagnosis) {
    return "请填写诊断名称";
  }

  if (selectedItems.value.length === 0) {
    return "请至少选择一种药品";
  }

  const drugIds = selectedItems.value.map((item) => item.drug_id);
  if (new Set(drugIds).size !== drugIds.length) {
    return "处方中存在重复药品，请移除重复项";
  }

  for (const item of selectedItems.value) {
    const qty = Number(item.qty);
    if (!Number.isInteger(qty) || qty < 1 || qty > 100000) {
      return `药品「${drugName(item.drug_id)}」的数量必须是 1 到 100000 的整数`;
    }
  }

  return "";
}

async function submitPrescription() {
  if (submitting.value) {
    return;
  }

  formError.value = "";
  successMessage.value = "";

  const validationError = validateForm();
  if (validationError) {
    formError.value = validationError;
    return;
  }

  const registration = selectedRegistration.value;
  const icd10 = form.icd10_code.trim().toUpperCase();
  const diagnosis = form.diagnosis_name.trim();
  const items = selectedItems.value.map((item) => ({
    drug_id: item.drug_id,
    qty: Number(item.qty),
  }));

  submitting.value = true;

  try {
    const created = await request("/api/prescriptions", {
      method: "POST",
      body: {
        registration_id: registration.id,
        icd10_code: icd10,
        diagnosis_name: diagnosis,
        items,
      },
    });

    lastCreated.value = created;
    selectedId.value = null;
    form.icd10_code = "";
    form.diagnosis_name = "";
    selectedItems.value = [];
    drugKeyword.value = "";
    formError.value = "";
    successMessage.value = `处方 #${created.id} 已保存，处方状态为待收费。`;

    await loadPending();
  } catch (error) {
    formError.value = friendlyError(error);
    if ([400, 403, 404, 409].includes(error?.status)) {
      await loadPending();
    }
  } finally {
    submitting.value = false;
  }
}

onMounted(loadPending);
</script>

<template>
  <section class="doctor-page">
    <div class="workstation-grid">
      <article class="card patient-panel">
        <div class="card-head">
          <div>
            <h2 class="card-title">待接诊患者</h2>
            <p class="card-subtitle">
              仅展示当前登录医生名下、尚未开具处方的挂号记录。
            </p>
          </div>
          <span class="badge badge-blue">{{ registrations.length }} 人</span>
        </div>

        <div class="toolbar">
          <input
            v-model="patientKeyword"
            class="input"
            type="search"
            placeholder="搜索姓名、手机号、科室或挂号号"
          />
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="loadingPatients"
            @click="loadPending"
          >
            刷新
          </button>
        </div>

        <p v-if="loadError" class="alert alert-error list-alert" role="alert">
          {{ loadError }}
        </p>

        <div v-else-if="loadingPatients" class="empty-state">
          <span class="spinner" aria-hidden="true"></span>
          正在加载待接诊患者...
        </div>

        <div v-else-if="visibleRegistrations.length === 0" class="empty-state">
          暂无待接诊患者。<br />
          完成挂号后，患者会自动出现在这里。
        </div>

        <ul v-else class="patient-list">
          <li
            v-for="registration in visibleRegistrations"
            :key="registration.id"
          >
            <button
              type="button"
              class="patient-item"
              :class="{ selected: selectedId === registration.id }"
              @click="selectRegistration(registration)"
            >
              <span class="patient-avatar" aria-hidden="true">
                {{ (registration.patient_name || "患").charAt(0) }}
              </span>

              <span class="patient-main">
                <span class="patient-name">{{ registration.patient_name }}</span>
                <span class="patient-meta">
                  {{ registration.phone }} · {{ registration.department || "-" }}
                </span>
                <span class="patient-meta">
                  就诊日期 {{ formatDate(registration.schedule_date) }} ·
                  挂号 #{{ registration.id }}
                </span>
              </span>

              <span
                class="badge"
                :class="
                  selectedId === registration.id
                    ? 'badge-blue'
                    : 'badge-green'
                "
              >
                {{ selectedId === registration.id ? "已选择" : "待接诊" }}
              </span>
            </button>
          </li>
        </ul>
      </article>

      <article class="card prescription-panel">
        <div class="card-head">
          <div>
            <h2 class="card-title">开具处方</h2>
            <p class="card-subtitle">
              填写 ICD-10 编码与诊断，选择药品及数量后提交，主表与明细在同一事务中保存。
            </p>
          </div>
          <span
            v-if="selectedRegistration"
            class="badge badge-green"
          >
            已选择患者
          </span>
        </div>

        <div class="card-body form-body">
          <div v-if="selectedRegistration" class="patient-summary">
            <div>
              <p class="summary-label">当前患者</p>
              <p class="summary-title">
                {{ selectedRegistration.patient_name }}
                <span class="summary-phone">
                  {{ selectedRegistration.phone }}
                </span>
              </p>
              <p class="summary-meta">
                {{ selectedRegistration.department || "-" }} ·
                就诊日期 {{ formatDate(selectedRegistration.schedule_date) }} ·
                挂号 #{{ selectedRegistration.id }}
              </p>
            </div>
            <span class="badge badge-blue">待接诊</span>
          </div>
          <p v-else class="alert alert-info">
            请先从左侧待接诊列表选择患者，再填写诊断和处方药品。
          </p>

          <form novalidate @submit.prevent="submitPrescription">
            <fieldset
              class="form-section"
              :disabled="!selectedRegistration || submitting"
            >
              <div class="form-grid two">
                <label class="field">
                  <span class="field-label">ICD-10 疾病编码</span>
                  <input
                    v-model="form.icd10_code"
                    class="input"
                    type="text"
                    list="icd10-options"
                    maxlength="20"
                    placeholder="例如 J06.9"
                    @change="onIcdChange"
                  />
                  <datalist id="icd10-options">
                    <option
                      v-for="item in ICD10_SUGGESTIONS"
                      :key="item.code"
                      :value="item.code"
                    >
                      {{ item.name }}
                    </option>
                  </datalist>
                  <span class="field-note">
                    参考 ICD-10 编码规则，系统会统一转换为大写。
                  </span>
                </label>

                <label class="field">
                  <span class="field-label">诊断名称</span>
                  <input
                    v-model="form.diagnosis_name"
                    class="input"
                    type="text"
                    list="diagnosis-options"
                    maxlength="200"
                    placeholder="请输入诊断中文名称"
                  />
                  <datalist id="diagnosis-options">
                    <option
                      v-for="item in ICD10_SUGGESTIONS"
                      :key="`${item.code}-diagnosis`"
                      :value="item.name"
                    />
                  </datalist>
                  <span class="field-note">
                    选择常用编码后，诊断名称为空时会自动填充。
                  </span>
                </label>
              </div>
            </fieldset>

            <section class="drug-section">
              <div class="drug-section-head">
                <div>
                  <h3>处方药品</h3>
                  <p class="field-note">
                    当前为课程演示药品目录，后端处方接口按 drug_id 保存明细。
                  </p>
                </div>
                <span class="badge badge-gray">
                  已选 {{ selectedItems.length }} 项
                </span>
              </div>

              <input
                v-model="drugKeyword"
                class="input drug-search"
                type="search"
                placeholder="搜索通用名、商品名或规格"
              />

              <div class="drug-picker">
                <div class="drug-catalog">
                  <button
                    v-for="drug in filteredDrugs"
                    :key="drug.id"
                    type="button"
                    class="drug-option"
                    :disabled="
                      !selectedRegistration ||
                      submitting ||
                      selectedDrugIds.has(drug.id)
                    "
                    @click="addDrug(drug)"
                  >
                    <span class="drug-main">
                      <span class="drug-name">
                        {{ drug.generic_name }}
                        <small v-if="drug.trade_name">
                          （{{ drug.trade_name }}）
                        </small>
                      </span>
                      <span class="drug-meta">
                        {{ drug.spec }} · {{ drug.dosage_form }} ·
                        医保{{ drug.insurance_type }}
                      </span>
                    </span>
                    <span class="drug-action">
                      {{ selectedDrugIds.has(drug.id) ? "已添加" : "+ 添加" }}
                    </span>
                  </button>

                  <p v-if="filteredDrugs.length === 0" class="empty-state">
                    没有匹配的药品。
                  </p>
                </div>

                <div class="selected-drugs">
                  <p class="selected-title">已选药品</p>

                  <div
                    v-if="selectedDrugDetails.length === 0"
                    class="empty-state selected-empty"
                  >
                    尚未选择药品。
                  </div>

                  <div
                    v-for="item in selectedDrugDetails"
                    :key="item.drug_id"
                    class="selected-drug-row"
                  >
                    <div class="selected-drug-main">
                      <p class="selected-drug-name">
                        {{ item.drug?.generic_name || drugName(item.drug_id) }}
                      </p>
                      <p class="selected-drug-meta">
                        {{ item.drug?.spec || "-" }} ·
                        {{ item.drug?.dosage_form || "-" }} ·
                        医保{{ item.drug?.insurance_type || "-" }}
                      </p>
                    </div>

                    <div class="qty-control">
                      <button
                        type="button"
                        :disabled="submitting || Number(item.qty) <= 1"
                        @click="stepQty(item, -1)"
                      >
                        -
                      </button>
                      <input
                        v-model.number="item.qty"
                        type="number"
                        min="1"
                        max="100000"
                        step="1"
                        :disabled="submitting"
                      />
                      <button
                        type="button"
                        :disabled="submitting"
                        @click="stepQty(item, 1)"
                      >
                        +
                      </button>
                    </div>

                    <button
                      class="btn btn-sm btn-danger"
                      type="button"
                      :disabled="submitting"
                      @click="removeDrug(item.drug_id)"
                    >
                      移除
                    </button>
                  </div>
                </div>
              </div>
            </section>

            <p v-if="formError" class="alert alert-error" role="alert">
              {{ formError }}
            </p>
            <p v-if="successMessage" class="alert alert-success" role="status">
              {{ successMessage }}
            </p>

            <div class="form-actions">
              <button
                class="btn btn-primary"
                type="submit"
                :disabled="submitting || !selectedRegistration"
              >
                <span
                  v-if="submitting"
                  class="spinner"
                  aria-hidden="true"
                ></span>
                {{ submitting ? "保存中..." : "保存处方" }}
              </button>
              <button
                class="btn btn-secondary"
                type="button"
                :disabled="submitting || !selectedRegistration"
                @click="resetForm"
              >
                清空
              </button>
            </div>
          </form>

          <div v-if="lastCreated" class="created-summary">
            <div class="created-head">
              <div>
                <p class="summary-label">最近创建处方</p>
                <p class="summary-title">
                  处方 #{{ lastCreated.id }} · {{ lastCreated.icd10_code }} ·
                  {{ lastCreated.diagnosis_name }}
                </p>
                <p class="summary-meta">
                  患者 {{ lastCreated.patient_name || "-" }} ·
                  {{ lastCreated.department || "-" }} ·
                  创建时间 {{ formatDateTime(lastCreated.created_at) }}
                </p>
              </div>
              <span class="badge badge-amber">待收费</span>
            </div>

            <ul class="created-items">
              <li v-for="item in lastCreated.items" :key="item.id">
                <span>{{ drugName(item.drug_id) }}</span>
                <span class="mono">× {{ item.qty }}</span>
              </li>
            </ul>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.doctor-page {
  display: grid;
  gap: 20px;
}

.workstation-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.85fr) minmax(0, 1.45fr);
  align-items: start;
  gap: 20px;
}

.patient-panel,
.prescription-panel {
  min-width: 0;
}

.patient-list {
  max-height: 66vh;
  margin: 0;
  padding: 14px;
  display: grid;
  gap: 10px;
  overflow-y: auto;
  list-style: none;
}

.patient-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 11px;
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
    box-shadow 0.18s ease,
    transform 0.15s ease;
}

.patient-item:hover {
  border-color: #bfdbfe;
  background: #f8fbff;
}

.patient-item.selected {
  border-color: #60a5fa;
  background: #eff6ff;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.patient-avatar {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 15px;
  font-weight: 800;
}

.patient-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.patient-name {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}

.patient-meta {
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.45;
}

.list-alert {
  margin: 14px;
}

.form-body {
  display: grid;
  gap: 18px;
}

.patient-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
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

.form-section {
  margin: 0;
  padding: 0;
  border: none;
}

.field-note {
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.5;
}

.drug-section {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px dashed #dbe3ee;
}

.drug-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}

.drug-section-head h3 {
  margin: 0 0 4px;
  color: #0f172a;
  font-size: 14px;
}

.drug-section-head p {
  margin: 0;
}

.drug-search {
  margin-bottom: 12px;
}

.drug-picker {
  display: grid;
  gap: 14px;
}

.drug-catalog {
  max-height: 270px;
  padding: 8px;
  display: grid;
  gap: 7px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 13px;
  background: #f8fafc;
}

.drug-option {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: #fff;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease;
}

.drug-option:hover:not(:disabled) {
  border-color: #bfdbfe;
  background: #f8fbff;
}

.drug-option:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.drug-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.drug-name {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.drug-name small {
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
}

.drug-meta {
  color: #64748b;
  font-size: 11px;
  line-height: 1.45;
}

.drug-action {
  flex: 0 0 auto;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.selected-drugs {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 13px;
  background: #fff;
}

.selected-title {
  margin: 0 0 10px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.selected-empty {
  padding: 16px 8px;
}

.selected-drug-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid #edf1f7;
}

.selected-drug-row:first-of-type {
  border-top: none;
  padding-top: 0;
}

.selected-drug-main {
  min-width: 0;
}

.selected-drug-name {
  margin: 0;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.selected-drug-meta {
  margin: 3px 0 0;
  color: #64748b;
  font-size: 11px;
}

.qty-control {
  display: flex;
  align-items: center;
  gap: 4px;
}

.qty-control button {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-weight: 800;
  cursor: pointer;
}

.qty-control button:hover:not(:disabled) {
  background: #f1f5f9;
}

.qty-control button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.qty-control input {
  width: 58px;
  height: 28px;
  padding: 0 4px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  text-align: center;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.created-summary {
  padding: 15px 16px;
  border: 1px solid #bbf7d0;
  border-radius: 13px;
  background: #f0fdf4;
}

.created-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.created-head .summary-title {
  color: #166534;
}

.created-items {
  margin: 10px 0 0;
  padding: 10px 0 0;
  border-top: 1px dashed #bbf7d0;
  list-style: none;
  display: grid;
  gap: 5px;
  color: #166534;
  font-size: 12px;
}

.created-items li {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

@media (max-width: 960px) {
  .workstation-grid {
    grid-template-columns: 1fr;
  }

  .patient-list {
    max-height: 320px;
  }
}

@media (max-width: 640px) {
  .selected-drug-row {
    grid-template-columns: 1fr;
  }

  .qty-control {
    justify-content: flex-start;
  }

  .form-actions {
    flex-direction: column;
  }

  .created-head {
    flex-direction: column;
  }
}
</style>

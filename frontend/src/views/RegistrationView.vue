<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { request } from "../api/client";
import {
  DEPARTMENTS,
  REGISTRATION_STATUS_LABELS,
  formatDate,
  formatDateTime,
} from "../constants";

function localToday() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

const query = reactive({
  date: localToday(),
  department: "内科",
});

const schedules = ref([]);
const loadingSchedules = ref(false);
const scheduleError = ref("");
const selectedDoctor = ref("all");
const selectedScheduleId = ref(null);

const form = reactive({
  patient_name: "",
  phone: "",
});
const submitting = ref(false);
const formError = ref("");
const successMessage = ref("");

const records = ref([]);
const recordsLoading = ref(false);
const recordsError = ref("");
const recordDate = ref("");
const recordKeyword = ref("");

const doctorOptions = computed(() => {
  const map = new Map();
  schedules.value.forEach((schedule) => {
    map.set(
      String(schedule.doctor_id),
      schedule.doctor_username || `医生 #${schedule.doctor_id}`
    );
  });
  return Array.from(map, ([id, label]) => ({ id, label })).sort((a, b) =>
    a.label.localeCompare(b.label, "zh-CN")
  );
});

const visibleSchedules = computed(() => {
  if (selectedDoctor.value === "all") {
    return schedules.value;
  }
  return schedules.value.filter(
    (schedule) => String(schedule.doctor_id) === selectedDoctor.value
  );
});

const selectedSchedule = computed(
  () =>
    schedules.value.find(
      (schedule) => schedule.id === selectedScheduleId.value
    ) || null
);

const filteredRecords = computed(() => {
  const keyword = recordKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return records.value;
  }
  return records.value.filter((record) => {
    const name = String(record.patient_name || "").toLowerCase();
    const phone = String(record.phone || "");
    return name.includes(keyword) || phone.includes(keyword);
  });
});

function friendlyError(error) {
  const message = error?.message || "操作失败，请稍后重试";
  if (error?.status === 400 && /quota/i.test(message)) {
    return "该排班号源已用完，请重新查询并选择其他医生";
  }
  if (error?.status === 404) {
    return "排班不存在或已停诊，请刷新号源后重试";
  }
  if (error?.status === 409) {
    return "操作冲突，请刷新页面后重试";
  }
  if (error?.status === 401) {
    return "登录状态已过期，请重新登录";
  }
  return message;
}

function quotaClass(schedule) {
  if (schedule.remaining_quota <= 0) {
    return "badge badge-red";
  }
  if (schedule.remaining_quota <= 3) {
    return "badge badge-amber";
  }
  return "badge badge-green";
}

function statusLabel(status) {
  return REGISTRATION_STATUS_LABELS[status] || status || "-";
}

function statusClass(status) {
  return status === "registered" ? "badge badge-green" : "badge badge-gray";
}

async function loadAvailable() {
  const department = query.department.trim();
  if (!query.date) {
    scheduleError.value = "请选择就诊日期";
    return;
  }

  loadingSchedules.value = true;
  scheduleError.value = "";

  try {
    const data = await request("/api/schedules/available", {
      params: { date: query.date, department },
    });
    schedules.value = Array.isArray(data) ? data : [];

    if (
      !schedules.value.some(
        (schedule) => String(schedule.doctor_id) === selectedDoctor.value
      )
    ) {
      selectedDoctor.value = "all";
    }
    if (
      !schedules.value.some(
        (schedule) => schedule.id === selectedScheduleId.value
      )
    ) {
      selectedScheduleId.value = null;
    }
  } catch (error) {
    schedules.value = [];
    selectedScheduleId.value = null;
    scheduleError.value = friendlyError(error);
  } finally {
    loadingSchedules.value = false;
  }
}

function selectSchedule(schedule) {
  if (schedule.remaining_quota <= 0) {
    return;
  }
  selectedScheduleId.value = schedule.id;
  formError.value = "";
  successMessage.value = "";
}

function resetForm() {
  form.patient_name = "";
  form.phone = "";
  formError.value = "";
}

async function submitRegistration() {
  if (submitting.value) {
    return;
  }

  formError.value = "";
  successMessage.value = "";

  if (!selectedSchedule.value) {
    formError.value = "请先选择要挂号的排班";
    return;
  }

  const patientName = form.patient_name.trim();
  const phone = form.phone.trim();

  if (!patientName) {
    formError.value = "请输入患者姓名";
    return;
  }
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    formError.value = "请输入正确的 11 位手机号";
    return;
  }

  submitting.value = true;

  try {
    const created = await request("/api/registrations", {
      method: "POST",
      body: {
        patient_name: patientName,
        phone,
        schedule_id: selectedSchedule.value.id,
      },
    });

    successMessage.value = `挂号成功，挂号单号 #${created.id}`;
    resetForm();
    await Promise.all([loadAvailable(), loadRegistrations()]);
  } catch (error) {
    formError.value = friendlyError(error);
    if (error?.status === 400 || error?.status === 404) {
      await loadAvailable();
    }
  } finally {
    submitting.value = false;
  }
}

async function loadRegistrations() {
  recordsLoading.value = true;
  recordsError.value = "";

  try {
    const data = await request("/api/registrations", {
      params: {
        date: recordDate.value,
        limit: 100,
      },
    });
    records.value = Array.isArray(data) ? data : [];
  } catch (error) {
    records.value = [];
    recordsError.value = friendlyError(error);
  } finally {
    recordsLoading.value = false;
  }
}

function resetRecordFilter() {
  recordDate.value = "";
  recordKeyword.value = "";
  loadRegistrations();
}

onMounted(() => {
  loadAvailable();
  loadRegistrations();
});
</script>

<template>
  <section class="registration-page">
    <article class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">查询可用号源</h2>
          <p class="card-subtitle">
            按日期、科室查询可用排班，再按医生筛选；号源为 0 的排班不会展示。
          </p>
        </div>
        <span class="badge badge-blue">实时号源</span>
      </div>

      <div class="toolbar">
        <div class="toolbar-group">
          <label class="field query-field">
            <span class="field-label">就诊日期</span>
            <input v-model="query.date" class="input" type="date" />
          </label>

          <label class="field query-field">
            <span class="field-label">科室</span>
            <select v-model="query.department" class="select">
              <option value="">全部科室</option>
              <option
                v-for="item in DEPARTMENTS"
                :key="item"
                :value="item"
              >
                {{ item }}
              </option>
            </select>
          </label>

          <label class="field query-field">
            <span class="field-label">医生</span>
            <select v-model="selectedDoctor" class="select">
              <option value="all">全部医生</option>
              <option
                v-for="doctor in doctorOptions"
                :key="doctor.id"
                :value="doctor.id"
              >
                {{ doctor.label }}
              </option>
            </select>
          </label>

          <button
            class="btn btn-primary"
            type="button"
            :disabled="loadingSchedules"
            @click="loadAvailable"
          >
            <span
              v-if="loadingSchedules"
              class="spinner"
              aria-hidden="true"
            ></span>
            {{ loadingSchedules ? "查询中..." : "查询号源" }}
          </button>
        </div>

        <button
          class="btn btn-secondary"
          type="button"
          :disabled="recordsLoading"
          @click="loadRegistrations"
        >
          刷新挂号记录
        </button>
      </div>

      <div v-if="scheduleError" class="card-body">
        <p class="alert alert-error" role="alert">{{ scheduleError }}</p>
      </div>

      <div v-else-if="loadingSchedules" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        正在查询可用号源...
      </div>

      <div v-else-if="visibleSchedules.length === 0" class="empty-state">
        当前日期和科室暂无可挂号源。<br />
        可尝试切换日期、科室或医生筛选条件。
      </div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>医生</th>
              <th>科室</th>
              <th>就诊日期</th>
              <th>号源</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="schedule in visibleSchedules"
              :key="schedule.id"
              :class="{ 'selected-row': selectedScheduleId === schedule.id }"
            >
              <td>
                <strong>
                  {{
                    schedule.doctor_username || `医生 #${schedule.doctor_id}`
                  }}
                </strong>
              </td>
              <td>{{ schedule.department }}</td>
              <td>{{ formatDate(schedule.schedule_date) }}</td>
              <td>
                <span :class="quotaClass(schedule)">
                  剩余 {{ schedule.remaining_quota }} / 共
                  {{ schedule.max_quota }}
                </span>
              </td>
              <td>
                <button
                  class="btn btn-sm"
                  :class="
                    selectedScheduleId === schedule.id
                      ? 'btn-secondary'
                      : 'btn-ghost'
                  "
                  type="button"
                  @click="selectSchedule(schedule)"
                >
                  {{ selectedScheduleId === schedule.id ? "已选择" : "选择" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">患者挂号</h2>
          <p class="card-subtitle">
            录入患者姓名和手机号，提交后系统在同一事务内扣减号源并生成挂号记录。
          </p>
        </div>
      </div>

      <div class="card-body form-body">
        <div v-if="selectedSchedule" class="selected-summary">
          <div>
            <p class="summary-label">已选择排班</p>
            <p class="summary-title">
              {{ selectedSchedule.department }} ·
              {{
                selectedSchedule.doctor_username ||
                `医生 #${selectedSchedule.doctor_id}`
              }}
            </p>
            <p class="summary-meta">
              就诊日期 {{ formatDate(selectedSchedule.schedule_date) }} ·
              剩余 {{ selectedSchedule.remaining_quota }} 个号源
            </p>
          </div>
          <span class="badge badge-blue">
            {{ selectedSchedule.remaining_quota }} / {{
              selectedSchedule.max_quota
            }}
          </span>
        </div>
        <p v-else class="alert alert-info">
          请先在上方号源列表中选择一个排班，再录入患者信息。
        </p>

        <form class="form-grid" novalidate @submit.prevent="submitRegistration">
          <div class="form-grid two">
            <label class="field">
              <span class="field-label">患者姓名</span>
              <input
                v-model="form.patient_name"
                class="input"
                type="text"
                maxlength="50"
                placeholder="请输入患者姓名"
              />
            </label>

            <label class="field">
              <span class="field-label">手机号</span>
              <input
                v-model="form.phone"
                class="input"
                type="tel"
                maxlength="11"
                placeholder="请输入 11 位手机号"
              />
            </label>
          </div>

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
              :disabled="submitting || !selectedSchedule"
            >
              <span v-if="submitting" class="spinner" aria-hidden="true"></span>
              {{ submitting ? "提交中..." : "确认挂号" }}
            </button>
            <button
              class="btn btn-secondary"
              type="button"
              :disabled="submitting"
              @click="resetForm"
            >
              清空
            </button>
          </div>
        </form>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">挂号记录</h2>
          <p class="card-subtitle">
            展示最近 100 条挂号记录，可按排班日期筛选，或按患者姓名、手机号快速查找。
          </p>
        </div>
        <span class="badge badge-gray">共 {{ filteredRecords.length }} 条</span>
      </div>

      <div class="toolbar">
        <div class="toolbar-group">
          <label class="field records-field">
            <span class="field-label">排班日期</span>
            <input v-model="recordDate" class="input" type="date" />
          </label>
          <label class="field records-field">
            <span class="field-label">姓名 / 手机号</span>
            <input
              v-model="recordKeyword"
              class="input"
              type="search"
              placeholder="本地筛选"
            />
          </label>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="recordsLoading"
            @click="loadRegistrations"
          >
            筛选
          </button>
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="recordsLoading"
            @click="resetRecordFilter"
          >
            重置
          </button>
        </div>
      </div>

      <p
        v-if="recordsError"
        class="alert alert-error records-alert"
        role="alert"
      >
        {{ recordsError }}
      </p>

      <div v-else-if="recordsLoading" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        正在加载挂号记录...
      </div>

      <div v-else-if="filteredRecords.length === 0" class="empty-state">
        暂无挂号记录。
      </div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>单号</th>
              <th>患者</th>
              <th>手机号</th>
              <th>科室</th>
              <th>医生</th>
              <th>排班日期</th>
              <th>状态</th>
              <th>挂号时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in filteredRecords" :key="record.id">
              <td class="mono">#{{ record.id }}</td>
              <td>{{ record.patient_name }}</td>
              <td class="mono">{{ record.phone }}</td>
              <td>{{ record.department || "-" }}</td>
              <td>{{ record.doctor_username || "-" }}</td>
              <td>{{ formatDate(record.schedule_date) }}</td>
              <td>
                <span :class="statusClass(record.status)">
                  {{ statusLabel(record.status) }}
                </span>
              </td>
              <td>{{ formatDateTime(record.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<style scoped>
.registration-page {
  display: grid;
  gap: 20px;
}

.query-field {
  width: 150px;
}

.query-field:nth-child(2) {
  width: 190px;
}

.selected-row {
  background: #eff6ff !important;
}

.form-body {
  display: grid;
  gap: 18px;
}

.selected-summary {
  display: flex;
  align-items: center;
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

.summary-meta {
  margin: 4px 0 0;
  color: #475569;
  font-size: 12px;
}

.form-actions {
  display: flex;
  gap: 10px;
}

.records-field {
  width: 170px;
}

.records-alert {
  margin: 18px 22px;
}

@media (max-width: 640px) {
  .query-field,
  .query-field:nth-child(2),
  .records-field {
    width: 100%;
  }

  .selected-summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .form-actions {
    flex-direction: column;
  }
}
</style>

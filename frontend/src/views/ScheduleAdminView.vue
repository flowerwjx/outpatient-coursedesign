<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { request } from "../api/client";
import { DEPARTMENTS, formatDate, formatDateTime } from "../constants";

function localToday() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

const schedules = ref([]);
const doctors = ref([]);
const loading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const filters = reactive({
  date: "",
  department: "",
});

const showForm = ref(false);
const editingId = ref(null);
const currentUsed = ref(0);
const saving = ref(false);
const formError = ref("");
const deletingId = ref(null);

const form = reactive({
  department: "内科",
  doctor_id: "",
  schedule_date: localToday(),
  max_quota: 20,
});

const hasDoctors = computed(() => doctors.value.length > 0);

const minQuota = computed(() =>
  editingId.value ? Math.max(currentUsed.value, 1) : 1
);

const formTitle = computed(() =>
  editingId.value ? "编辑排班" : "新增排班"
);

const doctorMap = computed(() => {
  const map = new Map();
  doctors.value.forEach((doctor) => map.set(doctor.id, doctor.username));
  return map;
});

function friendlyError(error) {
  const message = error?.message || "操作失败，请稍后重试";
  if (error?.status === 403) {
    return "仅系统管理员可以维护排班";
  }
  if (error?.status === 404) {
    return "排班不存在，可能已被其他操作删除";
  }
  if (error?.status === 409) {
    return "该医生当天在该科室已有排班，请勿重复新增";
  }
  if (error?.status === 400 && /doctor/i.test(message)) {
    return "请选择有效的医生账号";
  }
  if (error?.status === 400 && /max_quota|quota/i.test(message)) {
    return "最大号源不能小于已使用号源";
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

function usedPercent(schedule) {
  if (!schedule.max_quota) {
    return 0;
  }
  return Math.min(
    100,
    Math.round((schedule.used_quota / schedule.max_quota) * 100)
  );
}

async function loadDoctors() {
  try {
    const data = await request("/api/doctors");
    doctors.value = Array.isArray(data) ? data : [];
    if (!form.doctor_id && doctors.value.length > 0) {
      form.doctor_id = String(doctors.value[0].id);
    }
  } catch (error) {
    errorMessage.value = friendlyError(error);
  }
}

async function loadSchedules() {
  loading.value = true;
  errorMessage.value = "";

  try {
    const data = await request("/api/schedules", {
      params: {
        date: filters.date,
        department: filters.department.trim(),
      },
    });
    schedules.value = Array.isArray(data) ? data : [];
  } catch (error) {
    schedules.value = [];
    errorMessage.value = friendlyError(error);
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.date = "";
  filters.department = "";
  loadSchedules();
}

function openCreate() {
  editingId.value = null;
  currentUsed.value = 0;
  formError.value = "";
  successMessage.value = "";
  form.department = filters.department.trim() || "内科";
  form.doctor_id = doctors.value[0] ? String(doctors.value[0].id) : "";
  form.schedule_date = filters.date || localToday();
  form.max_quota = 20;
  showForm.value = true;
}

function openEdit(schedule) {
  editingId.value = schedule.id;
  currentUsed.value = schedule.used_quota;
  formError.value = "";
  successMessage.value = "";
  form.department = schedule.department;
  form.doctor_id = String(schedule.doctor_id);
  form.schedule_date = formatDate(schedule.schedule_date);
  form.max_quota = schedule.max_quota;
  showForm.value = true;
}

function closeForm() {
  showForm.value = false;
  editingId.value = null;
  currentUsed.value = 0;
  formError.value = "";
}

async function submitForm() {
  if (saving.value) {
    return;
  }

  formError.value = "";
  successMessage.value = "";

  const department = form.department.trim();
  const doctorId = Number(form.doctor_id);
  const maxQuota = Number(form.max_quota);

  if (!department) {
    formError.value = "请输入科室";
    return;
  }
  if (!Number.isInteger(doctorId) || doctorId <= 0) {
    formError.value = "请选择医生";
    return;
  }
  if (!form.schedule_date) {
    formError.value = "请选择排班日期";
    return;
  }
  if (!Number.isInteger(maxQuota) || maxQuota < 1) {
    formError.value = "最大号源必须是大于 0 的整数";
    return;
  }
  if (editingId.value && maxQuota < currentUsed.value) {
    formError.value = `最大号源不能小于已使用号源（${currentUsed.value}）`;
    return;
  }

  saving.value = true;

  try {
    const payload = {
      department,
      doctor_id: doctorId,
      schedule_date: form.schedule_date,
      max_quota: maxQuota,
    };
    if (editingId.value) {
      await request(`/api/schedules/${editingId.value}`, {
        method: "PUT",
        body: payload,
      });
      successMessage.value = "排班已更新";
    } else {
      await request("/api/schedules", { method: "POST", body: payload });
      successMessage.value = "排班已新增";
    }
    closeForm();
    await loadSchedules();
  } catch (error) {
    formError.value = friendlyError(error);
  } finally {
    saving.value = false;
  }
}

async function removeSchedule(schedule) {
  if (deletingId.value) {
    return;
  }

  const doctorName =
    schedule.doctor_username ||
    doctorMap.value.get(schedule.doctor_id) ||
    `医生 #${schedule.doctor_id}`;
  const confirmed = window.confirm(
    `确认删除 ${formatDate(schedule.schedule_date)} ${schedule.department} ${doctorName} 的排班吗？删除后不可恢复。`
  );
  if (!confirmed) {
    return;
  }

  deletingId.value = schedule.id;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    await request(`/api/schedules/${schedule.id}`, { method: "DELETE" });
    successMessage.value = "排班已删除";
    if (editingId.value === schedule.id) {
      closeForm();
    }
    await loadSchedules();
  } catch (error) {
    if (error?.status === 409) {
      errorMessage.value = "该排班已产生挂号记录，不能删除";
    } else {
      errorMessage.value = friendlyError(error);
    }
  } finally {
    deletingId.value = null;
  }
}

onMounted(async () => {
  await loadDoctors();
  await loadSchedules();
});
</script>

<template>
  <section class="schedule-page">
    <article class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">排班管理</h2>
          <p class="card-subtitle">
            系统管理员维护医生排班。新增排班时号源自动初始化，修改最大号源不会低于已使用号源。
          </p>
        </div>
        <button class="btn btn-primary" type="button" @click="openCreate">
          新增排班
        </button>
      </div>

      <div class="toolbar">
        <div class="toolbar-group">
          <label class="field filter-field">
            <span class="field-label">排班日期</span>
            <input v-model="filters.date" class="input" type="date" />
          </label>
          <label class="field filter-field">
            <span class="field-label">科室</span>
            <select v-model="filters.department" class="select">
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
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="loading"
            @click="loadSchedules"
          >
            查询
          </button>
          <button
            class="btn btn-ghost"
            type="button"
            :disabled="loading"
            @click="resetFilters"
          >
            重置
          </button>
        </div>
        <span class="badge badge-gray">共 {{ schedules.length }} 条排班</span>
      </div>

      <div v-if="errorMessage" class="card-body">
        <p class="alert alert-error" role="alert">{{ errorMessage }}</p>
      </div>
      <div v-if="successMessage" class="card-body">
        <p class="alert alert-success" role="status">{{ successMessage }}</p>
      </div>

      <div v-if="showForm" class="form-panel">
        <div class="form-panel-head">
          <div>
            <h3>{{ formTitle }}</h3>
            <p v-if="editingId" class="muted form-hint">
              当前排班已使用 {{ currentUsed }} 个号源，最大号源不能小于该值。
            </p>
          </div>
          <button class="btn btn-ghost btn-sm" type="button" @click="closeForm">
            取消
          </button>
        </div>

        <form class="form-grid" novalidate @submit.prevent="submitForm">
          <div class="form-grid two">
            <label class="field">
              <span class="field-label">科室</span>
              <select v-model="form.department" class="select">
                <option value="" disabled>请选择科室</option>
                <option
                  v-for="item in DEPARTMENTS"
                  :key="item"
                  :value="item"
                >
                  {{ item }}
                </option>
              </select>
            </label>

            <label class="field">
              <span class="field-label">医生</span>
              <select
                v-model="form.doctor_id"
                class="select"
                :disabled="!hasDoctors"
              >
                <option value="" disabled>请选择医生</option>
                <option
                  v-for="doctor in doctors"
                  :key="doctor.id"
                  :value="String(doctor.id)"
                >
                  {{ doctor.username }}（ID {{ doctor.id }}）
                </option>
              </select>
              <span v-if="!hasDoctors" class="field-note">
                暂无可选医生账号，请先初始化医生用户。
              </span>
            </label>

            <label class="field">
              <span class="field-label">排班日期</span>
              <input v-model="form.schedule_date" class="input" type="date" />
            </label>

            <label class="field">
              <span class="field-label">最大号源</span>
              <input
                v-model.number="form.max_quota"
                class="input"
                type="number"
                :min="minQuota"
                step="1"
              />
              <span class="field-note">
                创建后剩余号源等于最大号源；修改时按已使用数量重新计算剩余号源。
              </span>
            </label>
          </div>

          <p v-if="formError" class="alert alert-error" role="alert">
            {{ formError }}
          </p>

          <div class="form-actions">
            <button
              class="btn btn-primary"
              type="submit"
              :disabled="saving || !hasDoctors"
            >
              <span v-if="saving" class="spinner" aria-hidden="true"></span>
              {{ saving ? "保存中..." : editingId ? "保存修改" : "新增排班" }}
            </button>
            <button
              class="btn btn-secondary"
              type="button"
              :disabled="saving"
              @click="closeForm"
            >
              取消
            </button>
          </div>
        </form>
      </div>

      <div v-if="loading" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        正在加载排班...
      </div>

      <div v-else-if="schedules.length === 0" class="empty-state">
        暂无排班数据。点击右上角“新增排班”创建第一条排班。
      </div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>就诊日期</th>
              <th>科室</th>
              <th>医生</th>
              <th>号源使用</th>
              <th>最大号源</th>
              <th>剩余号源</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="schedule in schedules" :key="schedule.id">
              <td>{{ formatDate(schedule.schedule_date) }}</td>
              <td>{{ schedule.department }}</td>
              <td>
                <strong>
                  {{
                    schedule.doctor_username ||
                    doctorMap.get(schedule.doctor_id) ||
                    `医生 #${schedule.doctor_id}`
                  }}
                </strong>
              </td>
              <td>
                <div class="quota-cell">
                  <span class="muted">
                    {{ schedule.used_quota }} / {{ schedule.max_quota }}
                  </span>
                  <span class="quota-track">
                    <span
                      class="quota-fill"
                      :style="{ width: `${usedPercent(schedule)}%` }"
                    ></span>
                  </span>
                </div>
              </td>
              <td>{{ schedule.max_quota }}</td>
              <td>
                <span :class="quotaClass(schedule)">
                  {{ schedule.remaining_quota }}
                </span>
              </td>
              <td>{{ formatDateTime(schedule.updated_at) }}</td>
              <td>
                <div class="row-actions">
                  <button
                    class="btn btn-sm btn-secondary"
                    type="button"
                    @click="openEdit(schedule)"
                  >
                    编辑
                  </button>
                  <button
                    class="btn btn-sm btn-danger"
                    type="button"
                    :disabled="deletingId === schedule.id"
                    @click="removeSchedule(schedule)"
                  >
                    {{ deletingId === schedule.id ? "删除中..." : "删除" }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<style scoped>
.schedule-page {
  display: grid;
  gap: 20px;
}

.filter-field {
  width: 170px;
}

.form-panel {
  margin: 18px 22px 0;
  padding: 18px;
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  background: #f8fbff;
}

.form-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.form-panel-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
}

.form-hint {
  margin: 5px 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.field-note {
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.5;
}

.form-actions {
  display: flex;
  gap: 10px;
}

.quota-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 110px;
}

.quota-track {
  width: 64px;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.quota-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #0ea5e9);
}

.row-actions {
  display: flex;
  gap: 6px;
}

@media (max-width: 640px) {
  .filter-field {
    width: 100%;
  }

  .form-panel {
    margin-left: 14px;
    margin-right: 14px;
  }

  .form-actions {
    flex-direction: column;
  }
}
</style>

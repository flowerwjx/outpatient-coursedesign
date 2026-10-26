<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { clearSession, getToken, request } from "./api/client";
import { ROLE_LABELS } from "./constants";
import AuditLogView from "./views/AuditLogView.vue";
import CashierChargeView from "./views/CashierChargeView.vue";
import DoctorWorkstationView from "./views/DoctorWorkstationView.vue";
import LoginView from "./views/LoginView.vue";
import PharmacyView from "./views/PharmacyView.vue";
import RegistrationView from "./views/RegistrationView.vue";
import ScheduleAdminView from "./views/ScheduleAdminView.vue";
import StatisticsView from "./views/StatisticsView.vue";

const booting = ref(true);
const user = ref(null);
const token = ref("");
const activeView = ref("registration");
const notice = ref("");

const isAdmin = computed(() => user.value?.role === "admin");
const isDoctor = computed(() => user.value?.role === "doctor");
const isCashier = computed(() => user.value?.role === "cashier");
const isPharmacist = computed(() => user.value?.role === "pharmacist");
const canRegister = computed(() => isAdmin.value || isCashier.value);
const roleLabel = computed(
  () => ROLE_LABELS[user.value?.role] || user.value?.role || ""
);

const navItems = computed(() => {
  const items = [];

  if (isAdmin.value) {
    items.push({ key: "schedules", label: "排班管理" });
    items.push({ key: "audit", label: "审计日志" });
    items.push({ key: "statistics", label: "统计报表" });
  }
  if (isDoctor.value) {
    items.push({ key: "workstation", label: "医生工作站" });
  }
  if (isCashier.value) {
    items.push({ key: "cashier", label: "收费工作台" });
  }
  if (isPharmacist.value) {
    items.push({ key: "pharmacy", label: "药房工作台" });
  }

  if (canRegister.value) {
    items.push({ key: "registration", label: "门诊挂号" });
  }

  return items;
});

function defaultViewFor(currentUser) {
  if (currentUser?.role === "admin") {
    return "schedules";
  }
  if (currentUser?.role === "doctor") {
    return "workstation";
  }
  if (currentUser?.role === "cashier") {
    return "cashier";
  }
  if (currentUser?.role === "pharmacist") {
    return "pharmacy";
  }
  return "registration";
}

function handleAuthenticated({ token: accessToken, user: currentUser }) {
  token.value = accessToken;
  user.value = currentUser;
  notice.value = "";
  activeView.value = defaultViewFor(currentUser);
}

function handleUnauthorized(event) {
  if (!user.value) {
    return;
  }
  clearSession();
  user.value = null;
  token.value = "";
  notice.value = event?.detail?.message || "登录状态已过期，请重新登录";
}

function logout() {
  clearSession();
  user.value = null;
  token.value = "";
  notice.value = "";
  activeView.value = "registration";
}

onMounted(async () => {
  window.addEventListener("his:unauthorized", handleUnauthorized);

  const savedToken = getToken();
  if (!savedToken) {
    booting.value = false;
    return;
  }

  try {
    const currentUser = await request("/api/me", { token: savedToken });
    token.value = savedToken;
    user.value = currentUser;
    activeView.value = defaultViewFor(currentUser);
  } catch (error) {
    clearSession();
    notice.value =
      error.status === 401
        ? "登录状态已过期，请重新登录"
        : error.message || "无法恢复登录状态";
  } finally {
    booting.value = false;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("his:unauthorized", handleUnauthorized);
});
</script>

<template>
  <div v-if="booting" class="boot-screen">
    <span class="spinner" aria-hidden="true"></span>
    <p>正在恢复登录状态...</p>
  </div>

  <LoginView
    v-else-if="!user"
    :notice="notice"
    @authenticated="handleAuthenticated"
  />

  <div v-else class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <div class="brand-mark" aria-hidden="true">HIS</div>
          <div>
            <p class="brand-title">小型门诊医院信息管理系统</p>
            <p class="brand-subtitle">
              门诊挂号 · 医生工作站 · 收费 · 药房 · 排班管理
            </p>
          </div>
        </div>

        <nav class="main-nav" aria-label="业务导航">
          <button
            v-for="item in navItems"
            :key="item.key"
            type="button"
            class="nav-button"
            :class="{ active: activeView === item.key }"
            @click="activeView = item.key"
          >
            {{ item.label }}
          </button>
        </nav>

        <div class="account">
          <span class="account-name">{{ user.username }}</span>
          <span class="badge badge-green">{{ roleLabel }}</span>
          <button class="btn btn-secondary btn-sm" type="button" @click="logout">
            退出登录
          </button>
        </div>
      </div>
    </header>

    <main class="workspace">
      <RegistrationView
        v-if="activeView === 'registration' && canRegister"
      />
      <ScheduleAdminView v-else-if="activeView === 'schedules' && isAdmin" />
      <AuditLogView v-else-if="activeView === 'audit' && isAdmin" />
      <StatisticsView v-else-if="activeView === 'statistics' && isAdmin" />
      <DoctorWorkstationView
        v-else-if="activeView === 'workstation' && isDoctor"
      />
      <CashierChargeView v-else-if="activeView === 'cashier' && isCashier" />
      <PharmacyView
        v-else-if="activeView === 'pharmacy' && isPharmacist"
      />
      <section v-else class="card empty-state">
        当前账号没有访问该页面的权限。
      </section>
    </main>

    <footer class="app-footer">
      <span>课程设计演示系统</span>
      <span class="mono">JWT · RBAC · SQLite</span>
    </footer>
  </div>
</template>

<style scoped>
.boot-screen {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: #475569;
  background: #eef2f7;
}

.boot-screen p {
  margin: 0;
  font-size: 14px;
}

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 8% 0%, rgba(59, 130, 246, 0.12), transparent 38%),
    radial-gradient(circle at 96% 8%, rgba(16, 185, 129, 0.08), transparent 34%),
    #eef2f7;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid rgba(219, 227, 238, 0.9);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px);
}

.topbar-inner {
  width: min(100%, 1240px);
  min-height: 72px;
  margin: 0 auto;
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 22px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
}

.brand-mark {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 13px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.8px;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.28);
}

.brand-title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  white-space: nowrap;
}

.brand-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #64748b;
}

.main-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border-radius: 12px;
  background: #f1f5f9;
}

.nav-button {
  min-height: 34px;
  padding: 0 14px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.18s ease,
    color 0.18s ease,
    box-shadow 0.18s ease;
}

.nav-button:hover {
  color: #1d4ed8;
}

.nav-button.active {
  background: #fff;
  color: #1d4ed8;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
}

.account {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.account-name {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.workspace {
  width: min(100%, 1240px);
  margin: 0 auto;
  padding: 26px 24px 38px;
  display: grid;
  gap: 20px;
  flex: 1;
}

.app-footer {
  width: min(100%, 1240px);
  margin: 0 auto;
  padding: 0 24px 24px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #94a3b8;
  font-size: 12px;
}

@media (max-width: 860px) {
  .topbar-inner {
    flex-wrap: wrap;
    gap: 10px;
  }

  .main-nav {
    order: 3;
    width: 100%;
  }

  .nav-button {
    flex: 1;
  }

  .account {
    margin-left: auto;
  }
}

@media (max-width: 560px) {
  .topbar-inner,
  .workspace,
  .app-footer {
    padding-left: 14px;
    padding-right: 14px;
  }

  .brand-subtitle,
  .account-name {
    display: none;
  }

  .app-footer {
    flex-direction: column;
  }
}
</style>

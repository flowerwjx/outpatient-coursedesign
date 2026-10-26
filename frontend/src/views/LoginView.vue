<script setup>
import { computed, onMounted, ref } from "vue";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const STORAGE_KEYS = Object.freeze({
  token: "his_token",
  role: "his_role",
  username: "his_username",
});

const ROLE_META = Object.freeze({
  admin: {
    label: "系统管理员",
    route: "/admin",
    hint: "用户管理、药品档案、系统配置",
  },
  doctor: {
    label: "门诊医生",
    route: "/doctor",
    hint: "挂号、接诊、开具处方",
  },
  cashier: {
    label: "收费员",
    route: "/cashier",
    hint: "处方收费、收费单查询",
  },
  pharmacist: {
    label: "药房药师",
    route: "/pharmacist",
    hint: "处方发药、库存扣减",
  },
});

const username = ref("");
const password = ref("");
const loading = ref(false);
const restoring = ref(false);
const refreshing = ref(false);
const errorMessage = ref("");
const currentUser = ref(null);
const token = ref("");

const isLoggedIn = computed(
  () => Boolean(currentUser.value && token.value)
);

const roleInfo = computed(() => {
  const role = currentUser.value?.role;
  return role ? ROLE_META[role] || null : null;
});

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

function extractDetail(data, status) {
  if (typeof data === "string" && data.trim()) {
    return data;
  }
  if (data && typeof data === "object") {
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0];
      if (typeof first?.msg === "string") {
        return first.msg;
      }
    }
  }
  return `请求失败（HTTP ${status}）`;
}

async function request(path, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(apiUrl(path), {
      ...options,
      signal: controller.signal,
    });

    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }

    if (!response.ok) {
      const error = new Error(extractDetail(data, response.status));
      error.status = response.status;
      throw error;
    }

    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("请求超时，请确认后端服务已启动");
    }
    if (error instanceof TypeError) {
      throw new Error("无法连接后端服务，请检查后端地址或 Vite 代理配置");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function loadMe(accessToken) {
  const user = await request("/api/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!user?.role || !user?.username) {
    throw new Error("用户信息不完整，无法确定角色");
  }

  token.value = accessToken;
  currentUser.value = user;
  localStorage.setItem(STORAGE_KEYS.token, accessToken);
  localStorage.setItem(STORAGE_KEYS.role, user.role);
  localStorage.setItem(STORAGE_KEYS.username, user.username);
}

async function submitLogin() {
  if (loading.value) {
    return;
  }

  errorMessage.value = "";
  const normalizedUsername = username.value.trim();

  if (!normalizedUsername || !password.value) {
    errorMessage.value = "请输入用户名和密码";
    return;
  }

  loading.value = true;

  try {
    const result = await request("/api/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username: normalizedUsername,
        password: password.value,
      }),
    });

    if (!result?.access_token) {
      throw new Error("登录响应缺少 access_token");
    }

    await loadMe(result.access_token);
    password.value = "";
  } catch (error) {
    clearSession();
    errorMessage.value =
      error.status === 401 ? "用户名或密码错误" : error.message;
  } finally {
    loading.value = false;
  }
}

async function refreshMe() {
  if (!token.value || refreshing.value) {
    return;
  }

  errorMessage.value = "";
  refreshing.value = true;

  try {
    await loadMe(token.value);
  } catch (error) {
    if (error.status === 401) {
      clearSession();
      errorMessage.value = "登录状态已过期，请重新登录";
    } else {
      errorMessage.value = error.message;
    }
  } finally {
    refreshing.value = false;
  }
}

function clearSession() {
  currentUser.value = null;
  token.value = "";
  localStorage.removeItem(STORAGE_KEYS.token);
  localStorage.removeItem(STORAGE_KEYS.role);
  localStorage.removeItem(STORAGE_KEYS.username);
}

function logout() {
  clearSession();
  password.value = "";
  errorMessage.value = "";
}

onMounted(async () => {
  const savedToken = localStorage.getItem(STORAGE_KEYS.token);
  if (!savedToken) {
    return;
  }

  restoring.value = true;

  try {
    await loadMe(savedToken);
  } catch (error) {
    clearSession();
    errorMessage.value =
      error.status === 401
        ? "登录状态已过期，请重新登录"
        : error.message;
  } finally {
    restoring.value = false;
  }
});
</script>

<template>
  <main class="login-page">
    <section class="login-card" aria-labelledby="page-title">
      <header class="brand">
        <div class="brand-mark" aria-hidden="true">HIS</div>
        <div>
          <h1 id="page-title">小型门诊医院信息管理系统</h1>
          <p>用户登录 · 门诊业务入口</p>
        </div>
      </header>

      <div v-if="restoring" class="state-box" role="status">
        <span class="spinner" aria-hidden="true"></span>
        正在恢复登录状态...
      </div>

      <p v-if="errorMessage" class="alert" role="alert">
        {{ errorMessage }}
      </p>

      <template v-if="!restoring">
        <section v-if="isLoggedIn" class="session-panel">
          <p class="session-label">当前登录用户</p>

          <div class="identity">
            <span class="avatar" aria-hidden="true">
              {{ currentUser.username.charAt(0).toUpperCase() }}
            </span>
            <div>
              <p class="username">{{ currentUser.username }}</p>
              <span class="role-badge">
                {{ roleInfo?.label || currentUser.role }}
              </span>
            </div>
          </div>

          <div class="route-hint">
            <template v-if="roleInfo">
              <p>
                建议进入 <code>{{ roleInfo.route }}</code> 工作台
              </p>
              <p class="route-desc">{{ roleInfo.hint }}</p>
            </template>
            <p v-else>
              当前角色暂无路由提示，请联系管理员确认角色配置。
            </p>
          </div>

          <p class="session-note">
            JWT 已保存到浏览器 localStorage，可通过 /api/me 重新校验。
          </p>

          <div class="session-actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="refreshing"
              @click="refreshMe"
            >
              {{ refreshing ? "校验中..." : "刷新用户信息" }}
            </button>
            <button class="primary-button" type="button" @click="logout">
              退出登录
            </button>
          </div>
        </section>

        <form
          v-else
          class="login-form"
          novalidate
          @submit.prevent="submitLogin"
        >
          <label class="field">
            <span>用户名</span>
            <input
              v-model="username"
              type="text"
              name="username"
              autocomplete="username"
              placeholder="请输入用户名"
              :disabled="loading"
            />
          </label>

          <label class="field">
            <span>密码</span>
            <input
              v-model="password"
              type="password"
              name="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              :disabled="loading"
            />
          </label>

          <button class="primary-button" type="submit" :disabled="loading">
            <span v-if="loading" class="spinner" aria-hidden="true"></span>
            {{ loading ? "登录中..." : "登录" }}
          </button>
        </form>
      </template>

      <details class="test-accounts">
        <summary>课程测试账号</summary>
        <ul>
          <li><code>admin</code> / admin123 <span>系统管理员</span></li>
          <li><code>doctor</code> / doc123 <span>门诊医生</span></li>
          <li><code>cashier</code> / cash123 <span>收费员</span></li>
          <li><code>pharmacist</code> / pha123 <span>药房药师</span></li>
        </ul>
        <p>仅用于本地课程演示，请勿用于生产环境。</p>
      </details>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 16px;
  background:
    radial-gradient(circle at 12% 18%, rgba(59, 130, 246, 0.18), transparent 45%),
    radial-gradient(circle at 88% 82%, rgba(16, 185, 129, 0.14), transparent 45%),
    #eef2f7;
}

.login-card {
  width: min(100%, 460px);
  padding: 32px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.75);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(12px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 26px;
}

.brand-mark {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 1px;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.32);
}

.brand h1 {
  margin: 0;
  font-size: 20px;
  line-height: 1.35;
  color: #0f172a;
}

.brand p {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}

.login-form,
.session-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field span,
.session-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.field input {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #f8fafc;
  color: #0f172a;
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.field input::placeholder {
  color: #94a3b8;
}

.field input:focus {
  border-color: #2563eb;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.field input:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.primary-button,
.secondary-button {
  min-height: 44px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.primary-button {
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.25);
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 16px 28px rgba(37, 99, 235, 0.3);
}

.secondary-button {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
}

.secondary-button:hover:not(:disabled) {
  background: #f1f5f9;
}

.primary-button:disabled,
.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.alert {
  margin: 0 0 16px;
  padding: 11px 13px;
  border-radius: 11px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.5;
}

.state-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px;
  border-radius: 14px;
  background: #f1f5f9;
  color: #475569;
  font-size: 14px;
}

.identity {
  display: flex;
  align-items: center;
  gap: 14px;
}

.avatar {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 20px;
  font-weight: 700;
}

.username {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.role-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  background: #dcfce7;
  color: #15803d;
  font-size: 12px;
  font-weight: 600;
}

.route-hint {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1e3a8a;
  font-size: 14px;
  line-height: 1.6;
}

.route-hint p {
  margin: 0;
}

.route-hint code {
  padding: 2px 7px;
  border-radius: 6px;
  background: #dbeafe;
  color: #1d4ed8;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 13px;
}

.route-desc {
  margin-top: 6px !important;
  color: #475569;
  font-size: 13px;
}

.session-note {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.session-actions {
  display: flex;
  gap: 10px;
  margin-top: 2px;
}

.session-actions button {
  flex: 1;
}

.test-accounts {
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px dashed #cbd5e1;
  color: #64748b;
  font-size: 12px;
}

.test-accounts summary {
  cursor: pointer;
  font-weight: 600;
  color: #475569;
}

.test-accounts ul {
  margin: 12px 0 8px;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 7px;
}

.test-accounts li {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.test-accounts code {
  padding: 1px 6px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #334155;
  font-family: "Cascadia Code", Consolas, monospace;
}

.test-accounts li span {
  margin-left: auto;
  color: #94a3b8;
}

.test-accounts p {
  margin: 0;
  color: #94a3b8;
}

.spinner {
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.state-box .spinner {
  border-color: rgba(71, 85, 105, 0.25);
  border-top-color: #475569;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 480px) {
  .login-card {
    padding: 24px 20px;
    border-radius: 20px;
  }

  .brand h1 {
    font-size: 17px;
  }

  .session-actions {
    flex-direction: column;
  }
}
</style>

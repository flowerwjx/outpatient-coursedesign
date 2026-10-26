<script setup>
import { ref, watch } from "vue";

import { login } from "../api/client";

const props = defineProps({
  notice: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["authenticated"]);

const username = ref("");
const password = ref("");
const loading = ref(false);
const errorMessage = ref(props.notice);

watch(
  () => props.notice,
  (value) => {
    if (value) {
      errorMessage.value = value;
    }
  }
);

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
    const result = await login(normalizedUsername, password.value);
    password.value = "";
    emit("authenticated", result);
  } catch (error) {
    errorMessage.value =
      error.status === 401 ? "用户名或密码错误" : error.message;
  } finally {
    loading.value = false;
  }
}
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

      <p v-if="errorMessage" class="alert alert-error" role="alert">
        {{ errorMessage }}
      </p>

      <form class="login-form" novalidate @submit.prevent="submitLogin">
        <label class="field">
          <span class="field-label">用户名</span>
          <input
            v-model="username"
            class="input"
            type="text"
            name="username"
            autocomplete="username"
            placeholder="请输入用户名"
            :disabled="loading"
          />
        </label>

        <label class="field">
          <span class="field-label">密码</span>
          <input
            v-model="password"
            class="input"
            type="password"
            name="password"
            autocomplete="current-password"
            placeholder="请输入密码"
            :disabled="loading"
          />
        </label>

        <button
          class="btn btn-primary submit-button"
          type="submit"
          :disabled="loading"
        >
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
          {{ loading ? "登录中..." : "登录" }}
        </button>
      </form>

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

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.login-form .alert {
  margin-bottom: 16px;
}

.submit-button {
  width: 100%;
  min-height: 44px;
  margin-top: 2px;
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

@media (max-width: 480px) {
  .login-card {
    padding: 24px 20px;
    border-radius: 20px;
  }

  .brand h1 {
    font-size: 17px;
  }
}
</style>

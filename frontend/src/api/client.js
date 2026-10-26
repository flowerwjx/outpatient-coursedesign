const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const STORAGE_KEYS = Object.freeze({
  token: "his_token",
  user: "his_user",
  role: "his_role",
  username: "his_username",
});

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getToken() {
  return localStorage.getItem(STORAGE_KEYS.token) || "";
}

export function getStoredUser() {
  const raw = localStorage.getItem(STORAGE_KEYS.user);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setSession(token, user) {
  localStorage.setItem(STORAGE_KEYS.token, token);
  localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
  localStorage.setItem(STORAGE_KEYS.role, user.role);
  localStorage.setItem(STORAGE_KEYS.username, user.username);
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEYS.token);
  localStorage.removeItem(STORAGE_KEYS.user);
  localStorage.removeItem(STORAGE_KEYS.role);
  localStorage.removeItem(STORAGE_KEYS.username);
}

function buildUrl(path, params) {
  const url = `${API_BASE}${path}`;
  if (!params) {
    return url;
  }
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.append(key, value);
    }
  });
  const query = search.toString();
  return query ? `${url}?${query}` : url;
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
      return data.detail
        .map((item) => item?.msg)
        .filter(Boolean)
        .join("；");
    }
  }
  return `请求失败（HTTP ${status}）`;
}

export async function request(path, options = {}) {
  const {
    method = "GET",
    body,
    params,
    auth = true,
    token,
    headers = {},
    timeoutMs = 15000,
  } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const finalToken = token ?? (auth ? getToken() : "");
  const finalHeaders = { ...headers };

  if (finalToken) {
    finalHeaders.Authorization = `Bearer ${finalToken}`;
  }

  let payload = body;
  if (body !== undefined && !(body instanceof FormData)) {
    finalHeaders["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  try {
    const response = await fetch(buildUrl(path, params), {
      method,
      headers: finalHeaders,
      body: payload,
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
      if (response.status === 401 && auth && !token) {
        window.dispatchEvent(
          new CustomEvent("his:unauthorized", {
            detail: { message: "登录状态已过期，请重新登录" },
          })
        );
      }
      throw new ApiError(
        extractDetail(data, response.status),
        response.status,
        data
      );
    }

    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new ApiError("请求超时，请确认后端服务已启动", 0);
    }
    if (error instanceof TypeError) {
      throw new ApiError("无法连接后端服务，请检查后端地址或 Vite 代理配置", 0);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function login(username, password) {
  const data = await request("/api/auth/login", {
    method: "POST",
    auth: false,
    body: { username, password },
  });

  const accessToken = data?.access_token;
  if (!accessToken) {
    throw new ApiError("登录响应缺少 access_token", 0);
  }

  const user = await request("/api/me", { token: accessToken });
  if (!user?.role || !user?.username) {
    throw new ApiError("用户信息不完整，无法确定角色", 0);
  }

  setSession(accessToken, user);
  return { token: accessToken, user };
}

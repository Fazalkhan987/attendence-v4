import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1" });

const KEY = "sa_token";
export const tokenStore = {
  get: () => { try { return sessionStorage.getItem(KEY); } catch { return null; } },
  set: (t) => { try { sessionStorage.setItem(KEY, t); } catch { /* ignore */ } },
  clear: () => { try { sessionStorage.removeItem(KEY); } catch { /* ignore */ } },
};

api.interceptors.request.use((cfg) => {
  const t = tokenStore.get();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = err.config?.url || "";
    if (err.response?.status === 401 && !url.includes("/auth/login")) {
      tokenStore.clear();
      window.location.assign("/login");
    }
    return Promise.reject(err);
  }
);

export function errorMessage(err) {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`).join("; ");
  if (d.message) {
    const extra = (d.rejected || []).map((r) => r.reason).join(", ");
    return extra ? `${d.message} (${extra})` : d.message;
  }
  return JSON.stringify(d);
}

export const get = (url, params) => api.get(url, { params }).then((r) => r.data);
export const post = (url, body) => api.post(url, body).then((r) => r.data);
export const put = (url, body) => api.put(url, body).then((r) => r.data);
export const patch = (url, body) => api.patch(url, body).then((r) => r.data);
export const del = (url) => api.delete(url).then((r) => r.data);

export async function downloadFile(url, params, filename) {
  const r = await api.get(url, { params, responseType: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(r.data);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export async function fetchPhotoUrl(employeeId) {
  const r = await api.get(`/employees/${employeeId}/photo`, { responseType: "blob" });
  return URL.createObjectURL(r.data);
}

export default api;

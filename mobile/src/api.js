// ==========================================================================
// CrimTrack mobile — client API
// Miroir de frontend/api.js (mêmes routes FastAPI), adapté au stockage
// sécurisé mobile (expo-secure-store au lieu de localStorage).
// ==========================================================================
import * as SecureStore from "expo-secure-store";

// À adapter par environnement (dev/prod) — voir README pour la config via
// app.config.js/EAS une fois le scaffold transformé en vraie app.
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE || "http://localhost:8000";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export const TokenStore = {
  async getAccess() {
    return SecureStore.getItemAsync("ct_access");
  },
  async getRefresh() {
    return SecureStore.getItemAsync("ct_refresh");
  },
  async getUser() {
    const raw = await SecureStore.getItemAsync("ct_user");
    return raw ? JSON.parse(raw) : null;
  },
  async save(tokenResponse) {
    await SecureStore.setItemAsync("ct_access", tokenResponse.access_token);
    await SecureStore.setItemAsync("ct_refresh", tokenResponse.refresh_token);
    await SecureStore.setItemAsync(
      "ct_user",
      JSON.stringify({
        role: tokenResponse.role,
        nom: tokenResponse.nom,
        prenom: tokenResponse.prenom,
      })
    );
  },
  async clear() {
    await SecureStore.deleteItemAsync("ct_access");
    await SecureStore.deleteItemAsync("ct_refresh");
    await SecureStore.deleteItemAsync("ct_user");
  },
};

let refreshInFlight = null;

async function doRefresh() {
  const refresh = await TokenStore.getRefresh();
  if (!refresh) throw new ApiError("Session expirée", 401);
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    })
      .then(async (res) => {
        if (!res.ok) throw new ApiError("Session expirée", 401);
        const data = await res.json();
        await TokenStore.save(data);
        return data;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function request(path, opts = {}) {
  const { method = "GET", body, query, retry = true } = opts;
  const url = new URL(`${API_BASE}${path}`);
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  }
  const access = await TokenStore.getAccess();
  const headers = { "Content-Type": "application/json" };
  if (access) headers.Authorization = `Bearer ${access}`;

  const res = await fetch(url.toString(), {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && retry && access) {
    await doRefresh();
    return request(path, { ...opts, retry: false });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {}
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const Api = {
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/auth/me"),

  incidents: (query) => request("/incidents", { query }),
  incident: (id) => request(`/incidents/${id}`),
  hotspots: (query) => request("/incidents/analyse/hotspots", { query }),

  personnes: () => request("/personnes"),
  vehicules: () => request("/vehicules"),

  preuves: (incidentId) => request("/preuves", { query: { incident_id: incidentId } }),
  custodyChain: (preuveId) => request(`/preuves/${preuveId}/custody`),

  relationsGraphe: (query) => request("/relations/graphe", { query }),

  lecturesAnpr: (query) => request("/anpr/lectures", { query }),

  systemesNationaux: () => request("/integrations-nationales/systemes"),
};

export { ApiError };

// ==========================================================================
// CrimTrack — client API
// Petites fonctions fetch() autour de l'API FastAPI. Pas de framework HTTP :
// juste ce qu'il faut pour parler à /auth, /incidents, /personnes, etc.
// ==========================================================================

const API_BASE = window.CRIMTRACK_API_BASE;

const TokenStore = {
  get access() { return localStorage.getItem("ct_access") || null; },
  get refresh() { return localStorage.getItem("ct_refresh") || null; },
  get user() {
    const raw = localStorage.getItem("ct_user");
    return raw ? JSON.parse(raw) : null;
  },
  save(tokenResponse) {
    localStorage.setItem("ct_access", tokenResponse.access_token);
    localStorage.setItem("ct_refresh", tokenResponse.refresh_token);
    localStorage.setItem("ct_user", JSON.stringify({
      role: tokenResponse.role,
      nom: tokenResponse.nom,
      prenom: tokenResponse.prenom,
    }));
  },
  clear() {
    localStorage.removeItem("ct_access");
    localStorage.removeItem("ct_refresh");
    localStorage.removeItem("ct_user");
  },
};

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

let refreshInFlight = null;

async function doRefresh() {
  if (!TokenStore.refresh) throw new ApiError("Session expirée", 401);
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: TokenStore.refresh }),
    }).then(async (res) => {
      if (!res.ok) throw new ApiError("Session expirée", 401);
      const data = await res.json();
      TokenStore.save(data);
      return data;
    }).finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

// requestOpts: { method, body (objet -> JSON), form (FormData), query (objet), raw (bool: renvoie Response) }
async function request(path, opts = {}) {
  const { method = "GET", body, form, query, raw, retry = true } = opts;
  let url = `${API_BASE}${path}`;
  if (query) {
    const qs = new URLSearchParams(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const headers = {};
  if (TokenStore.access) headers["Authorization"] = `Bearer ${TokenStore.access}`;
  let fetchBody;
  if (form) {
    fetchBody = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(body);
  }

  const res = await fetch(url, { method, headers, body: fetchBody });

  if (res.status === 401 && retry && TokenStore.refresh) {
    try {
      await doRefresh();
      return request(path, { ...opts, retry: false });
    } catch (e) {
      TokenStore.clear();
      window.location.hash = "#/login";
      throw new ApiError("Session expirée, reconnecte-toi.", 401);
    }
  }

  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try {
      const errBody = await res.json();
      if (errBody.detail) {
        detail = typeof errBody.detail === "string"
          ? errBody.detail
          : JSON.stringify(errBody.detail);
      }
    } catch (_) { /* pas de corps JSON */ }
    throw new ApiError(detail, res.status);
  }

  if (raw) return res;
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// Télécharge une ressource protégée par JWT (les <a href> ne portent pas le header Authorization).
async function downloadAuthenticated(path, suggestedName) {
  const res = await request(path, { raw: true });
  const blob = await res.blob();
  let filename = suggestedName;
  const disposition = res.headers.get("Content-Disposition");
  if (!filename && disposition) {
    const m = /filename="?([^"]+)"?/.exec(disposition);
    if (m) filename = m[1];
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "telechargement";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const Api = {
  // --- auth ---
  async login(email, password) {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) {
      let detail = "Email ou mot de passe incorrect";
      try { const b = await res.json(); if (b.detail) detail = b.detail; } catch (_) {}
      throw new ApiError(detail, res.status);
    }
    const data = await res.json();
    TokenStore.save(data);
    return data;
  },
  async logout() {
    try {
      await request("/auth/logout", { method: "POST", body: { refresh_token: TokenStore.refresh } });
    } catch (_) { /* on nettoie quand même localement */ }
    TokenStore.clear();
  },
  me: () => request("/auth/me"),
  listUsers: () => request("/auth"),
  createUser: (payload) => request("/auth", { method: "POST", body: payload }),

  // --- incidents ---
  listIncidents: (query) => request("/incidents", { query }),
  getIncident: (id) => request(`/incidents/${id}`),
  createIncident: (payload) => request("/incidents", { method: "POST", body: payload }),
  getChronologie: (incidentId) => request(`/incidents/${incidentId}/chronologie`),
  addEvenementChronologie: (incidentId, payload) =>
    request(`/incidents/${incidentId}/chronologie`, { method: "POST", body: payload }),
  hotspots: (query) => request("/incidents/analyse/hotspots", { query }),
  incidentsCsvUrl: () => "/incidents/export/csv",
  incidentsPdfUrl: () => "/incidents/export/pdf",
  downloadCartePdf: (query) => {
    const qs = new URLSearchParams(
      Object.entries(query || {}).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    return downloadAuthenticated(
      `/incidents/export/carte.pdf${qs ? `?${qs}` : ""}`,
      `carte_incidents_${Date.now()}.pdf`
    );
  },

  // --- personnes ---
  listPersonnes: () => request("/personnes"),
  getPersonne: (id) => request(`/personnes/${id}`),
  createPersonne: (payload) => request("/personnes", { method: "POST", body: payload }),

  // --- véhicules ---
  listVehicules: () => request("/vehicules"),
  getVehicule: (id) => request(`/vehicules/${id}`),
  createVehicule: (payload) => request("/vehicules", { method: "POST", body: payload }),

  // --- preuves ---
  listPreuves: (incident_id) => request("/preuves", { query: { incident_id } }),
  getPreuve: (id) => request(`/preuves/${id}`),
  createPreuve: (payload) => request("/preuves", { method: "POST", body: payload }),
  getCustodyChain: (preuveId) => request(`/preuves/${preuveId}/custody`),
  addCustodyEvent: (preuveId, payload) => request(`/preuves/${preuveId}/custody`, { method: "POST", body: payload }),
  listPiecesJointes: (preuveId) => request(`/preuves/${preuveId}/pieces-jointes`),
  uploadPieceJointe: (preuveId, file) => {
    const form = new FormData();
    form.append("fichier", file);
    return request(`/preuves/${preuveId}/pieces-jointes`, { method: "POST", form });
  },
  deletePieceJointe: (preuveId, pieceId) => request(`/preuves/${preuveId}/pieces-jointes/${pieceId}`, { method: "DELETE" }),
  downloadPieceJointe: (preuveId, pieceId, filename) =>
    downloadAuthenticated(`/preuves/${preuveId}/pieces-jointes/${pieceId}/telechargement`, filename),
  downloadCustodyCsv: (preuveId) => downloadAuthenticated(`/preuves/${preuveId}/custody/export.csv`, `custody-${preuveId}.csv`),
  downloadCustodyPdf: (preuveId) => downloadAuthenticated(`/preuves/${preuveId}/custody/export.pdf`, `custody-${preuveId}.pdf`),

  // --- relations ---
  listRelations: () => request("/relations"),
  createRelation: (payload) => request("/relations", { method: "POST", body: payload }),
  getGraphe: (query) => request("/relations/graphe", { query }),
  getChemin: (depart_id, arrivee_id) => request("/relations/chemin", { query: { depart_id, arrivee_id } }),

  // --- anpr ---
  listLectures: (query) => request("/anpr/lectures", { query }),
  createLecture: (payload) => request("/anpr/lectures", { method: "POST", body: payload }),
  createLectureDepuisImage: (file, { camera_id, latitude, longitude } = {}) => {
    const form = new FormData();
    form.append("fichier", file);
    return request("/anpr/lectures/depuis-image", {
      method: "POST",
      form,
      query: { camera_id, latitude, longitude },
    });
  },
  createLecturesDepuisVideo: (source, { camera_id, latitude, longitude, intervalle_secondes } = {}) => {
    const form = new FormData();
    const query = { camera_id, latitude, longitude, intervalle_secondes };
    if (source instanceof File) {
      form.append("fichier", source);
    } else {
      query.url_flux = source;
    }
    return request("/anpr/lectures/depuis-video", { method: "POST", form, query });
  },
  corrigerLecture: (id, plaque_lue) => request(`/anpr/lectures/${id}`, { method: "PATCH", body: { plaque_lue } }),
  downloadLectureImage: (id) => downloadAuthenticated(`/anpr/lectures/${id}/image`, `anpr-${id}.jpg`),

  // --- audit ---
  listAudit: () => request("/audit"),

  // --- rgpd ---
  rgpdCandidats: (retention_days) => request("/rgpd/candidats", { query: { retention_days } }),
  rgpdPurge: (retention_days) => request("/rgpd/purge", { method: "POST", query: { retention_days } }),
};

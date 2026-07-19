// ==========================================================================
// CrimTrack — application
// React + htm chargés depuis un CDN : pas de npm, pas d'étape de build.
// ==========================================================================
const html = htm.bind(React.createElement);
const { useState, useEffect, useMemo, useCallback, useRef, createContext, useContext } = React;

// Couleurs par gravité d'incident, réutilisées par la carte et les badges.
const GRAVITE_COLORS = {
  faible: "#5b8c5a",
  moyenne: "#c2703d",
  eleve: "#bd4d3f",
  "élevé": "#bd4d3f",
  critique: "#8a1f1f",
};

const WRITE_ROLES = ["enqueteur", "opj", "administrateur"];
const ADMIN_ROLES = ["administrateur"];
const AUDIT_ROLES = ["opj", "administrateur"];

function hasRole(user, roles) {
  return !!user && roles.includes(user.role);
}

// ---------------------------------------------------------------------------
// Toasts (petit bus d'évènements, pas de prop-drilling)
// ---------------------------------------------------------------------------
const toastBus = (() => {
  let listeners = [];
  return {
    subscribe(fn) { listeners.push(fn); return () => { listeners = listeners.filter((l) => l !== fn); }; },
    emit(message, kind) { listeners.forEach((l) => l(message, kind || "error")); },
  };
})();

function notifyError(err) {
  toastBus.emit(err && err.message ? err.message : String(err), "error");
}
function notifyOk(message) {
  toastBus.emit(message, "ok");
}
// Alerte qui appelle une vigilance (correspondance ANPR avec un véhicule
// signalé/volé, rupture de chaîne de custody...) : ce n'est ni une réussite
// silencieuse (vert) ni une erreur technique (rouge) — kind "warn" dédié
// plutôt que de détourner notifyOk comme c'était fait auparavant.
function notifyWarn(message) {
  toastBus.emit(message, "warn");
}

const TOAST_ICONS = { ok: "✓", warn: "⚠", error: "✕" };

function ToastHost() {
  const [toasts, setToasts] = useState([]);
  useEffect(() => toastBus.subscribe((message, kind) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }), []);
  if (!toasts.length) return null;
  return html`
    <div>
      ${toasts.map((t) => html`
        <div class=${"toast toast-" + (t.kind || "error")} key=${t.id}>
          <span class="toast-icon">${TOAST_ICONS[t.kind] || TOAST_ICONS.error}</span>
          <span>${t.message}</span>
        </div>
      `)}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Hash router minimal
// ---------------------------------------------------------------------------
function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}
function navigate(path) { window.location.hash = path; }

// ---------------------------------------------------------------------------
// Auth context
// ---------------------------------------------------------------------------
const AuthContext = createContext(null);
function useAuth() { return useContext(AuthContext); }

// ---------------------------------------------------------------------------
// Petits composants réutilisables
// ---------------------------------------------------------------------------
function Field({ label, hint, children }) {
  return html`
    <div class="field">
      <label>${label}</label>
      ${children}
      ${hint ? html`<div class="hint">${hint}</div>` : null}
    </div>
  `;
}

function Loading({ label }) {
  return html`<div class="loading">${label || "Chargement…"}</div>`;
}

function Empty({ label }) {
  return html`<div class="empty">${label || "Rien à afficher pour l'instant."}</div>`;
}

function fmtDate(v) {
  if (!v) return "—";
  try {
    const d = new Date(v);
    return d.toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
  } catch (_) { return v; }
}

function Stamp({ text, kind }) {
  return html`<span class=${"stamp " + (kind || "neutral")}>${text}</span>`;
}

function statutKind(statut) {
  const s = (statut || "").toLowerCase();
  if (["ouvert", "signalé", "signale", "volé", "vole", "en_cours"].includes(s)) return "danger";
  if (["clos", "clôturé", "restitue", "restitué"].includes(s)) return "ok";
  if (["en_attente", "transfert"].includes(s)) return "warn";
  return "neutral";
}

// Générique : page "liste + création" pour les ressources simples.
function ResourcePage({ title, sub, columns, rows, loading, canCreate, createFields, onCreate, onRowClick, extraActions }) {
  const [showForm, setShowForm] = useState(false);
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onCreate(values);
      setValues({});
      setShowForm(false);
      notifyOk("Enregistré.");
    } catch (err) {
      notifyError(err);
    } finally {
      setSaving(false);
    }
  };

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">${title}</div>
          ${sub ? html`<div class="page-sub">${sub}</div>` : null}
        </div>
        <div style=${{ display: "flex", gap: "8px" }}>
          ${extraActions || null}
          ${canCreate ? html`
            <button class="btn" onClick=${() => setShowForm((s) => !s)}>
              ${showForm ? "Annuler" : "+ Nouveau"}
            </button>
          ` : null}
        </div>
      </div>

      ${showForm ? html`
        <div class="panel">
          <p class="panel-title">Nouvelle fiche</p>
          <form onSubmit=${submit}>
            <div class="field-row">
              ${createFields.map((f) => html`
                <${Field} key=${f.name} label=${f.label} hint=${f.hint}>
                  ${f.type === "select" ? html`
                    <select
                      value=${values[f.name] ?? f.default ?? ""}
                      required=${!!f.required}
                      onChange=${(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                    >
                      <option value="" disabled>Choisir…</option>
                      ${f.options.map((o) => html`<option value=${o} key=${o}>${o}</option>`)}
                    </select>
                  ` : html`
                    <input
                      type=${f.type || "text"}
                      step=${f.step}
                      required=${!!f.required}
                      value=${values[f.name] ?? f.default ?? ""}
                      onChange=${(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                    />
                  `}
                <//>
              `)}
            </div>
            <button class="btn" type="submit" disabled=${saving}>${saving ? "Enregistrement…" : "Enregistrer"}</button>
          </form>
        </div>
      ` : null}

      <div class="panel">
        ${loading ? html`<${Loading} />` : (
          rows.length === 0 ? html`<${Empty} />` : html`
            <table>
              <thead><tr>${columns.map((c) => html`<th key=${c.key}>${c.label}</th>`)}</tr></thead>
              <tbody>
                ${rows.map((row, i) => html`
                  <tr key=${row.id || i} class=${onRowClick ? "clickable" : ""} onClick=${() => onRowClick && onRowClick(row)}>
                    ${columns.map((c) => html`<td key=${c.key}>${c.render ? c.render(row) : row[c.key]}</td>`)}
                  </tr>
                `)}
              </tbody>
            </table>
          `
        )}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Carte interactive (Module 1, cahier des charges 3.1)
// Carte Leaflet réutilisable : incidents en points colorés par gravité,
// hotspots en cercles. Pas de dépendance npm : Leaflet est chargé depuis le
// CDN (voir index.html) et exposé globalement en `L`.
// ---------------------------------------------------------------------------
function IncidentMap({ incidents, hotspots, height }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  // Initialisation de la carte une seule fois.
  useEffect(() => {
    if (!containerRef.current || mapRef.current || typeof L === "undefined") return;
    const map = L.map(containerRef.current, { scrollWheelZoom: true }).setView([48.8566, 2.3522], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; contributeurs OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; layerRef.current = null; };
  }, []);

  // Rafraîchissement des marqueurs/cercles quand les données changent.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    const bounds = [];

    (hotspots || []).forEach((h) => {
      L.circle([h.latitude, h.longitude], {
        radius: h.rayon_metres,
        color: "#c2703d",
        weight: 1.5,
        fillColor: "#c2703d",
        fillOpacity: 0.12,
      })
        .bindPopup(
          `<b>${h.nombre_incidents} incident(s)</b><br/>rayon ${Math.round(h.rayon_metres)} m<br/>${h.types_infraction.join(", ")}`
        )
        .addTo(layer);
      bounds.push([h.latitude, h.longitude]);
    });

    (incidents || []).forEach((inc) => {
      if (inc.latitude == null || inc.longitude == null) return;
      const color = GRAVITE_COLORS[inc.gravite] || "#8a8f98";
      L.circleMarker([inc.latitude, inc.longitude], {
        radius: 7,
        color,
        weight: 1,
        fillColor: color,
        fillOpacity: 0.85,
      })
        .bindPopup(
          `<b>${inc.type_infraction}</b><br/>${fmtDate(inc.date_heure)}<br/>Statut : ${inc.statut} — Gravité : ${inc.gravite}<br/>${inc.adresse || ""}`
        )
        .addTo(layer);
      bounds.push([inc.latitude, inc.longitude]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
  }, [incidents, hotspots]);

  return html`<div ref=${containerRef} class="map-container" style=${{ height: height || "420px" }}></div>`;
}

// ---------------------------------------------------------------------------
// Graphe de relations interactif (Module 3, cahier des charges 3.3 :
// "Visualisation interactive (zoom, filtrage par type de lien, par force
// du lien)."). Simulation à forces D3, rendue en SVG, sans dépendance npm
// (D3 chargé depuis le CDN, voir index.html).
// ---------------------------------------------------------------------------
function RelationGraph({ nodes, edges, height, highlightIds }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof d3 === "undefined") return;
    el.innerHTML = "";

    const width = el.clientWidth || 600;
    const h = height || 480;

    if (!nodes || nodes.length === 0) {
      return;
    }

    // Copies locales : la simulation D3 mute directement les objets (x, y, vx, vy).
    const nodeById = new Map();
    const simNodes = nodes.map((n) => {
      const copy = { ...n };
      nodeById.set(n.id, copy);
      return copy;
    });
    const simEdges = (edges || [])
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ ...e, source: e.source, target: e.target }));

    const svg = d3.select(el).append("svg").attr("width", width).attr("height", h)
      .attr("viewBox", [0, 0, width, h]).style("cursor", "grab");

    const g = svg.append("g");

    svg.call(
      d3.zoom().scaleExtent([0.3, 4]).on("zoom", (event) => g.attr("transform", event.transform))
    );

    const NODE_COLORS = { vehicule: "#4b7bb0", lieu: "#5b8c5a", personne: "#c2703d" };
    const colorFor = (n) => NODE_COLORS[n.type] || NODE_COLORS.personne;
    const highlighted = new Set(highlightIds || []);

    const simulation = d3
      .forceSimulation(simNodes)
      .force("link", d3.forceLink(simEdges).id((d) => d.id).distance((d) => 60 + (10 - Math.min(d.poids, 10)) * 6))
      .force("charge", d3.forceManyBody().strength(-220))
      .force("center", d3.forceCenter(width / 2, h / 2))
      .force("collide", d3.forceCollide(26));

    const link = g.selectAll("line").data(simEdges).join("line")
      .attr("stroke", (d) => (highlighted.has(d.id) ? "#e8c07d" : "#3a4150"))
      .attr("stroke-width", (d) => Math.max(1, Math.min(d.poids, 10) / 2))
      .attr("stroke-opacity", 0.85);

    const linkLabel = g.selectAll("text.link-label").data(simEdges).join("text")
      .attr("class", "link-label")
      .attr("font-size", 9.5)
      .attr("fill", "#7c8496")
      .text((d) => d.type_relation);

    const nodeGroup = g.selectAll("g.node").data(simNodes).join("g")
      .attr("class", "node")
      .call(
        d3.drag()
          .on("start", (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on("end", (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    nodeGroup.append("circle")
      .attr("r", (d) => (d.type === "lieu" ? (highlighted.has(d.id) ? 10 : 7.5) : (highlighted.has(d.id) ? 12 : 9)))
      .attr("fill", colorFor)
      .attr("stroke", (d) => (highlighted.has(d.id) ? "#e8c07d" : "#10141a"))
      .attr("stroke-width", (d) => (highlighted.has(d.id) ? 3 : 1.5));

    nodeGroup.append("text")
      .text((d) => d.label)
      .attr("font-size", 11)
      .attr("dx", 13)
      .attr("dy", 4)
      .attr("fill", "#e8e6de");

    const TYPE_LABELS = { vehicule: "Véhicule", lieu: "Lieu", personne: "Personne" };
    nodeGroup.append("title").text((d) => `${TYPE_LABELS[d.type] || "Personne"} — ${d.label}${d.role ? " (" + d.role + ")" : ""}`);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
      linkLabel
        .attr("x", (d) => (d.source.x + d.target.x) / 2)
        .attr("y", (d) => (d.source.y + d.target.y) / 2);
      nodeGroup.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [nodes, edges, height, highlightIds]);

  return html`<div ref=${containerRef} class="map-container" style=${{ height: (height || 480) + "px" }}></div>`;
}

// ---------------------------------------------------------------------------
// Connexion
// ---------------------------------------------------------------------------
function LoginPage() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await auth.login(email, password);
      navigate("#/");
    } catch (err) {
      setError(err.message || "Connexion impossible.");
    } finally {
      setBusy(false);
    }
  };

  return html`
    <div class="login-wrap">
      <div class="login-card">
        <div class="login-title">CrimTrack</div>
        <div class="login-sub">ACCÈS RÉSERVÉ — ENQUÊTE EN COURS</div>
        ${error ? html`<div class="login-error">${error}</div>` : null}
        <form onSubmit=${submit}>
          <${Field} label="Adresse e-mail">
            <input type="email" required autoFocus value=${email} onChange=${(e) => setEmail(e.target.value)} />
          <//>
          <${Field} label="Mot de passe">
            <input type="password" required value=${password} onChange=${(e) => setPassword(e.target.value)} />
          <//>
          <button class="btn" type="submit" style=${{ width: "100%", justifyContent: "center" }} disabled=${busy}>
            ${busy ? "Connexion…" : "Se connecter"}
          </button>
        </form>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Coquille de l'application (barre latérale + contenu)
// ---------------------------------------------------------------------------
const NAV = [
  { group: "Vue d'ensemble", items: [
    { path: "#/", label: "Tableau de bord" },
    { path: "#/carte", label: "Carte" },
  ]},
  { group: "Dossiers", items: [
    { path: "#/incidents", label: "Incidents" },
    { path: "#/personnes", label: "Personnes" },
    { path: "#/vehicules", label: "Véhicules" },
    { path: "#/preuves", label: "Preuves & scellés" },
    { path: "#/relations", label: "Relations" },
    { path: "#/anpr", label: "Lectures ANPR" },
  ]},
  { group: "Administration", items: [
    { path: "#/audit", label: "Journal d'audit", roles: AUDIT_ROLES },
    { path: "#/rgpd", label: "Purge RGPD", roles: ADMIN_ROLES },
    { path: "#/utilisateurs", label: "Comptes utilisateurs", roles: ADMIN_ROLES },
  ]},
];

function Sidebar({ current }) {
  const auth = useAuth();
  const user = auth.user;
  return html`
    <div class="sidebar">
      <div class="brand">
        <div class="brand-mark">Crim<span>Track</span></div>
        <div class="brand-sub">Console d'enquête</div>
      </div>
      ${NAV.map((section) => html`
        <div key=${section.group}>
          <div class="nav-group">${section.group}</div>
          ${section.items.filter((it) => !it.roles || hasRole(user, it.roles)).map((it) => html`
            <a
              key=${it.path}
              class=${"nav-link" + (current === it.path || (it.path !== "#/" && current.startsWith(it.path)) || (it.path === "#/" && current === "#/") ? " active" : "")}
              onClick=${(e) => { e.preventDefault(); navigate(it.path); }}
              href=${it.path}
            >${it.label}</a>
          `)}
        </div>
      `)}
      <div class="sidebar-foot">
        <div class="who">${user ? `${user.prenom} ${user.nom}` : ""}</div>
        <div class="who-role">${user ? user.role : ""}</div>
        <span class="logout-link" onClick=${() => auth.logout()}>Se déconnecter</span>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Tableau de bord
// ---------------------------------------------------------------------------
function Dashboard() {
  const [hotspots, setHotspots] = useState(null);
  const [incidents, setIncidents] = useState(null);

  useEffect(() => {
    Api.hotspots().then(setHotspots).catch((e) => { notifyError(e); setHotspots([]); });
    Api.listIncidents().then(setIncidents).catch((e) => { notifyError(e); setIncidents([]); });
  }, []);

  const stats = useMemo(() => {
    if (!incidents) return null;
    const ouverts = incidents.filter((i) => i.statut === "ouvert").length;
    const graves = incidents.filter((i) => i.gravite === "eleve" || i.gravite === "élevé").length;
    return { total: incidents.length, ouverts, graves };
  }, [incidents]);

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">Tableau de bord</div>
          <div class="page-sub">Vue d'ensemble de l'activité en cours.</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <p class="panel-title">Incidents</p>
          ${!stats ? html`<${Loading} />` : html`
            <div class="kv">
              <dt>Total enregistré</dt><dd class="mono">${stats.total}</dd>
              <dt>Statut « ouvert »</dt><dd class="mono">${stats.ouverts}</dd>
              <dt>Gravité élevée</dt><dd class="mono">${stats.graves}</dd>
            </div>
            <div style=${{ marginTop: "14px" }}>
              <a href="#/incidents" onClick=${(e) => { e.preventDefault(); navigate("#/incidents"); }}>Voir tous les incidents →</a>
            </div>
          `}
        </div>

        <div class="panel" style=${{ padding: 0, overflow: "hidden" }}>
          <p class="panel-title" style=${{ padding: "16px 16px 0" }}>Points chauds (analyse géographique)</p>
          ${!hotspots || !incidents ? html`<div style=${{ padding: "16px" }}><${Loading} /></div>` : html`
            <${IncidentMap} incidents=${incidents} hotspots=${hotspots} height="280px" />
            <div style=${{ padding: "12px 16px" }}>
              <a href="#/carte" onClick=${(e) => { e.preventDefault(); navigate("#/carte"); }}>Ouvrir la carte complète (filtres) →</a>
            </div>
          `}
        </div>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Carte — page dédiée avec filtres (Module 1, cahier des charges 3.1 :
// "Carte interactive avec filtres par période, type d'infraction et zone.")
// ---------------------------------------------------------------------------
function CartePage() {
  const [allTypes, setAllTypes] = useState([]);
  const [incidents, setIncidents] = useState(null);
  const [hotspots, setHotspots] = useState(null);
  const [filters, setFilters] = useState({ type_infraction: "", date_debut: "", date_fin: "", adresse: "" });

  // Liste des types d'infraction (non filtrée) pour peupler le menu déroulant.
  useEffect(() => {
    Api.listIncidents().then((rows) => setAllTypes([...new Set(rows.map((r) => r.type_infraction))].sort()))
      .catch(() => setAllTypes([]));
  }, []);

  const load = useCallback(() => {
    const query = {
      type_infraction: filters.type_infraction || undefined,
      date_debut: filters.date_debut ? new Date(filters.date_debut).toISOString() : undefined,
      date_fin: filters.date_fin ? new Date(filters.date_fin).toISOString() : undefined,
      adresse: filters.adresse || undefined,
    };
    Api.listIncidents(query).then(setIncidents).catch((e) => { notifyError(e); setIncidents([]); });
    Api.hotspots(query).then(setHotspots).catch((e) => { notifyError(e); setHotspots([]); });
  }, [filters]);
  useEffect(load, [load]);

  const setFilter = (name) => (e) => setFilters((f) => ({ ...f, [name]: e.target.value }));
  const resetFilters = () => setFilters({ type_infraction: "", date_debut: "", date_fin: "", adresse: "" });

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">Carte</div>
          <div class="page-sub">Incidents géolocalisés et points chauds — filtrables par type, période et zone.</div>
        </div>
      </div>

      <div class="panel">
        <div class="field-row">
          <${Field} label="Type d'infraction">
            <select value=${filters.type_infraction} onChange=${setFilter("type_infraction")}>
              <option value="">Tous</option>
              ${allTypes.map((t) => html`<option value=${t} key=${t}>${t}</option>`)}
            </select>
          <//>
          <${Field} label="Du">
            <input type="date" value=${filters.date_debut} onChange=${setFilter("date_debut")} />
          <//>
          <${Field} label="Au">
            <input type="date" value=${filters.date_fin} onChange=${setFilter("date_fin")} />
          <//>
          <${Field} label="Zone (adresse contient…)">
            <input type="text" placeholder="ex. Secteur A" value=${filters.adresse} onChange=${setFilter("adresse")} />
          <//>
        </div>
        <div class="field-row" style=${{ marginTop: "10px" }}>
          <button class="btn ghost small" onClick=${resetFilters}>Réinitialiser les filtres</button>
          <button
            class="btn small"
            onClick=${async () => {
              try {
                await Api.downloadCartePdf({
                  type_infraction: filters.type_infraction || undefined,
                  date_debut: filters.date_debut ? new Date(filters.date_debut).toISOString() : undefined,
                  date_fin: filters.date_fin ? new Date(filters.date_fin).toISOString() : undefined,
                  adresse: filters.adresse || undefined,
                });
              } catch (e) { notifyError(e); }
            }}
          >Exporter le rapport cartographique (PDF)</button>
        </div>
      </div>

      <div class="panel" style=${{ padding: 0, overflow: "hidden" }}>
        ${incidents === null ? html`<${Loading} />` : html`<${IncidentMap} incidents=${incidents} hotspots=${hotspots || []} height="560px" />`}
      </div>

      <div class="panel">
        <p class="panel-title">Résumé</p>
        <div class="kv">
          <dt>Incidents affichés</dt><dd class="mono">${incidents ? incidents.length : "—"}</dd>
          <dt>Points chauds détectés</dt><dd class="mono">${hotspots ? hotspots.length : "—"}</dd>
        </div>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Incidents
// ---------------------------------------------------------------------------
function IncidentsListPage() {
  const auth = useAuth();
  const [rows, setRows] = useState(null);

  const load = useCallback(() => {
    Api.listIncidents().then(setRows).catch((e) => { notifyError(e); setRows([]); });
  }, []);
  useEffect(load, [load]);

  const createFields = [
    { name: "type_infraction", label: "Type d'infraction", required: true },
    { name: "date_heure", label: "Date et heure", type: "datetime-local", required: true },
    { name: "statut", label: "Statut", type: "select", options: ["ouvert", "en_cours", "clos"], default: "ouvert" },
    { name: "gravite", label: "Gravité", type: "select", options: ["faible", "moyenne", "eleve"], default: "faible" },
    { name: "adresse", label: "Adresse" },
    { name: "unite_en_charge", label: "Unité en charge" },
    { name: "latitude", label: "Latitude", type: "number", step: "any" },
    { name: "longitude", label: "Longitude", type: "number", step: "any" },
  ];

  const onCreate = async (values) => {
    const payload = {
      ...values,
      date_heure: values.date_heure ? new Date(values.date_heure).toISOString() : undefined,
      latitude: values.latitude ? parseFloat(values.latitude) : undefined,
      longitude: values.longitude ? parseFloat(values.longitude) : undefined,
    };
    await Api.createIncident(payload);
    load();
  };

  const exportsActions = html`
    <${React.Fragment}>
      <button class="btn ghost small" onClick=${() => downloadAuthenticated(Api.incidentsCsvUrl(), "incidents.csv")}>Export CSV</button>
      <button class="btn ghost small" onClick=${() => downloadAuthenticated(Api.incidentsPdfUrl(), "incidents.pdf")}>Export PDF</button>
    <//>
  `;

  return html`
    <${ResourcePage}
      title="Incidents"
      sub="Dossiers d'incidents enregistrés."
      loading=${rows === null}
      rows=${rows || []}
      columns=${[
        { key: "type_infraction", label: "Type" },
        { key: "date_heure", label: "Date", render: (r) => html`<span class="mono">${fmtDate(r.date_heure)}</span>` },
        { key: "statut", label: "Statut", render: (r) => html`<${Stamp} text=${r.statut} kind=${statutKind(r.statut)} />` },
        { key: "gravite", label: "Gravité" },
        { key: "adresse", label: "Adresse" },
      ]}
      onRowClick=${(r) => navigate(`#/incidents/${r.id}`)}
      canCreate=${hasRole(auth.user, WRITE_ROLES)}
      createFields=${createFields}
      onCreate=${onCreate}
      extraActions=${exportsActions}
    />
  `;
}

function IncidentDetailPage({ id }) {
  const auth = useAuth();
  const [incident, setIncident] = useState(null);
  const [preuves, setPreuves] = useState(null);
  const [chronologie, setChronologie] = useState(null);
  const [showPreuveForm, setShowPreuveForm] = useState(false);
  const [showChronoForm, setShowChronoForm] = useState(false);
  const [pv, setPv] = useState({ type: "", description: "", localisation_stockage: "" });
  const [ce, setCe] = useState({ date_heure: "", titre: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [savingChrono, setSavingChrono] = useState(false);

  const load = useCallback(() => {
    Api.getIncident(id).then(setIncident).catch(notifyError);
    Api.listPreuves(id).then(setPreuves).catch((e) => { notifyError(e); setPreuves([]); });
    Api.getChronologie(id).then(setChronologie).catch((e) => { notifyError(e); setChronologie([]); });
  }, [id]);
  useEffect(load, [load]);

  const createPreuve = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await Api.createPreuve({ incident_id: id, ...pv });
      setPv({ type: "", description: "", localisation_stockage: "" });
      setShowPreuveForm(false);
      notifyOk("Preuve ajoutée.");
      load();
    } catch (err) { notifyError(err); } finally { setSaving(false); }
  };

  const createEvenement = async (e) => {
    e.preventDefault();
    if (!ce.date_heure || !ce.titre.trim()) return;
    setSavingChrono(true);
    try {
      await Api.addEvenementChronologie(id, {
        date_heure: new Date(ce.date_heure).toISOString(),
        titre: ce.titre,
        description: ce.description || undefined,
      });
      setCe({ date_heure: "", titre: "", description: "" });
      setShowChronoForm(false);
      notifyOk("Événement ajouté à la chronologie.");
      load();
    } catch (err) { notifyError(err); } finally { setSavingChrono(false); }
  };

  if (!incident) return html`<${Loading} />`;

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">${incident.type_infraction}</div>
          <div class="page-sub mono">Dossier ${incident.id}</div>
        </div>
        <${Stamp} text=${incident.statut} kind=${statutKind(incident.statut)} />
      </div>

      <div class="panel">
        <p class="panel-title">Détails</p>
        <div class="kv">
          <dt>Date et heure</dt><dd>${fmtDate(incident.date_heure)}</dd>
          <dt>Gravité</dt><dd>${incident.gravite}</dd>
          <dt>Adresse</dt><dd>${incident.adresse || "—"}</dd>
          <dt>Unité en charge</dt><dd>${incident.unite_en_charge || "—"}</dd>
          <dt>Coordonnées</dt><dd class="mono">${incident.latitude ?? "—"}, ${incident.longitude ?? "—"}</dd>
        </div>
      </div>

      <div class="panel">
        <div class="section-head">
          <p class="panel-title" style=${{ margin: 0 }}>Chronologie des faits</p>
          ${hasRole(auth.user, WRITE_ROLES) ? html`
            <button class="btn small" onClick=${() => setShowChronoForm((s) => !s)}>${showChronoForm ? "Annuler" : "+ Événement"}</button>
          ` : null}
        </div>

        ${showChronoForm ? html`
          <form onSubmit=${createEvenement} style=${{ marginBottom: "16px" }}>
            <div class="field-row">
              <${Field} label="Date et heure"><input type="datetime-local" value=${ce.date_heure} onChange=${(e) => setCe((s) => ({ ...s, date_heure: e.target.value }))} /><//>
              <${Field} label="Titre"><input value=${ce.titre} onChange=${(e) => setCe((s) => ({ ...s, titre: e.target.value }))} placeholder="ex. Audition du témoin" /><//>
            </div>
            <${Field} label="Description">
              <textarea rows="2" value=${ce.description} onChange=${(e) => setCe((s) => ({ ...s, description: e.target.value }))}></textarea>
            <//>
            <button class="btn" type="submit" disabled=${savingChrono}>${savingChrono ? "…" : "Ajouter à la chronologie"}</button>
          </form>
        ` : null}

        ${chronologie === null ? html`<${Loading} />` : (chronologie.length === 0 ? html`<${Empty} label="Aucun événement enregistré pour cette affaire." /> ` : html`
          <ul class="timeline">
            ${chronologie.map((ev) => html`
              <li key=${ev.id} class=${"timeline-item timeline-" + ev.origine}>
                <div class="timeline-date mono">${fmtDate(ev.date_heure)}</div>
                <div class="timeline-body">
                  <div class="timeline-title">
                    ${ev.titre}
                    ${ev.origine === "auto" ? html`<${Stamp} text="auto" kind="info" />` : null}
                  </div>
                  ${ev.description ? html`<div class="timeline-desc">${ev.description}</div>` : null}
                </div>
              </li>
            `)}
          </ul>
        `)}
      </div>

      <div class="panel">
        <div class="section-head">
          <p class="panel-title" style=${{ margin: 0 }}>Preuves liées</p>
          ${hasRole(auth.user, WRITE_ROLES) ? html`
            <button class="btn small" onClick=${() => setShowPreuveForm((s) => !s)}>${showPreuveForm ? "Annuler" : "+ Preuve"}</button>
          ` : null}
        </div>

        ${showPreuveForm ? html`
          <form onSubmit=${createPreuve} style=${{ marginBottom: "16px" }}>
            <div class="field-row">
              <${Field} label="Type"><input value=${pv.type} onChange=${(e) => setPv((s) => ({ ...s, type: e.target.value }))} /><//>
              <${Field} label="Localisation de stockage"><input value=${pv.localisation_stockage} onChange=${(e) => setPv((s) => ({ ...s, localisation_stockage: e.target.value }))} /><//>
            </div>
            <${Field} label="Description">
              <textarea rows="2" value=${pv.description} onChange=${(e) => setPv((s) => ({ ...s, description: e.target.value }))}></textarea>
            <//>
            <button class="btn" type="submit" disabled=${saving}>${saving ? "…" : "Enregistrer la preuve"}</button>
          </form>
        ` : null}

        ${preuves === null ? html`<${Loading} />` : (preuves.length === 0 ? html`<${Empty} label="Aucune preuve rattachée." />` : html`
          <table>
            <thead><tr><th>Type</th><th>Description</th><th>Intégrité</th></tr></thead>
            <tbody>
              ${preuves.map((p) => html`
                <tr key=${p.id} class="clickable" onClick=${() => navigate(`#/preuves/${p.id}`)}>
                  <td>${p.type || "—"}</td>
                  <td>${p.description || "—"}</td>
                  <td class="mono" style=${{ fontSize: "11px" }}>${p.hash_integrite ? p.hash_integrite.slice(0, 16) + "…" : "—"}</td>
                </tr>
              `)}
            </tbody>
          </table>
        `)}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Personnes
// ---------------------------------------------------------------------------
function PersonnesPage() {
  const auth = useAuth();
  const [rows, setRows] = useState(null);
  const load = useCallback(() => Api.listPersonnes().then(setRows).catch((e) => { notifyError(e); setRows([]); }), []);
  useEffect(load, [load]);

  return html`
    <${ResourcePage}
      title="Personnes"
      sub="Individus rattachés à une ou plusieurs affaires."
      loading=${rows === null}
      rows=${rows || []}
      columns=${[
        { key: "nom", label: "Nom" },
        { key: "prenom", label: "Prénom" },
        { key: "role", label: "Rôle" },
        { key: "statut", label: "Statut", render: (r) => r.statut ? html`<${Stamp} text=${r.statut} kind=${statutKind(r.statut)} />` : "—" },
        { key: "date_naissance", label: "Naissance", render: (r) => r.date_naissance ? fmtDate(r.date_naissance).split(" ")[0] : "—" },
      ]}
      canCreate=${hasRole(auth.user, WRITE_ROLES)}
      createFields=${[
        { name: "nom", label: "Nom", required: true },
        { name: "prenom", label: "Prénom", required: true },
        { name: "role", label: "Rôle (suspect, témoin, victime…)" },
        { name: "statut", label: "Statut" },
        { name: "date_naissance", label: "Date de naissance", type: "date" },
        { name: "signalement", label: "Signalement" },
      ]}
      onCreate=${async (values) => {
        const payload = { ...values, date_naissance: values.date_naissance ? new Date(values.date_naissance).toISOString() : undefined };
        await Api.createPersonne(payload);
        load();
      }}
    />
  `;
}

// ---------------------------------------------------------------------------
// Véhicules
// ---------------------------------------------------------------------------
function VehiculesPage() {
  const auth = useAuth();
  const [rows, setRows] = useState(null);
  const load = useCallback(() => Api.listVehicules().then(setRows).catch((e) => { notifyError(e); setRows([]); }), []);
  useEffect(load, [load]);

  return html`
    <${ResourcePage}
      title="Véhicules"
      sub="Véhicules identifiés, signalés ou associés à une personne."
      loading=${rows === null}
      rows=${rows || []}
      columns=${[
        { key: "plaque_immatriculation", label: "Plaque", render: (r) => html`<span class="mono">${r.plaque_immatriculation}</span>` },
        { key: "marque", label: "Marque" },
        { key: "modele", label: "Modèle" },
        { key: "couleur", label: "Couleur" },
        { key: "statut", label: "Statut", render: (r) => r.statut ? html`<${Stamp} text=${r.statut} kind=${statutKind(r.statut)} />` : "—" },
      ]}
      canCreate=${hasRole(auth.user, WRITE_ROLES)}
      createFields=${[
        { name: "plaque_immatriculation", label: "Plaque d'immatriculation", required: true },
        { name: "marque", label: "Marque" },
        { name: "modele", label: "Modèle" },
        { name: "couleur", label: "Couleur" },
        { name: "statut", label: "Statut (ex. signalé, volé)" },
        { name: "proprietaire_id", label: "ID propriétaire (personne)" },
      ]}
      onCreate=${async (values) => { await Api.createVehicule(values); load(); }}
    />
  `;
}

// ---------------------------------------------------------------------------
// Preuves
// ---------------------------------------------------------------------------
function PreuvesListPage() {
  const [rows, setRows] = useState(null);
  useEffect(() => { Api.listPreuves().then(setRows).catch((e) => { notifyError(e); setRows([]); }); }, []);

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">Preuves & scellés</div>
          <div class="page-sub">Toutes les preuves, tous dossiers confondus. Une preuve se crée depuis la fiche d'un incident.</div>
        </div>
      </div>
      <div class="panel">
        ${rows === null ? html`<${Loading} />` : (rows.length === 0 ? html`<${Empty} label="Aucune preuve enregistrée." />` : html`
          <table>
            <thead><tr><th>Type</th><th>Description</th><th>Incident</th><th>Intégrité</th></tr></thead>
            <tbody>
              ${rows.map((p) => html`
                <tr key=${p.id} class="clickable" onClick=${() => navigate(`#/preuves/${p.id}`)}>
                  <td>${p.type || "—"}</td>
                  <td>${p.description || "—"}</td>
                  <td class="mono" style=${{ fontSize: "11px" }}>${p.incident_id}</td>
                  <td class="mono" style=${{ fontSize: "11px" }}>${p.hash_integrite ? p.hash_integrite.slice(0, 16) + "…" : "—"}</td>
                </tr>
              `)}
            </tbody>
          </table>
        `)}
      </div>
    </div>
  `;
}

function PreuveDetailPage({ id }) {
  const auth = useAuth();
  const [preuve, setPreuve] = useState(null);
  const [chain, setChain] = useState(null);
  const [pieces, setPieces] = useState(null);
  const [action, setAction] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = React.useRef(null);

  const load = useCallback(() => {
    Api.getPreuve(id).then(setPreuve).catch(notifyError);
    Api.getCustodyChain(id).then(setChain).catch((e) => { notifyError(e); setChain(null); });
    Api.listPiecesJointes(id).then(setPieces).catch((e) => { notifyError(e); setPieces([]); });
  }, [id]);
  useEffect(load, [load]);

  const addEvent = async (e) => {
    e.preventDefault();
    if (!action.trim()) return;
    setBusy(true);
    try {
      await Api.addCustodyEvent(id, { action });
      setAction("");
      notifyOk("Maillon ajouté à la chaîne de custody.");
      load();
    } catch (err) { notifyError(err); } finally { setBusy(false); }
  };

  const onUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    try {
      await Api.uploadPieceJointe(id, file);
      notifyOk("Pièce jointe ajoutée.");
      load();
    } catch (err) { notifyError(err); } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removePiece = async (pieceId) => {
    if (!window.confirm("Supprimer définitivement cette pièce jointe ?")) return;
    try {
      await Api.deletePieceJointe(id, pieceId);
      notifyOk("Pièce jointe supprimée.");
      load();
    } catch (err) { notifyError(err); }
  };

  if (!preuve) return html`<${Loading} />`;
  const canWrite = hasRole(auth.user, WRITE_ROLES);
  const canDeletePiece = hasRole(auth.user, ["opj", "administrateur"]);

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">Preuve — ${preuve.type || "sans type"}</div>
          <div class="page-sub mono">${preuve.id}</div>
        </div>
        ${chain ? html`<${Stamp} text=${chain.chaine_intacte ? "Chaîne intacte" : "Rupture détectée"} kind=${chain.chaine_intacte ? "ok" : "danger"} />` : null}
      </div>

      <div class="panel">
        <p class="panel-title">Détails</p>
        <div class="kv">
          <dt>Description</dt><dd>${preuve.description || "—"}</dd>
          <dt>Localisation</dt><dd>${preuve.localisation_stockage || "—"}</dd>
          <dt>Incident</dt><dd><a href="#/incidents/${preuve.incident_id}" onClick=${(e) => { e.preventDefault(); navigate(`#/incidents/${preuve.incident_id}`); }}>${preuve.incident_id}</a></dd>
          <dt>Hash d'intégrité</dt><dd class="mono" style=${{ fontSize: "11.5px", wordBreak: "break-all" }}>${preuve.hash_integrite || "—"}</dd>
        </div>
        <div style=${{ marginTop: "14px", display: "flex", gap: "8px" }}>
          <button class="btn ghost small" onClick=${() => Api.downloadCustodyCsv(id).catch(notifyError)}>Export custody CSV</button>
          <button class="btn ghost small" onClick=${() => Api.downloadCustodyPdf(id).catch(notifyError)}>Export custody PDF</button>
        </div>
      </div>

      <div class="panel">
        <p class="panel-title">Chaîne de custody</p>
        ${!chain ? html`<${Loading} />` : (chain.evenements.length === 0 ? html`<${Empty} label="Aucun évènement." />` : html`
          <div>
            ${chain.evenements.map((ev) => html`
              <div class="chain-item" key=${ev.id}>
                <div class="chain-dot"></div>
                <div>
                  <div style=${{ fontWeight: 600 }}>${ev.action}</div>
                  <div class="mono" style=${{ fontSize: "12px" }}>${fmtDate(ev.date_heure)} · agent ${ev.utilisateur_id.slice(0, 8)}…</div>
                </div>
              </div>
            `)}
          </div>
        `)}
        ${canWrite ? html`
          <form onSubmit=${addEvent} style=${{ marginTop: "14px", display: "flex", gap: "8px" }}>
            <input
              placeholder="Nouvelle action (collecte, transfert, analyse, restitution…)"
              value=${action}
              onChange=${(e) => setAction(e.target.value)}
              style=${{ flex: 1, background: "var(--ink)", border: "1px solid var(--border)", borderRadius: "3px", padding: "8px 10px", color: "var(--text)" }}
            />
            <button class="btn" type="submit" disabled=${busy}>Ajouter</button>
          </form>
        ` : null}
      </div>

      <div class="panel">
        <div class="section-head">
          <p class="panel-title" style=${{ margin: 0 }}>Pièces jointes</p>
        </div>
        ${pieces === null ? html`<${Loading} />` : (pieces.length === 0 ? html`<${Empty} label="Aucune pièce jointe." />` : html`
          <table>
            <thead><tr><th>Nom</th><th>Type</th><th>Taille</th><th>Ajoutée le</th><th></th></tr></thead>
            <tbody>
              ${pieces.map((p) => html`
                <tr key=${p.id}>
                  <td>${p.nom_fichier}</td>
                  <td class="mono" style=${{ fontSize: "11.5px" }}>${p.type_mime || "—"}</td>
                  <td>${(p.taille_octets / 1024).toFixed(1)} Ko</td>
                  <td>${fmtDate(p.date_ajout)}</td>
                  <td style=${{ display: "flex", gap: "10px" }}>
                    <button class="link-btn" onClick=${() => Api.downloadPieceJointe(id, p.id, p.nom_fichier).catch(notifyError)}>Télécharger</button>
                    ${canDeletePiece ? html`<button class="link-btn danger-link" onClick=${() => removePiece(p.id)}>Supprimer</button>` : null}
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
        `)}
        ${canWrite ? html`
          <div class="file-drop" style=${{ marginTop: "14px" }}>
            Ajouter un fichier :
            <input ref=${fileRef} type="file" onChange=${onUpload} disabled=${busy} style=${{ marginLeft: "8px" }} />
          </div>
        ` : null}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Relations
// ---------------------------------------------------------------------------
function RelationsPage() {
  const auth = useAuth();
  const [rows, setRows] = useState(null);
  const [graphFilters, setGraphFilters] = useState({ type_relation: "", poids_min: "" });
  const [graphe, setGraphe] = useState(null);
  const [chemin, setChemin] = useState({ depart_id: "", arrivee_id: "" });
  const [cheminResult, setCheminResult] = useState(null);
  const [cheminBusy, setCheminBusy] = useState(false);

  const load = useCallback(() => Api.listRelations().then(setRows).catch((e) => { notifyError(e); setRows([]); }), []);
  useEffect(load, [load]);

  const loadGraphe = useCallback(() => {
    const query = {
      type_relation: graphFilters.type_relation || undefined,
      poids_min: graphFilters.poids_min ? parseInt(graphFilters.poids_min, 10) : undefined,
    };
    Api.getGraphe(query).then(setGraphe).catch((e) => { notifyError(e); setGraphe({ nodes: [], edges: [] }); });
  }, [graphFilters]);
  useEffect(loadGraphe, [loadGraphe]);

  const typesRelation = useMemo(() => [...new Set((rows || []).map((r) => r.type_relation))].sort(), [rows]);

  const searchChemin = async (e) => {
    e.preventDefault();
    setCheminBusy(true);
    setCheminResult(null);
    try {
      const res = await Api.getChemin(chemin.depart_id, chemin.arrivee_id);
      setCheminResult(res);
    } catch (err) { notifyError(err); } finally { setCheminBusy(false); }
  };

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">Relations</div>
          <div class="page-sub">Réseau de liens entre personnes, véhicules et lieux, construit automatiquement à partir des enquêtes.</div>
        </div>
      </div>

      <div class="panel">
        <div class="field-row">
          <${Field} label="Type de lien">
            <select value=${graphFilters.type_relation} onChange=${(e) => setGraphFilters((f) => ({ ...f, type_relation: e.target.value }))}>
              <option value="">Tous</option>
              ${typesRelation.map((t) => html`<option value=${t} key=${t}>${t}</option>`)}
              <option value="proprietaire">proprietaire (véhicule)</option>
              <option value="vu_ensemble">vu_ensemble (personne ↔ véhicule, même incident)</option>
              <option value="lieu_incident">lieu_incident (personne/véhicule ↔ lieu)</option>
            </select>
          <//>
          <${Field} label="Force minimale (poids)">
            <input type="number" min="1" placeholder="ex. 5" value=${graphFilters.poids_min} onChange=${(e) => setGraphFilters((f) => ({ ...f, poids_min: e.target.value }))} />
          <//>
        </div>
        <div class="legend">
          <span class="legend-item"><span class="legend-dot" style=${{ background: "#c2703d" }}></span>Personne</span>
          <span class="legend-item"><span class="legend-dot" style=${{ background: "#4b7bb0" }}></span>Véhicule</span>
          <span class="legend-item"><span class="legend-dot" style=${{ background: "#5b8c5a" }}></span>Lieu</span>
        </div>
      </div>

      <div class="panel" style=${{ padding: 0, overflow: "hidden" }}>
        ${!graphe ? html`<div style=${{ padding: "16px" }}><${Loading} /></div>` : (
          graphe.nodes.length === 0 ? html`<div style=${{ padding: "16px" }}><${Empty} label="Aucun lien à afficher pour ces filtres." /></div>` :
          html`<${RelationGraph} nodes=${graphe.nodes} edges=${graphe.edges} height=${460} />`
        )}
      </div>

      <div class="panel">
        <p class="panel-title">Recherche de chemin entre deux entités (personne, véhicule ou lieu)</p>
        <form onSubmit=${searchChemin} class="field-row">
          <${Field} label="ID de départ">
            <input required value=${chemin.depart_id} onChange=${(e) => setChemin((s) => ({ ...s, depart_id: e.target.value }))} />
          <//>
          <${Field} label="ID d'arrivée">
            <input required value=${chemin.arrivee_id} onChange=${(e) => setChemin((s) => ({ ...s, arrivee_id: e.target.value }))} />
          <//>
        </form>
        <button class="btn" onClick=${searchChemin} disabled=${cheminBusy}>${cheminBusy ? "Recherche…" : "Rechercher le chemin"}</button>

        ${cheminResult ? html`
          <div style=${{ marginTop: "16px" }}>
            ${!cheminResult.trouve ? html`<${Empty} label="Aucun chemin trouvé entre ces deux entités." />` : html`
              <p style=${{ fontSize: "13.5px", marginBottom: "10px" }}>Chemin trouvé — ${cheminResult.longueur} saut(s).</p>
              <div style=${{ marginBottom: "12px" }}>
                <${RelationGraph}
                  nodes=${cheminResult.nodes}
                  edges=${cheminResult.edges}
                  height=${260}
                  highlightIds=${cheminResult.nodes.map((n) => n.id)}
                />
              </div>
              <div>
                ${cheminResult.edges.map((e) => html`
                  <div class="chain-item" key=${e.id}>
                    <div class="chain-dot"></div>
                    <div class="mono" style=${{ fontSize: "12px" }}>${e.source} → ${e.target} (${e.type_relation}, poids ${e.poids})</div>
                  </div>
                `)}
              </div>
            `}
          </div>
        ` : null}
      </div>

      <${ResourcePage}
        title="Liens (table brute)"
        sub="Édition directe des liens personne-personne. Les liens 'proprietaire' avec un véhicule sont déduits automatiquement et n'apparaissent pas ici."
        loading=${rows === null}
        rows=${rows || []}
        columns=${[
          { key: "personne_a_id", label: "Personne A", render: (r) => html`<span class="mono" style=${{ fontSize: "11px" }}>${r.personne_a_id}</span>` },
          { key: "type_relation", label: "Type de relation" },
          { key: "personne_b_id", label: "Personne B", render: (r) => html`<span class="mono" style=${{ fontSize: "11px" }}>${r.personne_b_id}</span>` },
          { key: "poids", label: "Poids" },
        ]}
        canCreate=${hasRole(auth.user, WRITE_ROLES)}
        createFields=${[
          { name: "personne_a_id", label: "ID personne A", required: true },
          { name: "personne_b_id", label: "ID personne B", required: true },
          { name: "type_relation", label: "Type de relation (famille, complice…)", required: true },
          { name: "poids", label: "Poids", type: "number", default: "1" },
          { name: "source_incident_id", label: "Incident source (optionnel)" },
        ]}
        onCreate=${async (values) => {
          await Api.createRelation({ ...values, poids: values.poids ? parseInt(values.poids, 10) : 1 });
          load();
          loadGraphe();
        }}
      />
    </div>
  `;
}

// ---------------------------------------------------------------------------
// ANPR
// ---------------------------------------------------------------------------
function AnprDetectionPanel({ onDetected }) {
  const fileRef = React.useRef(null);
  const [busy, setBusy] = useState(false);
  const [cameraId, setCameraId] = useState("");
  const [result, setResult] = useState(null);

  const analyser = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await Api.createLectureDepuisImage(file, { camera_id: cameraId || undefined });
      setResult(res);
      if (res.alerte) notifyWarn(`Alerte : ${res.motif_alerte || "véhicule signalé"}`);
      else notifyOk(`Plaque détectée : ${res.lecture.plaque_lue}`);
      onDetected();
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const choisirCandidat = async (texte) => {
    if (!result) return;
    try {
      const corrige = await Api.corrigerLecture(result.lecture.id, texte);
      notifyOk(`Lecture corrigée : ${texte}`);
      setResult({ ...result, lecture: corrige.lecture, vehicule_reconnu: corrige.vehicule_reconnu, alerte: corrige.alerte, motif_alerte: corrige.motif_alerte });
      onDetected();
    } catch (err) { notifyError(err); }
  };

  return html`
    <div class="panel">
      <p class="panel-title">Détecter une plaque depuis une image</p>
      <div class="field-row">
        <${Field} label="ID caméra (optionnel)">
          <input value=${cameraId} onChange=${(e) => setCameraId(e.target.value)} />
        <//>
        <${Field} label="Image (JPEG/PNG)">
          <input ref=${fileRef} type="file" accept="image/*" disabled=${busy} onChange=${analyser} />
        <//>
      </div>
      ${busy ? html`<p class="page-sub">Analyse en cours (détection + OCR)…</p>` : null}
      ${result ? html`
        <div style=${{ marginTop: "10px" }}>
          <p>
            Lecture retenue : <span class="mono">${result.lecture.plaque_lue}</span>
            (confiance ${result.lecture.confiance_ocr != null ? Math.round(result.lecture.confiance_ocr * 100) + "%" : "—"})
            ${result.alerte ? html`<span class="pill" style=${{ marginLeft: "8px", color: "var(--danger)" }}>ALERTE — ${result.motif_alerte}</span>` : null}
          </p>
          ${result.candidats && result.candidats.length > 1 ? html`
            <p class="page-sub">Autres lectures possibles détectées sur l'image — cliquer pour corriger si l'OCR s'est trompé :</p>
            <div style=${{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              ${result.candidats.map((c) => html`
                <button
                  key=${c.texte}
                  class="btn ghost small"
                  disabled=${c.texte === result.lecture.plaque_lue}
                  onClick=${() => choisirCandidat(c.texte)}
                >
                  ${c.texte} (${Math.round(c.confiance * 100)}%)
                </button>
              `)}
            </div>
          ` : null}
        </div>
      ` : null}
    </div>
  `;
}

function AnprVideoPanel({ onDetected }) {
  const fileRef = React.useRef(null);
  const [busy, setBusy] = useState(false);
  const [cameraId, setCameraId] = useState("");
  const [urlFlux, setUrlFlux] = useState("");
  const [intervalle, setIntervalle] = useState("1");
  const [result, setResult] = useState(null);

  const lancer = async (source) => {
    setBusy(true);
    setResult(null);
    try {
      const res = await Api.createLecturesDepuisVideo(source, {
        camera_id: cameraId || undefined,
        intervalle_secondes: intervalle ? parseFloat(intervalle) : undefined,
      });
      setResult(res);
      const alertes = res.lectures.filter((l) => l.alerte);
      if (alertes.length) notifyWarn(`${alertes.length} alerte(s) — ${alertes.map((a) => a.motif_alerte).join(" ; ")}`);
      else notifyOk(`${res.lectures.length} plaque(s) distincte(s) détectée(s).`);
      onDetected();
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onFile = (e) => {
    const file = e.target.files[0];
    if (file) lancer(file);
  };

  const onFlux = (e) => {
    e.preventDefault();
    if (urlFlux.trim()) lancer(urlFlux.trim());
  };

  return html`
    <div class="panel">
      <p class="panel-title">Détecter des plaques sur une vidéo ou un flux caméra</p>
      <div class="field-row">
        <${Field} label="ID caméra (optionnel)">
          <input value=${cameraId} onChange=${(e) => setCameraId(e.target.value)} />
        <//>
        <${Field} label="Intervalle d'échantillonnage (s)" hint="Une frame analysée toutes les N secondes">
          <input type="number" step="0.1" min="0.2" value=${intervalle} onChange=${(e) => setIntervalle(e.target.value)} />
        <//>
      </div>
      <div class="field-row">
        <${Field} label="Fichier vidéo (mp4, mov, avi, webm, mkv)">
          <input ref=${fileRef} type="file" accept="video/*" disabled=${busy} onChange=${onFile} />
        <//>
      </div>
      <form onSubmit=${onFlux} class="field-row" style=${{ alignItems: "flex-end" }}>
        <${Field} label="ou URL de flux caméra en direct" hint="ex. rtsp://... ou http://.../mjpeg — non stocké, seules les frames avec plaque détectée sont conservées">
          <input value=${urlFlux} disabled=${busy} onChange=${(e) => setUrlFlux(e.target.value)} placeholder="rtsp://..." />
        <//>
        <button class="btn" type="submit" disabled=${busy || !urlFlux.trim()}>Analyser le flux</button>
      </form>
      ${busy ? html`<p class="page-sub">Analyse en cours (échantillonnage + détection + OCR sur la vidéo/le flux)…</p>` : null}
      ${result ? html`
        <div style=${{ marginTop: "10px" }}>
          <p class="page-sub">
            ${result.frames_analysees} frame(s) analysée(s)${result.duree_video_s != null ? ` sur une vidéo de ${result.duree_video_s}s` : ""}
            — ${result.lectures.length} plaque(s) distincte(s) trouvée(s).
          </p>
          ${result.lectures.map((l) => html`
            <p key=${l.lecture.id}>
              <span class="mono">${l.lecture.plaque_lue}</span>
              à ${l.timestamp_s}s
              (confiance ${l.lecture.confiance_ocr != null ? Math.round(l.lecture.confiance_ocr * 100) + "%" : "—"})
              ${l.alerte ? html`<span class="pill" style=${{ marginLeft: "8px", color: "var(--danger)" }}>ALERTE — ${l.motif_alerte}</span>` : null}
            </p>
          `)}
        </div>
      ` : null}
    </div>
  `;
}

function AnprPage() {
  const auth = useAuth();
  const [rows, setRows] = useState(null);
  const load = useCallback(() => Api.listLectures().then(setRows).catch((e) => { notifyError(e); setRows([]); }), []);
  useEffect(load, [load]);

  const canWrite = hasRole(auth.user, WRITE_ROLES);

  const corriger = async (row) => {
    const nouvelle = window.prompt("Corriger la plaque lue :", row.plaque_lue);
    if (!nouvelle || nouvelle === row.plaque_lue) return;
    try {
      const res = await Api.corrigerLecture(row.id, nouvelle);
      if (res.alerte) notifyWarn(`Alerte : ${res.motif_alerte || "véhicule signalé"}`);
      else notifyOk("Lecture corrigée.");
      load();
    } catch (err) { notifyError(err); }
  };

  return html`
    <div>
      ${canWrite ? html`<${AnprDetectionPanel} onDetected=${load} />` : null}
      ${canWrite ? html`<${AnprVideoPanel} onDetected=${load} />` : null}
      <${ResourcePage}
        title="Lectures ANPR"
        sub="Lectures de plaques (saisie manuelle, image ou vidéo/flux caméra) rapprochées automatiquement de la base véhicules."
        loading=${rows === null}
        rows=${rows || []}
        columns=${[
          { key: "plaque_lue", label: "Plaque", render: (r) => html`<span class="mono">${r.plaque_lue}</span>` },
          { key: "date_heure", label: "Date", render: (r) => fmtDate(r.date_heure) },
          {
            key: "source", label: "Source", render: (r) => html`<span class="pill">${
              r.source === "image" ? "Image (auto)" : r.source === "video" ? `Vidéo (auto${r.video_timestamp_s != null ? `, ${r.video_timestamp_s}s` : ""})` : "Manuel"
            }</span>`,
          },
          { key: "camera_id", label: "Caméra" },
          { key: "confiance_ocr", label: "Confiance OCR", render: (r) => r.confiance_ocr != null ? `${Math.round(r.confiance_ocr * 100)}%` : "—" },
          { key: "vehicule_id", label: "Véhicule rapproché", render: (r) => r.vehicule_id ? html`<span class="mono" style=${{ fontSize: "11px" }}>${r.vehicule_id}</span>` : "—" },
          {
            key: "actions", label: "Actions", render: (r) => html`
              <div style=${{ display: "flex", gap: "6px" }}>
                ${r.image_chemin ? html`<button class="btn ghost small" onClick=${() => Api.downloadLectureImage(r.id)}>Image</button>` : null}
                ${canWrite ? html`<button class="btn ghost small" onClick=${() => corriger(r)}>Corriger</button>` : null}
              </div>
            `,
          },
        ]}
        canCreate=${canWrite}
        createFields=${[
          { name: "plaque_lue", label: "Plaque lue", required: true },
          { name: "date_heure", label: "Date et heure", type: "datetime-local" },
          { name: "camera_id", label: "ID caméra" },
          { name: "confiance_ocr", label: "Confiance OCR (0 à 1)", type: "number", step: "0.01" },
          { name: "latitude", label: "Latitude", type: "number", step: "any" },
          { name: "longitude", label: "Longitude", type: "number", step: "any" },
        ]}
        onCreate=${async (values) => {
          const payload = {
            ...values,
            date_heure: values.date_heure ? new Date(values.date_heure).toISOString() : undefined,
            confiance_ocr: values.confiance_ocr ? parseFloat(values.confiance_ocr) : undefined,
            latitude: values.latitude ? parseFloat(values.latitude) : undefined,
            longitude: values.longitude ? parseFloat(values.longitude) : undefined,
          };
          const res = await Api.createLecture(payload);
          if (res.alerte) notifyWarn(`Alerte : ${res.motif_alerte || "véhicule signalé"}`);
          else notifyOk("Lecture ANPR enregistrée.");
          load();
        }}
      />
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Journal d'audit
// ---------------------------------------------------------------------------
function AuditPage() {
  const [rows, setRows] = useState(null);
  useEffect(() => { Api.listAudit().then(setRows).catch((e) => { notifyError(e); setRows([]); }); }, []);

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">Journal d'audit</div>
          <div class="page-sub">Trace de toutes les actions sensibles effectuées sur la plateforme.</div>
        </div>
      </div>
      <div class="panel">
        ${rows === null ? html`<${Loading} />` : (rows.length === 0 ? html`<${Empty} />` : html`
          <table>
            <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Ressource</th><th>Détails</th><th>IP</th></tr></thead>
            <tbody>
              ${rows.map((r) => html`
                <tr key=${r.id}>
                  <td class="mono" style=${{ fontSize: "11.5px" }}>${fmtDate(r.date_heure)}</td>
                  <td>${r.utilisateur_email || "—"}</td>
                  <td><span class="pill">${r.action}</span></td>
                  <td>${r.ressource_type}</td>
                  <td style=${{ fontSize: "12.5px", color: "var(--text-dim)" }}>${r.details || "—"}</td>
                  <td class="mono" style=${{ fontSize: "11px" }}>${r.adresse_ip || "—"}</td>
                </tr>
              `)}
            </tbody>
          </table>
        `)}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// RGPD — purge
// ---------------------------------------------------------------------------
function RgpdPage() {
  const [retention, setRetention] = useState("");
  const [candidats, setCandidats] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const loadCandidats = useCallback(() => {
    Api.rgpdCandidats(retention || undefined).then(setCandidats).catch((e) => { notifyError(e); setCandidats([]); });
  }, [retention]);
  useEffect(loadCandidats, [loadCandidats]);

  const runPurge = async () => {
    if (!window.confirm("Cette opération est irréversible. Lancer la purge RGPD maintenant ?")) return;
    setBusy(true);
    try {
      const res = await Api.rgpdPurge(retention || undefined);
      setResult(res);
      notifyOk(`Purge effectuée : ${res.personnes_anonymisees} fiche(s) anonymisée(s).`);
      loadCandidats();
    } catch (err) { notifyError(err); } finally { setBusy(false); }
  };

  return html`
    <div>
      <div class="topline">
        <div>
          <div class="page-title">Purge RGPD</div>
          <div class="page-sub">Anonymisation des fiches individus liées à des dossiers clos anciens.</div>
        </div>
      </div>

      <div class="panel">
        <p class="panel-title">Durée de rétention</p>
        <div style=${{ display: "flex", gap: "10px", alignItems: "flex-end" }}>
          <${Field} label="Jours de rétention (laisser vide pour la valeur par défaut)">
            <input type="number" value=${retention} onChange=${(e) => setRetention(e.target.value)} placeholder="ex. 365" />
          <//>
          <button class="btn ghost" style=${{ marginBottom: "14px" }} onClick=${loadCandidats}>Recalculer</button>
        </div>
      </div>

      <div class="panel">
        <p class="panel-title">Candidats à la purge (mode à blanc, rien n'est modifié)</p>
        ${candidats === null ? html`<${Loading} />` : (candidats.length === 0 ? html`<${Empty} label="Aucun dossier éligible à la purge." />` : html`
          <table>
            <thead><tr><th>Incident</th><th>Statut</th><th>Personnes anonymisables</th></tr></thead>
            <tbody>
              ${candidats.map((c) => html`
                <tr key=${c.incident_id}>
                  <td class="mono" style=${{ fontSize: "11.5px" }}>${c.incident_id}</td>
                  <td><${Stamp} text=${c.statut} kind=${statutKind(c.statut)} /></td>
                  <td>${c.nombre_personnes_anonymisables}</td>
                </tr>
              `)}
            </tbody>
          </table>
        `)}
        <button class="btn danger" style=${{ marginTop: "16px" }} onClick=${runPurge} disabled=${busy || (candidats && candidats.length === 0)}>
          ${busy ? "Purge en cours…" : "Lancer la purge maintenant"}
        </button>
        ${result ? html`
          <div class="kv" style=${{ marginTop: "16px" }}>
            <dt>Rétention appliquée</dt><dd>${result.retention_days} jours</dd>
            <dt>Incidents concernés</dt><dd>${result.incidents_concernes}</dd>
            <dt>Personnes anonymisées</dt><dd>${result.personnes_anonymisees}</dd>
          </div>
        ` : null}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Comptes utilisateurs
// ---------------------------------------------------------------------------
function UsersPage() {
  const [rows, setRows] = useState(null);
  const load = useCallback(() => Api.listUsers().then(setRows).catch((e) => { notifyError(e); setRows([]); }), []);
  useEffect(load, [load]);

  return html`
    <${ResourcePage}
      title="Comptes utilisateurs"
      sub="Gestion des accès (rôles RBAC : enquêteur, analyste, OPJ, administrateur)."
      loading=${rows === null}
      rows=${rows || []}
      columns=${[
        { key: "email", label: "Email" },
        { key: "nom", label: "Nom" },
        { key: "prenom", label: "Prénom" },
        { key: "role", label: "Rôle", render: (r) => html`<span class="badge-role">${r.role}</span>` },
        { key: "actif", label: "Actif", render: (r) => r.actif ? html`<${Stamp} text="Actif" kind="ok" />` : html`<${Stamp} text="Désactivé" kind="danger" />` },
        { key: "date_creation", label: "Créé le", render: (r) => fmtDate(r.date_creation) },
      ]}
      canCreate=${true}
      createFields=${[
        { name: "email", label: "Email", type: "email", required: true },
        { name: "password", label: "Mot de passe (8 caractères min.)", type: "password", required: true },
        { name: "nom", label: "Nom", required: true },
        { name: "prenom", label: "Prénom", required: true },
        { name: "role", label: "Rôle", type: "select", options: ["enqueteur", "analyste", "opj", "administrateur"], default: "enqueteur" },
      ]}
      onCreate=${async (values) => { await Api.createUser(values); load(); }}
    />
  `;
}

// ---------------------------------------------------------------------------
// Garde d'accès par rôle
// ---------------------------------------------------------------------------
function RequireRole({ roles, children }) {
  const auth = useAuth();
  if (!hasRole(auth.user, roles)) {
    return html`
      <div class="panel">
        <p class="panel-title">Accès refusé</p>
        <p style=${{ fontSize: "13.5px", color: "var(--text-dim)" }}>Ton rôle (<span class="mono">${auth.user ? auth.user.role : "?"}</span>) ne permet pas d'accéder à cette section.</p>
      </div>
    `;
  }
  return children;
}

// ---------------------------------------------------------------------------
// Application racine
// ---------------------------------------------------------------------------
function AppShell() {
  const hash = useHashRoute();

  let content;
  const incidentMatch = /^#\/incidents\/([^/]+)$/.exec(hash);
  const preuveMatch = /^#\/preuves\/([^/]+)$/.exec(hash);

  if (hash === "#/" || hash === "") content = html`<${Dashboard} />`;
  else if (hash === "#/carte") content = html`<${CartePage} />`;
  else if (hash === "#/incidents") content = html`<${IncidentsListPage} />`;
  else if (incidentMatch) content = html`<${IncidentDetailPage} id=${incidentMatch[1]} />`;
  else if (hash === "#/personnes") content = html`<${PersonnesPage} />`;
  else if (hash === "#/vehicules") content = html`<${VehiculesPage} />`;
  else if (hash === "#/preuves") content = html`<${PreuvesListPage} />`;
  else if (preuveMatch) content = html`<${PreuveDetailPage} id=${preuveMatch[1]} />`;
  else if (hash === "#/relations") content = html`<${RelationsPage} />`;
  else if (hash === "#/anpr") content = html`<${AnprPage} />`;
  else if (hash === "#/audit") content = html`<${RequireRole} roles=${AUDIT_ROLES}><${AuditPage} /><//>`;
  else if (hash === "#/rgpd") content = html`<${RequireRole} roles=${ADMIN_ROLES}><${RgpdPage} /><//>`;
  else if (hash === "#/utilisateurs") content = html`<${RequireRole} roles=${ADMIN_ROLES}><${UsersPage} /><//>`;
  else content = html`<div class="panel"><p class="panel-title">Introuvable</p><p>Cette page n'existe pas.</p></div>`;

  return html`
    <div class="shell">
      <${Sidebar} current=${hash} />
      <div class="main">${content}</div>
    </div>
  `;
}

function App() {
  const [user, setUser] = useState(TokenStore.user);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!TokenStore.access) { setChecking(false); return; }
    Api.me()
      .then((me) => setUser({ role: me.role, nom: me.nom, prenom: me.prenom }))
      .catch(() => { TokenStore.clear(); setUser(null); })
      .finally(() => setChecking(false));
  }, []);

  const authValue = useMemo(() => ({
    user,
    login: async (email, password) => {
      const data = await Api.login(email, password);
      setUser({ role: data.role, nom: data.nom, prenom: data.prenom });
    },
    logout: async () => {
      await Api.logout();
      setUser(null);
      navigate("#/login");
    },
  }), [user]);

  if (checking) {
    return html`<div class="login-wrap"><${Loading} label="Vérification de la session…" /></div>`;
  }

  return html`
    <${AuthContext.Provider} value=${authValue}>
      ${!user ? html`<${LoginPage} />` : html`<${AppShell} />`}
      <${ToastHost} />
    <//>
  `;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);

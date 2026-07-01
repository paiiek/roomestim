// D29: this file performs ZERO physics — every metric is read verbatim from the
// /api/evaluate response; seed positions are literal UI data.
//
// immersive-layout P5.2 / ADR 0061 — static Three.js viewer (orbit camera only,
// no drag yet; drag is P5.3). Loads ONE built-in room, renders its geometry +
// literal seed speakers, POSTs the seed layout to /api/evaluate once, and paints
// the returned 4-axis report + honesty banner. No SPL/angle/RT60 math here.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const ROOM_ID = "builtin:shoebox";

// Literal initial speaker data (NOT computed via trig). Positions sit inside the
// 5x4x3 m origin-centred shoebox: x in [-2.5,2.5], y=1.2, z in [-2,2].
const SEED = [
  { channel: 1, position: { x: -1.5, y: 1.2, z: 1.8 }, aim_direction: null },  // FL
  { channel: 2, position: { x: 1.5, y: 1.2, z: 1.8 }, aim_direction: null },   // FR
  { channel: 3, position: { x: -2.0, y: 1.2, z: 0.0 }, aim_direction: null },  // SL
  { channel: 4, position: { x: 2.0, y: 1.2, z: 0.0 }, aim_direction: null },   // SR
  { channel: 5, position: { x: -1.5, y: 1.2, z: -1.8 }, aim_direction: null }, // BL
  { channel: 6, position: { x: 1.5, y: 1.2, z: -1.8 }, aim_direction: null },  // BR
];

// ---- DOM helpers ---------------------------------------------------------

const $ = (id) => document.getElementById(id);

function setStatus(text, isError) {
  const el = $("status");
  el.textContent = text;
  el.classList.toggle("error", !!isError);
}

function setDisclaimer(text, isError) {
  const el = $("disclaimer");
  el.textContent = text;
  el.classList.toggle("error", !!isError);
}

function metricRow(key, value, cls) {
  const row = document.createElement("div");
  row.className = "metric";
  const k = document.createElement("span");
  k.className = "k";
  k.textContent = key;
  const v = document.createElement("span");
  v.className = "v" + (cls ? " " + cls : "");
  v.textContent = value;
  row.appendChild(k);
  row.appendChild(v);
  return row;
}

function renderAxis(containerId, rows) {
  const el = $(containerId);
  el.replaceChildren();
  for (const [k, v, cls] of rows) el.appendChild(metricRow(k, v, cls));
}

// Fallback: render whatever keys a sub-dict actually has, without guessing.
function renderGeneric(containerId, obj) {
  const rows = [];
  for (const [k, v] of Object.entries(obj || {})) {
    if (k === "note") continue;
    rows.push([k, typeof v === "object" ? JSON.stringify(v) : String(v)]);
  }
  renderAxis(containerId, rows);
}

// ---- Three.js scene ------------------------------------------------------

let renderer, scene, camera, controls;

function initScene(container) {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0e1013);

  const w = container.clientWidth || 800;
  const h = container.clientHeight || 600;
  camera = new THREE.PerspectiveCamera(55, w / h, 0.05, 100);
  camera.position.set(5, 4, 6);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(w, h);
  container.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 1.0, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(4, 8, 5);
  scene.add(dir);

  window.addEventListener("resize", () => {
    const cw = container.clientWidth || 800;
    const ch = container.clientHeight || 600;
    camera.aspect = cw / ch;
    camera.updateProjectionMatrix();
    renderer.setSize(cw, ch);
  });

  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();
}

function buildRoom(geom) {
  // Floor: a THREE.Shape from floor_polygon (map x->x, z->z), laid flat at y=0.
  const floorPts = geom.floor_polygon.map((p) => new THREE.Vector2(p.x, p.z));
  const floorShape = new THREE.Shape(floorPts);
  const floorGeo = new THREE.ShapeGeometry(floorShape);
  const floorMat = new THREE.MeshStandardMaterial({
    color: 0x2b3440, side: THREE.DoubleSide,
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2; // shape XY-plane -> world XZ-plane
  scene.add(floor);

  // Walls: wireframe line loops of each wall polygon (already 3-D {x,y,z}).
  const wallMat = new THREE.LineBasicMaterial({ color: 0x5a6675 });
  for (const wall of geom.walls || []) {
    const pts = wall.polygon.map((p) => new THREE.Vector3(p.x, p.y, p.z));
    if (pts.length) pts.push(pts[0].clone()); // close the loop
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    scene.add(new THREE.Line(g, wallMat));
  }

  // Listener-area patch: semi-transparent, hovering just above the floor.
  const la = geom.listener_area;
  if (la && la.polygon && la.polygon.length) {
    const laPts = la.polygon.map((p) => new THREE.Vector2(p.x, p.z));
    const laGeo = new THREE.ShapeGeometry(new THREE.Shape(laPts));
    const laMat = new THREE.MeshBasicMaterial({
      color: 0x5aa9e6, transparent: true, opacity: 0.25, side: THREE.DoubleSide,
    });
    const patch = new THREE.Mesh(laGeo, laMat);
    patch.rotation.x = -Math.PI / 2;
    patch.position.y = 0.02;
    scene.add(patch);
  }
}

function addSpeakers(seed) {
  const sphereGeo = new THREE.SphereGeometry(0.12, 20, 16);
  const mat = new THREE.MeshStandardMaterial({ color: 0xe0b341 });
  for (const s of seed) {
    const m = new THREE.Mesh(sphereGeo, mat);
    m.position.set(s.position.x, s.position.y, s.position.z);
    scene.add(m);
  }
}

// ---- Report rendering ----------------------------------------------------

function fmt(v, suffix = "") {
  if (v === null || v === undefined) return "—";
  return (typeof v === "number" ? v : String(v)) + suffix;
}

function renderReport(report) {
  setStatus(
    `${report.layout_name} · ${report.target_algorithm} · ${report.n_speakers} speakers`,
    false
  );

  // Honesty banner: surface note + spl_provenance + rt60.source (mirror the
  // Gradio _build_disclaimer wording; NOT buried).
  const rt60 = report.rt60 || {};
  setDisclaimer(
    "Immersive trade-off — relative comparison guidance (not a guaranteed measurement).\n" +
      `SPL provenance: ${fmt(report.spl_provenance)} ` +
      "(absolute SPL/headroom is meaningful only when 'datasheet'; 'estimate' is a preview)\n" +
      `RT60 source: ${fmt(rt60.source)} ('measured' = engineer-injected, 'predicted' = model estimate)\n` +
      fmt(report.note),
    false
  );

  // Level / SPL axis — real keys: report.spl_headroom_db, meets_target_spl,
  // report.spl.{min_spl_db,mean_spl_db,max_spl_db,uniformity_db}.
  const spl = report.spl || {};
  renderAxis("axis-spl", [
    ["target SPL (dB)", fmt(report.target_spl_db)],
    ["headroom (dB)", fmt(report.spl_headroom_db), report.meets_target_spl ? "good" : "bad"],
    ["meets target", fmt(report.meets_target_spl), report.meets_target_spl ? "good" : "bad"],
    ["min SPL (dB)", fmt(spl.min_spl_db)],
    ["mean SPL (dB)", fmt(spl.mean_spl_db)],
    ["max SPL (dB)", fmt(spl.max_spl_db)],
    ["uniformity (dB)", fmt(spl.uniformity_db)],
    ["provenance", fmt(report.spl_provenance)],
  ]);

  // Panning / angular — real keys: min/mean/max_nn_gap_deg, uniformity.
  const ang = report.angular;
  if (ang) {
    renderAxis("axis-angular", [
      ["min gap (deg)", fmt(ang.min_nn_gap_deg)],
      ["mean gap (deg)", fmt(ang.mean_nn_gap_deg)],
      ["max gap (deg)", fmt(ang.max_nn_gap_deg)],
      ["uniformity", fmt(ang.uniformity)],
    ]);
  } else {
    renderGeneric("axis-angular", ang);
  }

  // Separation / interference — real keys: min_separation_deg,
  // min_pair_separation_deg, n_close_pairs.
  const itf = report.interference;
  if (itf) {
    renderAxis("axis-interference", [
      ["min separation (deg)", fmt(itf.min_separation_deg)],
      ["min pair sep (deg)", fmt(itf.min_pair_separation_deg)],
      ["close pairs", fmt(itf.n_close_pairs)],
    ]);
  } else {
    renderGeneric("axis-interference", itf);
  }

  // Cost — real keys: total_price, n_speakers, n_priced, complete.
  const cost = report.cost || {};
  renderAxis("axis-cost", [
    ["total price", cost.total_price === null ? "unpriced (not a quote)" : fmt(cost.total_price)],
    ["priced", `${fmt(cost.n_priced)} / ${fmt(cost.n_speakers)}`],
    ["complete", fmt(cost.complete)],
  ]);

  // RT60 context — real keys: predicted_s, measured_s, effective_s, source.
  renderAxis("axis-rt60", [
    ["effective (s)", fmt(rt60.effective_s)],
    ["predicted (s)", fmt(rt60.predicted_s)],
    ["measured (s)", fmt(rt60.measured_s)],
    ["source", fmt(rt60.source)],
    ["predictor", fmt(rt60.predictor_name)],
  ]);
}

// Standing honesty line kept visible even on error (the banner is "persistent" —
// HARD CONSTRAINT 1); the specific failure goes to #status, not over the banner.
const STANDING_DISCLAIMER =
  "Immersive trade-off — relative comparison guidance (not a guaranteed measurement).";

function showError(message) {
  setStatus(message || "Request failed.", true);
  setDisclaimer(
    STANDING_DISCLAIMER + "\nEvaluation failed — see the status panel for details.",
    true
  );
}

// ---- Boot flow -----------------------------------------------------------

async function main() {
  initScene($("scene"));

  // 1. Fetch room geometry and build the scene.
  try {
    const geoResp = await fetch("/api/rooms/" + encodeURIComponent(ROOM_ID));
    if (!geoResp.ok) {
      showError("Failed to load room geometry (HTTP " + geoResp.status + ").");
      return;
    }
    const geom = await geoResp.json();
    buildRoom(geom);
    addSpeakers(SEED);
  } catch (err) {
    showError("Failed to load room geometry.");
    return;
  }

  // 2. Build the seed evaluate request (matches schemas.EvaluateRequest).
  const body = {
    room_id: ROOM_ID,
    placement: {
      target_algorithm: "vbap",
      regularity_hint: "ring",
      layout_name: "live-edit",
      speakers: SEED,
    },
    spec: { model_key: "generic_surround_compact", price: null },
    params: { drive_w: 10.0, target_spl_db: 85.0, measured_rt60_s: null },
  };

  // 3. POST /api/evaluate and render the report (or the error envelope).
  try {
    const resp = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => null);
    if (!resp.ok || !data || data.ok !== true) {
      const msg = data && data.error ? data.error.message : "Evaluation failed.";
      showError(msg);
      return;
    }
    renderReport(data.report);
  } catch (err) {
    showError("Evaluation request failed.");
  }
}

main();

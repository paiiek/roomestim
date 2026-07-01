// D29: this file performs ZERO physics — every metric is read verbatim from the
// /api/evaluate response, every seeded speaker layout comes verbatim from the
// /api/place response, the spec dropdown comes verbatim from /api/specs, and an
// uploaded room.yaml is parsed ENTIRELY server-side by core read_room_yaml
// (POST /api/rooms/upload), an uploaded Apple RoomPlan JSON sidecar by core
// RoomPlanAdapter (POST /api/rooms/upload/roomplan), an uploaded Apple
// CapturedStructure multi-room export by core parse_structure
// (POST /api/rooms/upload/structure → N rooms), and the bundled examples by the
// same server paths (GET /api/examples + POST /api/examples/{id}/load).
// "Export trade-off JSON" downloads the exact report object the server already
// returned — NO recompute, NO client-side physics. Dragging only moves a
// speaker's {x,z} (keeps y) — that's UI geometry. The room-picker just re-selects
// among the already-parsed, already-registered rooms (no physics).
//
// immersive-layout P5.6 / ADR 0061 — multi-room CapturedStructure upload + bundled
// example loader + room-picker. Builds on P5.2 (static viewer) + P5.3 (draggable
// speakers + live re-evaluate) + P5.4 (spec/params/export) + P5.5 (RoomPlan single).

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// Mutable current room id — starts on the built-in shoebox, is replaced by the
// returned "uploaded:<n>" id after a successful room.yaml upload. Used by every
// evaluate/place/geometry request so the whole viewer follows the active room.
let currentRoomId = "builtin:shoebox";

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

// Mutable layout metadata forwarded verbatim into the /api/evaluate placement
// block; re-seeding via /api/place overwrites it from the core response.
let layoutMeta = {
  target_algorithm: "vbap",
  regularity_hint: "ring",
  layout_name: "live-edit",
};

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

// Speaker meshes are the source of truth for live positions. Each mesh carries
// its channel + aim_direction in userData so a drag only mutates x,z.
let speakerMeshes = [];
const _sphereGeo = new THREE.SphereGeometry(0.12, 20, 16);
const _speakerMat = new THREE.MeshStandardMaterial({ color: 0xe0b341 });

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

  initDrag();

  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();
}

// Room geometry meshes (floor, walls, listener patch) added by buildRoom —
// tracked so an upload can clear the previous room before rebuilding.
let roomMeshes = [];

// Remove + dispose the current room geometry meshes (NOT the speakers). Called
// before rebuilding the scene for an uploaded room.
function clearRoomMeshes() {
  for (const m of roomMeshes) {
    scene.remove(m);
    if (m.geometry) m.geometry.dispose();
  }
  roomMeshes = [];
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
  roomMeshes.push(floor);

  // Walls: wireframe line loops of each wall polygon (already 3-D {x,y,z}).
  const wallMat = new THREE.LineBasicMaterial({ color: 0x5a6675 });
  for (const wall of geom.walls || []) {
    const pts = wall.polygon.map((p) => new THREE.Vector3(p.x, p.y, p.z));
    if (pts.length) pts.push(pts[0].clone()); // close the loop
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.Line(g, wallMat);
    scene.add(line);
    roomMeshes.push(line);
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
    roomMeshes.push(patch);
  }
}

// Replace the on-screen speaker meshes from a list of {channel, position,
// aim_direction} entries. Positions/aim are literal UI data (from SEED or the
// /api/place response), never computed here.
function setSpeakers(list) {
  for (const m of speakerMeshes) scene.remove(m);
  speakerMeshes = [];
  for (const s of list) {
    const m = new THREE.Mesh(_sphereGeo, _speakerMat);
    m.position.set(s.position.x, s.position.y, s.position.z);
    m.userData.channel = s.channel;
    m.userData.aim_direction = s.aim_direction ?? null;
    scene.add(m);
    speakerMeshes.push(m);
  }
}

// Serialise the CURRENT speaker meshes into an /api/evaluate speakers[] payload.
// Reads x,y,z straight off the mesh (drag mutates x,z, keeps y). No trig.
function speakersFromMeshes() {
  return speakerMeshes.map((m) => ({
    channel: m.userData.channel,
    position: { x: m.position.x, y: m.position.y, z: m.position.z },
    aim_direction: m.userData.aim_direction ?? null,
  }));
}

// ---- Drag (manual raycaster onto a horizontal +Y plane) ------------------
// D29 note: this is pure UI geometry — a screen ray intersected with a floor-
// parallel plane to reposition a sphere's x,z. No acoustics is computed here.

const _raycaster = new THREE.Raycaster();
const _pointer = new THREE.Vector2();
const _dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hitPoint = new THREE.Vector3();
let _dragged = null;
let _dragMoved = false;

function _updatePointer(ev) {
  const rect = renderer.domElement.getBoundingClientRect();
  _pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
  _pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
}

function initDrag() {
  const canvas = renderer.domElement;

  canvas.addEventListener("pointerdown", (ev) => {
    _updatePointer(ev);
    _raycaster.setFromCamera(_pointer, camera);
    const hits = _raycaster.intersectObjects(speakerMeshes, false);
    if (!hits.length) return;
    _dragged = hits[0].object;
    _dragMoved = false;
    // Horizontal plane through the speaker's current height: y = const.
    _dragPlane.set(new THREE.Vector3(0, 1, 0), -_dragged.position.y);
    controls.enabled = false; // stop OrbitControls fighting the drag
    canvas.setPointerCapture(ev.pointerId);
  });

  canvas.addEventListener("pointermove", (ev) => {
    if (!_dragged) return;
    _updatePointer(ev);
    _raycaster.setFromCamera(_pointer, camera);
    if (_raycaster.ray.intersectPlane(_dragPlane, _hitPoint)) {
      _dragged.position.x = _hitPoint.x; // keep y — drag is horizontal only
      _dragged.position.z = _hitPoint.z;
      _dragMoved = true;
    }
  });

  function endDrag(ev) {
    if (!_dragged) return;
    _dragged = null;
    controls.enabled = true;
    try {
      canvas.releasePointerCapture(ev.pointerId);
    } catch (_e) { /* pointer may already be released */ }
    if (_dragMoved) scheduleEvaluate(); // debounced re-evaluate on release
    _dragMoved = false;
  }

  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);
}

// ---- Report rendering ----------------------------------------------------

function fmt(v, suffix = "") {
  if (v === null || v === undefined) return "—";
  return (typeof v === "number" ? v : String(v)) + suffix;
}

// The last SUCCESSFUL /api/evaluate report object, stored verbatim so "Export
// trade-off JSON" downloads EXACTLY what the server returned (no recompute, no
// drift — mirrors roomestim_web _on_export_tradeoff's write-what-was-shown rule).
let _lastReport = null;

function renderReport(report) {
  _lastReport = report;
  const btn = $("export");
  if (btn) btn.disabled = false;
  setStatus(
    `${report.layout_name} · ${report.target_algorithm} · ${report.n_speakers} speakers`,
    false
  );

  // Honesty banner: surface note + spl_provenance + rt60.source (mirror the
  // Gradio _build_disclaimer wording; NOT buried).
  const rt60 = report.rt60 || {};
  setDisclaimer(
    "Immersive trade-off — relative comparison guidance (not a guaranteed measurement).\n" +
      "Drag a speaker to move it; metrics update on release.\n" +
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

// ---- Live re-evaluate (shared by initial load, drag-end, and re-seed) -----

// Monotone request id so a slow older response can never overwrite a newer one.
let _evalSeq = 0;

// Read the spec/params blocks from the CURRENT form values — the single source
// of truth shared by initial load, drag-end, re-seed, and control-change. A blank
// RT60 field maps to null (→ core predicts RT60), NOT 0/NaN. These are forwarded
// verbatim to /api/evaluate; the server does all physics.
function readSpec() {
  const sel = $("spec");
  const key = sel && sel.value ? sel.value : "generic_surround_compact";
  return { model_key: key, price: null };
}

function _numOrDefault(id, fallback) {
  const raw = $(id).value;
  if (raw === "" || raw === null || raw === undefined) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

function readParams() {
  const rt60Raw = $("rt60").value;
  // Blank RT60 → null (predicted). A value is sent as-is; the server rejects a
  // non-positive injection (generic 400), so no client-side physics/clamping.
  const rt60 = rt60Raw === "" ? null : Number(rt60Raw);
  return {
    drive_w: _numOrDefault("drive", 10.0),
    target_spl_db: _numOrDefault("target", 85.0),
    measured_rt60_s: rt60 !== null && Number.isFinite(rt60) ? rt60 : null,
  };
}

async function evaluateAndRender(speakers) {
  const seq = ++_evalSeq;
  const body = {
    room_id: currentRoomId,
    placement: {
      target_algorithm: layoutMeta.target_algorithm,
      regularity_hint: layoutMeta.regularity_hint,
      layout_name: layoutMeta.layout_name,
      speakers,
    },
    spec: readSpec(),
    params: readParams(),
  };
  try {
    const resp = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => null);
    if (seq !== _evalSeq) return; // a newer evaluate superseded this one — drop it
    if (!resp.ok || !data || data.ok !== true) {
      const msg = data && data.error ? data.error.message : "Evaluation failed.";
      showError(msg);
      return;
    }
    renderReport(data.report);
  } catch (err) {
    if (seq !== _evalSeq) return;
    showError("Evaluation request failed.");
  }
}

let _debounceTimer = null;

function scheduleEvaluate() {
  if (_debounceTimer !== null) clearTimeout(_debounceTimer);
  _debounceTimer = setTimeout(() => {
    _debounceTimer = null;
    evaluateAndRender(speakersFromMeshes());
  }, 120);
}

// ---- Re-seed layout via /api/place ---------------------------------------

async function reseedLayout() {
  const algorithm = $("algo").value;
  const n = parseInt($("nspk").value, 10);
  const body = { room_id: currentRoomId, algorithm, n_speakers: n };
  setStatus(`Re-seeding (${algorithm}, n=${n})…`, false);
  try {
    const resp = await fetch("/api/place", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => null);
    if (!resp.ok || !data || data.ok !== true) {
      showError(data && data.error ? data.error.message : "Re-seed failed.");
      return;
    }
    const placement = data.placement;
    layoutMeta = {
      target_algorithm: placement.target_algorithm,
      regularity_hint: placement.regularity_hint,
      layout_name: placement.layout_name,
    };
    setSpeakers(placement.speakers);
    evaluateAndRender(speakersFromMeshes());
  } catch (err) {
    showError("Re-seed request failed.");
  }
}

// ---- Export trade-off JSON (verbatim last report — NO recompute) ---------

function exportTradeoff() {
  if (!_lastReport) return; // no-op until a report exists (button also disabled)
  // Download EXACTLY the dict the server returned — no physics, no re-derivation.
  const blob = new Blob([JSON.stringify(_lastReport, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "trade-off.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---- Spec dropdown (populated verbatim from GET /api/specs) ---------------

async function populateSpecs() {
  const sel = $("spec");
  if (!sel) return;
  try {
    const resp = await fetch("/api/specs");
    if (!resp.ok) return;
    const data = await resp.json();
    const specs = (data && data.specs) || [];
    sel.replaceChildren();
    for (const s of specs) {
      const opt = document.createElement("option");
      opt.value = s.model_key;
      // Label with provenance so the honesty of the numbers is visible in the UI
      // (e.g. "generic_surround_compact (estimate)"). textContent = XSS-safe.
      opt.textContent = `${s.model_key} (${s.provenance})`;
      sel.appendChild(opt);
    }
    // Default to generic_surround_compact when present (mirrors the P5.3 default).
    if ([...sel.options].some((o) => o.value === "generic_surround_compact")) {
      sel.value = "generic_surround_compact";
    }
  } catch (err) {
    /* leave the dropdown empty; readSpec() falls back to the default key */
  }
}

// ---- Load / upload a room (parsed entirely server-side by torch-free core) --
// Text formats share ONE switch flow: room.yaml (POST /api/rooms/upload, core
// read_room_yaml), an Apple RoomPlan JSON sidecar (POST /api/rooms/upload/roomplan,
// core RoomPlanAdapter → single room), an Apple CapturedStructure multi-room export
// (POST /api/rooms/upload/structure, core parse_structure → N rooms), and the
// bundled examples (POST /api/examples/{id}/load). D29: NO parsing or geometry math
// runs in the browser — the file/example text is parsed verbatim server-side.

// The rooms returned by the LAST multi-room result, indexed by the room-picker.
let _pickerRooms = [];

// Adopt a returned room geometry as the active room, rebuild the scene, keep the
// current speakers, and re-evaluate. Shared by every load/upload/pick path.
function switchToRoom(geom) {
  currentRoomId = geom.id;
  clearRoomMeshes();
  buildRoom(geom);
  evaluateAndRender(speakersFromMeshes());
}

// Populate (or hide) the room-picker from a list of returned room geometries.
function populateRoomPicker(rooms) {
  const sel = $("room-picker");
  const wrap = $("room-picker-wrap");
  if (!sel || !wrap) return;
  _pickerRooms = rooms || [];
  sel.replaceChildren();
  if (_pickerRooms.length <= 1) {
    wrap.style.display = "none";
    return;
  }
  _pickerRooms.forEach((geom, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = geom.name || geom.id; // textContent = XSS-safe
    sel.appendChild(opt);
  });
  sel.value = "0";
  wrap.style.display = "";
}

// Route a successful load/upload response to the viewer: a single room ({room})
// behaves exactly as before; a multi-room result ({rooms:[...]}) fills the picker
// and loads the first room. Each room already carries its uploaded:<n> id.
function handleLoadResult(data) {
  if (Array.isArray(data.rooms)) {
    if (!data.rooms.length) {
      showError("No rooms in the loaded capture.");
      return;
    }
    populateRoomPicker(data.rooms);
    switchToRoom(data.rooms[0]);
  } else if (data.room) {
    populateRoomPicker([]); // single room → hide the picker
    switchToRoom(data.room);
  }
}

// POST a JSON payload to a load/upload endpoint and route the result. Any error
// surfaces the server's generic message (no client-side parsing/physics).
async function _postAndSwitch(url, payload, statusLabel) {
  setStatus(statusLabel, false);
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => null);
    if (!resp.ok || !data || data.ok !== true) {
      showError(data && data.error ? data.error.message : "Load failed.");
      return;
    }
    handleLoadResult(data);
  } catch (err) {
    showError("Load request failed.");
  }
}

async function _uploadFile(file, url, fieldName) {
  if (!file) return;
  let text;
  try {
    text = await file.text();
  } catch (err) {
    showError("Could not read the selected file.");
    return;
  }
  return _postAndSwitch(url, { [fieldName]: text }, `Uploading ${file.name}…`);
}

function uploadRoom(file) {
  return _uploadFile(file, "/api/rooms/upload", "room_yaml");
}

function uploadRoomPlan(file) {
  return _uploadFile(file, "/api/rooms/upload/roomplan", "roomplan_json");
}

function uploadStructure(file) {
  return _uploadFile(file, "/api/rooms/upload/structure", "structure_json");
}

function loadExample(exampleId) {
  if (!exampleId) return;
  return _postAndSwitch(
    "/api/examples/" + encodeURIComponent(exampleId) + "/load",
    {},
    `Loading example ${exampleId}…`
  );
}

// Populate the "load example" dropdown verbatim from GET /api/examples.
async function populateExamples() {
  const sel = $("examples");
  if (!sel) return;
  try {
    const resp = await fetch("/api/examples");
    if (!resp.ok) return;
    const data = await resp.json();
    const examples = (data && data.examples) || [];
    sel.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "— load example —";
    sel.appendChild(placeholder);
    for (const ex of examples) {
      const opt = document.createElement("option");
      opt.value = ex.id;
      opt.textContent = ex.name || ex.id; // textContent = XSS-safe
      if (ex.description) opt.title = ex.description;
      sel.appendChild(opt);
    }
  } catch (err) {
    /* leave the dropdown with just the placeholder */
  }
}

// ---- Boot flow -----------------------------------------------------------

async function main() {
  initScene($("scene"));

  $("reseed").addEventListener("click", reseedLayout);
  $("export").addEventListener("click", exportTradeoff);
  $("upload").addEventListener("change", (ev) => {
    const file = ev.target.files && ev.target.files[0];
    uploadRoom(file);
    ev.target.value = ""; // allow re-uploading the same file
  });
  $("upload-roomplan").addEventListener("change", (ev) => {
    const file = ev.target.files && ev.target.files[0];
    uploadRoomPlan(file);
    ev.target.value = ""; // allow re-uploading the same file
  });
  $("upload-structure").addEventListener("change", (ev) => {
    const file = ev.target.files && ev.target.files[0];
    uploadStructure(file);
    ev.target.value = ""; // allow re-uploading the same file
  });
  $("examples").addEventListener("change", (ev) => {
    loadExample(ev.target.value);
  });
  $("room-picker").addEventListener("change", (ev) => {
    const i = parseInt(ev.target.value, 10);
    if (Number.isInteger(i) && _pickerRooms[i]) switchToRoom(_pickerRooms[i]);
  });

  // Any spec/param change → debounced re-evaluate (shares scheduleEvaluate with
  // drag-end). The form values are the single source of truth for every request.
  for (const id of ["spec", "target", "drive", "rt60"]) {
    $(id).addEventListener("change", () => scheduleEvaluate());
  }

  // Populate the spec + example dropdowns before the first evaluate. Failure is
  // non-fatal (the spec dropdown falls back to the default key; examples stay empty).
  await populateSpecs();
  await populateExamples();

  // 1. Fetch room geometry and build the scene.
  try {
    const geoResp = await fetch("/api/rooms/" + encodeURIComponent(currentRoomId));
    if (!geoResp.ok) {
      showError("Failed to load room geometry (HTTP " + geoResp.status + ").");
      return;
    }
    const geom = await geoResp.json();
    buildRoom(geom);
    setSpeakers(SEED);
  } catch (err) {
    showError("Failed to load room geometry.");
    return;
  }

  // 2. Evaluate the seed layout once on load (shared path with drag/re-seed).
  evaluateAndRender(speakersFromMeshes());
}

main();

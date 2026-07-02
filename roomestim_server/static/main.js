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
// regularity_hint defaults to "IRREGULAR" — the honest label for the hand-placed
// 5.1 SEED and any free-form dragged layout (non-uniform radii/angles). It is a
// real engine hint (min-count 1), so "Export layout.yaml" produces a valid
// layout.yaml on a fresh page too — never a spurious first-click error. (The old
// "ring" placeholder was NOT an engine hint and made export 400 before re-seed.)
let layoutMeta = {
  target_algorithm: "coverage_avoid",
  regularity_hint: "IRREGULAR",
  layout_name: "live-edit",
};

// ---- DOM helpers ---------------------------------------------------------

const $ = (id) => document.getElementById(id);

function setStatus(text, isError) {
  const el = $("status");
  el.textContent = text;
  el.classList.toggle("error", !!isError);
}

// Whether the disclaimer's full text is expanded — persisted across re-renders so
// a re-evaluate doesn't collapse a banner the installer just opened (P6.E item 1).
let _disclaimerExpanded = false;

// Render the persistent honesty banner as a COLLAPSIBLE block (P6.E item 1): a
// compact always-visible one-line `summary` (keeps the honesty essentials — SPL
// provenance + RT60 source + "relative comparison guidance (not a measurement)")
// plus a "▸ 자세히 (details)" toggle that expands the full `full` text. The honesty
// info is never deleted — collapsing only hides the long form; the summary keeps
// the essentials visible even on the error path. textContent = XSS-safe.
function setDisclaimer(summary, full, isError) {
  const el = $("disclaimer");
  el.replaceChildren();
  el.classList.toggle("error", !!isError);

  const row = document.createElement("div");
  row.className = "disc-summary";
  const text = document.createElement("span");
  text.className = "disc-summary-text";
  text.textContent = summary;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "disc-toggle";

  const fullEl = document.createElement("div");
  fullEl.className = "disc-full";
  fullEl.textContent = full;

  const applyState = () => {
    fullEl.style.display = _disclaimerExpanded ? "" : "none";
    toggle.textContent = _disclaimerExpanded ? "▾ 접기 (less)" : "▸ 자세히 (details)";
    toggle.setAttribute("aria-expanded", _disclaimerExpanded ? "true" : "false");
  };
  toggle.addEventListener("click", () => {
    _disclaimerExpanded = !_disclaimerExpanded;
    applyState();
  });
  applyState();

  row.appendChild(text);
  row.appendChild(toggle);
  el.appendChild(row);
  el.appendChild(fullEl);
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
// P6.F: depthTest:false so speaker markers never get occluded by the semi-opaque
// object obstacle boxes (color 0x8a5a3a) — the installer must always see every
// speaker, even one placed inside/behind furniture. Paired with a high renderOrder
// on the marker mesh (setSpeakers) so it also paints AFTER the transparent boxes.
const _speakerMat = new THREE.MeshStandardMaterial({
  color: 0xe0b341, depthTest: false,
});

// Invisible larger pick-target parented to each speaker so a click reliably hits
// the speaker even though the visible marker is only 0.12 m (P6.E item 4). The
// raycaster tests THESE, then maps hit.object.userData.speaker back to the marker.
// Shared geometry/material — never per-instance disposed. material.visible=false
// means it never renders, but THREE.Raycaster still intersects it.
const _pickGeo = new THREE.SphereGeometry(0.3, 12, 8);
const _pickMat = new THREE.MeshBasicMaterial({ visible: false });
let _pickMeshes = [];

// On-scene marking labels (P6.E item 3): a THREE.Sprite carrying a small canvas-
// drawn texture — the channel int on a speaker, the object kind on an obstacle.
// D29: the text is JUST the channel int / kind string already in the data; no
// physics. XSS-safe: drawn with canvas fillText, never innerHTML.
// P6.F: object labels are ENGLISH ONLY — the raw kind string (e.g. "table"),
// no bilingual Korean prefix.

function _makeLabelSprite(txt, color) {
  const text = String(txt);
  const canvas = document.createElement("canvas");
  const fontPx = 64;
  let ctx = canvas.getContext("2d");
  ctx.font = `bold ${fontPx}px system-ui, sans-serif`;
  const pad = 20;
  const textW = Math.max(1, Math.ceil(ctx.measureText(text).width));
  canvas.width = textW + pad * 2;
  canvas.height = fontPx + pad * 2;
  // Resizing a canvas resets its 2-D context, so re-acquire + re-set the font.
  ctx = canvas.getContext("2d");
  ctx.font = `bold ${fontPx}px system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(14,16,19,0.72)"; // legibility pill behind the glyphs
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = color || "#ffffff";
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);

  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true });
  const sprite = new THREE.Sprite(mat);
  const worldH = 0.26; // metres tall on screen; width tracks the text aspect ratio
  sprite.scale.set(worldH * (canvas.width / canvas.height), worldH, 1);
  return sprite;
}

// Dispose a mesh's attached label sprite (texture + material) and detach it, so a
// scene rebuild leaks no GPU resources. Safe on meshes with no label.
function _disposeLabel(mesh) {
  const label = mesh.userData && mesh.userData.label;
  if (!label) return;
  if (label.material) {
    if (label.material.map) label.material.map.dispose();
    label.material.dispose();
  }
  mesh.remove(label);
  mesh.userData.label = null;
}

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

// Room geometry meshes (floor, walls, listener patch, ceiling, objects) added by
// buildRoom — tracked so an upload can clear the previous room before rebuilding.
let roomMeshes = [];

// Ceiling meshes only — a SUBSET of roomMeshes kept separately so the "천장 표시"
// checkbox can toggle their .visible without touching the rest of the room.
let ceilingMeshes = [];

// Remove + dispose the current room geometry meshes (NOT the speakers). Called
// before rebuilding the scene for an uploaded room.
function clearRoomMeshes() {
  for (const m of roomMeshes) {
    _disposeLabel(m); // dispose any on-box kind label sprite (P6.E item 3)
    scene.remove(m);
    if (m.geometry) m.geometry.dispose();
  }
  roomMeshes = [];
  ceilingMeshes = [];
}

// Apply the "천장 표시" checkbox state to every ceiling mesh (default = ON).
function applyCeilingVisibility() {
  const cb = $("show-ceiling");
  const visible = cb ? cb.checked : true;
  for (const m of ceilingMeshes) m.visible = visible;
}

// Free-standing object kinds the viewer draws as solid boxes (obstacles the
// installer routes speakers around). Mirrors core FREESTANDING_OBJECT_KINDS.
const _FREESTANDING_KINDS = new Set(["column", "sofa", "table", "bed", "storage"]);
const _objectMat = new THREE.MeshStandardMaterial({
  color: 0x8a5a3a, transparent: true, opacity: 0.7,
});

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

  // Ceiling: each server-provided ceiling polygon (constant-y 3-D {x,y,z}) drawn
  // as a semi-transparent DoubleSide patch so the room reads enclosed but the
  // interior stays visible. Same map-only build as the floor (Shape from x,z,
  // rotate XY->XZ), placed at the polygon's own y. FALLBACK: if the geometry
  // carries no ceiling polygon, cover the floor outline at ceiling_height_m.
  const ceilMat = new THREE.MeshBasicMaterial({
    color: 0x8892a0, transparent: true, opacity: 0.15, side: THREE.DoubleSide,
  });
  const ceilPolys = geom.ceiling || [];
  if (ceilPolys.length) {
    for (const c of ceilPolys) {
      if (!c.polygon || !c.polygon.length) continue;
      const pts = c.polygon.map((p) => new THREE.Vector2(p.x, p.z));
      const cGeo = new THREE.ShapeGeometry(new THREE.Shape(pts));
      const mesh = new THREE.Mesh(cGeo, ceilMat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = c.polygon[0].y; // constant ceiling height (server coord)
      scene.add(mesh);
      roomMeshes.push(mesh);
      ceilingMeshes.push(mesh);
    }
  } else if (floorPts.length) {
    // Fallback: reuse the floor outline as a flat lid at ceiling_height_m.
    const lidGeo = new THREE.ShapeGeometry(floorShape);
    const lid = new THREE.Mesh(lidGeo, ceilMat);
    lid.rotation.x = -Math.PI / 2;
    lid.position.y = geom.ceiling_height_m;
    scene.add(lid);
    roomMeshes.push(lid);
    ceilingMeshes.push(lid);
  }

  // Objects: free-standing columns/furniture drawn as solid boxes so the
  // installer can see obstacles. The server anchor is the base centre ON the
  // floor, so the box centre sits at (anchor.x, anchor.y + height/2, anchor.z)
  // and the box is sized width x height x depth. These are NOT added to
  // speakerMeshes, so they are NOT draggable (they are obstacles). Wall-attached
  // door/window kinds are skipped: their anchor is wall-local, so drawing them
  // in world space needs the wall transform the geometry dict does not carry.
  for (const obj of geom.objects || []) {
    if (!_FREESTANDING_KINDS.has(obj.kind)) continue;
    const w = obj.width_m || 0.1;
    const h = obj.height_m || 0.1;
    const d = obj.depth_m || 0.1;
    const boxGeo = new THREE.BoxGeometry(w, h, d);
    const box = new THREE.Mesh(boxGeo, _objectMat);
    box.position.set(obj.anchor.x, obj.anchor.y + h / 2, obj.anchor.z);
    // On-scene kind label just above the box top (P6.E item 3) — child sprite so
    // it tracks the box; disposed with the box in clearRoomMeshes.
    const label = _makeLabelSprite(obj.kind, "#f0d9b0"); // P6.F: English kind only
    label.position.set(0, h / 2 + 0.18, 0);
    box.add(label);
    box.userData.label = label;
    scene.add(box);
    roomMeshes.push(box);
  }

  applyCeilingVisibility();
}

// Replace the on-screen speaker meshes from a list of {channel, position,
// aim_direction} entries. Positions/aim are literal UI data (from SEED or the
// /api/place response), never computed here.
function setSpeakers(list) {
  for (const m of speakerMeshes) {
    _disposeLabel(m); // dispose the channel label sprite before dropping the mesh
    scene.remove(m);
  }
  speakerMeshes = [];
  _pickMeshes = []; // pick spheres are children of the removed meshes — drop refs
  for (const s of list) {
    const m = new THREE.Mesh(_sphereGeo, _speakerMat);
    m.position.set(s.position.x, s.position.y, s.position.z);
    m.userData.channel = s.channel;
    m.userData.aim_direction = s.aim_direction ?? null;
    // P6.F: draw the marker (and its channel label) AFTER the transparent object
    // boxes so it is never hidden behind furniture — depthTest:false (on _speakerMat
    // and the label sprite material) plus this high renderOrder keep speakers on top.
    m.renderOrder = 10;

    // On-scene channel-number label above the marker (P6.E item 3).
    const label = _makeLabelSprite(s.channel, "#ffffff");
    label.position.set(0, 0.32, 0);
    label.renderOrder = 11; // P6.F: above the marker so the channel number stays legible
    m.add(label);
    m.userData.label = label;

    // Invisible larger pick-target so drags reliably hit the small marker (item 4).
    const pick = new THREE.Mesh(_pickGeo, _pickMat);
    pick.userData.speaker = m; // map a raycast hit back to the speaker marker
    m.add(pick);
    _pickMeshes.push(pick);

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
// Channel of the most-recently-moved speaker (P6.D) — its install-table row is
// highlighted after re-render. Null when nothing has been dragged since the last
// re-seed. Set on drag-end, cleared on re-seed.
let _movedChannel = null;

// Compromise-report state (D29: pure strings from the server placement notes).
// _placeNotesByChannel maps a channel int -> its server ``notes`` string from the
// last successful re-seed; the install-table "status" column reads it verbatim.
// _manuallyMovedChannels tracks every channel the installer has dragged since that
// re-seed, so their status shows "manual" (the seed note no longer applies).
let _placeNotesByChannel = {};
const _manuallyMovedChannels = new Set();

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
    // Raycast the invisible larger pick-spheres (item 4), then map the hit back to
    // the speaker marker. Objects/ceiling are NOT in _pickMeshes → non-draggable.
    const hits = _raycaster.intersectObjects(_pickMeshes, false);
    if (!hits.length) return;
    _dragged = hits[0].object.userData.speaker;
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
    // Record which channel just moved (BEFORE clearing _dragged) so renderInstall
    // can highlight its row (P6.D). userData.channel is set when the mesh is built.
    if (_dragMoved && _dragged.userData) {
      _movedChannel = _dragged.userData.channel;
      // The installer moved this channel — its seed note no longer describes where
      // it sits, so mark it "manual" in the install-table status column AND downgrade
      // the prominent summary badge so its verdict can't outlive the hand edit.
      _manuallyMovedChannels.add(_dragged.userData.channel);
      markSummaryManual();
    }
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
  // Gradio _build_disclaimer wording; NOT buried). Compact summary keeps the
  // essentials visible; the toggle expands the full text (P6.E item 1).
  const rt60 = report.rt60 || {};
  const summary =
    `SPL provenance: ${fmt(report.spl_provenance)} · ` +
    `RT60 source: ${fmt(rt60.source)} · ` +
    "relative comparison guidance (not a measurement)";
  setDisclaimer(
    summary,
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

// ---- Per-speaker install guide table (P6.C) ------------------------------

// Format a server-computed number to `d` decimals (display only — D29: NO physics
// in JS, this just rounds for readability); null/undefined → em-dash.
function fmtN(v, d) {
  if (v === null || v === undefined || typeof v !== "number") return "—";
  return v.toFixed(d);
}

function _installCell(text, cls) {
  const td = document.createElement("td");
  if (cls) td.className = cls;
  td.textContent = text; // textContent = XSS-safe
  return td;
}

// Map a channel to its compromise-report status [text, cssClass] from the last
// re-seed's server notes. Returns "manual" for a dragged channel, else parses the
// verbatim server note string (D29: JS reads the note, computes NO geometry).
function _channelStatus(channel) {
  if (_manuallyMovedChannels.has(channel)) return ["manual", null];
  const note = _placeNotesByChannel[channel];
  if (!note) return ["—", null];
  if (note.includes("[UNRESOLVED]")) return ["UNRESOLVED", "status-bad"];
  if (note.includes("[CLEARED]")) {
    const m = note.match(/dev=(\d+(?:\.\d+)?)deg/);
    return [m ? `cleared Δ${m[1]}°` : "cleared", null];
  }
  if (note.includes("obstacle-constrained")) return ["shortfall", "status-warn"];
  return ["—", null];
}

// Render the per-speaker install TABLE from data.install.speakers. EVERY number
// comes verbatim from the server block (positions, az/el/dist, wall/corner
// offsets) — the browser only formats + lays them out. Absent/null install (or a
// malformed block) blanks the table without crashing.
function renderInstall(install) {
  const body = $("install-body");
  if (!body) return;
  body.replaceChildren();
  const speakers = install && Array.isArray(install.speakers) ? install.speakers : null;
  if (!speakers) return;
  for (const s of speakers) {
    const pos = s.position || {};
    const row = document.createElement("tr");
    // channel · world x/y/z · height · az/el/dist · wall (idx@offset) · corner.
    const wall =
      s.nearest_wall_index === null || s.nearest_wall_index === undefined
        ? "—"
        : `#${s.nearest_wall_index} @ ${fmtN(s.wall_offset_m, 2)}m`;
    const corner =
      s.nearest_corner === null || s.nearest_corner === undefined
        ? "—"
        : `#${s.nearest_corner} @ ${fmtN(s.corner_dist_m, 2)}m`;
    row.appendChild(_installCell(fmt(s.channel)));
    row.appendChild(_installCell(fmtN(pos.x, 2)));
    row.appendChild(_installCell(fmtN(pos.y, 2)));
    row.appendChild(_installCell(fmtN(pos.z, 2)));
    row.appendChild(_installCell(fmtN(s.height_m, 2)));
    row.appendChild(_installCell(fmtN(s.az_deg, 1)));
    row.appendChild(_installCell(fmtN(s.el_deg, 1)));
    row.appendChild(_installCell(fmtN(s.dist_m, 2)));
    // Per-speaker direct-field SPL at the listener (server-computed, P6.D) — the
    // browser only formats it (D29: NO acoustics in JS).
    row.appendChild(_installCell(fmtN(s.spl_at_listener_db, 1)));
    row.appendChild(_installCell(wall));
    row.appendChild(_installCell(corner));
    // Per-channel obstacle-status (compromise report) — derived ENTIRELY from the
    // server placement notes threaded in via reseedLayout (D29: no JS physics).
    const [statusText, statusCls] = _channelStatus(s.channel);
    row.appendChild(_installCell(statusText, statusCls));
    // Highlight the most-recently-moved speaker's row so the installer sees
    // exactly what changed (P6.D).
    if (_movedChannel !== null && s.channel === _movedChannel) {
      row.className = "moved";
    }
    body.appendChild(row);
  }
}

// Standing honesty line kept visible even on error (the banner is "persistent" —
// HARD CONSTRAINT 1); the specific failure goes to #status, not over the banner.
const STANDING_DISCLAIMER =
  "Immersive trade-off — relative comparison guidance (not a guaranteed measurement).";

function showError(message) {
  renderInstall(null); // blank the install table on a failed evaluate (no stale rows)
  clearPlaceSummary(); // no stale compromise badge over a failed request
  clearPlaceNote(); // no stale obstacle-aware disclosure over a failed request
  setStatus(message || "Request failed.", true);
  setDisclaimer(
    STANDING_DISCLAIMER,
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

// Read the per-kind material override from the three dropdowns (P5.9). Each value
// is a MaterialLabel NAME or "" (the "— (keep)" option = no override → null). The
// server applies the curated rule-base and recomputes RT60; NO physics in JS.
function readMaterials() {
  const pick = (id) => {
    const sel = $(id);
    const v = sel && sel.value ? sel.value : "";
    return v === "" ? null : v;
  };
  return {
    floor: pick("mat-floor"),
    walls: pick("mat-walls"),
    ceiling: pick("mat-ceiling"),
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
    materials: readMaterials(),
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
    renderInstall(data.install); // P6.C — per-speaker positions (server-computed)
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
  // P7.3 additive forwards (D29: JS runs NO placement physics — these are just
  // the request knobs the server hands verbatim to core run_placement).
  const clearanceEl = $("clearance");
  if (clearanceEl) {
    const c = parseFloat(clearanceEl.value);
    if (Number.isFinite(c)) body.clearance_m = c; // else omit → server default
  }
  if (algorithm === "format_avoid") {
    const fmt = $("format");
    if (fmt && fmt.value) body.format_id = fmt.value; // missing → honest server 400
  }
  if (algorithm === "ambisonics") {
    const o = parseInt($("order").value, 10);
    if (Number.isInteger(o)) body.order = o; // missing/NaN → honest server 400
  }
  _movedChannel = null; // a fresh layout has no "just-moved" speaker to highlight
  setStatus(`Re-seeding (${algorithm}, n=${n})…`, false);
  try {
    const resp = await fetch("/api/place", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => null);
    if (!resp.ok || !data || data.ok !== true) {
      // Generic server message (e.g. "format_avoid requires a format" /
      // "ambisonics needs a valid order") — no crash, no leaked internals.
      showError(data && data.error ? data.error.message : "Re-seed failed.");
      return;
    }
    const placement = data.placement;
    layoutMeta = {
      target_algorithm: placement.target_algorithm,
      regularity_hint: placement.regularity_hint,
      layout_name: placement.layout_name,
    };
    // Thread the server per-speaker notes to the install-table status column and
    // reset the "manual" tracking — this fresh layout supersedes any prior drags.
    _placeNotesByChannel = {};
    for (const s of placement.speakers || []) {
      _placeNotesByChannel[s.channel] = s.notes || "";
    }
    _manuallyMovedChannels.clear();
    renderPlaceNote(placement); // obstacle-aware disclosure + per-speaker deviation
    renderPlaceSummary(placement); // prominent one-line compromise verdict
    setSpeakers(placement.speakers);
    evaluateAndRender(speakersFromMeshes());
  } catch (err) {
    showError("Re-seed request failed.");
  }
}

// Render the obstacle-aware placement disclosure (server ``note``) + a compact
// per-speaker ideal-vs-actual deviation summary (from each speaker's ``notes``).
// D29: pure text rendering, NO physics. Hidden when there is nothing to disclose.
function renderPlaceNote(placement) {
  const note = placement && placement.note;
  const flagged = ((placement && placement.speakers) || [])
    .map((s) => s.notes)
    .filter((t) => t); // drop empty notes (non-format algorithms)

  // Disclosure: show the FIXED Korean summary block and fill the collapsed English
  // original (#place-note-en) from the server ``note``, iff there is a disclosure.
  const ko = $("place-note-ko");
  const en = $("place-note-en");
  if (ko && en) {
    if (note) {
      en.textContent = note; // authoritative English original — XSS-safe
      ko.style.display = "";
    } else {
      en.textContent = "";
      ko.style.display = "none";
    }
  }

  // Dynamic per-speaker deviation / shortfall lines (kept visible, not collapsed).
  const el = $("place-note");
  if (!el) return;
  if (!flagged.length) {
    el.textContent = "";
    el.style.display = "none";
    return;
  }
  el.textContent = flagged.join("\n"); // textContent = XSS-safe
  el.style.display = "";
}

// Hide + blank the compromise-report summary badge (no stale verdict on error or a
// non-avoid algorithm). Removes every badge class so a re-show starts clean.
function clearPlaceSummary() {
  const el = $("place-summary");
  if (!el) return;
  el.textContent = "";
  el.classList.remove("badge-ok", "badge-warn", "badge-bad");
  delete el.dataset.manual; // a fresh/hidden verdict is no longer "manual"-qualified
  el.style.display = "none";
}

// Hide the obstacle-aware disclosure (Korean summary + English original) and the
// per-speaker note lines — so a prior avoid-seed's disclosure does not linger over a
// failed request or a room change that produced no fresh avoid layout.
function clearPlaceNote() {
  const ko = $("place-note-ko");
  if (ko) ko.style.display = "none";
  const en = $("place-note-en");
  if (en) en.textContent = "";
  const pn = $("place-note");
  if (pn) {
    pn.textContent = "";
    pn.style.display = "none";
  }
}

// After a manual drag the prominent verdict no longer describes the LIVE layout, so
// downgrade a clean "all cleared" headline to a warn — the badge must not keep
// asserting full obstacle clearance over a hand-edited layout (the per-channel
// status column already marks the moved row "manual"). Idempotent, string-only (D29).
function markSummaryManual() {
  const el = $("place-summary");
  if (!el || el.style.display === "none") return; // no active verdict to qualify
  if (el.dataset.manual === "1") return; // already qualified once
  el.dataset.manual = "1";
  if (el.classList.contains("badge-ok")) {
    el.classList.remove("badge-ok");
    el.classList.add("badge-warn");
  }
  el.textContent = `${el.textContent} · 수동 이동됨 — 재배치 검증 안 됨 (Re-seed to re-verify)`;
}

// Render the PROMINENT one-line compromise verdict for the last obstacle-aware
// re-seed, above the full #place-note dump. D29: pure string parsing of the server
// placement notes — JS computes NO physics/geometry. Non-avoid algorithms hide it.
function renderPlaceSummary(placement) {
  const el = $("place-summary");
  if (!el) return;
  const algo = placement && placement.target_algorithm;
  const notes = ((placement && placement.speakers) || []).map((s) => s.notes || "");

  let cls = null;
  let text = "";
  if (algo === "format_avoid") {
    const total = notes.length;
    const unresolved = notes.filter((t) => t.includes("[UNRESOLVED]")).length;
    // Count CLEARED explicitly instead of assuming "not unresolved == cleared":
    // if the server note format ever drifts (a note missing both tags), we must
    // NOT flash a false-positive green "all cleared" verdict over it.
    const cleared = notes.filter((t) => t.includes("[CLEARED]")).length;
    if (unresolved > 0) {
      cls = "badge-bad";
      text = `⚠ ${unresolved}/${total} 채널 미해결(UNRESOLVED) — 표준 각도로 안 풀림, 마운트/가구/청취위치 재검토 필요`;
    } else if (cleared === total && total > 0) {
      cls = "badge-ok";
      text = `✓ ${total}/${total} 채널 장애물 회피 (편차는 아래 상세 참조)`;
    } else {
      // No unresolved, but not every note is a clean [CLEARED] — don't over-claim.
      cls = "badge-warn";
      text = `⚠ ${cleared}/${total} 채널 장애물 회피 확인 — 나머지는 상태 불명, 아래 상세 확인`;
    }
  } else if (algo === "coverage_avoid") {
    const constrained = notes.find((t) => t.includes("obstacle-constrained"));
    if (constrained) {
      const m = constrained.match(/placed (\d+)\/(\d+)/);
      const k = m ? m[1] : "?";
      const n = m ? m[2] : "?";
      cls = "badge-warn";
      text = `⚠ 장애물 제약: 요청 ${n} 중 ${k}개만 배치 (나머지는 가구를 못 피함) — 상세는 아래`;
    } else {
      cls = "badge-ok";
      text = "✓ 요청 스피커 전부 장애물 회피 배치";
    }
  } else {
    clearPlaceSummary(); // non-avoid algorithm → no badge
    return;
  }

  el.classList.remove("badge-ok", "badge-warn", "badge-bad");
  el.classList.add(cls);
  delete el.dataset.manual; // fresh verdict — clears any prior "manual" qualifier
  el.textContent = text; // textContent = XSS-safe
  el.style.display = "";
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

// ---- Export layout.yaml (engine contract — produced server-side) ---------
// D29: NO physics/serialisation in JS — the CURRENT room_id + live placement
// (the same source /api/evaluate uses) is POSTed to /api/export/layout, where
// core write_layout_yaml produces the layout.yaml text; the browser only
// triggers a download of exactly the returned text.

async function exportLayout() {
  const body = {
    room_id: currentRoomId,
    placement: {
      target_algorithm: layoutMeta.target_algorithm,
      regularity_hint: layoutMeta.regularity_hint,
      layout_name: layoutMeta.layout_name,
      speakers: speakersFromMeshes(),
    },
  };
  setStatus("Exporting layout.yaml…", false);
  try {
    const resp = await fetch("/api/export/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => null);
    if (!resp.ok || !data || data.ok !== true) {
      showError(data && data.error ? data.error.message : "Layout export failed.");
      return;
    }
    const blob = new Blob([data.yaml], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = data.filename || "layout.yaml";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setStatus("Exported layout.yaml.", false);
  } catch (err) {
    showError("Layout export request failed.");
  }
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

// ---- Material dropdowns (populated verbatim from GET /api/materials) --------
// Each of the floor/walls/ceiling <select>s gets a "— (keep)" first option
// (value "" → no override) followed by every curated material, labelled with its
// REAL 500 Hz absorption α (honest coefficients). D29: JS runs NO physics — the
// chosen label NAMEs are POSTed to /api/evaluate, where core recomputes RT60.

async function populateMaterials() {
  const ids = ["mat-floor", "mat-walls", "mat-ceiling"];
  if (ids.some((id) => !$(id))) return;
  try {
    const resp = await fetch("/api/materials");
    if (!resp.ok) return;
    const data = await resp.json();
    const materials = (data && data.materials) || [];
    for (const id of ids) {
      const sel = $(id);
      sel.replaceChildren();
      const keep = document.createElement("option");
      keep.value = "";
      keep.textContent = "— (keep)";
      sel.appendChild(keep);
      for (const m of materials) {
        const opt = document.createElement("option");
        opt.value = m.label; // MaterialLabel NAME (what the override expects)
        // Show the honest α so the physical meaning is visible. textContent = XSS-safe.
        opt.textContent = `${m.name} (α=${m.absorption_500hz})`;
        sel.appendChild(opt);
      }
    }
  } catch (err) {
    /* leave the dropdowns at "— (keep)"; readMaterials() then sends nulls */
  }
}

// ---- Format dropdown (populated verbatim from GET /api/formats) ------------
// The immersive format ids ("5.1", "5.1.4", …) the format_avoid placement uses.
// D29: JS runs NO placement physics — the chosen id is POSTed to /api/place.

async function populateFormats() {
  const sel = $("format");
  if (!sel) return;
  try {
    const resp = await fetch("/api/formats");
    if (!resp.ok) return;
    const data = await resp.json();
    const formats = (data && data.formats) || [];
    sel.replaceChildren();
    for (const id of formats) {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = id; // textContent = XSS-safe
      sel.appendChild(opt);
    }
    // Default to 5.1.4 when present (a common immersive bed+height config).
    if ([...sel.options].some((o) => o.value === "5.1.4")) sel.value = "5.1.4";
  } catch (err) {
    /* leave the dropdown empty; format_avoid then 400s honestly if selected */
  }
}

// ---- Algo-conditional control visibility -----------------------------------
// #format shows only for format_avoid; #order only for ambisonics; #clearance
// only for the obstacle-aware algorithms (format_avoid / coverage_avoid).
function syncAlgoControls() {
  const algo = $("algo") ? $("algo").value : "";
  const show = (id, on) => {
    const el = $(id);
    if (el) el.style.display = on ? "" : "none";
  };
  show("format-wrap", algo === "format_avoid");
  show("order-wrap", algo === "ambisonics");
  show("clearance-wrap", algo === "format_avoid" || algo === "coverage_avoid");
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
// When "방 변경 시 자동 재배치" (auto re-place) is CHECKED (default), a room switch
// re-runs the SAME flow as the Re-seed button (POST /api/place with the current
// algo + n, then setSpeakers + evaluate) so the layout adapts to the new space.
// When unchecked, the previous behaviour holds — keep the current speakers and
// just re-evaluate them against the new room. NOTE: room-BLIND algorithms
// (vbap/dome) return the same ring regardless of the room; only dbap/coverage
// actually adapt (surfaced in the checkbox tooltip).
function switchToRoom(geom) {
  currentRoomId = geom.id;
  clearRoomMeshes();
  buildRoom(geom);
  // The prior room's obstacle notes / "manual" flags / verdict badge describe a
  // DIFFERENT space and are stale the moment the room changes. Clear them here; a
  // re-seed (auto or manual) repopulates them, and the non-reseed branch is left
  // honestly blank rather than showing the old room's clearance claims.
  _placeNotesByChannel = {};
  _manuallyMovedChannels.clear();
  const auto = $("auto-reseed");
  if (auto && auto.checked) {
    reseedLayout(); // re-place for the new room (place + setSpeakers + evaluate)
  } else {
    clearPlaceSummary(); // no re-seed → no fresh verdict; drop the stale badge
    clearPlaceNote(); // and drop the prior room's obstacle-aware disclosure
    evaluateAndRender(speakersFromMeshes());
  }
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

// A BINARY mesh file (.obj/.gltf/.glb/.ply/.usdz) — read as an ArrayBuffer, base64-
// encode, and POST {filename, content_b64} to /api/rooms/upload/mesh. D29: NO
// parsing/geometry math in the browser — core MeshAdapter parses it server-side.
function _arrayBufferToBase64(buf) {
  const bytes = new Uint8Array(buf);
  let binary = "";
  const CHUNK = 0x8000; // build the binary string in chunks to avoid arg-count limits
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

async function uploadMesh(file) {
  if (!file) return;
  let content_b64;
  try {
    const buf = await file.arrayBuffer();
    content_b64 = _arrayBufferToBase64(buf);
  } catch (err) {
    showError("Could not read the selected mesh file.");
    return;
  }
  return _postAndSwitch(
    "/api/rooms/upload/mesh",
    { filename: file.name, content_b64 },
    `Uploading ${file.name}…`
  );
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
  $("export-layout").addEventListener("click", exportLayout);
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
  $("upload-mesh").addEventListener("change", (ev) => {
    const file = ev.target.files && ev.target.files[0];
    uploadMesh(file);
    ev.target.value = ""; // allow re-uploading the same file
  });
  $("examples").addEventListener("change", (ev) => {
    loadExample(ev.target.value);
  });
  $("room-picker").addEventListener("change", (ev) => {
    const i = parseInt(ev.target.value, 10);
    if (Number.isInteger(i) && _pickerRooms[i]) switchToRoom(_pickerRooms[i]);
  });
  const showCeiling = $("show-ceiling");
  if (showCeiling) showCeiling.addEventListener("change", applyCeilingVisibility);

  // P7.3: toggle the format/order/clearance controls to match the chosen algo.
  const algoSel = $("algo");
  if (algoSel) algoSel.addEventListener("change", syncAlgoControls);
  syncAlgoControls();

  // Any spec/param change → debounced re-evaluate (shares scheduleEvaluate with
  // drag-end). The form values are the single source of truth for every request.
  for (const id of [
    "spec", "target", "drive", "rt60",
    "mat-floor", "mat-walls", "mat-ceiling",
  ]) {
    $(id).addEventListener("change", () => scheduleEvaluate());
  }

  // Populate the spec + material + example dropdowns before the first evaluate.
  // Failure is non-fatal (spec falls back to the default key; materials stay at
  // "— (keep)" → no override; examples stay empty).
  await populateSpecs();
  await populateMaterials();
  await populateFormats();
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

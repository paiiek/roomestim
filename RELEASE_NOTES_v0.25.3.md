# roomestim v0.25.3 — MeshAdapter up-axis(gravity) 자동 정규화 (measured 경로 P0 정확성 수정)

PATCH. **measured(install-grade) 캡처 경로의 P0 정확성 버그 수정** — 정확도 개선이 아니라 실데이터에서
조용히 틀린 지오메트리를 내던 것을 바로잡고, 모호하면 명확히 거부(fail-loud).

## 배경 (어떻게 발견됐나)
상용화(B2B AV-인스톨러) 관점의 냉정 분석 중, measured 경로가 **실제 캡처로 한 번도 검증된 적 없음**(모든
테스트 픽스처가 합성 Y-up shoebox; 유일한 real-scan 게이트는 영구 SKIP)을 확인. 로컬의 실제 **ARKitScenes**
10 scene(iPad LiDAR = RoomPlan 센서 정합)으로 MeshAdapter 를 처음 돌리자 **천장 높이가 6.5–9.6 m**(실제 ~2.5 m)
로 나왔다. 근본 원인: `mesh.py` 가 **Y-up 을 하드코딩**(`ceiling = y_max - y_min`)하고 gravity/up-축 정규화가
전무 — 그러나 ARKit/RoomPlan 및 많은 `.ply`/`.obj` export 는 **Z-up(gravity-aligned)**. 어댑터는 가로 치수를
천장으로 오인하고 floor polygon 도 틀린 평면에서 추출했다.

## 수정 (F1 / Phase 0a)
- **up-축 자동 검출 + Y-up 정규화** (`MeshAdapter`): 입력 mesh 에서 gravity/up 축을 **planar-density 판별자**로
  검출(축별 1-D 히스토그램의 floor/ceiling 평면 집중도; 종횡비 무관)한 뒤 모델 프레임(Y-up)으로 정규화하고 기존
  추출 로직을 그대로 적용. density 동률 시 floor-footprint **area tiebreaker**(clear-floor 마진 1.50×)로 보조.
- **fail-loud 모호성 가드**: density 와 area 둘 다 모호한 mesh(완전 정사각 cube, 또는 sparse+narrow 코너 mesh)는
  조용히 추측하지 않고 **명확한 `ValueError`(detected density/area 진단 + `up_axis=` override 권고)로 거부**.
- **`up_axis` override**(`MeshAdapter(up_axis="x"|"y"|"z")`, 기본 `"auto"`): gravity 메타데이터를 아는 호출자용.
- 합성 Y-up 픽스처는 정규화가 identity → **출력 byte-equal**(기존 동작 무변경).

## 검증
- 실 ARKitScenes 10 scene: up-축 모두 Z 로 검출, 천장 높이 **2.49–3.69 m**(다중층 1개는 5.76 m, 정직하게 별도 처리).
  (수정 전 6.5–9.6 m.) `@pytest.mark.lab` 회귀 테스트(로컬 데이터 게이트)로 고정.
- 게이트: default **368 passed / 6 skipped**, ruff/mypy(strict)/tense EXIT0.
- 독립 code-review 2라운드(APPROVE-WITH-FIXES, narrow-room silent-misdetect HIGH→해소, sparse-narrow MEDIUM→fail-loud)
  + 독립 verifier VERIFIED-GREEN(실 ARKit 천장 높이·fail-loud 경로·backward-compat 실측).

## 한계 (정직)
- 자동 검출은 **gravity-aligned-to-principal-axis** 입력 가정(ARKit/RoomPlan/대부분 스캔 충족). **기울어진 mesh**는
  보정 안 됨 → `up_axis=` 명시 필요. coarse/parametric narrow mesh 는 모호 시 거부(추측 안 함).
- 이 수정은 **추출 알고리즘 정확성**(올바른 평면에서 floor/ceiling 추출)을 고침. **센서 vs 실측(±10 cm) 절대
  정확도**는 독립 GT(Faro/ScanNet++) 필요 — Phase 0b 후속. install-grade 절대정확도 주장은 아직 미입증.

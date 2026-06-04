# Image→Geometry 캡처 백엔드 (단일-파노 rough tier) — BUILD (resume truth source)

## RESUME POINTER
- **결정 (2026-06-04, 사용자 선택)**: 두 feasibility 사이클(OQ-53 scale, OQ-59 front-end) 종료 후, 실제 진척 + north-star-first로 **in-repo 첫 image→geometry 캡처 백엔드(단일-파노 rough tier)** 빌드. provenance(OQ-54)는 Phase 1(하드 게이트)이지 종착점 아님.
- **근거 (검증·교차검증 수렴, 2026-06-04)**: ① 프로젝트 전부 GREEN(default 312/5·web 86/4·ruff·mypy·tense EXIT0 @ `3a69a6f`). ② 독립 sweep + adversarial critic 두 레인이 "image→geometry가 유일하게 *열린 경로 + 완성된 downstream*을 가진 north-star 축"으로 수렴(layout 이미 성숙 ADR 0003, material-from-image는 §E 거버넌스 차단). ③ downstream 파이프라인(`run`: ingest→place→export) 이미 완성 → 어댑터가 유일한 missing front-door → 증분 빌드.
- **오케스트레이션**: OMC 풀(planner→executor→code-reviewer→독립 verifier), 자기승인 금지. 자율 execute→verify(full gate)→repeat. 매 phase RESUME POINTER 갱신.
- **게이트 baseline (착수 시점)**: canonical `/home/seung/miniforge3/bin/python -m pytest`. default `-m "not web and not lab and not e2e"` 312p/5s; web `-m web` 86p/4s; ruff/mypy(roomestim only)/tense EXIT0. HEAD `3a69a6f`.

## 설계 출처 / 계약
- ADR 0045(image→geometry capture backend, PROPOSED) §B rough tier / §C / §E material UNKNOWN / §F provenance / Reverse-criterion #4(provenance 없이 출력 노출 금지) / Blocking gate #1-4.
- 이전 단일-파노 스파이크 `/home/seung/mmhoa/spike-image-geometry/`: **HorizonNet resnet50_rnn__st3d**(Structured3D-trained, HF `gum-tech/horizonnet-resnet50-rnn`, MIT). VERDICT FALLBACK — out-of-domain st3d로 ~43-45%만 ≤15cm, median shape ~18cm(perfect ScaleAnchor), ±10cm cam_h→32-38cm. → rough tier 한정.
- 재사용 seam: `adapters/mesh.py`(`parse`, `floor_polygon_from_mesh` @ v0.24.0 live, `walls_from_floor_polygon`), `model.py:canonicalize_ccw`, `base.py` ScaleAnchor Protocol, `[web]`/`[colmap]` extra 선례.

## Phases (체크포인트)
- [x] **P0** residential ckpt 리서치 — **완료(2026-06-04)**. 결론: HorizonNet 코드=MIT(상업OK, 이미 wired). 진짜 도메인정합 = ZInD-trained HorizonNet(`resnet50_rnn__zind.pth`, 20k real residential, in-domain ~90% 2D IoU)이나 **ZInD ToU 비상업/no-products(RED, 번들 금지)**; MatterportLayout=CC BY-NC-SA(RED); LGT-Net은 ZInD에서 HorizonNet 못 이김+arch 비용. **permissive residential ckpt 부재.** → **결정**: (a) 기본 = st3d HorizonNet(MIT 코드 + Structured3D weights, rough/experimental), HF mirror `gum-tech/horizonnet-resnet50-rnn` download-on-first-use; (b) opt-in `--weights zind`(gdown id `1FrMdk7Z4_sTZOOW65Ek77WbjiDbV98uJ`) + 비상업 ToU 고지; (c) **weights 번들 금지** — download-on-first-use + per-ckpt 라이선스 수락으로 roomestim 배포는 MIT-clean 유지. 정확도는 rough(st3d out-of-domain ~43-45% ≤15cm) — `--experimental` 정당.
- [x] **P1** provenance 스키마 (OQ-54, room-level) — **완료(2026-06-04, D85/ADR 0046)**. `RoomModel.provenance: Literal["measured","reconstructed","assumed"]="assumed"`(least-claim), 실측 어댑터 measured 단언, 0.2-draft 한정 방출(legacy 0.1 byte-equal), reader 기본화, additive 스키마. masquerade 경로 0(독립 code-review §B CLOSED = §F honesty 리뷰). executor 구현→code-reviewer APPROVE→minor(keyless-0.2 테스트) 적용. Gates: default 320p/5s, web 86p/4s, ruff/mypy/tense EXIT0. per-Surface OPEN(follow-up). 미커밋(이 P1 커밋 예정). version bump deferred→P5.
- [x] **P2** `[vision]` extra + vendored HorizonNet + ckpt fetcher — **완료(2026-06-04)**. HorizonNet 추론 핵심(model.py + misc/{post_proc,panostretch,utils}, MIT (c)2019 Cheng Sun, py3.12 fix distutils→packaging)을 `roomestim/vision/horizonnet/`에 vendor(+LICENSE+NOTICE, weights 미번들). `vision/checkpoints.py` torch-free fetcher: st3d HF `gum-tech/horizonnet-resnet50-rnn` 기본, zind opt-in(gdown + ToU accept gate), `ROOMESTIM_HORIZONNET_CKPT` 로컬 override. `[vision]` extra(torch/torchvision/Pillow/huggingface_hub/gdown/scikit-learn/opencv-python). **경계 게이트 #4 PASS**: core/adapters/vision import torch-free(깨진 canonical torchvision로 입증). vendored dir만 mypy/ruff exclude, checkpoints.py strict. out-of-gate smoke(spike venv): 모델 load+forward OK(bon(1,2,1024)). executor→code-reviewer APPROVE-WITH-FIXES(0 blocker)→minor 2건(sklearn/opencv 선언, ToU print→warnings) 적용. Gates: default 326p/5s, web 86p/4s, ruff/mypy(46)/tense EXIT0. 미커밋(이 P2 커밋 예정).
- [ ] **P3** `adapters/image.py` 단일-파노: HorizonNet forward → cam-height ScaleAnchor → `walls_from_floor_polygon`+`canonicalize_ccw` 재사용 → `provenance=reconstructed`, `Surface.material=UNKNOWN`(§E), Manhattan-flag + scale-source disclosure(§B). `--experimental` 게이트.
- [ ] **P4** CLI/web rough-tier 라벨링("estimated") + per-corner uncertainty 최소(OQ-57) + 엔지니어-확인-before-layout default.
- [ ] **P5** full gate(default+web+ruff+mypy+tense) + smoke `ingest→place→export` on 1 pano fixture + 독립 code-review + verifier. 버전 범프 검토(web/CLI feature → MINOR?). 커밋.

## 게이트 / 제약
- Reverse-criterion #4: provenance(P1) 미완 상태로 image 출력 노출 금지 → P1이 P3-P4 선행.
- 경계 게이트 #4: 모델 의존은 `[vision]` extra 뒤에만, core deps 0, default+web 게이트 회귀 0.
- rough tier 정직성: `provenance=reconstructed` + "estimated" 가시 라벨 + per-corner uncertainty + scale-source disclosure. ≤15cm install-grade 주장 금지(LiDAR/RoomPlan 한정).
- known-bad 정확도(43-45%) 완화: `--experimental` + 엔지니어 확인 전제. P0가 ckpt 개선 여지 판정.

## 미해결 결정 (P0/리뷰에서)
- single-pano ckpt 선택(st3d 유지 vs residential 대안) — P0 결과.
- 버전 범프 크기(MINOR vs 별도) — P5 리뷰.
- per-Surface provenance defer 명문화(별도 OQ/follow-up).

## 교차검증 산출물(이 결정 근거)
- 독립 sweep: 누락 후보 발견(PROPOSED ADR 0040-0043 미구현, OQ-55, AMBISONICS dead enum) — 그러나 north-star-first는 image→geometry로 수렴.
- adversarial critic: "OQ-54-only는 올바른 첫 링크지만 standalone은 real-progress 위배 → 어댑터 번들로 확장" REVISE 판정. downstream 완성 → 증분 빌드. single-pano(다중뷰 아님, VGGT base 비상업 라이선스+최중량).
- 코덱스 CLI 미설치 → 독립 에이전트 레인으로 교차검증 대체(투명 고지).

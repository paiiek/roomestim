# roomestim — "쓸 수 있는 연구·기법·기술" 전략 리서치 (2026-06-23)

RESUME POINTER for a strategic landscape research requested by the user:
"지금 하던 incremental grind 떠나서, 내가 원하고 실제로 잘 동작하게 할 수 있는(내가 쓸 수 있는)
연구·기법·기술을 아주 디테일하게 리서치해서 쓸만한 걸 제안하라."

## Scope (user-confirmed, 2026-06-23)
- 입력 모달리티: **전 스펙트럼** — 이미지/영상-only 부터 RGB-D/LiDAR(RoomPlan/ARKit)까지.
- 사용 가능성 바: **research-grade 포함**, 단 라이선스/성숙도 각각 명시 플래그.
- 출력 타겟: **기하(footprint/벽/천장) + 스피커 레이아웃 + 음향** 전 파이프라인.

## Project context fed to every research agent
- roomestim = 설치공간 영상/사진 → 방 기하(footprint polygon, walls, ceiling height) +
  스피커 레이아웃 + 음향(RT60). B2B AV-installer 프레이밍 (measured/LiDAR 코어).
- 현재 스택: VGGT(feed-forward multi-view, commercial OK) · HorizonNet(single-pano layout, MIT) ·
  MeshAdapter(RGB-D/.usdz/RoomPlan mesh ingest) · pyroomacoustics + custom polygon-ISM · ambisonics/DBAP.
- 진단된 북극성 블로커: 폰 영상 multi-view에서 VGGT 청크가 각각 ARKit에 독립 정합 → 청크간
  ~19cm pose 잔차(cam_reg_rmse). 이게 concave(L자) footprint(~20cm, install-grade ≤15cm 미달)
  와 TSDF 융합(청크 pose 불일치 → 파괴적 carving)을 동시에 죽임. convex-prior는 12.7cm/7-of-10
  이지만 convex가 노이즈를 가린 아티팩트라 비-convex 일반화 안 됨.
- Hard rules: NO FAKE NUMBERS · commercial-OK 선호(research-grade는 플래그) · metric scale 필수.

## 6 research facets (parallel agents dispatched)
1. Feed-forward multi-view recon + global/cross-chunk pose alignment (THE core blocker).
2. Monocular/multi-view METRIC depth + metric-scale recovery.
3. Room layout / floor-plan estimation, 특히 NON-CONVEX/multi-room.
4. RGB-D/LiDAR 폰 파이프라인 + dense fusion/SLAM (metric, chunk-consistent) + 상용 측정앱 벤치.
5. Speaker layout 최적화 + spatial audio rendering.
6. Room acoustics from geometry (RT60/auralization) + material-from-image.

## STATUS
- 2026-06-23: scope 확정, 6 facet 에이전트 병렬 dispatch. **세션 토큰 한도에서 종합 직전 전부 중단.**
- 2026-06-24 RECOVERY (session 697ce686): 이전 세션(ff0e0c1b) transcript에서 산출물 복구.
  - 6 facet 모두 종합 직전 "session limit"으로 사망. 단 일부는 죽기 전 리포트를 완성함:
  - **Facet 4 (RGB-D/LiDAR + 측정앱): 완성 ✓** → `.omc/research/usable-tech-facet4-rgbd-lidar-2026-06-23.md` (17.4KB).
  - **Facet 5 (speaker layout + spatial audio): 완성 ✓** → `.omc/research/usable-tech-facet5-speaker-layout-2026-06-23.md` (19KB).
  - **Facet 1(multi-view+pose)·2(metric depth)·3(non-convex floor)·6(acoustics RT60): 미완성** — 하위 검색 에이전트 spawn/대기 중 사망, 종합 없음 (2·6 부분 웹리서치만, 1·3 거의 미착수).
- 2026-06-24 RE-RUN (session 697ce686, user="4개 순차 재실행"): 각 에이전트에 "리포트를 .omc/research/<facet>.md 에 직접 Write" 계약 명시(중단 시 보존). sonnet, foreground 순차.
  - **Facet 1 (multi-view+pose): 완성 ✓** → `usable-tech-facet1-multiview-pose-2026-06-23.md` (19.6KB/248줄).
  - **Facet 2 (metric depth+scale): 완성 ✓** → `usable-tech-facet2-metric-depth-2026-06-23.md` (23.3KB/269줄).
  - **Facet 3 (non-convex floorplan): 완성 ✓** → `usable-tech-facet3-nonconvex-floorplan-2026-06-23.md` (25.6KB/329줄).
  - **Facet 6 (acoustics RT60): 미실행** — dispatch 직전 user가 리밋 임박으로 중단 요청.

## ★STATUS: COMPLETE (2026-06-24, session d47cfa8c)
- 6/6 facet 전부 디스크 보존: `.omc/research/usable-tech-facet1~6-*.md`.
  - Facet 6 (acoustics RT60) 재dispatch 완료 → `usable-tech-facet6-acoustics-rt60-2026-06-23.md` (29KB/376줄, scientist/sonnet).
- ★최종 종합 완료 → **`.omc/research/usable-tech-SYNTHESIS-2026-06-23.md`** (이 리서치의 최종 산출물).
  - 핵심 결론: (A) LiDAR/ARKit 경로 ≤15cm는 RoomPlan으로 이미 풀림(할 일=실캡처 laser GT 검증) · (B) video-only ≤15cm는 commercial-license-grade 미해결, 유일 정공법=VGGT(Apache)+GTSAM global BA(Apache).
  - 즉시 채택 RANKED 10건(commercial-OK, 코드-only): Metric3Dv2(BSD)·GTSAM BA·RoomFormer(MIT)·spaudiopy(MIT)·geometric grid·pyroomacoustics 고차ISM·다대역RT60·blind-rt60·door-scale·LGT-Net.
  - 권고 시퀀스: ①음향(ISM+다대역+blind-rt60, 低위험高ROI) ②스피커(grid+spaudiopy/DBAP) ③VGGT+GTSAM BA 스파이크(先 AMB3R 라이선스 확인) ④RoomFormer measured ⑤실 RoomPlan laser GT 검증.
  - 채택 전 LICENSE 직접확인 필요: AMB3R·PolyRoom·FRI-Net·Splat-SLAM·SplaTAM·DA3·SS-BRPE·IncVGGT.
- ★lesson(검증됨): 리서치 에이전트엔 "최종 리포트를 .omc/research/<facet>.md 에 직접 Write 하라" 출력계약 명시 → 이번 Facet6 재dispatch 시 적용해 중단대비 보존 성공.

## ★ADDENDUM 흡수 (2026-06-24, 동료 Claude 세션 5-에이전트 음향 심화)
- 외부 동료 세션이 음향 facet을 5개 하위에이전트(geo-rt60·neural-rir·material-image·blind-rt60·validation-datasets)로 심화 → distill 하여 `.omc/research/usable-tech-facet6-acoustics-DEEPDIVE-addendum-2026-06-24.md` 에 보존, SYNTHESIS §3e/§4/§6 패치.
- 핵심 신규/교정: ★Acta Acustica 2025 closed-form geo+audio 보정(≤1 JND, ~50줄, "novel"→실제 published) · MESH2IR(mesh→RIR pretrained, license 미확인 investigate) · FAST-RIR=AGPL 교정(Facet6 MIT 오기) · pyroomacoustics materials=MIT 확정 · within-class 분산 정량(카펫 0.25–0.73) · FLAIR(라이선스 확인 1순위)+Spatial LibriSpeech(MIT) 데이터.
- 미확정(채택 전 확인): FLAIR/MESH2IR/PTB/openMat/ACE-ND license, AST/CRNN pretrained weights 부재.

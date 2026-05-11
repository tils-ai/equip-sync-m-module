# CLAUDE.md - equip-sync-m-module (머그 전사지 프린터)

이 레포의 Claude 컨텍스트와 설계 문서는 **`dps-store`** 프로젝트에서 통합 관리한다.

- dps-store 로컬 경로: `~/Workspace/dps-store`
- 외부 레포 테이블·통합 정책: `dps-store/CLAUDE.md` 의 "관련 외부 레포" 섹션
- 관련 설계 문서: `dps-store/docs/print/20260507-mug-transfer-printer.md` 및 `dps-store/docs/print/20260511-equipment-gui-*.md`

이 레포 단독 작업 시에도 위 문서를 우선 참조하라.

## 간단 정리 (메모)

- 머그컵 전사지 자동 출력 Windows 프로그램
- Watcher (감시·좌우 반전·A4 가로 2-up 합성) + Agent (dps-store API 풀링·다운로드) + 자동 출력 파이프라인 통합 단일 exe
- 빌드 산출물: `equip-sync-m-vX.Y.Z.exe` (태그 push 시 GitHub Actions에서 자동 빌드)
- 합본 PDF는 `done/`에 저장되며, 설정 패널의 [프린터] 토글이 ON이면 자동 출력
- poppler Windows 바이너리는 PyInstaller 번들에 포함

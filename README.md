# equip-sync-m-module

머그컵 생산용 **전사지 출력 프린터** 자동화 워처 (Windows, Python).

## 기능

- **자동 좌우 반전** — 전사지에 거울상으로 출력해야 머그에 입혔을 때 정상 방향
- **A4 가로 2-up 배치** — 두 건을 위·아래로 묶어 한 장에 출력 (전사지 절약)
- **GUI** — 실시간 큐 대시보드, 다크/라이트/시스템 테마 즉시 전환
- **백그라운드 워처** — `incoming/` 폴더에 PDF가 들어오면 자동 처리

## 동작 흐름

```
incoming/{order}.pdf 추가
   ↓ 사이즈 검사 (절반 A4 가로 = 297×105mm 슬롯에 맞는지)
   ├─ 맞음  → FIFO 큐 (1건은 다음 1건 대기)
   │            ↓ 2건 모이면: A4 가로 한 장에 위·아래 배치 (좌우 반전)
   │            ↓ done/{ts}-{uuid}.pdf
   └─ 초과 → 설정에 따라 (error/ 이동) 또는 (1-up 단독 출력)
   원본 → done/originals/ (기본 보관)
```

## 수량 (한 디자인을 여러 슬롯에 배치)

파일명 끝의 `_qtyN.pdf` 패턴으로 수량을 표현합니다.

| 파일명 | 동작 |
| --- | --- |
| `order123.pdf` | 1슬롯 (다른 1건과 페어링) |
| `order123_qty2.pdf` | 2슬롯 (같은 디자인 두 번 → 한 장 출력) |
| `order123_qty3.pdf` | 3슬롯 (둘은 같은 디자인 한 장 + 1슬롯은 다음 1건과 페어링) |

향후 v0.3 Agent에서는 dps-store API의 주문 수량으로 자동 결정됩니다.

## 설정 (GUI 또는 config.ini)

GUI 설정 탭의 파이프라인 폼에서 즉시 변경:

| 항목 | 값 | 설명 |
| --- | --- | --- |
| 좌우 반전 | `horizontal` / `none` | 전사지는 거울상이 정상 — `horizontal` 권장 |
| 배치 방식 | `original` / `contain` / `cover` | 기본 `original`(원본 사이즈 유지). 슬롯보다 크면 자동 contain 폴백 |
| 사이즈 초과 시 | `error` / `single` | 초과 디자인 처리 — `error`(에러 폴더) 또는 `single`(1-up 단독 출력) |

## 요구사항

- Windows 10/11
- Python 3.11+ (개발 시) — 릴리즈 빌드는 단일 실행 파일

## 설치 및 실행

### 릴리즈 빌드 사용 (권장)

[Releases](https://github.com/tils-ai/equip-sync-m-module/releases) 페이지에서 단일 `equip-sync-m-vX.Y.Z.exe` 다운로드 → 더블 클릭 실행.

> 첫 실행 시 임시 폴더에 자체 추출 → 5\~10초 정도 지연될 수 있습니다 (PyInstaller `--onefile` 특성).
> SmartScreen 경고가 뜨면 "추가 정보 → 실행" 선택.

### 소스에서 실행 (개발)

```bash
git clone https://github.com/tils-ai/equip-sync-m-module
cd equip-sync-m-module
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m watcher              # GUI 실행
python -m watcher --headless   # 콘솔 모드
```

## GUI

| 탭 | 내용 |
| --- | --- |
| Dashboard | Watcher 상태(시작/중지), 대기/처리중/완료/오류 카운트, 폴더 바로가기, 최근 완료 목록 |
| Settings | `config.ini` 위치 + 내용 미리보기, 외부 편집기로 열기 |
| Agent | 페어링 정보 입력/삭제 (v0.2 스켈레톤, 실제 풀링은 v0.3 예정) |

상단 우측 **테마** 메뉴에서 `시스템 / 라이트 / 다크` 즉시 전환 — 선택값은 `config.ini`에 저장됩니다.

## 폴더 구조 (운영 시)

기본값 `%LOCALAPPDATA%\equip-sync-m-module\`:

```
incoming/        ← PDF 드롭 (감시 대상)
processing/      ← 처리 중
done/            ← 완료된 A4 2-up PDF
done/originals/  ← 원본 보관 (keep_originals=true)
error/           ← 처리 실패한 원본
logs/            ← rotating 로그
config.ini       ← 운영자 설정 (자동 생성)
agent.json       ← 에이전트 페어링 정보 (v0.3+)
```

## config.ini

첫 실행 시 자동 생성. 주요 항목:

```ini
[paths]
incoming = ...           ; 감시할 폴더
done = ...               ; 결과 폴더

[pipeline]
mirror = horizontal      ; horizontal | none
fit = original           ; original | contain | cover
keep_originals = true    ; 원본 보관 여부
oversize_action = error  ; error | single (사이즈 초과 디자인 처리)

[gui]
appearance = system      ; system | light | dark

[printer]
name =                   ; v0.3 자동 인쇄 시 사용

[log]
level = INFO
```

## 라이선스

TBD

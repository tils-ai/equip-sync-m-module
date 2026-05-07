# equip-sync-m-module

머그컵 생산용 **전사지 출력 프린터** 자동화 워처.

## 동작

`incoming/` 폴더에 PDF 파일이 추가되면 감지하여 다음 작업을 수행합니다.

1. **좌우 반전** — 전사지에 거울상으로 출력해야 머그컵에 입혔을 때 정상 방향이 됨
2. **2건 페어링** — FIFO로 두 건이 쌓일 때까지 대기
3. **A4 가로 2-up 배치** — A4(297×210mm) 가로 한 장에 위·아래로 두 건을 배치
4. **`done/` 이동** — 합쳐진 1장의 PDF를 완료 폴더로 옮김

> 1건만 들어와 있으면 다음 1건이 들어올 때까지 무기한 대기합니다 (시간 임계치 없음).

자동 인쇄·API 풀링·GUI는 v2에서 추가됩니다.

## 요구사항

- Windows 10/11
- Python 3.11+

## 설치 (개발 / 직접 실행)

```bash
git clone https://github.com/tils-ai/equip-sync-m-module
cd equip-sync-m-module
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m watcher
```

릴리즈된 단일 실행 파일(.exe)은 추후 GitHub Releases로 배포 예정.

## 폴더 구조 (운영 시)

기본값(`%LOCALAPPDATA%\equip-sync-m-module\`):

```
incoming/      ← PDF 드롭 (감시 대상)
processing/    ← 처리 중 (락 마커 역할)
done/          ← 완료된 A4 2-up PDF
done/originals/ ← 원본 보관 (keep_originals=true 일 때)
error/         ← 처리 실패한 원본
logs/          ← 로그 파일 (rotating)
config.ini     ← 운영자 설정 (자동 생성)
```

## config.ini

첫 실행 시 자동 생성됩니다.

```ini
[paths]
incoming = ...           ; 감시할 폴더
done = ...               ; 결과 폴더

[pipeline]
mirror = horizontal      ; horizontal | none
fit = contain            ; contain | cover
keep_originals = true    ; 원본 보관 여부

[printer]
name =                   ; v2 자동 인쇄 시 사용
```

## 라이선스

TBD

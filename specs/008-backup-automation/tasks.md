# Tasks: 백업 자동화 — 함께 백업하고 함께 복원

**Input**: plan.md, spec.md, research.md, data-model.md, contracts/backup-cli.md · **Code root**: `~/Documents/my-blog`

## Phase 1: Setup

- [x] T001 `.gitignore`에 `backups/`

## Phase 2: US2 원할 때 백업 (P1) 🎯 — 자동 백업의 기반

- [x] T002 [US2] `tools/backup.py`: 잠금, 임시 폴더, 두 DB 온라인 백업·무결성, 키·설정 복사, uploads 링크/복사, manifest, 이름 바꿈, 권한
- [x] T003 [US2] `backup-blog.command`(더블클릭 백업, 결과를 보여 주고 창 유지)

## Phase 3: US1 매일 자동 (P1)

- [x] T004 [US1] `tools/backup.py` `--daily`·`--keep`(정리 규칙)·임시 폴더 청소·`--quiet`
- [x] T005 [US1] `start-blog.command`: 켜기 전 `--daily`, 켜져 있는 동안 1시간마다, 끌 때 함께 종료, 실패해도 블로그는 켬

## Phase 4: US3 복원 (P2)

- [x] T006 [US3] `tools/restore.py`: 목록, 확인값 검사, 서버 포트 확인, 안전 백업, 백업 그대로 되돌림(`os.replace`, `-wal`·`-shm` 삭제, 남는 파일 치움)

## Phase 5: Polish

- [x] T007 [P] `tests/smoke_backup.py` (contracts 확인 1~7)
- [x] T008 [P] `deploy/my-blog-backup.service.example`·`.timer.example`, `deploy/README.md` 운영: 백업·복원
- [x] T009 `README.md` 백업·복원 절, 파일 구조
- [x] T010 001~007 회귀
- [x] T011 requirements.md 두 사본·원본 문서: NFR-16 추가, NFR-08·14, 7장 남은 과제

## Phase 6: 점검 결과

- [x] T012 점검: 스모크 008(7: 내용·권한·WAL 회원 포함·`--daily`·정리 규칙·하드 링크·켜진 서버 거절·변조/경로 거절·복원 그대로·안전 백업·선택 파일
  없음), `start-blog.command` 흉내(처음엔 "아직 백업할 자료 없음", 다음엔 백업 1개, 끈 뒤 남는 프로세스 0), Python 3.9로 스모크 003~008 모두 통과,
  화면 004(42)·005(24)·006(36), 스모크 001(4)·002(2) 통과

## Phase 7: 독립 검토 반영 (research.md D7)

- [x] T013 `tools/backup.py` 안전 백업은 있는 것 모두·망가진 DB는 파일째, 백업 위치 확인(남도 쓰는·남의 폴더 거절, 만든 폴더만 700), `.lock` O_NOFOLLOW,
  root 거절, 정리 실패는 경고, 목록은 읽을 수 없는 항목 건너뜀, 업로드 링크 전 앞 백업 파일 확인값 검사, `--kind`, Ctrl + C 안내
- [x] T014 `tools/restore.py` 두 단계(준비 → 한꺼번에 바꿔 넣기)와 실패 시 안전 백업으로 되돌림, 복원 중 잠금, localhost IPv4·IPv6·PHP-FPM 소켓 확인,
  설정 파일은 기본으로 그대로(`--with-config`), 업로드 손상은 그 파일만 제외, 남의 백업 거절, 안전한 임시 파일, `fullmatch`
- [x] T015 `tests/smoke_backup.py` 15개(복원 견고성 8개 추가: blog.db 없음·망가진 DB·중간 실패 되돌림·잠금·설정 유지·업로드 손상·남도 쓰는 위치·root·
  IPv6 포트), Python 3.9·3.13, 문서(README·deploy/README·계약·data-model) 갱신

## Dependencies

T002 → T003·T004 → T005, T002 → T006 → T007. 문서(T008·T009)는 나란히.

# Implementation Plan: 백업 자동화 — 함께 백업하고 함께 복원

**Branch**: `008-backup-automation` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-backup-automation/spec.md`

**Code root**: `~/Documents/my-blog` (GitHub `changpcg/my-blog`)

## Summary

- `tools/backup.py`(표준 라이브러리): 잠금(`fcntl.flock`) → 임시 폴더 `.tmp-…`에 두 DB를 `sqlite3` 온라인 백업(`Connection.backup`, 원본은 `mode=rw` URI로
  열어 없는 DB를 만들지 않음) → `PRAGMA integrity_check` → 키·설정 복사 → uploads는 앞 백업과 이름·크기·수정 시각이 같으면 `os.link`, 아니면 복사 →
  `manifest.json` → 이름 바꿈 → `--keep` 정리. 옵션 `--daily`, `--keep N`, `--dest`, `--quiet`, `--kind`.
- `tools/restore.py`: 인자 없으면 목록. 백업 폴더를 받으면 확인값 검사 → 서버 포트(8000·8080, `--ports`) 확인 → 안전 백업(`_before-restore`) →
  백업에 있는 그대로 되돌림(같은 폴더의 임시 파일에 쓴 뒤 `os.replace`, 낡은 `-wal`·`-shm` 삭제, 백업에 없던 파일은 치움).
- `backup-blog.command`(더블클릭 백업), `start-blog.command`(켜기 전 `--daily`, 켜져 있는 동안 1시간마다 `--daily`, 끌 때 함께 정리), `.gitignore`에
  `backups/`.
- 배포: `deploy/my-blog-backup.service.example`·`.timer.example`(매일 04:10, myblog 사용자, `/var/backups/my-blog`), deploy/README 운영 절의 백업·복원.

## Technical Context

**Language/Version**: Python 3.9+ 표준 라이브러리(`sqlite3`, `hashlib`, `json`, `os`, `shutil`, `fcntl`, `socket`, `argparse`), bash(macOS .command)

**Primary Dependencies**: 없음

**Storage**: 백업 폴더(기본 `<블로그 폴더>/backups/`, 바꾸려면 `--dest`·`MYBLOG_BACKUP_DIR`)

**Testing**: `tests/smoke_backup.py`(임시 폴더: 서버로 blog.db를 만들고, 회원 DB는 WAL 모드로 직접 만들어 합쳐지지 않은 변경을 둔 채 백업 → 내용·무결성·권한,
`--daily`, 하드 링크, 정리 규칙, 켜진 서버 거절, 변조 거절, 복원 그대로·안전 백업·`-wal` 정리, 없는 선택 파일) + 001~007 회귀

**Target Platform**: macOS(사용자 컴퓨터, Python 3.9), Ubuntu VPS(systemd)

**Constraints**: 서버를 끄지 않고 백업(온라인 백업), 복원은 서버를 끈 뒤. 비밀 파일 권한. 같은 파일 시스템이 아니면 하드 링크 대신 복사

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* (헌법 v1.3.0)

| 원칙 | 확인 | 결과 |
| --- | --- | --- |
| I 서버 판단 | 화면·API 변경 없음(도구는 컴퓨터에서만 실행). 비밀 파일은 600·폴더 700, git 제외 | 통과 |
| II 설치 없음 | Python 표준 라이브러리만, 새 라이브러리 없음 | 통과 |
| III 서명·POST | 회원 연결 변경 없음. 복원은 sso.key와 두 DB를 함께 되돌려 서명 키·회원 번호가 어긋나지 않음 | 통과 |
| IV 데이터 보존 | 원칙의 백업 범위 그대로, 두 DB 함께 백업·복원, 복원 전 안전 백업, 스키마 변경 없음 | 통과 |
| V 추적 | NFR-16 추가, NFR-08·14와 7장 남은 과제 갱신 작업 포함 | 통과 |
| VI 한국어·모든 사람 | 도구 출력·오류는 한국어, 다음에 할 일을 알려 줌 | 통과 |

**Phase 1 뒤 재확인**: 새 네트워크 입구 없음(포트는 확인만, 연결해 보고 바로 닫음). 위반 없음.

## Project Structure

```text
my-blog/
├── tools/backup.py · tools/restore.py
├── backup-blog.command · start-blog.command(자동 백업)
├── deploy/my-blog-backup.service.example · deploy/my-blog-backup.timer.example · deploy/README.md(운영: 백업·복원)
├── .gitignore(backups/) · README.md(백업·복원)
└── tests/smoke_backup.py
```

## Complexity Tracking

해당 없음.

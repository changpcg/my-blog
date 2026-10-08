# Feature Specification: 백업 자동화 — 함께 백업하고 함께 복원

**Feature Branch**: `008-backup-automation`

**Created**: 2026-10-08

**Status**: Implemented (2026-10-08)

**Input**: User description: "다음 작업 — 백업 자동화: 블로그 DB·회원 DB·업로드·키·설정을 함께, 켤 때 하루 한 번 자동으로 백업하고 오래된 백업 정리, 손으로 백업·복원 도구"

**관련 요구사항 ID**: NFR-08(개정), 7장 남은 과제 "회원 DB와 blog.db는 항상 함께 백업·복원"(완료 처리), NFR-14(개정: 배포 안내의 백업) /
새 ID: NFR-16(자동 백업과 복원 도구)

**조사 근거**: 헌법 원칙 IV는 백업 범위(blog.db·uploads/·php-auth/db/·php-auth/oauth.config.php·deploy.config.json)와 "회원 DB와 blog.db는 함께"를
정했지만, 지금은 사람이 직접 복사해야 한다(README·deploy/README의 cp·tar 안내). 회원 DB는 WAL 모드라 서버가 켜진 채 파일만 복사하면 최근 변경이
빠질 수 있고, 복원 때 한쪽 DB만 되돌리면 회원 번호가 어긋난다. 티스토리·네이버는 서비스가 백업을 맡지만, 우리 블로그는 내 컴퓨터(또는 내 서버)에
있으므로 백업도 스스로 돌아야 한다.

## Clarifications

### Session 2026-10-08

- 범위는 사용자가 고른 "백업 자동화". "알아서 진행"이라 아래 기본값은 Assumptions에 적고 진행한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 켜 두기만 하면 매일 백업된다 (Priority: P1)

블로그 주인은 평소처럼 `start-blog.command`로 블로그를 켠다. 그날 백업이 없으면 바로 하나 만들고, 며칠 켜 두어도 날짜가 바뀌면 새로 만든다.
오래된 백업은 최근 14개만 남기고 정리된다.

**Why this priority**: 사용자가 고른 핵심이고, 사람이 잊어도 백업이 남아야 한다.

**Independent Test**: 블로그를 켜고 `backups/`에 오늘 날짜 폴더가 생기는지, 다시 켜도 오늘 것이 하나뿐인지, 15번째 날에 가장 오래된 것이 지워지는지 본다.

**Acceptance Scenarios**:

1. **Given** 오늘 백업이 없는 상태, **When** `start-blog.command`로 켜면, **Then** 블로그가 켜지기 전에 `backups/날짜_시각/`가 생기고 "백업했어요"가 보인다.
2. **Given** 오늘 백업이 이미 있으면, **Then** 새로 만들지 않는다.
3. **Given** 블로그를 켠 채 날짜가 바뀌면, **Then** 한 시간 안에 새 날짜 백업이 생긴다.
4. **Given** 자동 백업이 15개째가 되면, **Then** 가장 오래된 자동 백업 하나가 지워진다(복원 직전 안전 백업과 사람이 넣은 다른 폴더는 지우지 않음).
5. **Given** 백업이 실패하면(디스크 가득 등), **Then** 이유를 한국어로 보여 주고 블로그는 그대로 켜진다.

---

### User Story 2 - 원할 때 바로 백업한다 (Priority: P1)

블로그 주인은 큰 작업 전에 `backup-blog.command`를 더블클릭(또는 `python3 tools/backup.py`)해 지금 상태를 백업한다. 서버를 끄지 않아도 된다.

**Why this priority**: 자동 백업 사이의 변경을 지키는 가장 쉬운 방법이다.

**Independent Test**: 서버가 켜져 글을 쓰는 중에 백업을 만들고, 백업 속 두 DB가 온전하고(무결성 검사 통과) 방금 쓴 글·가입한 회원이 들어 있는지 본다.

**Acceptance Scenarios**:

1. **Given** 두 서버가 켜져 있어도, **When** 백업하면, **Then** 두 DB를 같은 순간에 가깝게 온전한 사본(SQLite 백업 기능)으로 저장하고, 회원 DB의 아직
   합쳐지지 않은 최근 변경(WAL)도 들어간다.
2. **Given** 백업, **Then** 폴더에 blog.db·회원 DB·sso.key·oauth.config.php(있으면)·deploy.config.json(있으면)·uploads/와 목록 파일(manifest.json:
   파일마다 크기·SHA-256, 글 수·회원 수)이 있다.
3. **Given** 업로드 파일이 앞 백업과 같으면, **Then** 복사하지 않고 하드 링크로 이어 디스크를 아낀다.
4. **Given** 백업에는 비밀(키·비밀번호 해시)이 들어 있으므로, **Then** 백업 폴더는 주인만 열 수 있다(폴더 700, DB·키·설정 600).
5. **Given** 백업이 도중에 끊기면, **Then** 반쯤 만든 폴더는 완성된 백업으로 보이지 않는다(임시 이름 → 끝나면 이름 바꿈).

---

### User Story 3 - 백업한 그때로 되돌린다 (Priority: P2)

블로그 주인은 실수로 글을 지웠을 때 `python3 tools/restore.py`로 백업 목록을 보고, 고른 백업으로 두 DB·업로드·키·설정을 함께 되돌린다.

**Why this priority**: 백업은 복원할 수 있어야 의미가 있지만, 자주 쓰지는 않는다.

**Independent Test**: 백업 뒤 글을 지우고 사진을 올린 다음 서버를 끄고 복원 → 지운 글이 돌아오고 새 사진은 빠지며, 복원 직전 상태가 안전 백업으로 남는지 본다.

**Acceptance Scenarios**:

1. **Given** 인자 없이 실행하면, **Then** 백업 목록(날짜·글 수·회원 수·크기)과 사용법을 보여 준다.
2. **Given** 블로그(8000)나 회원 서버(8080)가 켜져 있으면, **Then** "서버를 끈 뒤 다시 실행하세요"로 거절하고 아무것도 바꾸지 않는다.
3. **Given** 백업 파일이 목록 파일의 확인값과 다르면(손상·변조), **Then** 거절하고 아무것도 바꾸지 않는다.
4. **Given** 복원하면, **Then** 먼저 지금 상태를 `…_before-restore` 안전 백업으로 남기고(지금 DB가 망가졌거나 blog.db가 없어도 있는 것은 모두),
   두 DB·서명 키·업로드를 백업 그대로(백업에 없던 업로드·DB는 치움) 되돌리며, 낡은 `-wal`·`-shm` 파일을 지운다. 이 컴퓨터의 설정 파일
   (deploy.config.json·oauth.config.php)은 그대로 둔다(없을 때만 백업에서, `--with-config`면 백업 그대로).
5. **Given** 되돌리는 중간에 실패하면(디스크 가득 등), **Then** 안전 백업으로 자동으로 돌려놓아 두 DB가 엇갈린 채 남지 않는다.
6. **Given** 복원 뒤 서버를 켜면, **Then** 글·회원·로그인 연결이 백업한 그때와 같다.

---

### Edge Cases

- 회원 서버를 한 번도 켜지 않아 회원 DB·sso.key가 없으면? → 있는 것만 백업하고 목록 파일에 "없음"으로 적는다.
- 백업 두 개가 동시에 돌면? → 뒤의 것은 "다른 백업이 진행 중이에요"로 끝난다(잠금 파일).
- 같은 초에 두 번 백업하면? → 폴더 이름 뒤에 `-2`를 붙인다.
- 백업 위치를 바꾸고 싶으면? → `--dest 폴더` 또는 `MYBLOG_BACKUP_DIR`(외장 디스크·클라우드 동기화 폴더 권장).
- `MYBLOG_CONFIG`로 설정 파일 위치를 바꾼 경우 → 그 파일을 백업하고 복원도 그 위치로.
- 공개 운영(VPS) → systemd 타이머 예시로 매일 새벽 백업, 복원은 두 서비스를 멈춘 뒤.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 백업 도구는 MUST blog.db·php-auth/db/sqlite.db를 SQLite 온라인 백업으로, sso.key·oauth.config.php·deploy.config.json·uploads/를 파일로 한
  폴더에 함께 저장하고, 두 DB는 무결성 검사를 통과해야 완성으로 본다. (새 NFR-16, 헌법 IV)
- **FR-002**: 백업 폴더는 MUST 임시 이름으로 만든 뒤 다 되면 `YYYY-MM-DD_HHMMSS`로 이름을 바꾸고, `manifest.json`에 파일마다 크기·SHA-256과 글 수·회원
  수·만든 시각을 적는다. (새 NFR-16)
- **FR-003**: `--daily`는 MUST 오늘 자동/수동 백업이 있으면 건너뛰고, `--keep N`(기본 14)은 이름 규칙에 맞고 목록 파일이 있는 일반 백업만 오래된
  순서로 지운다. (새 NFR-16)
- **FR-004**: `start-blog.command`는 MUST 서버를 켜기 전에 `--daily` 백업을 하고, 켜져 있는 동안 한 시간마다 `--daily`를 다시 시도하며, 백업이
  실패해도 블로그는 켠다. `backup-blog.command`는 바로 백업한다. (새 NFR-16)
- **FR-005**: 복원 도구는 MUST 서버가 켜져 있거나(localhost의 IPv4·IPv6, 공개 운영의 PHP-FPM 소켓) 다른 백업·복원이 진행 중이거나 DB·키의 확인값이
  다르면 거절하고, 복원 전에 안전 백업을 만들고, 준비를 모두 마친 뒤 한꺼번에 바꿔 넣어 두 DB를 함께 되돌리며, 실패하면 안전 백업으로 돌려놓는다. 이 컴퓨터의
  설정 파일은 기본으로 그대로 둔다. (새 NFR-16, 헌법 IV "함께 복원")
- **FR-006**: 백업 폴더는 MUST 주인만 읽을 수 있게(폴더 700, 비밀 파일 600) 만들고 git에 올라가지 않는다(`backups/`). 남도 쓸 수 있는 폴더·남의 폴더에는
  백업하지 않고, 두 도구 모두 root 실행을 막는다(파일 주인이 바뀌어 다음 백업·서버가 실패하지 않게). (헌법 I·기술 제약 "비밀")
- **FR-007**: 배포 안내는 MUST systemd 타이머 예시(매일, myblog 사용자)와 복원 순서를 담는다. (NFR-14 개정)
- **FR-008**: 구현 후 MUST requirements.md 두 사본과 원본 문서에 NFR-16을 더하고 NFR-08·14와 7장 남은 과제를 고친다. (헌법 V)

### Key Entities

- **백업 폴더**: `backups/2026-10-08_140512/` = `blog.db`, `php-auth/db/sqlite.db`, `php-auth/db/sso.key`, `php-auth/oauth.config.php`, `deploy.config.json`,
  `uploads/…`, `manifest.json`. 안전 백업은 이름 끝이 `_before-restore`.
- **manifest.json**: `format`, `created_at`, `kind`(auto·manual·before-restore), `files{경로: {size, sha256}}`, `missing[]`, `counts{posts, blog_users,
  members}`, `config_path`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 블로그를 켜면 그날 백업이 정확히 1개 생기고, 자동 백업은 최근 14개만 남는다.
- **SC-002**: 서버가 켜진 채 만든 백업의 두 DB가 100% 무결성 검사를 통과하고, WAL에만 있던 회원 변경도 들어 있다.
- **SC-003**: 바뀌지 않은 업로드는 두 번째 백업부터 추가 용량 0(하드 링크).
- **SC-004**: 복원 뒤 글·회원·업로드·키가 백업과 100% 같고, 복원 직전 상태가 안전 백업으로 남는다. 손상된 백업·켜진 서버에서는 0건 바뀐다.
- **SC-005**: 기존 스모크 테스트(001~007)가 모두 통과한다.

## Assumptions

- 백업 위치 기본값은 블로그 폴더 안 `backups/`다. 디스크 고장까지 대비하려면 `MYBLOG_BACKUP_DIR`로 외장 디스크·클라우드 동기화 폴더를 쓰라고 안내한다.
- 블로그 화면에서 백업·복원하는 기능은 만들지 않는다(복원은 서버를 꺼야 하고, 비밀 파일을 화면으로 내보내지 않으려고).
- 백업 암호화·원격 업로드는 범위 밖이다(폴더 권한으로 보호).
- 날짜는 이 컴퓨터의 현지 시각 기준이다.

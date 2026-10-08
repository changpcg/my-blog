# Implementation Plan: 남은 보안 과제 정리 (댓글 비밀번호·로그아웃 표·탈퇴 회원 댓글)

**Branch**: `001-security-gap-fixes` | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-security-gap-fixes/spec.md`

**Note**: 코드는 이 문서 저장소가 아니라 `~/Documents/my-blog`에 있다. 아래 경로는 모두 my-blog 기준이다.

## Summary

세 가지를 서버에서 고친다.

1. **댓글 비밀번호(P1)**: `DELETE /api/comments/{id}`가 비밀번호를 JSON 본문으로만 받고, 주소에
   `password`가 있으면 거절한다. blog.db에 `comment_pw_fails` 표를 더해 댓글·IP별 15분 5회,
   댓글당 15분 20회에 잠그고 틀릴 때마다 0.5초 늦춘다.
2. **로그아웃 표(P2)**: 블로그는 회원 페이지와 연결된 계정(`users.auth_uid`)에만 표를 만들고 표에
   `uid`를 넣는다. 화면은 표를 주소가 아니라 **POST 폼**으로 `sso_logout.php`에 보낸다. PHP는 POST만
   받고, `uid == $_SESSION['uid']`일 때만 로그아웃하며, `sso_used_nonces` 표로 1회용을 강제한다.
3. **탈퇴 회원 댓글(P3)**: `api_DELETE_users`가 그 회원의 답글을 먼저 지우고, 남의 답글이 남는 댓글은
   `deleted = 1` 자리로 바꾼다. 서버 시작 시 한 번, 부모가 사라진 답글에 "삭제된 댓글" 자리를 같은
   id로 되살린다.

## Technical Context

**Language/Version**: Python 3.9+ (표준 라이브러리만), PHP 8 (pdo_sqlite·mbstring)

**Primary Dependencies**: 없음 (http.server, sqlite3, hmac / PDO). 화면은 바닐라 JS

**Storage**: SQLite — `blog.db`(블로그), `php-auth/db/sqlite.db`(회원). 둘 다 `CREATE TABLE IF NOT EXISTS`로 표 추가

**Testing**: 자동 테스트 프레임워크 없음. `quickstart.md`의 curl·브라우저 시나리오로 수동 검증 +
표준 라이브러리 `unittest`/`urllib`로 만든 스모크 스크립트(`tests/smoke_security_gaps.py`, 선택)

**Target Platform**: macOS 로컬 (블로그 127.0.0.1:8000, 회원 localhost:8080)

**Project Type**: 웹 서비스 2개 (Python 블로그 서버 + PHP 회원 서버) + SPA 화면

**Performance Goals**: 정상 로그아웃 2초 이내 유지(SC-004). 잠금 확인은 색인 1회 조회

**Constraints**: 헌법 II(설치 없음), IV(기존 DB 그대로 열림, 표·칸 추가만), 쿼리는 모두 `?` 바인딩

**Scale/Scope**: 개인·소규모. 수정 파일 4개: `server.py`, `static/app.js`, `php-auth/public/sso_logout.php`, `php-auth/src/db.php`(+ `src/sso.php` 함수 1개)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 원칙 | 확인 | 결과 |
| --- | --- | --- |
| I. 서버가 최종 판단 | 잠금·주소 비밀번호 거절·uid 일치·1회용 모두 서버에서 강제. 화면은 보내는 방식만 바꿈 | 통과 |
| I. 비밀은 주소에 없음 | 댓글 비밀번호 → 본문, 로그아웃 표 → POST 본문 | 통과 (현재 위반 2건 해소) |
| II. 설치 없이 | 새 의존성 없음 | 통과 |
| III. 서명·1회용·POST | 로그아웃 표에 uid·nonce, PHP가 nonce 기록, `sso_logout.php` GET 거절 | 통과 (현재 위반 해소) |
| IV. 데이터 보존 | 새 표 2개(`comment_pw_fails`, `sso_used_nonces`)만 추가. 고아 답글은 지우지 않고 부모 자리를 되살림. 마이그레이션 전 `blog.backup-before-reply-restore.db` 자동 복사 | 통과 |
| V. 요구사항 추적 | FR마다 BLOG-08·AUTH-13·SEC-03·SEC-12·BLOG-16·SOC-01 매핑, 완료 후 requirements.md 갱신 작업 포함 | 통과 |
| VI. 한국어·접근성 | 새 거절 문구 한국어, 화면 구조 변화 없음 | 통과 |

설계 후 재확인(Phase 1 이후): 위반 없음. Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/001-security-gap-fixes/
├── plan.md              # 이 파일
├── research.md          # Phase 0: 결정과 근거
├── data-model.md        # Phase 1: 새 표·상태 변화
├── quickstart.md        # Phase 1: 검증 시나리오
├── contracts/
│   ├── blog-api.md      # DELETE /api/comments/{id}, POST /api/logout, DELETE /api/users/{id}
│   └── sso-logout.md    # POST sso_logout.php, 로그아웃 표 형식
└── tasks.md             # /speckit-tasks 출력
```

### Source Code (~/Documents/my-blog)

```text
my-blog/
├── server.py                     # init_db 마이그레이션, make_logout_ticket, api_POST_logout,
│                                 # api_DELETE_comments, api_DELETE_users, 잠금 헬퍼
├── static/app.js                 # 댓글 삭제(본문 전송), logout()(POST 폼)
├── php-auth/
│   ├── src/db.php                # sso_used_nonces 표
│   ├── src/sso.php               # read_logout_ticket() 추가
│   └── public/sso_logout.php     # POST 전용, uid·nonce 확인
└── tests/smoke_security_gaps.py  # (선택) 표준 라이브러리 스모크 테스트
```

**Structure Decision**: 기존 2서버 구조를 그대로 쓰고 새 파일은 선택적 스모크 테스트 1개뿐이다.

## Complexity Tracking

해당 없음.

# Tasks: 남은 보안 과제 정리

**Input**: Design documents from `/specs/001-security-gap-fixes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: 자동 테스트는 요청되지 않았다. 각 스토리 끝에 quickstart.md 시나리오 검증 작업을 둔다.

**Code root**: `~/Documents/my-blog` (아래 경로는 이 폴더 기준)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일이라 동시에 진행 가능
- **[Story]**: US1 댓글 비밀번호 / US2 로그아웃 표 / US3 탈퇴 회원 댓글

## Phase 1: Setup

- [x] T001 my-blog 백업: `blog.db` → `blog.backup-before-001.db`, `php-auth/db/` → `php-auth/db.backup-before-001/`
- [x] T002 [P] my-blog를 git 저장소로 만들고 현재 상태를 첫 커밋 (`.gitignore`: `*.db`, `*.db-*`, `uploads/`, `php-auth/db/`, `php-auth/oauth.config.php`, `.DS_Store`)

## Phase 2: Foundational

- [x] T003 `server.py` `api_DELETE_comments`의 "자리 정리" 블록(1559~1565행)을 `_tidy_deleted_parent(conn, parent_id)` 함수로 뽑아내기 (US1·US3 공통, 동작 변화 없음)

**Checkpoint**: 기존 댓글 삭제·답글 정리가 그대로 동작

## Phase 3: User Story 1 - 방문자 댓글 비밀번호 보호 (P1) 🎯 MVP

**Goal**: 비밀번호를 본문으로만 받고 15분 5회/20회 잠금
**Independent Test**: quickstart.md US1 1~7

- [x] T004 [US1] `server.py` `init_db`에 `comment_pw_fails` 표와 `idx_comment_pw_fails` 색인 추가 (data-model.md)
- [x] T005 [US1] `server.py`에 잠금 헬퍼 추가: `pw_lock_minutes(conn, cid, ip)` (오래된 행 정리 + 5/20회 판정 + 남은 분), `record_pw_fail(conn, cid, ip)`, `clear_pw_fails(conn, cid)`
- [x] T006 [US1] `server.py` `api_DELETE_comments`: 쿼리 `password` 거절(400) → 404 문구 "댓글을 찾을 수 없어요." → 권한자 통과 → 방문자 댓글이면 잠금 확인(429) → `self.body()`의 `password` 확인, 틀리면 기록·0.5초·403 "비밀번호가 맞지 않아요." → 성공 시 기록 삭제 (contracts/blog-api.md)
- [x] T007 [P] [US1] `static/app.js` 619행: `api('comments/' + id, { method: 'DELETE', body: pw ? { password: pw } : undefined })`로 변경
- [x] T008 [US1] quickstart.md US1 검증, 화면 Network 탭에서 주소에 비밀번호 없음 확인

**Checkpoint**: US1만으로 배포 가능 (P1 MVP)

## Phase 4: User Story 2 - 로그아웃 표를 회원에 묶고 1회용 (P2)

**Goal**: 다른 회원·재사용·GET 링크로는 회원 페이지가 로그아웃되지 않음
**Independent Test**: quickstart.md US2 1~7

- [x] T009 [P] [US2] `php-auth/src/db.php`에 `sso_used_nonces(nonce PRIMARY KEY, expires)` 표 추가
- [x] T010 [P] [US2] `php-auth/src/sso.php`에 `read_logout_ticket(string $t): ?array` 추가 (contracts/sso-logout.md)
- [x] T011 [US2] `php-auth/public/sso_logout.php`: POST만, `read_logout_ticket`, uid == `$_SESSION['uid']`, nonce 미사용 확인 후 기록·로그아웃, 만료 nonce 정리, 항상 블로그로 302 (T009·T010 이후)
- [x] T012 [US2] `server.py` `make_logout_ticket(auth_uid)`: payload에 `uid`, nonce 16바이트
- [x] T013 [US2] `server.py` `api_POST_logout`: 세션 삭제 전 `self.user` 확인, `auth_uid` 있을 때만 `auth_logout: {action, t}` 응답, `auth_logout_url` 제거 (T012 이후)
- [x] T014 [P] [US2] `static/app.js` `logout()`: `r.auth_logout`이 있고 `reachable(r.auth_url)`이면 숨은 POST 폼(`t` 필드)을 만들어 submit, 없으면 지금처럼 블로그만
- [x] T015 [US2] quickstart.md US2 검증 (특히 3·4·5: 다른 회원·재사용·GET)

**Checkpoint**: US1 + US2 독립 동작

## Phase 5: User Story 3 - 탈퇴 회원 댓글의 답글 보존 (P3)

**Goal**: 탈퇴 후에도 남의 답글이 보이고 숫자가 맞음
**Independent Test**: quickstart.md US3 1~5

- [x] T016 [US3] `server.py` `api_DELETE_users`: `DELETE FROM comments WHERE user_id = ?` 한 줄을 research.md R4의 1~4단계로 교체 (T003의 `_tidy_deleted_parent` 사용, 자리는 `user_id = NULL`)
- [x] T017 [US3] `server.py` `init_db`: `restored_orphan_replies` 1회 마이그레이션 — 고아 있으면 `blog.backup-before-reply-restore.db` 복사 후 부모 id로 자리 행 삽입 (research.md R5)
- [x] T018 [US3] 댓글 수 집계 3곳(글 카드 323행, 최근 댓글 970·1127행, 관리 1047·1055·1060행)이 `deleted = 0` 기준으로 화면과 같은지 확인 (복구 후 추가 수정 필요 없으면 확인만)
- [x] T019 [US3] quickstart.md US3 검증 (백업 DB 복사본으로 5번 포함)

## Phase 6: Polish & Cross-Cutting

- [x] T020 [P] (선택) `tests/smoke_security_gaps.py`: 표준 라이브러리 `unittest`+`urllib`로 US1 2~4, US2 2, US3 3 자동 확인
- [x] T021 기존 blog.db로 서버를 다시 켜 글·댓글·로그인 유지 확인 (헌법 IV)
- [x] T022 [P] `requirements.md`(문서 저장소)와 원본 Claude Docs 문서 갱신: BLOG-08·AUTH-13·SEC-03·SEC-12·BLOG-16 완료 기준, 7·8장 남은 과제 3건 체크 (헌법 V)
- [x] T023 my-blog 커밋, 문서 저장소 커밋·push

## Dependencies & Execution Order

- Setup(T001~T002) → Foundational(T003) → US1·US2·US3 (서로 독립, 순서는 우선순위대로 권장)
- US1: T004 → T005 → T006, T007은 동시 가능 → T008
- US2: T009·T010 동시 → T011 / T012 → T013 / T014 동시 → T015
- US3: T003 필요 → T016 → T017 → T018 → T019
- Polish는 원하는 스토리 완료 후

## Parallel Opportunities

- T007(app.js) ∥ T004~T006(server.py)
- T009·T010(PHP) ∥ T012·T013(server.py) ∥ T014(app.js)
- `server.py`를 건드리는 작업끼리는 순서대로

## Implementation Strategy

1. MVP: Phase 1~3 (US1) 후 멈추고 검증 → 가장 큰 보안 구멍 해소
2. US2 → 검증 → US3 → 검증
3. Polish에서 문서 갱신·커밋

# Tasks: 회원 계정을 두 서버에서 함께 관리하기

**Input**: plan.md, spec.md, contracts/bridge.md · **Code root**: `~/Documents/my-blog`

## Phase 1: Setup

- [x] T001 DB 백업 (`blog.backup-before-002.db`, `php-auth/db.backup-before-002/`)

## Phase 2: Foundational

- [x] T002 [P] `php-auth/src/db.php`: `users.session_ver`, `users.nickname_at` 칸(없을 때만), `bridge_cache` 표
- [x] T003 [P] `server.py` `init_db`: `users.auth_joined`, `users.auth_nick_at` 칸
- [x] T004 [P] `php-auth/src/sso.php`: `sign_bridge()`, `read_bridge()`, `blog_call()`(3초, JSON), 입장권에 `joined`·`nick_at`
- [x] T005 [P] `server.py`: `sign_bridge()`/`read_bridge()`, `post_form()` 헬퍼, 탈퇴 정리를 `delete_blog_account(conn, uid)`로 추출

## Phase 3: US1 내 정보 수정 (P1) 🎯

- [x] T006 [US1] `auth.php`: `current_user()`가 `session_ver` 다르면 로그아웃, `login_user()`가 `session_ver` 기록
- [x] T007 [US1] `public/profile.php`: 닉네임·자기소개 저장, 비밀번호 변경(현재 비밀번호·잠금, SNS 전용은 첫 비밀번호), CSRF
- [x] T008 [US1] `public/index.php`: "내 정보 수정" 링크, SNS 전용 안내 문구 조정
- [x] T009 [US1] `server.py` `api_POST_sso`: `joined` 비교·저장, `nick_at` 반영
- [x] T010 [US1] 검증

## Phase 4: US2 가입 허용 (P2)

- [x] T011 [US2] `server.py` `GET /api/bridge/signup`
- [x] T012 [US2] `auth.php` `signup_open()` (1분 캐시·실패 시 마지막 값·없으면 false)
- [x] T013 [US2] `register.php`·`social_signup.php`·`check_username.php`·`oauth_callback.php`(새 SNS 계정) 차단
- [x] T014 [US2] 검증

## Phase 5: US3 탈퇴 (P3)

- [x] T015 [US3] `public/bridge_delete.php` + `auth.php` `delete_member_local()`
- [x] T016 [US3] `server.py` `POST /api/bridge/delete_member`
- [x] T017 [US3] `server.py` `api_DELETE_users`: `auth_uid` 있으면 회원 서버 먼저, 실패 시 503
- [x] T018 [US3] `profile.php` 탈퇴 섹션: 비밀번호(SNS 전용은 아이디) 확인 → 블로그 먼저 → 로컬 삭제
- [x] T019 [US3] 검증 (한쪽 서버 꺼짐 포함)

## Phase 6: Polish

- [x] T020 `tests/smoke_member_lifecycle.py`
- [x] T021 기존 DB로 시작 확인, requirements.md·원본 문서 갱신, 커밋·push

## Dependencies

Phase 2 → US1·US2·US3 (US3는 T005·T015 필요). `server.py` 작업끼리는 순서대로.

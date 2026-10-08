# Tasks: 인터넷 공개(배포) 준비

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts/), [quickstart.md](./quickstart.md) · **Code root**: `~/Documents/my-blog` · **헌법**: v1.1.1

**Tests**: 스펙이 TDD를 요구하지는 않지만, 헌법 품질 관문(완료 기준을 실제 요청으로 재현, 공개 모드 로컬 점검)과 plan이
`tests/smoke_public_deploy.py`를 산출물로 정했으므로 스토리마다 점검 케이스를 먼저 쓴다. 실제 blog.db·회원 DB는 쓰지 않는다.

**Organization**: 스토리별 단계. 경로는 모두 `my-blog/` 기준(문서 갱신 T046만 `blog-project/`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일이고 앞 작업에 기대지 않아 함께 할 수 있음
- **[Story]**: US1~US4 (spec.md의 사용자 스토리)

---

## Phase 1: Setup

- [x] T001 데이터 백업: `blog.db` → `blog.backup-before-003.db`, `php-auth/db/` → `php-auth/db.backup-before-003/` (둘 다 .gitignore 대상인지 확인)
- [x] T002 [P] `deploy.config.example.json` 새로 만들기(contracts/deploy-config.md의 공개 모드 예시 그대로, 주소는 example.com) + `.gitignore`에 `deploy.config.json` 추가

---

## Phase 2: Foundational (모든 스토리의 바탕)

**⚠️ 이 단계가 끝나야 스토리 작업 시작**

- [x] T003 `server.py` 설정 로더: 모듈 위쪽에 `load_config()` — `MYBLOG_CONFIG` 또는 `BASE_DIR/deploy.config.json`을 읽고 contracts/deploy-config.md "값을 정하는 순서" 표대로 `PUBLIC_MODE`, `BLOG_URL`(새), `AUTH_URL`(기존 상수 대체), `TRUSTED_PROXIES`(`ipaddress` 객체 집합, 공개 모드 기본 `["127.0.0.1", "::1"]` / 개발 모드 기본 `[]`), `SIGNUP_LIMITS`를 정한다. 파일 오류는 예외로 죽지 말고 `CONFIG_ERRORS`에 모은다. `check_config()`가 C1~C7·C11을 contracts 문구 그대로 돌려준다(주소 규칙: "https 오리진만, 경로·쿼리·사용자 정보 없음", 두 오리진 다름). `is_trusted(ip)` 도우미(정규화 비교)
- [x] T004 [P] `php-auth/src/config.php` 새 파일: `app_config()`(요청마다 한 번 읽고 static 캐시, 경로는 `getenv('MYBLOG_CONFIG')` 또는 `dirname(__DIR__, 2) . '/deploy.config.json'`), 같은 우선순위로 `public_mode()`·`app_blog_url()`·`app_auth_url()`·`trusted_proxies()`·`signup_limits()`·`bot_check_enabled()`, `config_errors()`(C1~C6, 문구는 contracts 그대로), `is_trusted_proxy($ip)`(`inet_pton`/`inet_ntop` 정규화)
- [x] T005 `php-auth/src/auth.php`·`php-auth/src/sso.php`: `auth.php` 맨 앞에서 `config.php`를 불러오고, `config_errors()`가 있으면 DB를 열기 전에 503 — 화면 "회원 서버 설정을 확인하고 있어요. 잠시 뒤 다시 시도해 주세요."(JSON 엔드포인트 `check_username.php`·`bridge_*.php`는 `{"ok": false, "error": ...}`), 자세한 이유는 `error_log`. `sso.php`의 `BLOG_URL` 상수를 `app_blog_url()` 값으로(T004 뒤)
- [x] T006 `server.py` `__main__` 시작 순서: `check_config()` 결과가 있으면 "서버를 켜지 않았어요. 아래 설정을 고쳐 주세요." + ` - 문구` 줄들 출력 후 `SystemExit(78)` — 포트·`init_db()`·uploads 폴더보다 먼저(T003 뒤)
- [x] T007 [P] `tests/smoke_public_deploy.py` 뼈대(표준 라이브러리): 임시 폴더에 `server.py`·`static/`·`php-auth/src/`·`php-auth/public/` 복사, 설정 파일·가짜 `oauth.config.php`(naver client_id/secret 더미) 쓰기, 빈 포트 고르기, 블로그·`php -S` 띄우기/끄기(환경변수 지정), 머리글을 붙이고 리디렉션을 따라가지 않는 요청 도우미, 끝나면 프로세스 종료·폴더 삭제. 실제 DB 경로를 절대 열지 않음

**Checkpoint**: 설정 파일 없이 켜면 지금과 똑같다(quickstart A). 깨진 JSON이면 블로그는 78로 끝나고 회원 서버는 503.

---

## Phase 3: User Story 1 — 기본 관리자 비밀번호로는 공개 서버가 켜지지 않는다 (P1) 🎯 MVP

**Goal**: 공개 모드에서 비밀번호가 없거나 admin1234·약한 값이면 블로그가 켜지지 않고, 바꾸면 예전 관리자 세션이 끊긴다.

**Independent Test**: 공개 모드 임시 복사본을 비밀번호 없음/admin1234/짧은 값/강한 값으로 켜 본다(quickstart B 1~3줄).

- [x] T008 [P] [US1] `tests/smoke_public_deploy.py`에 US1 케이스: 세 가지 약한 경우 종료 코드 78·한국어 안내·blog.db 미생성, 강한 값으로 켜면 `/api/login` admin1234는 401·새 비밀번호는 200, 다른 강한 값으로 다시 켜면 예전 세션 쿠키의 `/api/blog` `is_admin`이 false
- [x] T009 [US1] `server.py` `check_config()`에 C8~C10: 공개 모드에서 `BLOG_PASSWORD` 환경변수 없음 / 값이 `admin1234` / "12자 미만이거나 영문·숫자 중 하나가 없음" → contracts 문구
- [x] T010 [US1] `server.py` `init_db()` 관리자 처리: 기존 해시로 `check_pw(PASSWORD, 기존 해시)`가 실패하면(비밀번호가 바뀜) `DELETE FROM sessions WHERE user_id = 관리자 id` 뒤 새 해시 저장(두 모드 공통, blog.db 스키마 변경 없음)
- [x] T011 [US1] `server.py` 시작 안내: 공개 모드면 contracts/deploy-config.md "성공(공개 모드)" 3줄(공개 주소·회원 서버·콜백 주소), 개발 모드는 지금 출력 그대로
- [x] T012 [US1] 검증: `python3 tests/smoke_public_deploy.py`의 US1 케이스 통과 + 개발 모드에서 기존 blog.db로 켜도 글·댓글 그대로(SC-001·SC-007)

**Checkpoint**: US1만으로도 공개 직후 가장 큰 구멍(기본 관리자 비밀번호)이 막힌다.

---

## Phase 4: User Story 2 — 공개 주소와 HTTPS로 안전하게 접속한다 (P1)

**Goal**: 공개 모드에서 https만 쓰고(308·HSTS·Secure), 모든 주소가 설정 값에서 나오며, 회원 서버는 정식 웹 서버에서만 돈다. 운영자는 배포 안내와 콜백 주소를 본다.

**Independent Test**: 공개 모드 복사본에 `X-Forwarded-Proto: http/https`로 요청해 308·HSTS·Secure를 확인하고, php -S 거절·redirect_uri·관리자 상태를 본다(quickstart B, US2 줄).

### Tests

- [x] T013 [P] [US2] `tests/smoke_public_deploy.py`에 US2 케이스: 블로그 http→308 `https://blog.test/경로`, https→HSTS·`vid`/`session` 쿠키 Secure, 믿는 프록시가 아닌 설정(`trusted_proxies: ["127.0.0.2"]`)에서 308, HEAD도 같은 관문, XFP 없음→500, 회원 서버 php -S(예외 없음)→503, 예외 켬→308/`AUTHSESS` secure·HSTS, `oauth_start.php?provider=naver`의 `redirect_uri=https://auth.test/oauth_callback.php`, 관리자 `GET /api/admin/status`의 `deploy` 값과 `auth: null`(공개 모드 복사본은 https://auth.test에 실제로 연결할 수 없음), 공개 폴더 밖 파일이 열리지 않음(회원 `db/sqlite.db`·`db/sso.key`·`oauth.config.php`, 블로그 `blog.db`·`deploy.config.json`·`php-auth/db/sso.key` 모두 404, SC-004)

### Blog server

- [x] T014 [US2] `server.py` 공개 모드 관문 `Handler.public_gate()`: contracts/public-mode-http.md 규칙 1 — 믿는 프록시 + `X-Forwarded-Proto: https`가 아니면 308 `Location: BLOG_URL + 경로`(경로가 `/`로 시작하지 않으면 `/`), 믿는 프록시인데 XFP 없음이면 500 JSON + 서버 출력 1회. `route()` 맨 앞과 새 `do_HEAD()`에서 호출
- [x] T015 [US2] `server.py` 응답 머리글: `end_headers()`에서 공개 모드면 `Strict-Transport-Security: max-age=31536000`, `send_header()`를 덮어써 공개 모드면 모든 `Set-Cookie`에 `; Secure`(이미 있으면 그대로). 로그아웃 지우기 쿠키도 `HttpOnly; SameSite=Strict` 맞춤
- [x] T016 [US2] `server.py` `api_GET_admin(parts)`: `["status"]`만, `require_admin()`, `auth_post("/bridge_status.php", {"t": sign_bridge({"act": "auth_status"})})` 결과가 200·`ok`면 `auth`, 아니면 `null` → `{"deploy": {"public_mode", "blog_url", "auth_url"}, "auth": ...}` (contracts/admin-status.md)

### Member server

- [x] T017 [US2] `php-auth/src/config.php` `is_https()`와 `enforce_public_mode()`: 공개 모드에서 ① `PHP_SAPI === 'cli-server'`이고 `getenv('ALLOW_PHP_DEV_SERVER') !== '1'`이면 503 안내(contracts 문구), ② https가 아니면 308 `app_auth_url() . REQUEST_URI`, ③ https면 HSTS. `auth.php`에서 `session_start()` 전에 호출
- [x] T018 [US2] `php-auth/src/auth.php` 세션 쿠키: `'secure' => public_mode() || is_https()` (로그아웃·탈퇴의 지우기 쿠키는 `session_get_cookie_params()`를 따르므로 그대로)
- [x] T019 [P] [US2] `php-auth/src/oauth.php` `redirect_uri()`: 공개 모드는 `app_auth_url() . '/oauth_callback.php'`(oauth.config의 `redirect_uri` 무시), 개발 모드는 `redirect_uri`가 있으면 그 값, 없으면 같은 식
- [x] T020 [US2] `php-auth/public/bridge_status.php` 새 파일: POST만(아니면 405), `read_bridge(post_str('t'), 'auth_status')` 실패면 400 `{"ok": false, "error": "서명이 올바르지 않아요."}`, 성공이면 `{"ok": true, "public_mode", "sns": {"callback_url": redirect_uri(), "providers": enabled_providers()}}`. `signup_open()` 등 블로그 호출 금지

### Screens & docs

- [x] T021 [US2] `static/app.js` `renderSettings()`에 '공개 주소' 상자(`GET /api/admin/status`): 실행 모드·블로그 주소·회원 서버 주소·콜백 주소(고정폭)·키가 등록된 SNS, `public_mode` 불일치 경고, 연결 실패 문구(contracts/admin-status.md) + `static/style.css`(다크 모드·375px 넘침 없음)
- [x] T022 [P] [US2] `deploy/nginx-my-blog.conf.example`: blog 서버 블록(`proxy_pass http://127.0.0.1:8000`, `Host`, `X-Forwarded-For $proxy_add_x_forwarded_for`, `X-Forwarded-Proto $scheme`, `client_max_body_size 45m`), auth 서버 블록(`root /srv/my-blog/php-auth/public`, `try_files $uri $uri/ =404`, `fastcgi_pass unix:/run/php/my-blog.sock`, 점 파일 거부), `server_tokens off`, 80번만 쓰고 certbot이 443·이동을 더한다는 주석
- [x] T023 [P] [US2] `deploy/my-blog.service.example`: `User=myblog`, `WorkingDirectory=/srv/my-blog`, `Environment=HOST=127.0.0.1 PORT=8000`, `EnvironmentFile=/etc/my-blog/blog.env`(BLOG_PASSWORD, root 600), `ExecStart=/usr/bin/python3 server.py`, `Restart=on-failure`, `RestartPreventExitStatus=78`, `NoNewPrivileges`·`ProtectSystem=strict`·`ReadWritePaths=/srv/my-blog`·`PrivateTmp`
- [x] T024 [P] [US2] `deploy/php-fpm-my-blog.conf.example`: 풀 `[my-blog]`, `user/group = myblog`, `listen = /run/php/my-blog.sock`, `listen.owner/group = www-data`, `pm = ondemand`, `php_admin_flag[display_errors] = off`, `catch_workers_output = yes`, `clear_env`는 기본값(yes) 유지 주석
- [x] T025 [US2] `deploy/README.md` 한국어 배포 안내(1시간 목표, SC-003): 준비물(VPS·도메인·DNS A 레코드 2개, 두 주소는 반드시 같은 도메인의 하위 도메인 — 쿠키 SameSite 때문에 함께 로그아웃·블로그 입장에 필요) → 패키지(research R13) → `myblog` 사용자·`/srv/my-blog` 배치·권한(DB·키·설정 600/700, `php-auth/public`만 Nginx가 읽기) → `deploy.config.json`·`/etc/my-blog/blog.env` → systemd·PHP-FPM·Nginx(기본 사이트 제거) → `certbot --nginx --redirect` → 방화벽(22·80·443) → SNS 콘솔 콜백 등록 → `/etc/hosts` 팁(R9) → 점검(quickstart D) → 백업(두 DB 함께, 헌법 IV)·업데이트·문제 해결(리디렉션 반복·502·종료 코드 78)
- [x] T026 [US2] 배포 예시 리허설(SC-003): 작업 환경(Ubuntu 24.04, PHP 8.3)에 `nginx`·`php8.3-fpm`을 설치하고 `deploy/` 예시(자체 서명 인증서로 443)로 두 서버를 띄워 quickstart D의 머리글·쿠키·404·함께 로그아웃을 점검, 예시 파일에서 틀린 곳을 고침
- [x] T027 [US2] 검증: `tests/smoke_public_deploy.py`의 US2 케이스 + quickstart C 손 점검(`deploy.config.example.json` 복사본)

**Checkpoint**: US1+US2로 공개 배포가 가능하다(배포 안내대로 VPS에 올릴 수 있음).

---

## Phase 5: User Story 3 — 프록시 뒤에서도 로그인 잠금이 사람마다 걸린다 (P2)

**Goal**: 믿는 프록시가 알려 준 실제 방문자 IP로 잠금·횟수 제한을 센다.

**Independent Test**: 믿는 프록시(127.0.0.1)에서 `X-Forwarded-For` A/B를 바꿔 댓글 비밀번호를 틀려 본다(quickstart B, US3 줄).

- [x] T028 [P] [US3] `tests/smoke_public_deploy.py`에 US3 케이스: 공개 모드 복사본에서 관리자가 글을 쓰고 방문자 댓글을 단 뒤, XFF A로 5번 틀리면 A는 429·XFF B는 403, 가짜 XFF 왼쪽 값으로는 우회 안 됨(`X-Forwarded-For: B, A`는 A로 셈)
- [x] T029 [US3] `server.py` `Handler.client_ip()`: contracts/public-mode-http.md 알고리즘(믿는 프록시에서 온 경우만 XFF 오른쪽부터, IP 형식 아니면 peer), `api_DELETE_comments`의 `self.client_address[0]`을 교체
- [x] T030 [P] [US3] `php-auth/src/config.php` `client_ip()`(같은 알고리즘)로 옮기고 `php-auth/src/auth.php`의 기존 `client_ip()` 삭제 — 로그인 잠금 `login_attempts.ip`가 새 함수를 씀
- [x] T031 [US3] 검증: `tests/smoke_public_deploy.py`의 US3 케이스 + 개발 모드(믿는 프록시 없음)에서 XFF가 무시되는지

---

## Phase 6: User Story 4 — 자동·대량 가입을 막는다 (P2)

**Goal**: 같은 IP 1시간 3개·전체 1시간 30개 한도와 자체 자동 가입 방지(숨은 칸·3초·1회용 토큰), 관리자 가입 현황.

**Independent Test**: 개발 모드 임시 복사본에서 봇 3종·IP 4번째·전체 한도를 시도하고 관리자 현황을 본다(quickstart B, US4 줄).

- [x] T032 [P] [US4] `tests/smoke_public_deploy.py`에 US4 케이스(개발 모드 복사본, `trusted_proxies: ["127.0.0.1"]`, `site_per_hour: 4`): 숨은 칸 채움·토큰 없음·3초 미만 → 가입 안 됨, XFF X로 3개 후 4번째 F4, XFF Y 1개 뒤 XFF Z는 F5, 믿는 프록시 없는 복사본에서는 XFF만 바꿔도 4번째 F4, 관리자 `/api/admin/status`의 `auth.signups.blocked` 합 > 0·`auth.sns.callback_url`이 `auth_url + /oauth_callback.php`·응답 어디에도 IP 없음. 폼은 먼저 모두 받아 두고 3초를 한 번만 기다린다
- [x] T033 [P] [US4] `php-auth/src/db.php` `signup_log` 표: "`id` INTEGER PRIMARY KEY AUTOINCREMENT, `ip` TEXT NOT NULL, `kind` TEXT NOT NULL(`ok`·`limit_ip`·`limit_site`·`bot`), `created_at` INTEGER NOT NULL" + 인덱스 `(kind, created_at)`, `(ip, kind, created_at)` (`IF NOT EXISTS`)
- [x] T034 [US4] `php-auth/src/signup_guard.php` 새 파일 — 폼 보호: `signup_form_token(?string $posted)`(`$_SESSION['signup_forms']` "세션당 최근 5개", "30분 지난 항목은 발급·확인 때 정리", 보낸 토큰이 유효하면 그대로), `signup_guard_fields(string $token)`(hidden `form_token` + 화면 밖 `website` 칸: `aria-hidden="true"`, `tabindex="-1"`, `autocomplete="off"`, 라벨 "이 칸은 비워 두세요"), `signup_bot_error()`(contracts/signup-guard.md 4단계: F1·F2·F3과 `bot` 기록 규칙), `bot_check_enabled()`가 false면 모두 건너뜀
- [x] T035 [US4] `php-auth/src/signup_guard.php` 횟수 제한: `log_signup(string $kind)`, `signup_limit_kind(PDO $pdo)`("같은 ip의 최근 3600초 ok 수 ≥ per_ip_per_hour → limit_ip", "전체 최근 3600초 ok 수 ≥ site_per_hour → limit_site"), `create_member_guarded(callable $create)` — `BEGIN IMMEDIATE` → "created_at < now - 86400" 삭제 → 판정 → 생성 + `ok` 기록 → `COMMIT`, 막히면 `ROLLBACK` 후 막힌 기록, 예외면 `ROLLBACK`. `signup_stats()`(data-model §5, IP 없음)
- [x] T036 [US4] `php-auth/public/register.php`: GET에서 한도면 폼 대신 F4/F5, 폼에 `signup_guard_fields()`, POST `action=signup` 처리 순서(contracts/signup-guard.md 1~6), 폼 위 오류 `role="alert"`, 성공 시 토큰 소모. `action=check`는 보호 단계 없이 지금대로
- [x] T037 [US4] `php-auth/public/social_signup.php`: 같은 보호 적용, 기존 `beginTransaction()` 묶음(`social_user_id`·`create_user`·`link_social`)을 `create_member_guarded()` 안으로
- [x] T038 [P] [US4] `php-auth/public/style.css`: 숨은 칸 클래스(화면 밖 배치, `display:none` 아님), 폼 오류 상자
- [x] T039 [US4] `php-auth/public/bridge_status.php`에 `"signups": signup_stats()` 추가
- [x] T040 [US4] `static/app.js` '가입 현황(최근 24시간)' 상자: 새 가입 N · 막힘(한 곳에서 너무 많이 a · 전체 한도 b · 자동 가입 의심 c), `site_limited_now` 문구, 연결 실패 문구(contracts/admin-status.md) + `static/style.css`
- [x] T041 [US4] `tests/smoke_member_lifecycle.py`: 가입 때 `form_token`·빈 `website`를 보내고 폼을 받은 뒤 3초 기다림
- [x] T042 [US4] 검증: `tests/smoke_public_deploy.py`의 US4 케이스 + `php-auth/public/register.php`를 실제 브라우저로 열어 회원가입 1번(추가 입력 없이 한 번에 됨, SC-006)

---

## Phase 7: Polish & Cross-Cutting

- [x] T043 [P] `README.md`: 실행 모드(개발/공개), `deploy.config.json`, 인터넷 공개는 `deploy/README.md`, 백업 범위(blog.db·uploads·php-auth/db·oauth.config.php·deploy.config.json, 두 DB 함께), 개발 모드 가입 한도 바꾸는 법
- [x] T044 [P] `php-auth/README.md`·`php-auth/oauth.config.example.php`: 공개 모드 콜백은 `auth_url + /oauth_callback.php`로 자동, `redirect_uri`는 개발 모드에서만 쓰임
- [x] T045 전체 회귀: quickstart A(기존 blog.db로 개발 모드 시작, `smoke_security_gaps.py`·`smoke_member_lifecycle.py`) + B(`smoke_public_deploy.py` 전체) + `server.py`·`php-auth/`에서 `Host` 머리글로 주소를 만드는 곳이 없는지 grep 확인(FR-007)
- [x] T046 요구사항 문서 갱신(헌법 V): `blog-project/requirements.md`와 `my-blog/docs/requirements.md`(두 사본 동일 유지)에 SEC-13(HTTPS 전용·HSTS·Secure)·SEC-14(가입 남용 방지)·SEC-15(공개 모드 관리자 비밀번호)·SEC-16(실제 방문자 IP)·NFR-13(실행 모드·배포 설정 파일)·NFR-14(공개 운영 방법) 행 추가, SEC-03·05·06·10, NFR-07·08(백업 범위)·09·12 문구 갱신, 7장 '인터넷 공개(배포)와 HTTPS' 과제 갱신(준비 완료, 실제 배포는 운영자)
- [x] T047 원본 Claude Docs 문서 "나만의 블로그 요구사항 정의서"(https://claude.ai/artifact/RwM5NYppuiRaTd2v61Phud)에 T046과 같은 변경 반영
- [x] T048 커밋: `my-blog`(코드·deploy·tests)와 `blog-project`(tasks 체크·requirements.md). push는 사용자 맥에서(`git push`)

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup(T001~T002) → Foundational(T003~T007) → 스토리 단계들 → Polish.
- `server.py`를 고치는 작업은 서로 순서대로: T003 → T006 → T009 → T010 → T011 → T014 → T015 → T016 → T029.
- `php-auth/src/config.php`: T004 → T017 → T030. `php-auth/src/auth.php`: T005 → T017(호출 추가) → T018 → T030(삭제).
- `php-auth/src/signup_guard.php`: T034 → T035. `bridge_status.php`: T020 → T039. `static/app.js`: T021 → T040.
- `tests/smoke_public_deploy.py`: T007 → T008 → T013 → T028 → T032.

### User Story Dependencies

- **US1**: Foundational만 필요.
- **US2**: Foundational만 필요(US1과 같은 `server.py`라 순서만 이어서). 
- **US3**: Foundational의 `is_trusted()`·`is_trusted_proxy()`만 필요. US2 관문과 독립.
- **US4**: T030(PHP `client_ip()`)를 쓰므로 US3의 PHP 부분 뒤. 관리자 상자는 US2의 T016·T020·T021 뒤.

### Parallel Opportunities

- T002와 T003, T004와 T003, T007(테스트 뼈대)은 서로 다른 파일.
- 스토리마다 테스트 케이스 작업([P])은 구현과 다른 파일이라 먼저 함께 쓸 수 있다.
- US2의 배포 예시 T022·T023·T024는 서로 독립, T019(oauth.php)도 독립.
- US3의 T029(블로그)과 T030(회원 서버)는 다른 파일.
- US4의 T033(db.php)·T038(style.css)은 T034와 함께.

## Parallel Example: User Story 2

```text
함께: T013 테스트 케이스 · T019 oauth.php redirect_uri · T022 nginx 예시 · T023 systemd 예시 · T024 php-fpm 예시
이어서: T014 → T015 → T016 (server.py) / T017 → T018 → T020 (회원 서버) → T021 (화면) → T025 (안내) → T026 (리허설) → T027 (검증)
```

## Implementation Strategy

### MVP First (US1)

1. Phase 1·2 → 2. US1 → 3. T012로 확인. 이 상태로도 개발 모드는 그대로이고, 공개 모드에서 기본 비밀번호가 막힌다.

### Incremental Delivery

1. US1 → 2. US2(이 시점에 실제 배포 가능) → 3. US3(프록시 뒤 잠금 정확) → 4. US4(공개 후 스팸 대비) → 5. Polish.
- 실제 인터넷 공개는 US1~US3이 끝난 뒤 권장, US4 전에 공개한다면 사이트 설정의 '회원가입 허용'을 꺼 둔다(AUTH-14).

## Notes

- 매 단계 끝에 개발 모드로 기존 blog.db를 켜서 데이터가 그대로인지 본다(헌법 IV).
- 보안 항목은 화면을 우회한 직접 요청(curl/테스트 스크립트)으로 거절을 확인한다(헌법 품질 관문).
- 커밋 메시지 예: `feat(deploy): 003 공개 모드·HTTPS·관리자 비밀번호·실제 IP·가입 보호`

## 구현 결과 (2026-10-08)

- 48개 작업 완료. `tests/smoke_public_deploy.py` 16개 통과(Ubuntu 24.04·PHP 8.3 작업 환경), 연결된 컴퓨터의 작업 환경(Python 3.10)에서도
  블로그 부분 7개 통과. 기존 blog.db·회원 DB 복사본으로 개발 모드 회귀(`smoke_security_gaps.py`·`smoke_member_lifecycle.py`) 통과,
  글 10개·회원 그대로.
- T026 리허설: Nginx + PHP-FPM + TLS(자체 서명 인증서)로 가입 → 블로그 입장 → 글쓰기 → 함께 로그아웃, Nginx를 거친 실제 IP별
  잠금(127.0.0.2 잠김·127.0.0.3 통과), HSTS·Secure·비공개 파일 404, 서버 간 https 호출 모두 확인. 이 과정에서 배포 안내에
  IPv6 없는 VPS의 `listen [::]` 안내를 더함.
- 화면: 사이트 설정의 '공개 주소'·'가입 현황' 상자를 라이트·다크, 1280px·375px에서 확인(가로 넘침 없음).

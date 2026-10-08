# Implementation Plan: 인터넷 공개(배포) 준비

**Branch**: `003-public-deploy-readiness` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-public-deploy-readiness/spec.md`

**Code root**: `~/Documents/my-blog` (GitHub `changpcg/my-blog`) · **헌법**: v1.1.1 (2026-10-08 개정, '공개 운영 (공개 모드)')

## Summary

- **설정 한 곳**: 두 서버가 함께 읽는 `deploy.config.json`(웹 폴더 밖)에 `public_mode`·공개 주소·믿는 프록시·가입 한도를 둔다.
  파일이 없으면 지금과 똑같은 개발 모드다. 관리자 비밀번호는 넣지 않고 `BLOG_PASSWORD`로만 받는다(R1·R2).
- **US1 관리자 비밀번호**: 블로그가 시작할 때 DB를 열기 전에 설정을 검사(C1~C11)해, 공개 모드에서 비밀번호가 없거나
  admin1234·약한 값이면 종료 코드 78로 끝낸다. 비밀번호가 바뀌어 켜지면 관리자 세션을 모두 지운다.
- **US2 HTTPS·주소**: TLS는 Nginx + Let's Encrypt. 앱도 공개 모드에서 "믿는 프록시 + `X-Forwarded-Proto: https`"가 아니면 308로
  https 공개 주소로 보내고, HSTS와 모든 쿠키의 Secure를 붙인다. 이동·입장권·로그아웃·SNS 콜백 주소는 설정 값으로만 만든다.
  회원 서버는 공개 모드에서 php -S 실행을 거절한다. VPS용 Nginx·PHP-FPM·systemd 예시와 한국어 배포 안내(`deploy/`)를 더하고,
  관리자 사이트 설정에 공개 주소·SNS 콜백 상자를 둔다.
- **US3 실제 IP**: 두 서버에 `client_ip()` — 믿는 프록시에서 온 요청만 `X-Forwarded-For`를 오른쪽부터 읽는다. 댓글 비밀번호 잠금,
  회원 로그인 잠금, 가입 횟수가 이 값을 쓴다.
- **US4 가입 남용**: 회원 서버에 폼 토큰(세션, 3초~30분) + 숨은 칸 + `signup_log` 표 기반 횟수 제한(IP 1시간 3개, 전체 30개,
  `BEGIN IMMEDIATE`로 동시 요청에도 정확). 관리자는 블로그 사이트 설정에서 서명된 `bridge_status.php`로 받은 24시간 현황을 본다(IP 없음).

## Technical Context

**Language/Version**: Python 3.9+ 표준 라이브러리(`json`·`ipaddress` 추가 사용), PHP 8.1+ (pdo_sqlite·mbstring, SNS만 curl).
운영 기준 Ubuntu 24.04(Python 3.12, PHP 8.3)

**Primary Dependencies**: 앱 의존성 추가 없음. 운영 환경(헌법 II 새 항목): Nginx, PHP-FPM, certbot, systemd

**Storage**: 회원 DB에 `signup_log` 표 추가, blog.db 스키마 변경 없음, 새 파일 `deploy.config.json`([data-model.md](./data-model.md))

**Testing**: `tests/smoke_public_deploy.py`(새, 임시 복사본으로 두 서버를 직접 띄움) + `tests/smoke_member_lifecycle.py`(가입 보호 반영)
+ `tests/smoke_security_gaps.py`(회귀) + [quickstart.md](./quickstart.md) A~D

**Target Platform**: 개발 — macOS 로컬(`python3`, `php -S`) / 공개 — Ubuntu VPS(Nginx → 127.0.0.1:8000, Nginx → PHP-FPM 소켓)

**Project Type**: 웹 서비스 2개 + 배포 문서

**Performance Goals**: 가입 보호·IP 판정은 요청당 수 ms 이내(작은 SQLite 조회 2~3번). 회원 서버는 설정 파일을 요청마다 읽는다(수 KB)

**Constraints**: php -S는 단일 스레드 — 새 브리지(`bridge_status.php`)는 블로그를 다시 부르지 않는다(002 규칙). PHP-FPM은 환경변수를
지운다(`clear_env`) → 회원 서버 설정은 파일에서만. 첨부 30MB(base64 약 40MB) → Nginx `client_max_body_size 45m`.
HSTS 1년(`includeSubDomains` 없음)

**Scale/Scope**: 개인 블로그 규모. 수정 파일 약 12개 + 새 파일 약 9개(아래 구조)

## Constitution Check

*GATE: Phase 0 전 확인 → Phase 1 설계 뒤 다시 확인. 두 번 모두 통과.*

| 원칙·섹션 | 이 기능에서 확인할 것 | 결과 |
| --- | --- | --- |
| I 서버가 최종 판단 | 가입 횟수·자동 가입 방지·https 강제·관리자 비밀번호 검사 모두 서버. 숨은 칸·토큰은 서버가 확인 | 통과 |
| II 설치 없이 돈다 | 앱 코드는 표준 라이브러리·PHP 기본 기능만. Nginx·PHP-FPM·certbot·systemd는 운영 환경(v1.1.0 II). 개발 모드 실행법 그대로 | 통과 |
| III 회원은 한 곳, 서명으로 | 가입·횟수 제한은 회원 서버에서. `bridge_status`는 HMAC + 1분 만료(읽기 전용이라 1회용 불필요). 가입은 POST + CSRF 유지 | 통과 |
| IV 데이터 보존 | `signup_log` 표 추가만. 설정 오류면 DB를 열지 않음. 백업 범위에 `deploy.config.json` | 통과 |
| V 요구사항 ID | 새 SEC-13~16·NFR-13~14 + SEC-03·05·06·10, NFR-07·08·09·12, 7장 갱신 작업 포함 | 통과 |
| VI 한국어·접근성 | 모든 안내 한국어. 숨은 칸은 `aria-hidden`·`tabindex=-1`, 오류는 `role="alert"`. 새 상자 다크 모드·375px | 통과 |
| 기술·보안 제약 | Host 머리글 미사용, 비밀값은 설정 파일 금지, 남용 방지 항목 충족 | 통과 |
| 공개 운영 (공개 모드) | HTTPS 전용·HSTS·Secure·관리자 비밀번호·php -S 금지·127.0.0.1·실제 IP·안전한 실패·기준 환경을 각각 FR로 구현 | 통과(예외 1건은 아래 Complexity Tracking) |

## Project Structure

### Documentation (this feature)

```text
specs/003-public-deploy-readiness/
├── spec.md · checklists/requirements.md
├── plan.md              # 이 파일
├── research.md          # R1~R14 결정
├── data-model.md        # 설정 파일·signup_log·폼 토큰·현황
├── contracts/
│   ├── deploy-config.md     # 설정 형식·우선순위·검사 C1~C11·시작 출력
│   ├── public-mode-http.md  # https 판단·308·HSTS·Secure·실제 IP
│   ├── signup-guard.md      # 폼 칸·처리 순서·문구 F1~F5
│   └── admin-status.md      # GET /api/admin/status, POST bridge_status.php
├── quickstart.md        # A 개발 모드 회귀, B 자동 점검, C 손 점검, D VPS 점검
└── tasks.md             # /speckit-tasks
```

### Source Code (`~/Documents/my-blog`)

```text
my-blog/
├── deploy.config.example.json     # 새: 공개 모드 예시 (실제 deploy.config.json은 .gitignore)
├── .gitignore                     # deploy.config.json 추가
├── server.py                      # 설정 읽기·검사(C1~C11, 종료 78), 시작 순서(검사 → 포트 → init_db),
│                                  # 관리자 세션 끊기, 공개 모드 관문(route·do_HEAD: 308·500, HSTS),
│                                  # send_header로 Secure, client_ip(), GET /api/admin/status, 시작 안내
├── static/app.js                  # 사이트 설정: '공개 주소'·'가입 현황' 상자
├── static/style.css               # 상자 스타일(다크 모드·375px)
├── php-auth/src/config.php        # 새: 설정 읽기·검사(C1~C6), 공개 모드 관문(503·308·HSTS·php -S 거절),
│                                  # is_https(), client_ip(), app_auth_url()/app_blog_url()
├── php-auth/src/auth.php          # config.php 먼저, 쿠키 secure, 기존 client_ip() 제거(→ config.php)
├── php-auth/src/sso.php           # BLOG_URL을 설정에서
├── php-auth/src/oauth.php         # redirect_uri: 공개 모드는 auth_url에서
├── php-auth/src/signup_guard.php  # 새: 폼 토큰·숨은 칸·시간, 횟수 제한(BEGIN IMMEDIATE), 현황 집계
├── php-auth/src/db.php            # signup_log 표·인덱스
├── php-auth/public/register.php   # 가입 보호 적용(F1~F5), GET 한도 안내
├── php-auth/public/social_signup.php # 같은 보호(SNS 첫 가입)
├── php-auth/public/bridge_status.php # 새: 서명된 현황 응답
├── php-auth/public/style.css      # 숨은 칸 클래스, 폼 오류
├── php-auth/oauth.config.example.php, php-auth/README.md, README.md   # 실행 모드·콜백·배포 안내 링크
├── deploy/README.md               # 새: VPS 배포 안내(한국어, 1시간 목표, 점검 = quickstart D)
├── deploy/nginx-my-blog.conf.example     # 새: blog.·auth. 서버 블록(80 → certbot이 443·이동 추가)
├── deploy/my-blog.service.example        # 새: systemd(EnvironmentFile, RestartPreventExitStatus=78)
├── deploy/php-fpm-my-blog.conf.example   # 새: 전용 풀(user myblog, 소켓)
└── tests/
    ├── smoke_public_deploy.py     # 새: 임시 복사본 공개·개발 모드 점검(quickstart B)
    └── smoke_member_lifecycle.py  # form_token·website·3초 대기 반영
```

**Structure Decision**: 기존 2서버 구조를 유지한다. 공통 로직(설정·IP)은 언어마다 한 파일/한 곳(`server.py` 상단 함수,
`php-auth/src/config.php`)에 모으고, 가입 보호는 `signup_guard.php` 한 파일로 분리해 두 가입 화면이 같이 쓴다.

### 구현 순서와 주의

1. **설정 로더(양쪽)** → 2. **US1** → 3. **US2**(관문·쿠키·주소·php -S·콜백·상태 상자) → 4. **US3**(client_ip) → 5. **US4**
   (가입 보호·현황) → 6. 배포 문서·README → 7. 테스트·requirements.md.
- `server.py` 시작 순서: 설정 검사(실패 시 78, DB 안 엶) → 포트 잡기(이미 실행 중 안내는 지금처럼) → `init_db()`.
- `auth.php` 부트스트랩 순서: `config.php` → 공개 모드 관문(세션 시작 전) → `session_set_cookie_params` → `session_start` → `db()`.
- 공개 모드 관문은 블로그의 모든 메서드(`do_GET/POST/PUT/DELETE/HEAD`)에 걸린다. `SimpleHTTPRequestHandler.do_HEAD`가
  `route()`를 거치지 않으므로 따로 덮어쓴다.
- `signup_open()`(블로그 호출)은 가입 보호보다 먼저, `bridge_status.php`에서는 부르지 않는다.
- 테스트는 실제 `blog.db`·회원 DB를 열지 않는다(임시 폴더 복사본 + 빈 포트).

## Complexity Tracking

| 예외 | 왜 필요한가 | 더 단순한 방법을 버린 이유 |
| --- | --- | --- |
| 공개 모드 회원 서버의 php -S 거절에 `ALLOW_PHP_DEV_SERVER=1` 예외(헌법 1.1.1에 명시) | 헌법 품질 관문 "공개 모드 변경은 로컬에서 믿는 프록시 머리글로 점검"을 회원 서버에도 하려면 php -S로 공개 모드를 띄워야 함 | 예외 없이 막으면 회원 서버 공개 모드 동작(308·Secure·HSTS·콜백)을 배포 전에 확인할 방법이 없음. 이 값은 php -S에서만 의미가 있고 PHP-FPM은 기본으로 환경변수를 지워 운영에 영향이 없음 |

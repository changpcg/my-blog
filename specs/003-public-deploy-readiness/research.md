# Research: 인터넷 공개(배포) 준비

**Feature**: [spec.md](./spec.md) · **Date**: 2026-10-08 · **Code root**: `~/Documents/my-blog`

Technical Context에 남은 미정 항목은 없다. 아래는 설계 결정과 버린 대안이다.

## R1. 공개 설정을 어디에 두나

- **Decision**: 두 서버가 함께 읽는 JSON 파일 `my-blog/deploy.config.json`(웹 폴더 밖, `.gitignore`)에 둔다.
  예시는 `deploy.config.example.json`으로 저장소에 넣는다. 경로는 `MYBLOG_CONFIG` 환경변수로 바꿀 수 있다(테스트·php -S용).
- **우선순위**
  - 개발 모드: 환경변수(`AUTH_URL`·`BLOG_URL`) > 파일 > 기본값(localhost). 지금 실행 방법이 그대로 돈다.
  - 공개 모드: 주소는 파일 값만 쓴다. 블로그 실행 환경의 주소 환경변수가 파일과 다르면 켜지지 않는다(한 곳 원칙).
  - 파일이 있는데 JSON으로 읽을 수 없으면 모드와 관계없이 안전한 쪽(블로그 미기동, 회원 서버 503). 깨진 파일 때문에
    `public_mode: true`가 조용히 무시되어 개발 모드로 공개되는 일을 막는다.
- **Rationale**: PHP-FPM은 기본으로 환경변수를 지운다(`clear_env = yes`). 환경변수만 쓰면 systemd와 FPM 풀 두 곳에 같은 값을
  적어야 하고 어긋나기 쉽다. JSON은 Python(`json`)·PHP(`json_decode`, PHP 8 기본 내장) 모두 표준 기능으로 똑같이 읽는다.
- **Alternatives**: 서버별 환경변수(두 곳 관리), INI(PHP `parse_ini_file`과 Python `configparser`의 따옴표·특수 문자 처리가
  달라 같은 파일을 다르게 읽을 수 있음), 블로그 DB `settings` 표(회원 서버가 블로그 DB를 직접 열어야 해 헌법 III 경계 위반).

## R2. 관리자 비밀번호

- **Decision**: 지금처럼 `BLOG_PASSWORD` 환경변수로만 받는다. 배포 설정 파일에는 넣지 않는다(헌법 '비밀' 항목).
  VPS에서는 systemd `EnvironmentFile=/etc/my-blog/blog.env`(root 소유, 600)에 둔다.
- **공개 모드 규칙**: 값이 있고, `admin1234`가 아니고, 12자 이상이며 영문과 숫자를 모두 포함. 어기면 DB를 열기 전에
  종료 코드 78(EX_CONFIG)로 끝낸다. systemd는 `RestartPreventExitStatus=78`로 재시작을 반복하지 않는다.
- **세션 끊기**: 시작할 때 DB의 관리자 해시로 새 비밀번호를 확인해 보고, 맞지 않으면(=바뀌었으면) 관리자 세션을 모두 지운다.
  두 모드 공통. 지금도 시작할 때마다 해시를 새로 저장하므로 예전 비밀번호는 이미 무효다.
- **Alternatives**: 공유 설정 파일에 저장(회원 서버도 읽는 파일이라 PHP 쪽 취약점 하나로 관리자 비밀번호까지 샘),
  첫 로그인 때 강제 변경 화면(공개 직후 첫 접속자가 먼저 바꿔 버릴 수 있음).

## R3. HTTPS는 누가 맡나

- **Decision**: 앞단 Nginx가 TLS를 맡고 인증서는 Let's Encrypt(`certbot --nginx --redirect`)로 받는다. 앱은 공개 모드에서
  한 번 더 강제한다: "믿는 프록시에서 왔고 `X-Forwarded-Proto: https`"가 아닌 요청은 308로 같은 경로의 https 공개 주소로 보낸다.
  믿는 프록시가 `X-Forwarded-Proto`를 아예 보내지 않으면(설정 실수) 무한 이동 대신 500과 한국어 안내를 낸다.
- **HSTS**: 앱이 `Strict-Transport-Security: max-age=31536000`를 보낸다. `includeSubDomains`·`preload`는 쓰지 않는다
  (같은 도메인의 다른 서비스에 영향 없게). Nginx 예시에는 중복으로 넣지 않는다.
- **Alternatives**: Python `ssl`로 블로그가 직접 TLS(인증서 갱신·재시작·HTTP/2 부담, PHP는 여전히 웹 서버 필요),
  Nginx만 믿기(설정 실수 하나로 평문 노출 — 헌법 I '서버가 최종 판단').

## R4. Secure 쿠키

- **Decision**: 블로그는 `Handler.send_header`를 감싸 공개 모드면 모든 `Set-Cookie`에 `; Secure`를 붙인다(session·vid·
  seen_*·로그아웃 지우기 쿠키를 한 곳에서, 앞으로 생길 쿠키까지). PHP는 `session_set_cookie_params(['secure' => 공개 모드 || https])`.
  로그아웃·탈퇴의 `setcookie()`는 `session_get_cookie_params()`를 따르므로 따로 고칠 필요가 없다.
- **Alternatives**: 쿠키 만드는 곳 5군데를 각각 고치기(빠뜨리기 쉬움).

## R5. 실제 방문자 IP

- **Decision**: 믿는 프록시는 정확한 IP 목록(`trusted_proxies`, 공개 모드 기본 `127.0.0.1`·`::1`, 개발 모드 기본 없음).
  바로 앞 접속(REMOTE_ADDR/`client_address`)이 믿는 프록시일 때만 `X-Forwarded-For`를 오른쪽부터 읽어, 믿는 프록시가 아닌
  첫 번째 IP를 방문자로 본다. 그 밖에는 바로 앞 접속 IP. IPv6은 정규화해 비교한다(Python `ipaddress`, PHP `inet_pton`/`inet_ntop`).
  `X-Forwarded-Proto`도 같은 조건에서만 믿는다.
- **적용 곳**: 블로그 댓글 비밀번호 잠금(SEC-03), 회원 로그인 잠금(SEC-03), 가입 횟수(SEC-14).
- **Rationale**: Nginx는 `$proxy_add_x_forwarded_for`로 실제 IP를 맨 끝에 붙이므로, 방문자가 가짜 머리글을 보내도 오른쪽부터
  읽으면 속지 않는다. PHP-FPM은 Nginx와 FastCGI로 붙어 REMOTE_ADDR가 이미 실제 IP라 같은 함수로 두 경우가 모두 맞다.
- **Alternatives**: `X-Real-IP` 하나만 믿기(Nginx 설정에 달림), CIDR 범위 지원(CDN 앞단용 — 범위 밖, PHP에서 직접 구현 필요).

## R6. 자동 가입 방지 (자체 방식 — Clarification 확정)

- **Decision**: 가입 화면을 열 때 서버가 폼 토큰을 발급해 세션에 발급 시각과 함께 저장(세션당 최근 5개, 30분 유효)하고,
  사람 눈에 안 보이는 칸 `website`를 둔다. 가입 POST에서 ① 숨은 칸이 비어 있고 ② 토큰이 세션에 있고 ③ 발급 후 3초 이상
  30분 이내일 때만 통과. 토큰은 계정이 만들어질 때 소모하고, 입력 오류로 화면을 다시 그릴 때는 같은 토큰을 유지한다
  (사람이 고쳐서 다시 보내도 막히지 않게). 일반 가입·SNS 첫 가입 모두 적용. 아이디 중복 확인(action=check)은 기존 세션 제한만.
- **끄기**: 개발 모드에서만 `signup.bot_check: false` 허용(공개 모드에서 false면 설정 오류).
- **Alternatives**: 외부 CAPTCHA(헌법 II·사용자 선택에서 제외), 퀴즈(단계 추가), 자바스크립트 계산(지금은 JS 없이도 가입되는데 그 경로가 막힘).

## R7. 공개 주소 형식

- **Decision**: `https://호스트[:포트]`만(경로·쿼리·조각·사용자 정보 없음, 끝 `/` 제거). 블로그와 회원 서버는 서로 다른 오리진.
- **Rationale**: 회원 화면은 상대 링크 + 문서 루트 `public/` 구조이고, Nginx에서 하위 경로 + PHP-FPM(`alias`)은 실수가 잦다.
  다른 호스트를 쓰면 쿠키(경로 `/`)도 섞이지 않는다.

## R8. 공개 모드에서 php -S 거절

- **Decision**: 공개 모드 + `PHP_SAPI === 'cli-server'`면 모든 요청에 503과 "Nginx + PHP-FPM으로 실행하세요" 안내.
  예외는 `ALLOW_PHP_DEV_SERVER=1` 환경변수 하나(로컬 점검 전용, 헌법 품질 관문의 '공개 모드 로컬 점검'에 필요).
- **Rationale**: php -S는 한 번에 요청 하나만 처리해 SNS 호출(최대 10초) 하나가 모든 회원을 막고, PHP 공식 문서도 운영 사용을
  금한다. 예외 변수는 php -S에서만 의미가 있고 PHP-FPM은 기본으로 환경변수를 지우므로 운영 서버에 영향이 없다.

## R9. 서버끼리 부르는 주소

- **Decision**: 공개 주소(https) 그대로 부른다(블로그→회원 `urllib`, 회원→블로그 `file_get_contents`, 둘 다 기본 인증서 검증).
  VPS가 자기 도메인으로 되돌아오는 연결을 막는 경우를 위해, `/etc/hosts`에 두 도메인을 `127.0.0.1`로 적는 방법을 안내한다
  (Nginx가 443에서 이름(SNI)으로 받으므로 그대로 동작).
- **Alternatives**: 내부 주소 설정을 따로 두기(설정·검증 항목이 늘고 https 판단이 복잡해짐 — 필요해지면 다음 기능).

## R10. SNS 콜백 주소

- **Decision**: 공개 모드에서는 `auth_url + /oauth_callback.php`로 만들고 `oauth.config.php`의 `redirect_uri`는 무시한다.
  개발 모드는 지금처럼 `redirect_uri`가 있으면 그 값(현재 등록된 네이버 로그인 유지). 실제로 쓰는 값은 회원 서버가 상태 응답(R12)으로
  알려 주어 블로그 사이트 설정에 보이고, 블로그 시작 안내(공개 모드)에도 출력한다.

## R11. 가입 횟수 제한

- **Decision**: 회원 DB에 `signup_log(ip, kind, created_at)` 표를 더한다. 성공한 가입(`ok`)만 센다: 같은 IP 최근 1시간 3개,
  사이트 전체 최근 1시간 30개(설정으로 변경). 막힌 시도도 `limit_ip`·`limit_site`·`bot`으로 남겨 현황에 쓰고, 24시간 지난 기록은
  가입 시도 때 지운다. 세기·계정 만들기·`ok` 기록을 `BEGIN IMMEDIATE` 트랜잭션 하나로 묶어 PHP-FPM 작업자 여럿이 동시에 받아도
  한도를 넘지 않게 한다. SNS 첫 가입도 같은 함수를 쓴다.
- **Alternatives**: 세션별 제한(쿠키를 버리면 우회), 블로그 쪽 제한(계정은 회원 서버가 만듦 — 헌법 III).

## R12. 관리자 가입 현황

- **Decision**: 블로그 `GET /api/admin/status`(관리자만) → 회원 서버 `POST /bridge_status.php`(서명 `act=auth_status`, 1분 만료).
  읽기 전용이라 1회용 번호는 두지 않는다(헌법 III은 상태를 바꾸는 표만 1회용 요구). 응답은 24시간 성공 수·이유별 막힌 수·지금
  전체 제한 여부·설정 한도·SNS 콜백 주소·키가 등록된 SNS 목록. IP는 보내지 않는다. 회원 서버가 꺼져 있으면 "연결할 수 없어요".
- **Alternatives**: 회원 서버에 관리자 화면 새로 만들기(관리자 로그인이 블로그에만 있음).

## R13. 기준 운영 환경

- **Decision**: Ubuntu 24.04 LTS(Python 3.12, PHP 8.3). 22.04(Python 3.10, PHP 8.1)도 된다 — 코드가 이미 PHP 8.1의 `never`
  반환형을 써서 PHP 8.1 이상이 필요하다. 패키지: `nginx php8.3-fpm php8.3-sqlite3 php8.3-mbstring php8.3-curl certbot python3-certbot-nginx`.
- 실행 사용자 `myblog` 하나로 블로그(systemd)와 전용 PHP-FPM 풀을 함께 돌려 `sso.key`·DB·설정 파일을 600/700으로 유지한다.
  Nginx(www-data)는 블로그를 프록시하고 `php-auth/public`만 읽는다.
- Nginx 블로그 쪽 `client_max_body_size 45m`(첨부 30MB가 base64로 약 40MB). 기본 사이트 제거, 방화벽은 22·80·443만.

## R14. 점검 방법

- **Decision**: `tests/smoke_public_deploy.py`(표준 라이브러리) — 코드를 임시 폴더에 복사해 새 DB로 두 서버를 띄운다(실제
  blog.db·회원 DB를 건드리지 않음). 공개 모드 복사본은 믿는 프록시 머리글로 https를 흉내 내고(`ALLOW_PHP_DEV_SERVER=1`),
  개발 모드 복사본으로 가입 보호(횟수·숨은 칸·시간·토큰)와 관리자 현황을 확인한다. 기존 `smoke_member_lifecycle.py`는 가입 보호
  필드를 보내고 3초 기다리도록 고친다.

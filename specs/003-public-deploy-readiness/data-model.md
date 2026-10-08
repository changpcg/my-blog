# Data Model: 인터넷 공개(배포) 준비

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

blog.db 스키마는 바꾸지 않는다. 회원 DB에 표 하나, 새 설정 파일 하나, PHP 세션 값 하나가 생긴다(헌법 IV: 더하기만).

## 1. 배포 설정 파일 `deploy.config.json` (새)

- 위치: `my-blog/deploy.config.json` (웹 폴더 `static/`·`php-auth/public/` 밖). 저장소에는 `deploy.config.example.json`만.
- 경로 바꾸기: `MYBLOG_CONFIG` 환경변수. 파일이 없으면 모두 기본값(= 개발 모드, 지금과 같음).
- 권한: 운영에서는 `myblog` 소유 600. 백업 범위에 포함(헌법 IV).
- 읽는 때: 블로그는 시작할 때 한 번(바꾸면 다시 켜기). 회원 서버는 요청마다(작은 파일).

| 키 | 형식 | 기본값 | 규칙 |
| --- | --- | --- | --- |
| `public_mode` | bool | `false` | `true`일 때만 공개 모드 |
| `blog_url` | 문자열 | 환경변수 `BLOG_URL` → `http://localhost:8000` | 공개 모드: https 오리진 필수(R7) |
| `auth_url` | 문자열 | 환경변수 `AUTH_URL` → `http://localhost:8080` | 공개 모드: https 오리진 필수, `blog_url`과 다른 오리진 |
| `trusted_proxies` | 문자열 배열 | 공개 `["127.0.0.1", "::1"]` / 개발 `[]` | 각 항목은 IP 주소 하나(범위 표기 불가). 공개 모드에서 빈 배열 불가 |
| `signup.per_ip_per_hour` | 정수 | `3` | 1~1000 |
| `signup.site_per_hour` | 정수 | `30` | 1~100000, `per_ip_per_hour` 이상 |
| `signup.bot_check` | bool | `true` | 공개 모드에서 `false`면 설정 오류 |

파일에 두지 않는 값: `BLOG_PASSWORD`(비밀값, 블로그 실행 환경), `HOST`·`PORT`(블로그 실행 환경. 공개 모드의 `HOST`는
`127.0.0.1`·`::1`·`localhost`만). 알 수 없는 키는 무시한다. 검사 목록과 오류 문구는 [contracts/deploy-config.md](./contracts/deploy-config.md).

## 2. 실행 모드 (상태)

```text
개발 모드 (public_mode 없음/false)  ──파일에서 true로 바꾸고 다시 켬──▶  공개 모드
        ▲                                                              │
        └────────────────── false로 바꾸고 다시 켬 ◀────────────────────┘
공개 모드 + 설정 오류 → 블로그: 켜지지 않음(종료 코드 78, DB 안 엶) / 회원 서버: 모든 요청 503(DB 안 엶)
파일이 JSON으로 읽히지 않음 → 모드와 관계없이 위와 같음
```

## 3. 회원 DB `signup_log` 표 (새, `php-auth/db/sqlite.db`)

| 칸 | 형식 | 설명 |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `ip` | TEXT NOT NULL | 실제 방문자 IP(R5) |
| `kind` | TEXT NOT NULL | `ok`(계정 생성) · `limit_ip` · `limit_site` · `bot` |
| `created_at` | INTEGER NOT NULL | 유닉스 초 |

- 인덱스: `(kind, created_at)`, `(ip, kind, created_at)`. `CREATE TABLE IF NOT EXISTS`로 자동 추가.
- 보존: 24시간. 가입 시도 때 `created_at < now - 86400` 행을 지운다.
- 회원 번호와 잇지 않는다(탈퇴와 무관, 개인 정보 최소화). 화면·응답에 IP를 내보내지 않는다.
- 판정(가입 POST, `BEGIN IMMEDIATE` 안):
  - 같은 `ip`의 최근 3600초 `ok` 수 ≥ `per_ip_per_hour` → `limit_ip`
  - 전체 최근 3600초 `ok` 수 ≥ `site_per_hour` → `limit_site`
  - 통과하면 계정 생성과 `ok` 기록을 같은 트랜잭션에서 커밋. 막히면 롤백 후 막힌 기록만 남긴다.

## 4. 가입 폼 토큰 (PHP 세션 `$_SESSION['signup_forms']`, 새)

- 모양: `{ 토큰(32자 16진수): 발급 시각(유닉스 초) }`, 세션당 최근 5개. 30분 지난 항목은 발급·확인 때 정리.
- 통과 조건: 토큰이 있고 `발급 + 3초 ≤ 지금 ≤ 발급 + 30분`, 숨은 칸 `website`가 빈 값.
- 소모: 계정이 만들어지면 그 토큰을 지운다. 입력 오류로 다시 그릴 때는 보낸 토큰이 유효하면 그대로 쓴다.
- 세션 기반이라 서버를 다시 켜도(PHP 세션 파일) 유지되고, 로그인 세션 재발급(`session_regenerate_id`) 뒤에도 값은 남는다.

## 5. 가입 현황 (회원 서버 상태 응답, 저장하지 않음)

| 필드 | 뜻 |
| --- | --- |
| `signups.window_hours` | 24 |
| `signups.created` | 최근 24시간 `ok` 수 |
| `signups.blocked.limit_ip` / `limit_site` / `bot` | 최근 24시간 이유별 막힌 수 |
| `signups.site_limited_now` | 지금 최근 1시간 `ok` 수가 `site_per_hour` 이상인지 |
| `signups.limits` | `{per_ip_per_hour, site_per_hour}` |
| `sns.callback_url` | 회원 서버가 실제로 쓰는 콜백 주소(R10) |
| `sns.providers` | 키가 등록된 SNS 이름 목록(키 값은 없음) |
| `public_mode` | 회원 서버가 읽은 공개 모드 값(두 서버 일치 확인용) |

## 6. blog.db

- 스키마 변경 없음.
- 관리자 비밀번호가 바뀌어 켜지면 `sessions`에서 관리자(`users.role = 'admin'`) 행을 지운다(기존 표·칸 사용).

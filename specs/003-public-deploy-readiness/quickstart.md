# Quickstart: 인터넷 공개(배포) 준비 점검

**Feature**: [spec.md](./spec.md) · 명령은 코드 폴더 `~/Documents/my-blog` 기준(VPS에서는 `/srv/my-blog`).
계약: [deploy-config](./contracts/deploy-config.md) · [public-mode-http](./contracts/public-mode-http.md) ·
[signup-guard](./contracts/signup-guard.md) · [admin-status](./contracts/admin-status.md)

## A. 개발 모드 그대로 (SC-007)

```bash
cd ~/Documents/my-blog && BLOG_PASSWORD='비밀번호' python3 server.py     # 블로그 8000
cd ~/Documents/my-blog/php-auth && php -S localhost:8080 -t public       # 회원 8080
```

- 기대: `deploy.config.json` 없이 지금과 똑같이 켜지고, 기존 blog.db의 글·댓글·로그인이 그대로다.
- 회귀 테스트(두 서버를 켠 상태):

```bash
python3 tests/smoke_security_gaps.py
python3 tests/smoke_member_lifecycle.py   # 가입 1개, 자동 가입 방지 대기 3초 포함
```

- 개발 모드에도 가입 한도(같은 곳 1시간 3개)가 걸린다. 테스트를 자주 돌리면 `deploy.config.json`에
  `{"signup": {"per_ip_per_hour": 50}}`을 넣고 회원 서버만 그대로 두면 된다(요청마다 읽음).

## B. 자동 점검 — 임시 복사본, 실제 DB를 건드리지 않음

```bash
python3 tests/smoke_public_deploy.py      # 약 1분, 빈 포트 두 개를 골라 서버를 직접 띄우고 끝나면 지움
```

| 점검 | 기대 | 관련 |
| --- | --- | --- |
| 공개 모드 + 비밀번호 없음 / admin1234 / 짧은 값 | 종료 코드 78, 한국어 안내, blog.db가 생기지 않음 | US1-1·2, FR-002·003, SC-001 |
| 공개 모드 + 강한 비밀번호 | 켜짐. admin1234 로그인 401, 새 비밀번호 로그인 200 | US1-3 |
| 비밀번호를 바꿔 다시 켬 | 예전 관리자 세션 쿠키로 `/api/blog`의 `is_admin`이 false | US1-4, FR-004 |
| `X-Forwarded-Proto: http` | 308, `Location: https://blog.test/경로` | US2-1, FR-005 |
| `X-Forwarded-Proto: https` | 200 + HSTS, `Set-Cookie`에 Secure | US2-2, FR-005·006, SC-002 |
| 믿는 프록시가 아닌 곳에서 옴 | 308(https 아님으로 봄), `X-Forwarded-For` 무시 | US3-2 |
| 공개 모드 HEAD 요청 | GET과 같은 관문(308 또는 HSTS) | FR-005 |
| 댓글 비밀번호: XFF A로 5번 틀림 | A는 429, XFF B는 403(아직 잠기지 않음) | US3-1, FR-011 |
| 회원 서버 php -S + 공개 모드(예외 없음) | 503 안내 | FR-009 |
| 회원 서버(예외 켬) `X-Forwarded-Proto: http` / `https` | 308 → `https://auth.test/...` / `AUTHSESS`에 Secure, HSTS | US2-1·2 |
| SNS 시작(가짜 네이버 키) | `redirect_uri=https://auth.test/oauth_callback.php` | US2-4, FR-007 |
| 개발 모드 복사본: 숨은 칸 채움 / 토큰 없음 / 3초 미만 | 가입 안 됨(F1·F1·F3) | US4-3, FR-013 |
| 같은 IP 3개 가입 후 4번째 | F4로 거절 | US4-1, FR-012, SC-005 |
| 전체 한도(테스트 설정 4개) 이후 다른 IP | F5로 거절 | US4-2 |
| 믿는 프록시 없음(개발 기본)에서 XFF만 바꿔 가입 | 모두 같은 IP로 세어 4번째 거절 | US3-2 |
| 관리자 `GET /api/admin/status` | 막힌 수 > 0, 응답에 IP 없음, 콜백 주소 있음 | FR-008·014 |

## C. 로컬 공개 모드 손 점검 (선택)

```bash
mkdir -p /tmp/pub && cp deploy.config.example.json /tmp/pub/deploy.config.json   # blog/auth 주소는 https://blog.test 등으로
MYBLOG_CONFIG=/tmp/pub/deploy.config.json BLOG_PASSWORD='StrongPass2026x' PORT=18000 python3 server.py
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' -H 'X-Forwarded-Proto: http' http://127.0.0.1:18000/   # 308 https://blog.test/
curl -s -D - -o /dev/null -H 'X-Forwarded-Proto: https' http://127.0.0.1:18000/api/blog | grep -i -E 'strict|set-cookie'
```

주의: C는 실제 blog.db를 쓴다(관리자 비밀번호가 바뀌고 관리자 세션이 끊김). 실제 데이터로 하지 않으려면 B를 쓴다.

## D. VPS 배포 후 점검 (deploy/README.md 마지막 단계)

```bash
B=https://blog.example.com; A=https://auth.example.com
curl -sI http://blog.example.com/ | head -1                       # 301 (https로)
curl -sI $B/ | grep -i strict-transport                           # HSTS
curl -s -D - -o /dev/null $B/api/blog | grep -i set-cookie        # vid=...; Secure
curl -s -D - -o /dev/null $A/login.php | grep -i set-cookie       # AUTHSESS=...; secure; HttpOnly; SameSite=Lax
for p in db/sqlite.db db/sso.key oauth.config.php ../deploy.config.json; do
  curl -s -o /dev/null -w "%{http_code} $p\n" "$A/$p"; done        # 모두 404
for p in blog.db deploy.config.json php-auth/db/sso.key; do
  curl -s -o /dev/null -w "%{http_code} $p\n" "$B/$p"; done        # 모두 404
```

- 브라우저: 회원가입 → 블로그 입장 → 글쓰기 → 로그아웃(두 서버 함께) — 빈 서버에서 1시간 안(SC-003).
- 관리자 사이트 설정: 실행 모드 "공개", 콜백 주소 확인 → 각 SNS 개발자 콘솔에 등록(FR-008).
- 실제 IP: 휴대폰(LTE)으로 회원 로그인을 5번 틀리면 휴대폰만 잠기고 PC는 로그인된다(US3).
- `sudo systemctl restart my-blog` 뒤 `journalctl -u my-blog -n 5`에 공개 모드 시작 안내와 콜백 주소가 보인다.

# Contract: 공개 모드의 요청 처리 (두 서버 공통)

관련: FR-005·006·007·011, US2·US3, 새 SEC-13·SEC-16

## https 판단

| 서버 | https로 보는 경우 |
| --- | --- |
| 블로그 | 바로 앞 접속이 믿는 프록시이고 `X-Forwarded-Proto`가 `https`(대소문자 무시) |
| 회원 | `$_SERVER['HTTPS']`가 비어 있지 않고 `off`가 아님, 또는 바로 앞 접속이 믿는 프록시이고 `X-Forwarded-Proto`가 `https` |

## 공개 모드 응답 규칙

1. **https가 아니면** `308 Permanent Redirect`, `Location: {공개 주소}{원래 경로와 쿼리}`(경로가 `/`로 시작하지 않으면 `/`).
   DB·쿠키 작업 없이 바로 응답한다. GET·HEAD·POST·PUT·DELETE 모두 같다(블로그는 `do_HEAD`도 이 관문을 거친다).
   - 블로그 예외: 믿는 프록시에서 왔는데 `X-Forwarded-Proto`가 없으면 설정 실수로 보고 **500**
     `{"error": "서버 설정 오류: 앞단 웹 서버가 X-Forwarded-Proto를 보내지 않아요. Nginx 설정을 확인해 주세요."}`.
     같은 안내를 서버 출력에 한 번 남긴다(무한 이동 방지).
2. **https면** 모든 응답에 `Strict-Transport-Security: max-age=31536000`.
3. **쿠키**: 모든 `Set-Cookie`에 `Secure`.
   - 블로그: `session`(HttpOnly; SameSite=Strict), `vid`·`seen_*`(SameSite=Lax), 로그아웃 때 지우는 `session` 쿠키.
   - 회원: `AUTHSESS`(HttpOnly; SameSite=Lax). 로그아웃·탈퇴의 지우기 쿠키는 세션 쿠키 설정을 따른다.
4. **주소는 설정 값으로만**: 이동 주소, 입장권을 들고 가는 블로그 주소, 로그아웃 폼 `action`, SNS `redirect_uri`, 회원 화면의
   "블로그 홈으로" 링크는 모두 `blog_url`·`auth_url`에서 만든다. `Host`·`X-Forwarded-Host`는 쓰지 않는다.
5. 회원 서버를 php -S로 켜면 503([deploy-config.md](./deploy-config.md)).

개발 모드에서는 1~3을 적용하지 않는다(PHP 세션 쿠키의 Secure는 지금처럼 https로 접속했을 때만).

## 실제 방문자 IP (두 모드 공통)

```text
peer = 바로 앞 접속 IP
if peer가 trusted_proxies에 없음: return peer
hops = X-Forwarded-For를 쉼표로 나누고 앞뒤 공백 제거
for ip in hops를 오른쪽부터:
    if ip가 IP 형식이 아님: return peer
    if ip가 trusted_proxies에 없음: return ip
return peer
```

비교는 정규화한 IP로 한다(`::1`과 `0:0:0:0:0:0:0:1`은 같음).

| 쓰는 곳 | 서버 | 바뀌는 점 |
| --- | --- | --- |
| 댓글 비밀번호 잠금 `comment_pw_fails.ip` | 블로그 | `client_address[0]` → `client_ip()` |
| 회원 로그인 잠금 `login_attempts.ip` | 회원 | `REMOTE_ADDR` → `client_ip()` |
| 가입 횟수 `signup_log.ip` | 회원 | 새로 사용 |

## 바뀌지 않는 것

- 서버 간 서명 요청(입장권·로그아웃 표·브리지)의 형식·만료·1회용 규칙. 공개 모드에서는 https 공개 주소로 오가며 위 관문을
  똑같이 통과한다.
- 기존 API 경로·응답 모양.

# Contract: 서버 간 브리지 (sso.key HMAC)

모든 값 = `base64url(JSON) + "." + hex(HMAC-SHA256(sso.key, base64url부분))`. `act`로 용도를 나누고 `exp`(유닉스 초)를 검사한다.

## 블로그 → 회원 서버가 읽는 가입 허용

`GET {BLOG_URL}/api/bridge/signup` → `200 {"t": "<signed>"}`, payload `{"act":"signup_state","allow":true|false,"exp":now+60}`

회원 서버: `bridge_cache('signup')`에 값·시각 저장, 60초 안이면 재사용. 실패 시 마지막 값, 없으면 false.

## 회원 서버 → 블로그 탈퇴 (회원 스스로)

`POST {BLOG_URL}/api/bridge/delete_member`, JSON `{"t":"<signed>"}`, payload `{"act":"delete_member","uid":N,"exp":now+60,"nonce":32hex}`

| 결과 | 응답 |
| --- | --- |
| 서명·act·exp 불일치, 재사용 nonce | 400 |
| 그 uid의 블로그 계정 없음 | 200 `{"ok":true,"deleted":false}` |
| 관리자 계정 | 400 |
| 삭제 | 200 `{"ok":true,"deleted":true}` (001 규칙대로 글·댓글·공감·이웃·세션·파일 정리) |

블로그는 이 요청 중 회원 서버를 부르지 않는다.

## 블로그 → 회원 서버 탈퇴 (관리자)

`POST {AUTH_URL}/bridge_delete.php`, form `t=<signed>`, payload 위와 같음(`act:"delete_member"`).
응답 JSON `{"ok":true,"deleted":bool}` 또는 400. 회원 서버는 nonce를 `sso_used_nonces`에 기록, 회원·SNS 연결·로그인 실패
기록을 지운다. 회원 서버는 이 요청 중 블로그를 부르지 않는다.

## 입장권 추가 필드

`make_ticket`에 `joined`(회원 가입 시각 문자열), `nick_at`(닉네임 변경 유닉스 초, 없으면 0).
블로그: `auth_joined`가 비어 있으면 저장, 다르면 409 "회원 정보가 블로그 기록과 맞지 않아요. 관리자에게 문의해 주세요."
`nick_at > auth_nick_at`이면 블로그 닉네임 = 입장권 닉네임, `auth_nick_at` 갱신.

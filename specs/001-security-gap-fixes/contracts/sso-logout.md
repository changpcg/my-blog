# Contract: 회원 서버 함께 로그아웃 (php-auth/public/sso_logout.php)

## 요청

```http
POST /sso_logout.php
Content-Type: application/x-www-form-urlencoded

t=<로그아웃 표>
```

브라우저가 블로그 화면에서 숨은 폼을 제출해 보낸다(최상위 이동, AUTHSESS 쿠키 포함).

## 처리

| 조건 | 결과 |
| --- | --- |
| 메서드가 POST가 아님 (GET 링크 등) | 아무것도 안 함 |
| 서명 불일치·`act != logout`·만료 | 아무것도 안 함 |
| `uid`가 지금 `$_SESSION['uid']`와 다름 또는 로그인 안 됨 | 아무것도 안 함 |
| `nonce`가 `sso_used_nonces`에 있음 | 아무것도 안 함 |
| 위를 모두 통과 | nonce 기록(expires = exp) → 세션 비우기·쿠키 삭제·`session_destroy()` |

모든 경우 마지막에 `BLOG_URL/#/`로 302 이동(열린 리다이렉트 없음). 만료된 nonce 행은 요청마다 정리.

## 함수 (php-auth/src/sso.php)

`read_logout_ticket(string $t): ?array` — 서명·act·exp를 확인해 payload 배열을, 아니면 null을 돌려준다.
`hash_equals`로 비교한다.

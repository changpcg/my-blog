# Contract: 관리자 상태 (블로그 ↔ 회원 서버)

관련: FR-008·014, US2-4·US4-2 · 모델: [data-model.md §5](../data-model.md)

## 블로그 `GET /api/admin/status`

- 관리자만. 아니면 403 "관리자만 할 수 있습니다."(기존 문구).
- 회원 서버에 3초 안에 묻고(기존 `auth_post`), 실패하면 `auth`를 `null`로.

```json
{
  "deploy": {
    "public_mode": true,
    "blog_url": "https://blog.example.com",
    "auth_url": "https://auth.example.com"
  },
  "auth": {
    "ok": true,
    "public_mode": true,
    "signups": {
      "window_hours": 24,
      "created": 5,
      "blocked": { "limit_ip": 2, "limit_site": 0, "bot": 7 },
      "site_limited_now": false,
      "limits": { "per_ip_per_hour": 3, "site_per_hour": 30 }
    },
    "sns": {
      "callback_url": "https://auth.example.com/oauth_callback.php",
      "providers": ["naver"]
    }
  }
}
```

## 회원 서버 `POST /bridge_status.php`

- 요청: 폼 값 `t` = `sign_bridge({"act": "auth_status"})`(sso.key HMAC-SHA256, 1분 만료, 기존 형식).
- 서명·act·만료가 틀리면 400 `{"ok": false, "error": "서명이 올바르지 않아요."}`. POST가 아니면 405.
- 성공 200: 위 `auth` 객체. IP·회원 정보·SNS 키 값은 넣지 않는다.
- 읽기 전용이라 1회용 번호를 쓰지 않는다(헌법 III은 상태를 바꾸는 표만 1회용 요구).
- 이 엔드포인트는 블로그를 다시 부르지 않는다(`signup_open()` 호출 금지 — php -S 교착 방지, 002와 같은 규칙).

## 사이트 설정 화면 (관리자)

| 상자 | 내용 |
| --- | --- |
| 공개 주소 | 실행 모드(개발/공개), 블로그 주소, 회원 서버 주소, SNS 콜백 주소(고정폭 글꼴, 선택해 복사), 키가 등록된 SNS. 두 서버의 `public_mode`가 다르면 "두 서버의 공개 모드 설정이 달라요. 설정 파일을 확인하고 블로그 서버를 다시 켜 주세요." |
| 가입 현황(최근 24시간) | 새 가입 N · 막힘: 한 곳에서 너무 많이 a · 전체 한도 b · 자동 가입 의심 c. `site_limited_now`면 "지금 사이트 전체 가입 제한이 걸려 있어요(1시간 30개)." |
| 회원 서버 연결 실패 | "회원 서버에 연결할 수 없어 가입 현황을 불러오지 못했어요." |

IP는 어디에도 표시하지 않는다. 두 상자는 다크 모드·375px에서 넘치지 않는다(헌법 VI).

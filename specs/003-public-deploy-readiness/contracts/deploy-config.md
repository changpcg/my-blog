# Contract: 배포 설정 파일과 시작 검사

관련: FR-001·002·003·007, 새 NFR-13·SEC-15 · 모델: [data-model.md §1·2](../data-model.md)

## 파일 예시

개발 모드는 파일이 없어도 된다(지금과 같음). 공개 모드 예시(`deploy.config.example.json`과 같은 모양):

```json
{
  "public_mode": true,
  "blog_url": "https://blog.example.com",
  "auth_url": "https://auth.example.com",
  "trusted_proxies": ["127.0.0.1", "::1"],
  "signup": { "per_ip_per_hour": 3, "site_per_hour": 30, "bot_check": true }
}
```

## 값을 정하는 순서

| 값 | 개발 모드 | 공개 모드 |
| --- | --- | --- |
| `blog_url` | 환경변수 `BLOG_URL` > 파일 > `http://localhost:8000` | 파일만(환경변수가 다르면 C7) |
| `auth_url` | 환경변수 `AUTH_URL` > 파일 > `http://localhost:8080` | 파일만(환경변수가 다르면 C7) |
| `trusted_proxies` | 파일 > `[]` | 파일 > `["127.0.0.1", "::1"]` |
| `signup.*` | 파일 > 3 / 30 / true | 파일 > 3 / 30 / true |
| 관리자 비밀번호 | `BLOG_PASSWORD` > `admin1234` | `BLOG_PASSWORD`만(C8~C10) |

주소 값은 끝의 `/`를 지워서 쓴다. 환경변수는 php -S에는 전달되지만 PHP-FPM은 기본으로 지우므로, 운영에서는 파일이 유일한 출처다.

## 검사 목록

블로그 서버는 시작할 때 C1~C11을 모두 검사하고, 회원 서버는 요청마다 C1~C6을 검사한다.

| 번호 | 조건 | 모드 | 안내 문구 |
| --- | --- | --- | --- |
| C1 | 파일이 있는데 JSON 객체로 읽히지 않음 | 모두 | 배포 설정 파일(deploy.config.json)을 읽을 수 없어요: {이유}. JSON 형식을 확인해 주세요. |
| C2 | 형식 오류(`public_mode`·`bot_check`가 true/false 아님, 정수 범위 밖, `trusted_proxies`가 배열·IP가 아님, 주소가 문자열 아님) | 모두 | deploy.config.json의 {키} 값이 올바르지 않아요: {규칙}. |
| C3 | `blog_url`·`auth_url`이 https 오리진이 아님 | 공개 | 공개 모드에서는 {키}에 https 주소만 넣어 주세요(예: https://blog.example.com, 경로 없이). |
| C4 | 두 주소의 오리진이 같음 | 공개 | 블로그와 회원 서버는 서로 다른 주소를 써야 해요(예: blog.·auth. 하위 도메인). |
| C5 | `trusted_proxies`가 비어 있음 | 공개 | 공개 모드에서는 믿는 프록시(trusted_proxies)를 하나 이상 적어 주세요(같은 서버의 Nginx면 127.0.0.1). |
| C6 | `signup.bot_check`가 false | 공개 | 공개 모드에서는 자동 가입 방지(signup.bot_check)를 끌 수 없어요. |
| C7 | 환경변수 `BLOG_URL`·`AUTH_URL`이 있고 파일 값과 다름 | 공개(블로그) | 공개 모드에서는 주소를 deploy.config.json 한 곳에만 넣어 주세요. 환경변수 {이름}을 지우거나 파일과 같게 맞춰 주세요. |
| C8 | `BLOG_PASSWORD`가 없음 | 공개(블로그) | 공개 모드에서는 관리자 비밀번호를 정해야 해요. BLOG_PASSWORD 환경변수(예: /etc/my-blog/blog.env)에 넣어 주세요. |
| C9 | `BLOG_PASSWORD`가 admin1234 | 공개(블로그) | 기본 관리자 비밀번호(admin1234)는 공개 모드에서 쓸 수 없어요. |
| C10 | 12자 미만이거나 영문·숫자 중 하나가 없음 | 공개(블로그) | 관리자 비밀번호는 12자 이상, 영문과 숫자를 함께 넣어 주세요. |
| C11 | `HOST`가 127.0.0.1·::1·localhost가 아님 | 공개(블로그) | 공개 모드에서는 블로그 서버를 127.0.0.1에만 열어요. HOST 환경변수를 지우거나 127.0.0.1로 바꿔 주세요. |

## 블로그 서버 시작 출력

실패: DB·업로드 폴더를 열기 전에 끝내고 종료 코드 **78**.

```text
서버를 켜지 않았어요. 아래 설정을 고쳐 주세요.
 - 공개 모드에서는 관리자 비밀번호를 정해야 해요. BLOG_PASSWORD 환경변수(예: /etc/my-blog/blog.env)에 넣어 주세요.
```

성공(공개 모드):

```text
블로그 실행 중 (공개 모드) → https://blog.example.com  (내부 127.0.0.1:8000)
회원 서버: https://auth.example.com
SNS 개발자 콘솔에 등록할 콜백 주소: https://auth.example.com/oauth_callback.php
```

개발 모드는 지금 출력 그대로(admin1234 안내 포함).

## 회원 서버 동작

- C1~C6 위반: DB를 열지 않고 모든 요청에 **503**. 화면은 "회원 서버 설정을 확인하고 있어요. 잠시 뒤 다시 시도해 주세요."
  (JSON 엔드포인트는 `{"ok": false, "error": "..."}`), 자세한 이유는 `error_log`로만 남긴다(방문자에게 설정 내용을 보이지 않음).
- 공개 모드 + `PHP_SAPI === 'cli-server'` + `ALLOW_PHP_DEV_SERVER`가 1이 아님: **503** "공개 모드에서는 php -S로 회원 서버를 켤 수
  없어요. Nginx + PHP-FPM으로 실행해 주세요(deploy/README.md)."

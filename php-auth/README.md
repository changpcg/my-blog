# PHP 회원가입 / 로그인

PHP + SQLite로 만든 회원가입·로그인입니다. 추가 라이브러리 없이 PHP만 있으면 됩니다.

## 실행

```bash
cd ~/Documents/my-blog/php-auth
php -S localhost:8080 -t public
```

브라우저에서 http://localhost:8080 을 엽니다. 처음 접속할 때 `db/sqlite.db` 파일과 테이블이 자동으로 만들어집니다.

## 가입 항목

| 항목 | 규칙 |
|---|---|
| 아이디 | 영문 소문자·숫자·밑줄(_) 4~20자, 중복 불가 |
| 비밀번호 | 영문+숫자 섞어 8자 이상 (확인 입력 포함) |
| 닉네임 | 2~20자 |
| 자기소개 | 선택, 300자까지 |

## 파일 구조

```
php-auth/
├── public/          ← 웹에 공개되는 폴더 (이것만 서버에 연결)
│   ├── index.php    내 정보 (닉네임·자기소개) / 로그아웃
│   ├── register.php 회원가입
│   ├── login.php    로그인
│   ├── logout.php   로그아웃
│   └── style.css
├── src/
│   ├── db.php       DB 연결, db/sqlite.db·테이블 자동 생성
│   └── auth.php     세션·보안·가입·로그인 로직
└── db/sqlite.db     (자동 생성, 웹에서 접근 불가)
```

## 보안

- **SQL 인젝션 방지:** 모든 쿼리를 PDO `prepare()` + 자리표시자(`?`)로 실행하고, 입력값을 SQL 문자열에 붙이지 않습니다. 에뮬레이션도 꺼서(`ATTR_EMULATE_PREPARES=false`) SQLite가 직접 값을 바인딩합니다.
- **비밀번호:** `password_hash()`(bcrypt)로 저장하고 `password_verify()`로 확인합니다. 원래 비밀번호는 어디에도 저장하지 않습니다.
- **무차별 대입 방지:** 같은 아이디·IP로 15분 안에 5번 틀리면 15분 동안 로그인을 막습니다.
- **XSS 방지:** 화면에 나가는 모든 값은 `htmlspecialchars()`로 처리합니다.
- **CSRF 방지:** 가입·로그인·로그아웃 폼에 일회성 토큰을 넣고 확인합니다.
- **세션 보호:** 로그인할 때 세션 번호를 새로 발급하고, 쿠키는 `HttpOnly`·`SameSite=Lax`로 설정합니다.
- **DB 파일 보호:** `db/` 폴더는 `public/` 바깥에 있어 브라우저로 내려받을 수 없습니다. 실제 서버(Apache·Nginx)에서도 문서 루트를 `public/`으로 설정하세요.

## 블로그와 연결

블로그(8000)에서 `?return=blog`를 붙여 들어오면 가입·로그인 뒤 블로그로 돌려보냅니다 (`src/sso.php`).
블로그 주소가 다르면 `BLOG_URL=http://주소 php -S localhost:8080 -t public`처럼 실행하세요.
`admin`, `root` 같은 아이디는 가입할 수 없습니다.

## SNS 로그인 (카카오 · 네이버 · 구글)

1. `oauth.config.php`를 열어 각 SNS의 키를 넣습니다. 키를 비워 둔 SNS는 버튼이 나오지 않습니다.
2. 각 개발자 센터에 Redirect URI(콜백 주소)를 똑같이 등록합니다: `http://localhost:8080/oauth_callback.php`

| SNS | 등록하는 곳 | 넣을 값 |
|---|---|---|
| 카카오 | developers.kakao.com → 내 애플리케이션 | REST API 키 (`client_id`), 카카오 로그인 켜기, 동의항목 "닉네임" |
| 네이버 | developers.naver.com → Application 등록 (네이버 로그인) | Client ID / Client Secret, 제공 정보 "별명" |
| 구글 | console.cloud.google.com → OAuth 클라이언트 ID (웹) | 클라이언트 ID / 보안 비밀번호 |

- 처음 SNS로 들어오면 **아이디(중복 확인)·닉네임·자기소개**만 받고 가입합니다. 비밀번호는 없습니다.
- 이미 회원이면 **내 정보 → SNS 연결**에서 연결해 두고 SNS로도 로그인할 수 있습니다.
- 계정은 SNS 회원 번호로만 연결하고, 이메일이 같다고 자동으로 합치지 않습니다.
- 보안: state 값으로 위조 요청 차단, 구글은 PKCE 사용, 키는 서버(`oauth.config.php`, 웹에서 접근 불가)에만 저장

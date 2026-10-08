# Contract: 내장 화면 파일

관련: FR-001~FR-005 · NFR-02·06·07·15

## 화면이 부르는 파일 (static/index.html)

| 종류 | 주소 |
| --- | --- |
| 글꼴 | `/vendor/pretendard-1.3.9/pretendard.css` → `PretendardVariable.woff2` |
| 코드 색 | `/vendor/highlight-11.9.0/styles/github.min.css`(id `hljsLight`), `…/github-dark.min.css`(id `hljsDark`) |
| 스크립트 | `/vendor/marked-12.0.2/marked.min.js`, `/vendor/dompurify-3.1.6/purify.min.js`, `/vendor/highlight-11.9.0/highlight.min.js` |

`https://`로 시작하는 `<script src>`·`<link href>`는 없다.

## 응답 규칙 (server.py)

| 요청 | 응답 |
| --- | --- |
| `GET /vendor/…`(있는 파일) | 200, 알맞은 Content-Type(`font/woff2`, `text/javascript`, `text/css`), `Cache-Control: public, max-age=31536000, immutable`, `Access-Control-Allow-Origin: *` |
| 같은 요청 + `If-Modified-Since`(안 바뀜) | 304 + 같은 캐시·CORS 머리글 |
| `GET /vendor/없는파일` | 404, 1년 캐시·CORS 없음 |
| `GET /vendor/`, `GET /vendor/marked-12.0.2/` | 404 (폴더 목록 없음) |
| 그 밖의 화면 파일 | 지금처럼 `Cache-Control: no-cache` |

## 회원 화면 (php-auth/src/auth.php)

`<link rel="stylesheet" href="{BLOG_URL}/vendor/pretendard-1.3.9/pretendard.css">` — CDN 주소 없음.

## 확인 목록 (tests/smoke_offline_assets.py)

1. index.html·static/*.js·php-auth 코드에 `cdn.jsdelivr.net` 없음, 바깥 `<script src>`·`<link href>` 없음
2. index.html이 부르는 모든 파일 200·Content-Type, 글꼴 CSS 속 woff2 200 `font/woff2`
3. `/vendor/` 캐시·CORS, 304도 같은 머리글, 404에는 없음, 폴더 목록 404, 다른 화면 파일은 `no-cache`
4. `static/vendor/README.md`의 SHA-256 = 실제 파일, 라이선스 파일 4개

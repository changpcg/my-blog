# 내장 화면 라이브러리·글꼴

블로그 화면과 회원 화면은 인터넷(CDN) 없이도 돌도록 아래 파일만 씁니다(요구사항 NFR-15, 007-offline-assets).
폴더 이름에 버전이 들어 있어 블로그 서버가 1년 캐시로 내려주고, 회원 화면에서도 글꼴을 쓸 수 있게 다른 주소의 요청을 허용합니다.

| 폴더 | 라이브러리 | 쓰는 곳 | 라이선스 | 받은 곳 (npm 공식 패키지) |
| --- | --- | --- | --- | --- |
| `marked-12.0.2/` | marked 12.0.2 | 마크다운 → HTML | MIT (`LICENSE.md`) | `marked@12.0.2` 의 `marked.min.js` |
| `dompurify-3.1.6/` | DOMPurify 3.1.6 | 본문 HTML 정리(보안) | Apache-2.0 또는 MPL-2.0 (`LICENSE`) | `dompurify@3.1.6` 의 `dist/purify.min.js` |
| `highlight-11.9.0/` | highlight.js 11.9.0 | 코드 색(라이트 github·다크 github-dark) | BSD-3-Clause (`LICENSE`) | `@highlightjs/cdn-assets@11.9.0` 의 `highlight.min.js`, `styles/github.min.css`, `styles/github-dark.min.css` |
| `pretendard-1.3.9/` | Pretendard 1.3.9 가변 글꼴 | 블로그·회원 화면 글꼴 | SIL OFL 1.1 (`LICENSE.txt`) | `pretendard@1.3.9` 의 `dist/web/variable/woff2/PretendardVariable.woff2` |

`pretendard-1.3.9/pretendard.css`는 원본 `pretendardvariable.css`와 같고 글꼴 이름만 `'Pretendard'`로 맞춘 파일입니다(style.css 수정 없이 쓰려고).

npm 패키지 무결성(설치 때 확인한 값):

- marked@12.0.2 `sha512-qXUm7e/YKFoqFPYPa3Ukg9xlI5cyAtGmyEIzMfW//m6kXwCy2Ps9DYf5ioijFKQ8qyuscrHoY04iJGctu2Kg0Q==`
- dompurify@3.1.6 `sha512-cTOAhc36AalkjtBpfG6O8JimdTMWNXjiePT2xQH/ppBGi/4uIpmj8eKyIkMJErXWARyINV/sB38yf8JCLF5pbQ==`
- @highlightjs/cdn-assets@11.9.0 `sha512-F1vJKVAkLwj2Uz2ik1PDc+mDbkrecLI6gcBlAxSRUjyDpMPJjeDBanT9Y2B+xpNe1MT6zSG204Ohm/+nUMCApQ==`
- pretendard@1.3.9 `sha512-PaQAADyLY5v4kYFwkpSJHbSSYIkiriY/1xXw75TKoZ9UQQqeU+tvP05yTdZAWibiIYoo8ZKtRv8PM7w0IaywSw==`

## 파일 확인값 (SHA-256)

`tests/smoke_offline_assets.py`가 아래 값과 실제 파일을 비교합니다. 직접 확인하려면 이 폴더에서
`grep -E '^[0-9a-f]{64} ' README.md | shasum -a 256 -c` (리눅스는 `sha256sum -c`).

```sha256
15fabce5b65898b32b03f5ed25e9f891a729ad4c0d6d877110a7744aa847a894  marked-12.0.2/marked.min.js
c0845096a7c4a6741f362ac506c94c1c7d27dc603bcc1bf64a587f76f2dbe3a1  dompurify-3.1.6/purify.min.js
837a6fa5b0c736b52bbde2b2b6190f305da3fc9ed41681db5321507057b5c846  highlight-11.9.0/highlight.min.js
3a9a5def8b9c311e5ae43abde85c63133185eed4f0d9f67fea4b00a8308cf066  highlight-11.9.0/styles/github.min.css
9f208d022102b1d0c7aebfecd8e42ca7997d5de636649d2b31ea63093d809019  highlight-11.9.0/styles/github-dark.min.css
9599f12fd42fc0bce1cd50b47a0c022e108d7aa64dd0d1bb0ed44f3282d900b4  pretendard-1.3.9/PretendardVariable.woff2
93236c37f61dff454a7983241ed6f8a516bf291238d69eb15ecd3ae7c609e99d  pretendard-1.3.9/pretendard.css
```

## 버전을 올릴 때

1. 새 버전을 npm 공식 패키지에서 받는다(예: `npm pack marked@새버전` 후 압축 풀기). 받은 패키지의 무결성 값(`npm view 패키지@버전 dist.integrity`)을 적어 둔다.
2. 새 버전 이름으로 폴더를 만들어(예: `marked-12.0.3/`) 파일과 라이선스를 넣고, 예전 폴더는 지운다(같은 이름 폴더의 내용을 바꾸면 1년 캐시 때문에 방문자에게
   예전 파일이 남는다).
3. `static/index.html`(그리고 글꼴이면 `php-auth/src/auth.php`)의 주소, 이 문서의 표·무결성·SHA-256을 함께 바꾼다.
4. `python3 tests/smoke_offline_assets.py`와 화면 점검을 돌린다. DOMPurify·marked는 본문 보안과 직결되므로 바뀐 점(변경 기록)을 읽고 올린다.
5. 새 라이브러리를 더하는 것은 헌법 원칙 II 개정(MINOR)이 필요하다.

# Research: 인터넷이 끊겨도 동작

**Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

## 지금 상태

| 파일 | CDN 주소 | 크기 | 라이선스 |
| --- | --- | --- | --- |
| marked 12.0.2 | `/npm/marked@12.0.2/marked.min.js` | 약 35KB | MIT |
| DOMPurify 3.1.6 | `/npm/dompurify@3.1.6/dist/purify.min.js` | 약 21KB | Apache-2.0 또는 MPL-2.0 |
| highlight.js 11.9.0 | `/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js` + `styles/github(-dark).min.css` | 약 120KB | BSD-3-Clause |
| Pretendard 1.3.9 | `/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css` → 굵기별 woff2 | 굵기마다 약 750KB | SIL OFL 1.1 |

## 결정

### D1. 같은 버전을 npm 공식 패키지에서

- **Decision**: npm 레지스트리의 `marked@12.0.2`, `dompurify@3.1.6`, `@highlightjs/cdn-assets@11.9.0`(cdn-release와 같은 배포물), `pretendard@1.3.9`의
  배포 파일을 그대로 복사한다. npm 설치 때 패키지 무결성(sha512)을 확인했고, 저장소에는 파일별 SHA-256을 README에 남겨 시험으로 지킨다.
- **Rationale**: 버전을 바꾸지 않아 화면 동작이 같고(004~006 점검 그대로), 출처가 분명하다.
- **Alternatives**: 최신 버전으로 올리기 → 동작 변화 위험(이번 범위 밖). 직접 빌드 → 출처 확인이 어려움.

### D2. 글꼴은 가변 글꼴 하나

- **Decision**: `PretendardVariable.woff2`(2.0MB, 굵기 45~920) 하나 + 우리 CSS(`font-family: 'Pretendard'`로 이름을 맞춰 style.css 수정 불필요).
- **Rationale**: 지금 화면은 굵기 400·600·700·800을 써서 CDN 굵기별 파일로는 약 3MB를 받는다. 가변 글꼴은 한 번에 2MB, 이후 1년 캐시.
- **Alternatives**: 한글 2,350자 부분 글꼴(굵기마다 270KB) → 드문 글자(예: 똠·햏 등 완성형 밖)가 기기 글꼴로 섞임. 유니코드 범위로 쪼갠 파일
  92개 → 파일이 많아 저장소·안내가 복잡.

### D3. 캐시와 CORS

- **Decision**: `/vendor/`의 200·304 응답에만 `Cache-Control: public, max-age=31536000, immutable`, `Access-Control-Allow-Origin: *`. 그 밖의 화면 파일은
  지금처럼 `no-cache`. 404 등 오류에는 붙이지 않음. 폴더 목록은 404.
- **Rationale**: 폴더 이름에 버전이 있어 내용이 바뀌지 않음. 회원 화면(다른 주소)에서 글꼴을 쓰려면 CORS가 필요하고, 내장 파일은 공개 파일이라 `*`가
  안전(쿠키 없이 요청). 오류를 1년 캐시하면 파일을 넣은 뒤에도 안 보일 수 있음.

### D4. 회원 화면 글꼴

- **Decision**: `page_start()`의 링크를 `BLOG_URL . '/vendor/pretendard-1.3.9/pretendard.css'`로. 블로그 서버가 꺼져 있으면 CSS 요청이 실패하고 기존
  글꼴 목록(-apple-system, Apple SD Gothic Neo)으로 보인다.
- **Alternatives**: php-auth/public에 글꼴 복사 → 2MB 중복. PHP가 글꼴을 대신 읽어 주기 → 코드 늘어남.

### D5. Python 3.9 MIME

- **Decision**: `Handler.extensions_map`에 `.woff2 → font/woff2`, `.js → text/javascript`, `.css → text/css`, `.md → text/plain; charset=utf-8`.
- **Rationale**: Python 3.9의 `mimetypes`는 운영체제 목록에 따라 woff2를 모를 수 있어(`application/octet-stream`) 글꼴 확인이 엄격한 브라우저에서
  문제가 될 수 있다.

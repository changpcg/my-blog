# Implementation Plan: 인터넷이 끊겨도 동작 — 화면 라이브러리·글꼴 내장

**Branch**: `007-offline-assets` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-offline-assets/spec.md`

**Code root**: `~/Documents/my-blog` (GitHub `changpcg/my-blog`)

## Summary

- `static/vendor/<이름>-<버전>/`에 지금 CDN과 같은 버전의 배포 파일과 라이선스를 넣는다: marked 12.0.2(`marked.min.js`), DOMPurify 3.1.6
  (`purify.min.js`), highlight.js 11.9.0(`highlight.min.js`, `styles/github(.min)·github-dark.min.css`), Pretendard 1.3.9(가변 글꼴
  `PretendardVariable.woff2` + 우리 `pretendard.css`: `font-family: 'Pretendard'`, `font-weight: 45 920`). `static/vendor/README.md`에 출처·라이선스·
  SHA-256·버전 올리는 법.
- `static/index.html`은 내장 파일만 부르고(preconnect 삭제), 화면 파일 버전을 올린다.
- `server.py`: `/vendor/` 응답(200·304)에 `Cache-Control: public, max-age=31536000, immutable`과 `Access-Control-Allow-Origin: *`, 폴더 목록 끄기
  (`list_directory` → 404), `.woff2` 등 MIME을 Python 3.9에서도 맞게(`extensions_map`).
- 회원 화면 `php-auth/src/auth.php` `page_start()`: 글꼴 링크를 `BLOG_URL/vendor/pretendard-1.3.9/pretendard.css`로.
- 헌법 원칙 II 개정 1.3.0(MINOR): "jsDelivr CDN의 …로 한정" → "저장소 안 내장 파일(static/vendor/, 라이선스·확인값 포함)로 한정, 실행 중 CDN 요청 없음".

## Technical Context

**Language/Version**: Python 3.9+ 표준 라이브러리, PHP 8, 바닐라 JS·CSS

**Primary Dependencies**: 같은 4개(위치만 CDN → 저장소). 새 라이브러리 없음

**Storage**: 해당 없음 (파일 약 2.3MB 추가: 글꼴 2.0MB, 스크립트 약 180KB)

**Testing**: `tests/smoke_offline_assets.py`(표준 라이브러리: CDN 주소 없음·화면이 부르는 파일 200·MIME·캐시·CORS·404 캐시 없음·폴더 목록 404·SHA-256·
라이선스) + 화면 점검(Playwright, 바깥 요청 모두 차단: 목록·본문·코드 색·미리보기·글꼴, 회원 화면 글꼴) + 001~006 회귀

**Target Platform**: 최신 브라우저. 가변 글꼴은 `format('woff2-variations')` 다음에 `format('woff2')`로도 적어 둔다

**Constraints**: 회원 화면은 다른 주소(8080·공개 모드 auth.) → 글꼴 CORS 필요. 내장 파일 주소에 버전이 들어 있어 캐시를 길게 둬도 안전

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* (헌법 v1.2.0 → 개정 후 v1.3.0)

| 원칙 | 확인 | 결과 |
| --- | --- | --- |
| I 서버 판단 | 동작 변화 없음. 본문은 그대로 DOMPurify를 거침(같은 버전). 내장 파일은 공개 관문(https 규칙)을 그대로 지남 | 통과 |
| II 설치 없음 | 설치 없이 그대로 돎(파일만 추가). **문구 "jsDelivr CDN의 …로 한정"과 충돌** → 헌법 개정 1.3.0(MINOR): 같은 4개 라이브러리를 저장소 안 내장 파일로 한정 | 개정 후 통과 |
| III 서명·POST | 변경 없음 | 해당 없음 |
| IV 데이터 보존 | 데이터 변경 없음 | 해당 없음 |
| V 추적 | NFR-15 추가, NFR-02·06·07·7장 개정 작업 포함 | 통과 |
| VI 한국어·접근성·디자인 | 같은 글꼴·색, 블로그 서버가 꺼졌을 때 회원 화면은 기기 한글 글꼴 | 통과 |

**Phase 1 뒤 재확인**: 새 권한 경로 없음(정적 파일만), CORS는 내장 파일에만, 쿠키·인증 없는 응답. 위반 없음.

## Project Structure

```text
my-blog/
├── static/vendor/
│   ├── README.md                        # 출처·버전·라이선스·SHA-256·올리는 법
│   ├── marked-12.0.2/{marked.min.js, LICENSE.md}
│   ├── dompurify-3.1.6/{purify.min.js, LICENSE}
│   ├── highlight-11.9.0/{highlight.min.js, styles/github.min.css, styles/github-dark.min.css, LICENSE}
│   └── pretendard-1.3.9/{pretendard.css, PretendardVariable.woff2, LICENSE.txt}
├── static/index.html                    # 내장 파일 주소, 버전 올림
├── server.py                            # /vendor/ 캐시·CORS, 폴더 목록 끄기, MIME
├── php-auth/src/auth.php                # 글꼴 링크 → 블로그 서버 내장 글꼴
└── tests/smoke_offline_assets.py
```

## Complexity Tracking

해당 없음 (원칙 II 문구는 위반으로 두지 않고 개정으로 해결).

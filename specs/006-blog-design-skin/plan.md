# Implementation Plan: 블로그 꾸미기 — 대표 색·사이드바 구성·인기 글

**Branch**: `006-blog-design-skin` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-blog-design-skin/spec.md`

**Code root**: `~/Documents/my-blog` (GitHub `changpcg/my-blog`)

## Summary

- **US1 대표 색**: `users.skin` 칸(기본 `coral`)과 `style.css`의 색 8가지(`[data-skin=…]`마다 `--accent`·`--accent-soft`, 라이트·다크 두 벌)를
  더한다. 라우터는 블로그 화면(`#/@아이디…`)·글 화면에서만 `<html data-skin>`을 그 블로그 색으로 두고, 나머지 화면에 들어가는 순간 지운다.
  강조색 바탕 위 글자는 새 변수 `--on-accent`(라이트 흰색·다크 #161616)로 바꿔 다크 모드 버튼 글자 대비를 2.6:1 → 6.7:1 이상으로 올린다.
- **US2 인기 글**: 서버가 공개 글 중 조회수 1 이상을 `views DESC, created_at DESC, id DESC` 5개로 골라 `GET /api/blogs/<아이디>`(그 블로그)와
  `GET /api/blog`(사이트 전체, 블로그 이름 포함)의 `popular`로 준다. 대표 사진은 005의 `post_thumbnail()` 그대로. 화면은 두 사이드바에 순위 목록.
- **US3 항목 켜고 끄기**: `users.hidden_widgets`(JSON 목록, 기본 `[]`). 허용 이름 `room·types·popular·tags·comments·stats`. 끈 항목 중
  `popular·tags·comments·stats`는 블로그 API가 빈 값으로 보내고, 화면은 칸을 그리지 않는다. `room`을 끄면 배너에 미니룸이 없다.
- **꾸미기 화면**: 블로그 관리 탭 '🎨 꾸미기' — 색 라디오(진짜 `input type=radio`, 화살표 이동) + 미리보기 카드(`data-skin`으로 그 안만 색 적용),
  항목 체크박스, 바뀐 것이 있을 때만 저장(`PUT /api/me`).

## Technical Context

**Language/Version**: Python 3.9+ 표준 라이브러리, 바닐라 JS·CSS (기존 CDN 라이브러리만)

**Primary Dependencies**: 없음 (새 의존성 없음)

**Storage**: blog.db `users`에 `skin TEXT NOT NULL DEFAULT 'coral'`, `hidden_widgets TEXT NOT NULL DEFAULT '[]'` 칸 추가(없을 때만)

**Testing**: `tests/smoke_blog_design.py`(표준 라이브러리, 임시 폴더 서버: 색·항목 저장 검사, 인기 글 규칙, 끈 항목 자료 빠짐, 예전 DB) + 화면 동작
점검(Playwright, 작업 환경: 색 적용·해제·깜빡임·다크·375px) + 001~005 회귀

**Target Platform**: 최신 브라우저(PC·휴대폰). CSS 변수·`:not()`·속성 선택자만 사용

**Constraints**: 해시 라우터 — 블로그 사이를 오갈 때 늦게 온 응답이 색을 덮지 않아야 함(`routeSeq`). 화면 모드는 `<html data-theme>`이므로 색 규칙은
`data-theme`과 함께 써서 다시 그리지 않고도 라이트/다크가 바뀌게 함

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* (헌법 v1.2.0)

| 원칙 | 확인 | 결과 |
| --- | --- | --- |
| I 서버 판단 | 색·항목 값은 서버가 허용 목록으로 검사, 인기 글은 서버가 공개 글만 골라 줌, 끈 항목 자료는 서버가 빼고 보냄. 수정은 로그인한 본인 블로그만(`PUT /api/me`) | 통과 |
| II 설치 없음 | 새 라이브러리·외부 요청 없음, 색은 CSS 변수 | 통과 |
| III 서명·POST | 회원 연결 변경 없음, 상태 변경은 기존 `PUT /api/me` | 해당 없음 |
| IV 데이터 보존 | `users` 칸 2개 추가(기본값 = 지금 모습), 기존 블로그 그대로 | 통과 |
| V 추적 | BLOG-26·27 추가, BLOG-01·02·17, NFR-01·04 개정 작업 포함 | 통과 |
| VI 한국어·접근성·디자인 | 한국어 문구, 색마다 대비 4.5:1 이상(기본 코랄 라이트는 지금 색 유지), 다크 버튼 글자 대비 개선, 라디오·체크박스는 기본 입력 요소, 375px·다크, NFR-01 담백한 카드 | 통과 |

**Phase 1 뒤 재확인**: 새 저장소는 `users` 칸 2개뿐이고 새 권한 경로가 없다(본인 정보 수정 API 재사용). 위반 없음.

## Project Structure

### Documentation (this feature)

```text
specs/006-blog-design-skin/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
├── contracts/blog-design.md   # PUT /api/me(skin·hidden_widgets), 블로그 API popular·숨김, 화면 색 적용 규칙
└── checklists/requirements.md
```

### Source Code (repository root)

```text
my-blog/
├── server.py                 # SKINS·WIDGET_KEYS, init_db 칸 2개, BLOG_FIELDS·blog_dict, popular_posts(), GET blogs/blog, PUT me
├── static/app.js             # setSkin()·라우터, renderBlog routeSeq, 사이드바 인기 글·항목 숨김, 배너 미니룸 숨김, 꾸미기 탭
├── static/style.css          # --on-accent, 006 구역: 색 8가지(라이트·다크), 인기 글 목록, 꾸미기 화면
├── static/index.html         # 버전 올림
└── tests/smoke_blog_design.py
```

**Structure Decision**: 기존 단일 저장소 구조 그대로.

## Complexity Tracking

해당 없음.

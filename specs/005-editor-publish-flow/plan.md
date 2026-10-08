# Implementation Plan: 넓은 글쓰기 화면과 발행 설정 창

**Branch**: `005-editor-publish-flow` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-editor-publish-flow/spec.md`

**Code root**: `~/Documents/my-blog` (GitHub `changpcg/my-blog`)

## Summary

- **US1 넓은 편집 화면**: 라우터가 글쓰기·수정 화면에서 `body.editor-mode`를 켜서 사이드바를 숨기고 본문 칸을 1열로 쓴다(다른 화면에서는 끔).
  도구 모음은 `position: sticky`, 편집 화면 아래에 글자 수.
- **US2 발행 설정 창**: 편집 화면의 카테고리·태그·공개 칸을 `<dialog id="publishDlg">`로 옮긴다. '발행'/'저장'은 창을 열고, 창의 확인 버튼이
  API를 부른다. 대표 사진 선택지는 본문에서 찾은 업로드 사진(서버와 같은 규칙), 미리보기는 004의 `postRowHtml` 모양 그대로.
- **서버**: `posts.cover TEXT NOT NULL DEFAULT ''` 칸 추가(init_db), `read_post_body`가 `cover`를 검사(`''`·`'none'`·본문 속 업로드 사진),
  `post_thumbnail(row)`이 고른 사진 → 없음 → 자동 순으로 정해 목록·관련 글에 쓴다.
- **US3 나가기 경고**: 라우터의 `hashchange`를 `leaveGuard`로 감싸 확인을 받고, 취소하면 주소를 되돌린다. `beforeunload`로 탭 닫기 경고.

## Technical Context

**Language/Version**: Python 3.9+ 표준 라이브러리, 바닐라 JS·CSS (기존 CDN 라이브러리만)

**Primary Dependencies**: 없음 (새 의존성 없음)

**Storage**: blog.db `posts`에 `cover` 칸 추가(없을 때만, 기본값 `''`)

**Testing**: `tests/smoke_editor_cover.py`(표준 라이브러리, 임시 폴더 서버) + 화면 동작 점검(Playwright, 작업 환경) + 001~004 회귀

**Target Platform**: 최신 브라우저(PC·휴대폰), `<dialog>` 사용(004와 같음)

**Constraints**: 해시 라우터 — 나가기를 취소할 때 주소를 되돌리며 화면을 다시 그리지 않아야 함. 대표 사진 판단은 서버가 최종(헌법 I).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* (헌법 v1.2.0)

| 원칙 | 확인 | 결과 |
| --- | --- | --- |
| I 서버 판단 | 대표 사진 값은 서버가 허용 목록(자동·없음·본문 속 업로드 사진)으로 검사, 화면 선택지는 안내용. 권한은 기존 글쓰기·수정 규칙 그대로 | 통과 |
| II 설치 없음 | 새 라이브러리 없음, `<dialog>`·sticky는 브라우저 기능 | 통과 |
| III 서명·POST | 변경 없음 | 해당 없음 |
| IV 데이터 보존 | `cover` 칸만 추가(기본 `''` = 지금과 같은 자동), 기존 글 그대로 | 통과 |
| V 추적 | BLOG-24·25 추가, BLOG-05·20 개정 작업 포함 | 통과 |
| VI 한국어·접근성·디자인 | 한국어 문구, 창은 Esc·포커스 가둠, 375px·다크, NFR-01 담백한 카드 규칙 | 통과 |

## Project Structure

```text
my-blog/
├── server.py                 # init_db: posts.cover, upload_images()·post_thumbnail(), read_post_body(cover), POST/PUT, post_dict·related
├── static/app.js             # renderEditor(넓은 화면·발행 창·글자 수·나가기 경고), 라우터 hashchange 감싸기, editor-mode
├── static/style.css          # 005 구역: editor-mode, sticky 도구 모음, 발행 창, 대표 사진 선택지
├── static/index.html         # 버전 올림
└── tests/smoke_editor_cover.py
```

## Complexity Tracking

해당 없음.

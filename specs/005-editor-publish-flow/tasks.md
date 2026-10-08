# Tasks: 넓은 글쓰기 화면과 발행 설정 창

**Input**: plan.md, spec.md, research.md, data-model.md, contracts/posts-cover.md · **Code root**: `~/Documents/my-blog`

## Phase 1: Foundational

- [x] T001 `server.py` init_db: `posts.cover` 칸(없을 때만)
- [x] T002 `server.py` `upload_images()`·`post_thumbnail()`, `post_dict()`·`get_post()` related가 `post_thumbnail` 사용

## Phase 2: US2 발행 설정 창 (P1) 🎯

- [x] T003 [US2] `server.py` `read_post_body()` `cover` 검사, `api_POST_posts`·`api_PUT_posts`에 `cover` 저장
- [x] T004 [US2] `static/app.js` `renderEditor()`: 카테고리·태그·공개를 `<dialog id="publishDlg">`로, 대표 사진 선택지·미리보기, 확인 시 API
- [x] T005 [US2] `static/style.css` 발행 창·대표 사진 선택지·미리보기(라이트·다크·375px)

## Phase 3: US1 넓은 편집 화면 (P1)

- [x] T006 [US1] `static/app.js` 라우터: 글쓰기·수정에서 `body.editor-mode`, 다른 화면에서 끔
- [x] T007 [US1] `static/style.css` editor-mode(사이드바 숨김·1열), sticky 도구 모음, 글자 수 줄
- [x] T008 [US1] `static/app.js` 글자 수(전체·공백 제외)

## Phase 4: US3 나가기 경고 (P2)

- [x] T009 [US3] `static/app.js` `leaveGuard`·hashchange 되돌리기·`beforeunload`, 발행·저장 뒤 해제

## Phase 5: Polish

- [x] T010 `static/index.html` 화면 파일 버전 올림
- [x] T011 [P] `tests/smoke_editor_cover.py` (contracts 확인 1~5)
- [x] T012 화면 점검(라이트·다크 × 1280·375, 발행 창 흐름·대표 사진·나가기 경고) + 001~004 회귀
- [x] T013 requirements.md 두 사본·원본 문서: BLOG-24·25 추가, BLOG-05·20 개정

## Phase 6: 점검 반영

- [x] T014 `static/style.css` 발행 창의 공개 설정 라디오(`.field input` 폭 100%)·대표 사진 칸(`.field span` 블록·굵게)이 기존 규칙에 덮이던 문제를
  구체적인 선택자로 고침, 720px 이하에서 도구 모음 고정 해제(여러 줄이라 자판이 올라오면 쓸 자리가 좁아짐)·자동 저장 안내를 아래 한 줄로
- [x] T015 화면 동작 점검 24개(`check005`: 넓은 화면·글자 수·제목 안내·발행 창·카테고리 오류·대표 사진·태그 Enter·Esc·값 유지·발행·수정 창·
  나가기 확인/취소/바꾸지 않음·휴대폰 넘침), 004 화면 동작 42개, 스모크 001(4)·002(2)·003(16)·004(6)·005(5) 모두 통과

## Phase 7: 독립 검토 반영 (research.md D6)

- [x] T016 `static/app.js` 발행 뒤 임시 저장 예약 취소, `renderEditor` `routeSeq`, `logout()` 나가기 확인, 창이 닫힌 뒤 실패 토스트
- [x] T017 `static/style.css` 대표 사진 선택지 포커스 링, 창 안내 글자 `--text-2`, `fieldset` 규칙을 발행 창 안으로
- [x] T018 다시 점검: 검토 반영 화면 점검 12개(`check_review`), 화면 005(24)·004(42)·006(36), 스모크 001~008 통과

## Dependencies

T001 → T002 → T003 → T004. 같은 파일 작업은 순서대로.

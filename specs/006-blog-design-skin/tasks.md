# Tasks: 블로그 꾸미기 — 대표 색·사이드바 구성·인기 글

**Input**: plan.md, spec.md, research.md, data-model.md, contracts/blog-design.md · **Code root**: `~/Documents/my-blog`

## Phase 1: Foundational

- [x] T001 `server.py` `SKINS`·`WIDGET_KEYS`, init_db `users.skin`·`users.hidden_widgets`(없을 때만), `BLOG_FIELDS`·`blog_dict()`(색 확인·항목 목록)
- [x] T002 `server.py` `popular_posts(conn, blog_id=None)`(공개·조회수 1 이상·정렬·5개·대표 사진)

## Phase 2: US1 대표 색 (P1) 🎯

- [x] T003 [US1] `server.py` `api_PUT_me`: `skin`·`hidden_widgets` 검사·저장(틀리면 400, 한 요청은 한 트랜잭션)
- [x] T004 [US1] `static/style.css` `--on-accent`(라이트 #fff·다크 #161616)와 강조색 바탕 글자 5곳 교체, 006 구역: 색 8가지 라이트·다크
- [x] T005 [US1] `static/app.js` `setSkin()`, `render()`에서 블로그·글 화면이 아니면 먼저 해제, `renderBlog()` `routeSeq` 확인 후 `setSkin(b.skin)`,
  `renderPost()` `setSkin(b.skin)`

## Phase 3: US2 인기 글 (P1)

- [x] T006 [US2] `server.py` `GET /api/blogs/<아이디>`·`GET /api/blog`에 `popular`
- [x] T007 [US2] `static/app.js` `popularHtml()`, 블로그 사이드바(카테고리·글 종류 다음)·블로그 홈 사이드바(내 블로그 다음), 사진 오류 처리
- [x] T008 [US2] `static/style.css` 인기 글 목록(순위·제목 2줄·조회수·48px 사진, 라이트·다크)

## Phase 4: US3 항목 켜고 끄기 + 꾸미기 탭 (P2)

- [x] T009 [US3] `server.py` 끈 항목 자료 빼기(`popular`·`tags`·`recent_comments` → `[]`, `stats` → `null`)
- [x] T010 [US3] `static/app.js` `renderBlogSidebar()` 끈 항목 숨김, `blogBanner()` 미니룸 숨김
- [x] T011 [US3] `static/app.js` 블로그 관리 '🎨 꾸미기' 탭(`manageDesign`): 색 라디오·미리보기·항목 체크박스·저장
- [x] T012 [US3] `static/style.css` 꾸미기 화면(색 고르기·미리보기·375px)

## Phase 5: Polish

- [x] T013 `static/index.html` 화면 파일 버전 올림
- [x] T014 [P] `tests/smoke_blog_design.py` (contracts 확인 1~6)
- [x] T015 화면 점검(라이트·다크 × 1280·375: 꾸미기 탭·색 적용 블로그·글·블로그 홈 해제·인기 글·항목 숨김, 늦은 응답) + 001~005 회귀
- [x] T016 requirements.md 두 사본·원본 문서: BLOG-26·27 추가, BLOG-01·02·17, NFR-01·04 개정

## Phase 6: 점검 결과

- [x] T017 `render()`가 늦게 실패한 이전 화면의 오류로 새 화면을 덮지 않게(`seq` 확인), 없는 블로그·글 오류는 기본색, 이전 화면이 끝날 때 맨 위로
  올리지 않음
- [x] T018 화면 동작 점검 36개(`check006`: 꾸미기 탭·화살표 이동·미리보기만 바뀜·저장·내 블로그/글 파랑·블로그 홈/다른 블로그/관리/글쓰기/내 정보
  색·모드만 바꿔도 다크 색·늦은 응답·없는 블로그·방문자 API에 방문자 수 없음·라이트/다크 × 1280/375 넘침 0), 004 화면 42개·005 화면 24개,
  스모크 001(4)·002(2)·003(16)·004(6)·005(5)·006(6) 모두 통과

## Phase 7: 독립 검토 반영 (research.md D8)

- [x] T019 `static/style.css` 분홍 라이트 #be185d, 꾸미기 체크박스 포커스, `#designForm` 간격, 미니룸 없는 배너 줄, 지금 카테고리 굵게
- [x] T020 `static/app.js` `renderPortal`·`renderNeighbors`·`renderManage`(사이드바 포함)·`renderSettings`·맛집/로그인 사이드바에 `routeSeq` 확인
- [x] T021 다시 점검: 검토 반영 화면 점검 12개, 화면 006(36)·004(42)·005(24), 스모크 006(6)·001~008 통과

## Dependencies

T001 → T002·T003 → T005·T006 → T007·T009 → T010·T011. `static/app.js`·`style.css`는 같은 파일이라 순서대로. T014는 T003·T006·T009 뒤.

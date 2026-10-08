# Tasks: 담백한 디자인과 읽기 좋은 글 화면

**Input**: plan.md, spec.md, research.md, data-model.md, contracts/posts-api.md, contracts/reading-ui.md · **Code root**: `~/Documents/my-blog`

## Phase 1: Setup

- [x] T001 바꾸기 전 화면 캡처(라이트·다크 × 1280·375: 홈·개인 블로그·글 보기)와 375px 넘침 측정(글 보기 479px) — 비교 기준
- [x] T002 헌법 개정 v1.2.0(MINOR): 원칙 VI 디자인 문구 → "requirements.md NFR-01의 디자인 규칙", Sync Impact Report (`blog-project/.specify/memory/constitution.md`)

## Phase 2: Foundational

- [x] T003 `static/style.css` 디자인 토큰: `--radius` 12px, `--line-strong`, `--shadow-soft`, `--shadow-pop`(라이트·다크 두 곳)
- [x] T004 `static/style.css` 900px 이하 `.layout` 열을 `minmax(0, 1fr)`로 (375px 넘침 원인)

## Phase 3: US1 담백한 디자인 (P1) 🎯

- [x] T005 [US1] `static/style.css` 카드 컴포넌트 교체: 1px·12px·그림자 없음, hover는 선 색·옅은 그림자만, PC 오프셋 그림자·떠오름·눌림 삭제
- [x] T006 [P] [US1] `static/style.css` 위젯·공감 버튼·첨부 파일 카드·미니룸 선·미니룸 고르기·맛집 검색 칸의 2~3px 선과 그림자 제거, 내 메뉴 `--shadow-pop`
- [x] T007 [P] [US1] `php-auth/public/style.css` 회원 화면 같은 규칙(카드·입력·버튼·알림·블로그 홈으로·SNS 버튼), `php-auth/src/auth.php` `style.css?v=4`

## Phase 4: US2 글 목록 대표 사진 (P1)

- [x] T008 [US2] `server.py` `THUMB_RE`·`FENCE_RE`·`first_upload_image()`, `post_dict()` 대표 사진·요약(HTML 태그 제거)
- [x] T009 [US2] `static/app.js` `postRowHtml()`(has-thumb, 사진 오른쪽), `postsBody()` → `.post-list`
- [x] T010 [US2] `static/style.css` `.post-list`·`.post-row` grid 영역(PC·600px 이하), 사진 120/84px, 제목·요약 2줄
- [x] T011 [US2] `static/app.js` 사진 `error` 캡처 리스너: 목록 사진·`has-thumb` 제거

## Phase 5: US3 읽기 도구 (P1)

- [x] T012 [US3] `static/app.js` `jumpTo()`(포커스 + 동작 줄이기 반영), 용어 사전 색인도 사용
- [x] T013 [US3] `static/app.js` `renderPost()` 읽는 시간(`readMinutes`), 목차(`buildToc`, 900px 이하 접힘)
- [x] T014 [US3] `static/app.js` `startReadingTools()`/`stopReadingTools()` 진행 막대·맨 위로, 라우터 `render()`에서 정리
- [x] T015 [US3] `static/style.css` 목차·진행 막대·맨 위로, `scroll-margin-top`, 표 칸 `overflow-wrap: break-word`, 인용문 여백

## Phase 6: US4 글 아래 (P2)

- [x] T016 [US4] `server.py` `get_post()` 관련 글 최신순 4개 + `type`·`is_public`·`thumbnail`
- [x] T017 [US4] `static/app.js` 공감 옆 공유하기(`sharePost`·`copyText`·직접 복사 칸), 작성자 카드(`neighborBtn` 공용), 관련 글 사진 카드, 이전·다음 카드
- [x] T018 [US4] `static/style.css` `.post-actions`·`.share-btn`·`.author-card`·`.related-grid`(4칸/2칸)·`.prevnext`

## Phase 7: US5 사진·코드 (P3)

- [x] T019 [US5] `static/app.js` `renderMd()` 사진 → `button.img-zoom`, `pre` → `.code-block`(언어 이름·복사)
- [x] T020 [US5] `static/app.js` `openLightbox()`(`<dialog>`), `copyCode()`, `announce()`, 클릭 위임
- [x] T021 [US5] `static/style.css` 크게 보기·코드 머리, 다크 모드 색

## Phase 8: 검증

- [x] T022 `static/index.html` `style.css?v=19`, `app.js?v=20`
- [x] T023 [P] `tests/smoke_reading_ui.py` (contracts/posts-api.md 확인 1~5 + 화면 파일 버전)
- [x] T024 화면 점검: 라이트·다크 × 1280·375 × (홈·개인 블로그·글 보기 3개·FAQ·용어 사전·이웃 새 글·블로그 관리·사이트 설정·회원 로그인·가입) 넘침 0건
- [x] T025 회귀: `smoke_public_deploy.py`(16)·`smoke_member_lifecycle.py`(2)·`smoke_security_gaps.py`(4, 회원 둘), 기존 blog.db 복사본으로 켜서 글 그대로

## Phase 9: 독립 검토 반영 (research.md D11)

- [x] T026 `server.py` 정규식을 길이에 비례하게(`[^<>]`·`[^\[\]\n]`·`[^()]`), `POST_MAX_CHARS` 20만 자(`read_post_body`), 줄 맨 앞 코드 울타리·HTML 주석·두 겹 인라인 코드 제외, 요약에서 인라인 코드 보호(`strip_tags_outside_code`)
- [x] T027 `static/app.js` `renderMd()` DOMPurify `SANITIZE_NAMED_PROPS`·`ALLOW_DATA_ATTR: false`, 글쓴이 class 제거(`language-*`만), 코드 칸 `style`·`hidden` 제거, 언어 이름 자기 항목만
- [x] T028 `static/app.js` `routeSeq`(늦게 온 글은 그리지 않음), 목차·색인 보조 키 클릭은 브라우저에 맡김
- [x] T029 [P] `static/style.css` 목차 소제목·코드 언어 `--text-2`, 복사 완료 #157347, 맨 위로 44px / `php-auth/public/style.css` `--line` #ebebea, 입력 포커스 2px
- [x] T030 다시 점검: `smoke_reading_ui.py` 6개(길이 상한·악성 본문 속도 추가), 화면 동작 42개(악성 본문 흉내·느린 응답 추가), 화면 36장 넘침 0건, 회귀 16·2·4

## Phase 10: 문서·마무리

- [x] T031 requirements.md 두 사본(blog-project·my-blog) + 원본 Claude Docs: BLOG-20~23 추가, NFR-01·03·10, BLOG-01·05·09, SEC-04, SOC-03, 남은 과제 갱신
- [x] T032 커밋(blog-project·my-blog), push는 사용자

## Dependencies

Phase 2 → US1~US5 → Phase 8 → Phase 9. T008 → T009·T016·T026. `static/app.js`·`style.css` 작업은 같은 파일이라 순서대로. T002·T031은 문서라 코드와 나란히.

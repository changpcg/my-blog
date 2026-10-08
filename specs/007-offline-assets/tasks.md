# Tasks: 인터넷이 끊겨도 동작 — 화면 라이브러리·글꼴 내장

**Input**: plan.md, spec.md, research.md, data-model.md, contracts/static-assets.md · **Code root**: `~/Documents/my-blog`

## Phase 1: Setup

- [x] T001 헌법 개정 v1.3.0(MINOR): 원칙 II "jsDelivr CDN의 …로 한정" → 저장소 안 내장 파일, Sync Impact Report (`blog-project/.specify/memory/constitution.md`)

## Phase 2: US1 블로그 화면 (P1) 🎯

- [x] T002 [US1] `static/vendor/` 4개 폴더에 배포 파일·라이선스 복사, `pretendard-1.3.9/pretendard.css`(가변 글꼴, 이름 'Pretendard')
- [x] T003 [US1] `static/index.html` 내장 파일 주소, preconnect 삭제, 화면 파일 버전 올림
- [x] T004 [US1] `server.py` `/vendor/` 200·304에 1년 캐시·CORS, `list_directory` 404, `extensions_map`(woff2·js·css·md)

## Phase 3: US2 회원 화면 (P2)

- [x] T005 [US2] `php-auth/src/auth.php` `page_start()` 글꼴 링크 → `BLOG_URL/vendor/pretendard-1.3.9/pretendard.css`

## Phase 4: US3 출처·무결성 (P2)

- [x] T006 [US3] `static/vendor/README.md` 출처·버전·라이선스·SHA-256·버전 올리는 법

## Phase 5: Polish

- [x] T007 [P] `tests/smoke_offline_assets.py` (contracts 확인 1~4)
- [x] T008 화면 점검: 바깥 요청 모두 차단한 브라우저로 홈·글 보기·코드 색·글쓰기 미리보기·글꼴, 회원 화면 글꼴(블로그 서버 켬/끔) + 001~006 회귀
- [x] T009 README(내 컴퓨터 실행 안내)·requirements.md 두 사본·원본 문서: NFR-15 추가, NFR-02·06·07, 7장 jsDelivr 행·범위 문장

## Phase 6: 점검 결과

- [x] T010 `server.py` 내장 파일 판단은 `%xx`·`..`를 푼 경로로(`/vendor/../index.html`에 1년 캐시가 붙지 않게), 요청마다 `vendor` 표시를 새로 정함
  (연결을 다시 쓰더라도 API 응답에 붙지 않게)
- [x] T011 점검: 스모크 007(4), 바깥 요청을 모두 막은 브라우저 10개(목록·글꼴 loaded·코드 색·미리보기·CDN 0건·회원 화면 CORS 글꼴·블로그 서버를
  끄면 회원 화면 0.02초에 기기 글꼴), 화면 004(42)·005(24)·006(36), 스모크 001(4)·002(2)·003(16)·004(6)·005(5)·006(6) 모두 통과

## Phase 7: 독립 검토

- [x] T012 검토 결과 007은 고칠 점 없음: 내장 파일·라이선스가 npm 배포물과 바이트 단위로 같음, `/vendor/` 머리글(리디렉션·폴더 목록·HEAD·질의 문자열·
  `%2e%2e`·`..%2f`·304·공개 모드 308/500)과 회원 화면의 다른 주소 글꼴 불러오기 확인

## Dependencies

T001은 문서라 나란히. T002 → T003·T005·T006 → T007 → T008.

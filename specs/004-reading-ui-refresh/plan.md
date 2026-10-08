# Implementation Plan: 담백한 디자인과 읽기 좋은 글 화면

**Branch**: `004-reading-ui-refresh` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-reading-ui-refresh/spec.md`

**Code root**: `~/Documents/my-blog` (GitHub `changpcg/my-blog`)

## Summary

- **US1 디자인**: `static/style.css`의 네오 브루탈리즘 규칙(PC 3px 테두리·6px 오프셋 그림자·떠오름)을 걷어 내고, 카드·위젯·공감 버튼·
  첨부 파일 카드·미니룸 선을 1px 선 + 둥근 모서리 12px + 그림자 없음으로 통일한다. 마우스를 올리면 선 색(`--line-strong`)과 옅은
  그림자(`--shadow-soft`)만 바뀐다. 회원 화면 `php-auth/public/style.css`도 같은 값으로 바꾼다.
- **US2 목록**: `post_dict()`의 대표 사진 정규식을 `first_upload_image()`로 바꿔 업로드 사진만(마크다운·HTML, 띄어쓰기·제목·꺾쇠 허용,
  코드 블록 제외) 고르고, 요약에서 HTML 태그를 뺀다. 화면은 카드 2열 대신 `post-row` 한 줄 목록(오른쪽 정사각형 사진)으로 그린다.
- **US3 읽기 도구**: 글 보기에서 읽는 시간·목차(`<details>`)·진행 막대·맨 위로 버튼을 붙이고, 화면이 바뀌면 정리한다. 375px 넘침은
  `.layout`의 900px 이하 열을 `minmax(0, 1fr)`로 바꿔 고친다(긴 코드가 열을 넓히던 원인). 표 칸은 `overflow-wrap: break-word`로 한 글자씩
  끊기지 않게 한다.
- **US4 글 아래**: 공감 옆 공유하기(Web Share → 클립보드 → 직접 복사 안내), 작성자 카드에 이웃 추가 버튼(기존 `bindNeighborButtons`),
  관련 글 최신순 4개를 대표 사진 카드로(`get_post`가 `type·is_public·thumbnail`을 함께 줌), 이전·다음 글 카드.
- **US5 사진·코드**: `renderMd()`에서 사진을 `button.img-zoom`으로 감싸 `<dialog>` 크게 보기를 열고, `pre`를 `.code-block`(언어 이름 +
  복사 버튼)으로 감싼다. 동작은 문서 전체 클릭 위임 하나로 처리한다. 본문 HTML이 이 부품을 흉내 내지 못하도록 DOMPurify 설정(id 접두어·
  data-* 제거)과 글쓴이 class 제거를 함께 한다.
- **검토 반영**: 구현 뒤 독립 검토에서 찾은 문제 9건(높음 1·중간 2·낮음 6)을 고쳤다 → research.md D11.

## Technical Context

**Language/Version**: Python 3.9+ 표준 라이브러리(블로그 서버), PHP 8(회원 서버, 스타일만), 바닐라 JS(ES2020)·CSS

**Primary Dependencies**: 기존 CDN만 — marked 12.0.2·DOMPurify 3.1.6·highlight.js 11.9.0·Pretendard 1.3.9. 새 의존성 없음

**Storage**: 변경 없음(표·칸 추가 없음). 대표 사진은 목록·글 보기 응답을 만들 때 계산

**Testing**: `tests/smoke_reading_ui.py`(표준 라이브러리, 임시 폴더 서버로 대표 사진·관련 글 규칙) + 기존 001·002·003 스모크 회귀 +
quickstart의 화면 점검(라이트·다크 × PC 1280·375px)

**Target Platform**: 최신 Chrome·Safari·Firefox·Edge(PC·휴대폰). `<dialog>`·`:is()`·`aspect-ratio`·`navigator.clipboard`를 쓰고, 공유 창이
없는 브라우저는 복사로 대신

**Project Type**: 웹 서비스 2개(블로그 SPA + 회원 PHP) 중 화면 위주 변경

**Performance Goals**: 새 요청 없음(대표 사진만 lazy 로딩), 스크롤 처리는 `requestAnimationFrame`으로 한 프레임에 한 번

**Constraints**: 해시 라우팅(`#/post/11`)이라 목차·색인 이동은 해시를 바꾸면 안 됨, 위쪽 고정 바 높이 106px만큼 이동 위치 보정,
'동작 줄이기'면 부드러운 스크롤 끔, 화면 파일 버전(`?v=`) 올림(NFR-06)

**Scale/Scope**: 화면 파일 3개(app.js·style.css·index.html), server.py 함수 2곳, 회원 style.css·auth.php(버전) 1곳

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* (헌법 v1.1.1 기준, 개정 후 v1.2.0으로 재확인)

| 원칙 | 확인 | 결과 |
| --- | --- | --- |
| I 서버 판단 | 관련 글에 비공개 글을 넣을지는 서버의 `visible()` 조건으로만 정함. 대표 사진 허용 형식(/uploads/ 사진)도 서버가 고름. 본문 20만 자 상한과 길이에 비례하는 정규식으로 긴 본문 하나가 서버를 멈추지 못하게 함(검토 반영). 이웃 추가는 기존 서버 API 그대로. 출력은 `esc()`와 DOMPurify(글 속 id 접두어·data-*·class 제거) 뒤 DOM API로만 꾸밈 | 통과 |
| II 설치 없음 | 새 CDN·라이브러리 없음. 공유는 브라우저 Web Share·클립보드만, 아이콘은 코드 안 SVG | 통과 |
| III 서명·POST | 회원 연결·상태 변경 요청 변경 없음 | 해당 없음 |
| IV 데이터 보존 | 스키마 변경 없음, 기존 blog.db로 그대로 동작(회귀 확인) | 통과 |
| V 추적 | 새 BLOG-20~23, NFR-01·03·10, BLOG-01·09, SOC-03 개정을 requirements.md 두 사본·원본 문서에 반영하는 작업 포함 | 통과 |
| VI 한국어·접근성·디자인 | 모든 문구 한국어, 375px 넘침 수정, 다크 모드 색 지정, '동작 줄이기'·포커스·화면 읽기 이름 포함. **디자인 문구 "네오 브루탈리즘 카드 규칙(NFR-01)"은 사용자가 고른 방향과 충돌** → 헌법 개정 v1.2.0(MINOR): "디자인은 NFR-01의 디자인 규칙을 따른다"로 바꾸고 NFR-01 내용을 담백한 카드로 개정 | 개정 후 통과 |

**Phase 1 뒤 재확인**: 계약(contracts/)과 데이터 모델에 새 저장소·새 권한 경로가 없음을 확인. 위반 없음.

## Project Structure

### Documentation (this feature)

```text
specs/004-reading-ui-refresh/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # 조사·결정
├── data-model.md        # 응답 모양 변화(표 변경 없음)
├── quickstart.md        # 점검 순서
├── contracts/
│   ├── posts-api.md     # 목록 thumbnail·글 보기 related 규칙
│   └── reading-ui.md    # 화면 동작 계약(목차·막대·공유·크게 보기·복사)
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
my-blog/
├── server.py                   # THUMB_RE·FENCE_RE·CODE_RE·first_upload_image(), post_dict() 요약, get_post() related 4개 + 대표 사진
├── static/
│   ├── index.html              # style.css?v=19, app.js?v=20
│   ├── app.js                  # renderMd(코드 머리·사진 버튼), postRowHtml, renderPost(읽기 도구·공유·작성자 카드·관련 글),
│   │                           #   jumpTo·buildToc·startReadingTools·copyText·sharePost·openLightbox·copyCode, 라우터에서 정리
│   └── style.css               # 디자인 토큰·카드 규칙 교체, 004 구역(목록·목차·막대·공유·작성자·관련 글·크게 보기·코드)
├── php-auth/public/style.css   # 회원 화면 1px·12px·그림자 없음
├── php-auth/src/auth.php       # style.css?v=4 (캐시 갱신)
└── tests/smoke_reading_ui.py   # 새 스모크 테스트
```

**Structure Decision**: 기존 단일 저장소 구조 그대로. 화면 로직은 app.js 한 파일 안에 "004" 구역으로 모은다.

## Complexity Tracking

해당 없음. (헌법 VI 디자인 문구는 위반으로 두지 않고 개정으로 해결)

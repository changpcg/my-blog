# Feature Specification: 인터넷이 끊겨도 동작 — 화면 라이브러리·글꼴 내장

**Feature Branch**: `007-offline-assets`

**Created**: 2026-10-08

**Status**: Implemented (2026-10-08)

**Input**: User description: "다음 작업 — 인터넷 끊겨도 동작: 화면 라이브러리(marked·DOMPurify·highlight.js)와 Pretendard 글꼴을 CDN 대신 저장소 안에 두고 불러오기"

**관련 요구사항 ID**: NFR-02·NFR-07(개정), 7장 외부 서비스 표 jsDelivr 행(삭제) / 새 ID: NFR-15(화면 라이브러리·글꼴은 저장소 안에서)

**조사 근거**: 지금 블로그 화면은 마크다운 변환(marked)·본문 정리(DOMPurify)·코드 색(highlight.js)·글꼴(Pretendard)을 jsDelivr CDN에서 받는다.
인터넷이 끊기거나 CDN이 막히면(회사·학교 망, CDN 장애) 글 목록·본문이 나오지 않는다(requirements.md 7장 "동작 중, 인터넷이 끊기거나 CDN이 막히면
글 목록·본문이 나오지 않음"). 회원 화면(PHP)도 글꼴을 CDN에서 받는다. 내 컴퓨터에서 쓰는 블로그가 인터넷에 따라 멈추면 안 된다.

## Clarifications

### Session 2026-10-08

- 범위는 사용자가 고른 "인터넷 끊겨도 동작". "알아서 진행"이라 아래 기본값은 Assumptions에 적고 진행한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 인터넷 없이 글을 읽고 쓴다 (Priority: P1)

블로그 주인은 와이파이가 끊긴 상태에서도 내 컴퓨터의 블로그를 열어 글 목록·본문(마크다운·코드 색)을 보고, 글을 쓰고 미리 본다.

**Why this priority**: 사용자가 고른 핵심이고, 지금은 인터넷이 끊기면 블로그의 기본 기능이 멈춘다.

**Independent Test**: 바깥 주소로 가는 요청을 모두 막은 브라우저로 블로그를 열어 목록·본문·코드 색·글쓰기 미리보기·글꼴이 정상인지 본다.

**Acceptance Scenarios**:

1. **Given** 바깥 인터넷이 막힌 상태, **When** 블로그 홈·글 보기를 열면, **Then** 글 목록과 본문(제목·목록·표·코드 색)이 정상으로 보인다.
2. **Given** 같은 상태, **When** 글쓰기에서 마크다운을 쓰면, **Then** 미리보기가 바로 바뀐다.
3. **Given** 같은 상태, **Then** 블로그 글자는 Pretendard 글꼴로 보인다(기기 글꼴로 바뀌지 않음).
4. **Given** 블로그 화면, **Then** 화면이 바깥 주소(CDN)에 요청을 하나도 보내지 않는다(날씨·시세·맛집처럼 바깥 정보를 가져오는 위젯은 제외).

---

### User Story 2 - 회원 화면도 같은 글꼴 (Priority: P2)

방문자는 회원가입·로그인 화면(PHP)에서도 인터넷 CDN 없이 블로그와 같은 글꼴을 본다.

**Why this priority**: 회원 화면은 가끔 쓰고, 글꼴이 없어도 기기 글꼴로 동작은 한다.

**Independent Test**: 바깥 인터넷을 막고 회원 로그인 화면을 열어 글꼴이 블로그 서버에서 오는지, 블로그 서버가 꺼져 있으면 기기 글꼴로 정상 표시되는지 본다.

**Acceptance Scenarios**:

1. **Given** 블로그 서버가 켜져 있으면, **Then** 회원 화면 글꼴은 블로그 서버의 글꼴 파일에서 온다(다른 주소에서도 쓸 수 있게 허용).
2. **Given** 블로그 서버가 꺼져 있으면, **Then** 회원 화면은 기기 한글 글꼴로 정상 표시된다.

---

### User Story 3 - 내장 파일을 믿을 수 있다 (Priority: P2)

관리자는 내장한 라이브러리의 이름·버전·출처·라이선스·파일 확인값(SHA-256)을 한 문서에서 보고, 파일이 바뀌지 않았는지 시험으로 확인한다.

**Why this priority**: 남이 만든 코드를 저장소에 넣으므로 출처와 무결성을 남겨야 한다(헌법 I·II).

**Independent Test**: 시험을 돌려 각 파일의 SHA-256이 안내 문서의 값과 같은지, 라이선스 파일이 함께 있는지 본다.

**Acceptance Scenarios**:

1. **Given** `static/vendor/README.md`, **Then** 라이브러리마다 버전·원래 주소·라이선스·SHA-256이 적혀 있다.
2. **Given** 누가 내장 파일을 고치면, **Then** 시험이 실패한다.

---

### Edge Cases

- 브라우저에 예전 CDN 파일이 캐시돼 있어도? → 새 화면 파일(버전 올림)은 내장 파일만 부른다.
- 내장 파일 주소에 없는 파일·폴더 목록을 요청하면? → 404(폴더 안 목록을 보여 주지 않음).
- 내장 파일은 버전 이름 폴더라 내용이 바뀌지 않음 → 1년 캐시. 404 응답은 캐시하지 않는다.
- 공개 모드에서도 내장 파일은 https·공개 관문 규칙을 그대로 따른다.
- 날씨·시세·맛집·SNS 로그인은 바깥 서비스라 인터넷이 필요하다 → 지금처럼 "불러오지 못함" 안내.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 블로그 화면은 MUST marked 12.0.2·DOMPurify 3.1.6·highlight.js 11.9.0(github·github-dark 색)·Pretendard 1.3.9를 블로그 서버의
  내장 파일(`/vendor/<이름>-<버전>/…`)에서만 불러온다. (새 NFR-15, NFR-02·07 개정)
- **FR-002**: 회원 화면(PHP)은 MUST 글꼴을 블로그 서버의 내장 글꼴에서 불러오고, 못 불러오면 기기 한글 글꼴로 보인다. (NFR-02)
- **FR-003**: 블로그 서버는 MUST 내장 파일에 1년 캐시(내용 불변)와 다른 주소 허용(CORS `*`, 글꼴용)을 붙이되, 오류 응답에는 붙이지 않고, 폴더 목록은
  보여 주지 않는다. (NFR-06 개정)
- **FR-004**: 내장 파일은 MUST 각 라이브러리의 라이선스 파일과 함께 두고, `static/vendor/README.md`에 버전·출처·라이선스·SHA-256을 적는다. (새 NFR-15)
- **FR-005**: 시험은 MUST 화면·회원 화면 코드에 CDN 주소가 남지 않았는지, 화면이 부르는 파일이 모두 200인지, 내장 파일 SHA-256이 문서와 같은지
  확인한다.
- **FR-006**: 헌법 원칙 II의 "jsDelivr CDN" 문구를 "저장소 안 내장 파일"로 바꾼다(MINOR 1.3.0). (헌법 Governance)
- **FR-007**: 구현 후 MUST requirements.md 두 사본과 원본 문서에 NFR-15를 더하고 NFR-02·06·07, 7장 jsDelivr 행·범위 문장을 고친다. (헌법 V)

### Key Entities

- **내장 파일(static/vendor/)**: `marked-12.0.2/`, `dompurify-3.1.6/`, `highlight-11.9.0/`(styles 포함), `pretendard-1.3.9/`(가변 글꼴 woff2 1개 + CSS),
  각 폴더의 라이선스, `README.md`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 바깥 요청을 모두 막은 브라우저에서 블로그 홈·글 보기·글쓰기 미리보기가 100% 정상(마크다운·코드 색·Pretendard).
- **SC-002**: 블로그 화면 첫 접속에서 CDN 요청 0건.
- **SC-003**: 내장 파일 SHA-256 100% 일치, 라이선스 파일 4개 모두 있음.
- **SC-004**: 기존 스모크 테스트(001~006)와 화면 점검이 모두 통과한다.

## Assumptions

- 글꼴은 가변 글꼴 파일 하나(약 2MB, 모든 굵기)로 바꾼다. 지금 CDN은 굵기별 파일(굵기 하나에 약 750KB)을 받으므로 첫 접속 용량이 오히려 줄거나 같다.
- 내장 파일은 npm 레지스트리에서 받은 공식 패키지(설치 시 무결성 확인)의 배포 파일을 그대로 쓴다. 버전을 올릴 때는 README의 절차대로 파일·확인값을
  함께 바꾼다.
- 바깥 정보를 가져오는 기능(날씨·시세·맛집·SNS 로그인·지도 링크)은 범위 밖이다.

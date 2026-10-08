# Contract: 글 화면 동작 (static/app.js · style.css)

관련: FR-001~FR-016 · BLOG-20~23, NFR-01, NFR-03, NFR-04, NFR-10

## 디자인 값 (style.css `:root`)

| 변수 | 라이트 | 다크 | 쓰는 곳 |
| --- | --- | --- | --- |
| `--radius` | 12px | 12px | 카드·위젯·목차·작성자 카드·이전/다음 |
| `--line` | #ebebea | #2c2c2c | 모든 1px 선 |
| `--line-strong` | #d6d6d3 | #444444 | 마우스를 올린 카드·버튼 선 |
| `--shadow-soft` | 0 2px 12px rgba(0,0,0,.05) | 0 2px 12px rgba(0,0,0,.35) | 마우스를 올린 카드, 맨 위로 버튼 |
| `--shadow-pop` | 0 10px 30px rgba(0,0,0,.10) | 0 10px 30px rgba(0,0,0,.55) | 내 메뉴(떠 있는 메뉴) |

새 요소의 작은 글자는 `--bg-soft` 위에서도 읽히게 `--text-2`(라이트 5.35:1·다크 7.6:1)를 쓴다(목차 소제목·코드 언어 이름). 복사 완료 색은
라이트 #157347(5.9:1)·다크 #74d39b. 맨 위로 버튼은 모든 폭에서 44px. 회원 화면 입력 칸 포커스는 강조색 2px(1px 선 + 1px 링).

금지: 오프셋 그림자(`Npx Npx 0`), 2px 이상 카드 테두리, 마우스를 올렸을 때 `transform` 이동. 회원 화면(PHP)도 같은 값(`--line` #ebebea 포함).

## 글 목록 한 줄 (`postRowHtml`)

```html
<a class="post-row has-thumb" href="#/post/ID">
  <div class="post-text"><div class="labels">…</div><h2 class="post-title">…</h2><p class="post-excerpt">…</p></div>
  <div class="meta post-meta">블로그 · 날짜 · 댓글 · 조회 · ♥</div>
  <img class="post-thumb" src="/uploads/…" alt="" width="120" height="120" loading="lazy" decoding="async">
</a>
```

- 사진 크기: PC 120×120(둥글기 10px), 600px 이하 84×84. 영역: PC `"text thumb" / "meta thumb"`, 600px 이하 `"text thumb" / "meta meta"`.
- 제목·요약 2줄 말줄임. 사진을 못 불러오면 `img`와 `has-thumb`를 지운다.

## 글 보기 순서

작은 블로그 배너 → 종류·카테고리 → 제목(`h1 tabindex=-1`) → 글쓴이·날짜·조회·**N분 읽기** → (FAQ면 'A 답변') → **목차** → 본문 →
태그 → **공감 + 공유하기** → (공유 실패 칸) → **작성자 카드** → **관련 글 사진 카드** → **이전·다음 글** → 댓글

## 목차

- 본문 `h2`·`h3`(빈 글자 제외) 2개 이상일 때만 `<details class="toc">`, 요약줄 "목차 N". 900px 이하는 닫힌 채, 넓으면 열린 채.
- 항목: `<a href="#/post/ID" data-toc="순번">`. 클릭 → 기본 동작 막음 → 소제목 포커스(`tabindex=-1`, preventScroll) →
  `scrollIntoView({behavior: 동작 줄이기 ? 'auto' : 'smooth', block: 'start'})`. `scroll-margin-top: 124px`.
- `location.hash`는 그대로. Ctrl·Cmd·Shift·Alt·가운데 클릭은 막지 않음(새 탭에 같은 글). 용어 사전 색인(`data-jump`)도 같은 규칙.

## 진행 막대 · 맨 위로

- `.read-progress`(fixed, top 0, 3px, z 30, `aria-hidden`) 안 `i`의 `scaleX(진행률)`.
- `.to-top`(fixed 오른쪽 아래, 44px, `aria-label="맨 위로"`): `scrollY ≥ innerHeight`일 때만 보임. 누르면 맨 위(동작 줄이기면 즉시) +
  제목 포커스.
- 라우터 `render()` 시작 때 `routeSeq += 1`과 `stopReadingTools()`: 리스너 제거, 둘 다 `hidden`. `renderPost()`는 응답을 기다린 뒤
  `routeSeq`가 바뀌었으면(그사이 다른 화면으로 감) 아무것도 그리지 않는다.

## 공유하기

1. `navigator.share({title, url: location.href})` (있고 `canShare` 통과) — 사용자가 닫으면(AbortError) 아무것도 안 함
2. 없거나 실패 → `copyText(url)` 성공 → 토스트 "주소를 복사했어요."
3. 복사 실패 → `#shareSlot`에 읽기 전용 주소 칸(포커스·전체 선택) + "주소를 복사하지 못했어요. 직접 복사해 주세요."

`copyText`: 보안 연결이면 `navigator.clipboard.writeText`, 아니면(또는 실패하면) 숨은 textarea + `execCommand('copy')`, 포커스 되돌림.

## 작성자 카드

`section.author-card[aria-label=글쓴이]`: 사진(링크, 탭 순서 제외) · 블로그 이름(링크) · "닉네임 · 글 N개 · 이웃 <span.nb-count>N</span>명" ·
소개 · [이웃 추가 `data-nb`(내 블로그면 없음)] [블로그 가기]. 이웃 버튼은 배너 버튼과 같은 `bindNeighborButtons`로 함께 바뀜.

## 관련 글 · 이전/다음

- `section.related` 제목 "<em>카테고리</em> 카테고리의 다른 <종류> 글", `.related-grid` PC 4칸·900px 이하 2칸. 카드: 4:3 사진(없거나 깨지면 종류
  아이콘) · 제목 2줄 · 날짜, 비공개면 '비공개' 표시.
- `nav.prevnext[aria-label="이전 글과 다음 글"]`: 있을 때만. "‹ 이전 글" 왼쪽, "다음 글 ›" 오른쪽, 600px 이하 위아래.

## 본문 정리 (renderMd, 모든 본문·FAQ 답·글쓰기 미리보기 공통)

1. `DOMPurify.sanitize(html, { SANITIZE_NAMED_PROPS: true, ALLOW_DATA_ATTR: false })` — 글 속 `id`·`name`은 `user-content-` 접두어(화면의
   `#likeBtn`·`#comments`·`#shareUrl`·`#srStatus` 등과 겹치지 않음), `data-*` 속성 없음(`data-nb`·`data-jump` 흉내 불가)
2. 글쓴이가 붙인 `class`는 모두 지움. `code`의 `language-*`만 남김 → `.code-copy`·`.code-block`·`.img-zoom`·`.sr-only` 등을 흉내 낼 수 없음
3. `pre > code` 칸은 `pre`·`code`의 `style`·`hidden`을 지운 뒤 코드 머리를 붙임 → 보이는 코드와 복사되는 코드가 같음
4. 그다음 화면이 붙이는 부품: 코드 머리·복사 버튼, 사진 버튼, 바깥 링크 새 창, 첨부 파일 카드

## 사진 크게 보기

- `renderMd()`: 링크 안이 아닌 `img` → `<button type=button class="img-zoom" aria-label="사진 크게 보기[: 대체 글]">` 안으로.
- 클릭 위임 → `dialog.lightbox`(한 번 만들어 재사용) `showModal()`, 큰 사진 `src`=원래 사진, 설명=대체 글, 포커스=닫기 버튼, `html.lb-open`.
- 닫기: Esc(기본), 사진 밖 아무 곳 클릭, 닫기 버튼 → `close` 이벤트에서 `lb-open` 제거·원래 버튼 포커스(아직 화면에 있으면).
- 화면 이동 시 열려 있으면 닫음.

## 코드 블록

```html
<div class="code-block">
  <div class="code-head"><span class="code-lang">Python</span><button type="button" class="code-copy" aria-label="Python 코드 복사">복사</button></div>
  <pre><code class="hljs language-python">…</code></pre>
</div>
```

- 언어 이름: 강조 전 `language-xxx` → 소문자로 `CODE_LANG` 표의 **자기 항목만** 찾음(`constructor`·`__proto__` 같은 이름도 안전),
  표에 없으면 글쓴이가 적은 그대로(대소문자 유지), 없으면 '코드'.
- 복사 성공: 버튼 '복사했어요' + `.done`(1.6초) + `#srStatus`(role=status) "코드를 복사했어요." / 실패: 토스트 "복사하지 못했어요. 코드를 직접 골라 복사해 주세요."

## 넘침

- 900px 이하 `.layout { grid-template-columns: minmax(0, 1fr) }`.
- 긴 코드: `pre`(또는 highlight.js의 `code.hljs`) 안에서만 가로 스크롤. 표: `display:block; overflow-x:auto` + 칸 `overflow-wrap: break-word`.

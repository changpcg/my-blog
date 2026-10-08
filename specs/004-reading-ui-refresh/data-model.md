# Data Model: 담백한 디자인과 읽기 좋은 글 화면

**DB 변경 없음** — blog.db·회원 DB의 표와 칸을 더하거나 바꾸지 않는다(헌법 IV). 바뀌는 것은 API 응답 모양과 화면에서만 쓰는 값이다.

## 1. 글 목록 항목 (`GET /api/posts`의 `posts[]`)

| 필드 | 바뀜 | 규칙 |
| --- | --- | --- |
| `thumbnail` | 규칙 변경 | 본문에서 코드 블록을 뺀 뒤, 마크다운 사진 또는 HTML `<img src>` 중 `/uploads/<32자리 16진수>.(png\|jpg\|gif\|webp)`인 첫 번째. 없으면 `null`. 외부 주소 사진은 쓰지 않음 |
| `excerpt` | 규칙 보완 | 기존(코드 블록·마크다운 기호 제거, 160자)에 더해 HTML 태그를 뺌. 인라인 코드 글자는 남김 |
| 나머지 | 그대로 | `id, title, type, category, tags, is_public, views, created_at, author_*, comment_count, like_count` |

`full=1`(자주 묻는 질문 목록)일 때는 지금처럼 `content`를 주고 `thumbnail`·`excerpt`는 없다.

## 2. 글 보기 (`GET /api/posts/<id>`)

| 필드 | 바뀜 | 모양 |
| --- | --- | --- |
| `related[]` | 변경 | 최대 **4개**(전에는 5개), 같은 블로그·종류·카테고리·볼 수 있는 글, `created_at DESC, id DESC` |
| `related[].id`·`title`·`created_at` | 그대로 | |
| `related[].type` | 추가 | 사진이 없을 때 종류 아이콘 |
| `related[].is_public` | 추가(bool) | 비공개 표시(글쓴이·관리자에게만 오는 글) |
| `related[].thumbnail` | 추가 | 1의 규칙과 같음, 없으면 `null` |
| `prev`·`next` | 그대로 | `{id, title}` 또는 `null` |

## 3. 화면에서만 만드는 값

| 값 | 만드는 곳 | 규칙 |
| --- | --- | --- |
| 읽는 시간 | `readMinutes(#postContent)` | 공백을 뺀 글자 수 ÷ 500, 올림, 최소 1 → "N분 읽기" |
| 목차 항목 | `buildToc()` | 본문의 `h2`·`h3`(빈 글자 제외) 순서대로, 2개 미만이면 목차 상자 삭제 |
| 진행률 | `startReadingTools()` | 0~1, 본문 기준(D6) |
| 코드 언어 이름 | `renderMd()` | 강조 전 `language-xxx` → `CODE_LANG` 표, 없으면 '코드' |

## 4. 상태 변화

- 글 보기 진입: 읽기 도구 시작(막대 보임, 스크롤 리스너 등록) → 다른 화면으로 이동(라우터 `render()` 시작): 리스너 제거·막대와 맨 위로 숨김,
  열린 사진 크게 보기 닫음.
- 사진 크게 보기: 닫힘 → (사진 버튼 클릭·Enter) 열림(`html.lb-open`, 포커스는 닫기 버튼) → (Esc·바깥·닫기) 닫힘(포커스는 원래 사진 버튼).
- 코드 복사 버튼: '복사' → 성공 시 '복사했어요'(1.6초) → '복사'.

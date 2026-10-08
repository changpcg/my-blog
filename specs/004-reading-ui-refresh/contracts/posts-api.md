# Contract: 글 목록 대표 사진 · 관련 글 (블로그 서버)

관련: FR-005, FR-006, FR-013 · BLOG-20, BLOG-22, BLOG-09, SEC-12

## `GET /api/posts` — 목록 항목의 `thumbnail`

대표 사진은 서버가 정한다. 화면은 받은 주소를 그대로 보여 주기만 한다.

| 본문 | `thumbnail` |
| --- | --- |
| `![사진](/uploads/<hex32>.png)` | `/uploads/<hex32>.png` |
| `![사진]( /uploads/<hex32>.jpg "제목" )` (띄어쓰기·제목) | `/uploads/<hex32>.jpg` |
| `![사진](</uploads/<hex32>.gif>)` (꺾쇠) | `/uploads/<hex32>.gif` |
| `<img alt="x" src="/uploads/<hex32>.webp">`, `<IMG SRC='…'>` | 그 주소 |
| `![외부](https://…)` 다음에 `![올린](/uploads/<hex32>.png)` | 올린 사진 주소 |
| 외부 주소 사진만 | `null` |
| `[📎 파일 (1KB)](/uploads/<hex32>.pdf)`·`[링크](/uploads/<hex32>.png)`(느낌표 없음) | `null` |
| ``` · ~~~ 코드 블록(줄 맨 앞에서 열고 닫음)·인라인 코드(한 겹·두 겹)·HTML 주석 `<!-- -->` 안의 사진 문법 | `null` |
| 문장 중간의 ``` 기호 뒤에 있는 사진 (코드 블록이 아님) | 그 사진 주소 |
| `<img data-src="/uploads/…">` | `null` |
| `/uploads/../../x.png` 같은 형식 밖 이름 | `null` |

`excerpt`에는 HTML 태그가 남지 않는다(`<img …>` 등 제거). 인라인 코드 안의 `<글자>`는 태그로 보지 않고 남긴다.

**처리 시간**: 대표 사진·요약 정규식은 모두 다음 구분 문자(`[ ] < > ( )`·줄바꿈)에서 멈추게 써서 본문 길이에 비례한다(1MB 악성 본문 ≈ 0.03~0.2초).
고치기 전 식(`[^>]*?`, `[^\]]*`)은 `"<img " × 2만`(10만 자) 본문 하나로 목록 응답 16초, 그동안 다른 요청도 대기였다.

## `POST /api/posts`, `PUT /api/posts/<id>` — 본문 길이

- 본문(`content`) 200,000자 초과 → `400 {"error": "본문은 20만 자까지 쓸 수 있어요. 글을 나눠서 올려 주세요."}` (저장 안 함)

## `GET /api/posts/<id>` — `related`

```json
"related": [
  {"id": 14, "title": "…", "created_at": "2026-10-06T10:00:00", "type": "insight", "is_public": false,
   "thumbnail": "/uploads/<hex32>.png"},
  {"id": 12, "title": "…", "created_at": "2026-10-05T10:00:00", "type": "insight", "is_public": true, "thumbnail": null}
]
```

- 조건: `p.category = 지금 글의 카테고리`, `p.id != 지금 글`, 같은 글쓴이·같은 종류, **지금 요청한 사람이 볼 수 있는 글**(`visible()`:
  방문자는 공개 글만, 회원은 공개 + 내 글, 관리자는 모두).
- 순서·개수: `created_at DESC, id DESC`, 최대 4개.
- 필드는 위 여섯 개뿐(본문 `content`는 주지 않음).

## 확인 (tests/smoke_reading_ui.py)

1. 위 표의 대표 사진 규칙(띄어쓰기·HTML·외부·첨부·코드 속)
2. 요약에 HTML 태그 없음
3. 관련 글 ≤ 4, 최신순, 지금 글·다른 카테고리·다른 종류 제외, 필드 집합 일치, 관리자에게 비공개 글 포함
4. 방문자에게 비공개 글은 관련 글·목록 모두에 없음
5. 20만 1자 본문은 400, 같은 기호를 되풀이한 20만 자 본문 3개가 있어도 목록 2초 안

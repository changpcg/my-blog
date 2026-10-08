# Contract: 글 저장의 대표 사진 (`cover`)

## `POST /api/posts`, `PUT /api/posts/<id>`

요청 본문에 `cover` (없으면 `''`):

| 값 | 결과 |
| --- | --- |
| `""` | 저장, 자동 |
| `"none"` | 저장, 목록 사진 없음 |
| 본문 속 업로드 사진 주소 | 저장 |
| 본문에 없는 업로드 주소, 외부 주소, 형식 밖 문자열, 문자열이 아닌 값 | `400 {"error": "대표 사진은 본문에 있는 사진 중에서 골라 주세요."}` |

## `GET /api/posts`

`thumbnail` = data-model의 `post_thumbnail` 결과.

## `GET /api/posts/<id>`

`cover` 값 그대로(편집 화면이 창을 채울 때), `related[].thumbnail`은 `post_thumbnail`.

## 확인 (tests/smoke_editor_cover.py)

1. 두 번째 사진을 고르면 목록·관련 글 대표 사진이 그 사진
2. `none`이면 목록 `thumbnail` null
3. 본문에 없는 사진·외부 주소·임의 문자열은 400, 글은 저장 안 됨
4. 고른 사진을 본문에서 지우고 저장하면 자동으로 돌아감
5. 예전 글(칸 없음 → 기본 `''`)은 자동

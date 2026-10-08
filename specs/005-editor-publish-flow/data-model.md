# Data Model: 넓은 글쓰기 화면과 발행 설정 창

## posts (blog.db) — 칸 추가

| 칸 | 형식 | 기본 | 규칙 |
| --- | --- | --- | --- |
| `cover` | TEXT NOT NULL | `''` | `''` 자동(본문 첫 업로드 사진), `'none'` 사진 없이, `/uploads/<32 hex>.(png\|jpg\|gif\|webp)` 고른 사진(저장할 때 본문에 있어야 함) |

init_db가 칸이 없을 때만 `ALTER TABLE posts ADD COLUMN cover TEXT NOT NULL DEFAULT ''`.

## 대표 사진 계산 (`post_thumbnail(content, cover)`)

1. `cover == 'none'` → 없음
2. `cover`가 주소이고 `upload_images(content)`에 있으면 → 그 주소
3. 그 밖 → `first_upload_image(content)` (004 규칙)

목록(`GET /api/posts`)의 `thumbnail`, 글 보기 `related[].thumbnail`에 같은 계산을 쓴다. 글 보기(`GET /api/posts/<id>`, full)는 `cover` 값을 그대로 준다.

## 화면 상태 (renderEditor)

- `initial` = 열었을 때의 {type, title, content, category, tags, is_public, cover}, `dirty()` = 지금 값과 다르면 true
- 발행 창 값은 창을 열 때 편집 상태에서 채우고, 창의 확인으로 편집 상태에 반영 후 API 호출

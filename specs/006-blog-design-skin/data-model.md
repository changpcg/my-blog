# Data Model: 블로그 꾸미기

## users (칸 추가, init_db에서 없을 때만)

| 칸 | 형식 | 기본값 | 규칙 |
| --- | --- | --- | --- |
| `skin` | TEXT NOT NULL | `'coral'` | `coral·blue·green·teal·purple·pink·mustard·ink` 중 하나. 그 밖의 값이 DB에 있어도 응답은 `coral` |
| `hidden_widgets` | TEXT NOT NULL | `'[]'` | JSON 문자열 목록, 이름은 `room·types·popular·tags·comments·stats`. 읽을 때 모르는 이름·형식 오류는 버림 |

`BLOG_FIELDS`에 두 칸을 넣어 로그인 사용자(`blog.user`)·블로그 응답·이웃 목록에 같이 실린다. `blog_dict()`가 `hidden_widgets`를 목록으로 바꾼다.

## 응답 모양 변화

- `GET /api/blogs/<아이디>`: `skin`, `hidden_widgets`, `popular`(최대 5개 `{id, title, type, views, thumbnail, created_at}`) 추가.
  `hidden_widgets`에 있으면 `popular`·`tags`·`recent_comments` = `[]`, `stats` = `null`.
- `GET /api/blog`: `popular`(최대 5개, 위 항목 + `author_username`, `blog_title`) 추가.

## 상태 변화

색·항목은 저장하면 바로 다음 응답부터 적용(캐시 없음).

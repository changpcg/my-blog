# Contract: 블로그 꾸미기 (API · 화면)

관련: FR-001~FR-008 · BLOG-26·27, BLOG-01·02·17, NFR-01·04

## PUT /api/me (로그인 필요, 본인 블로그)

| 보낸 값 | 결과 |
| --- | --- |
| `{"skin": "blue"}` | 200 `{"ok": true}`, 저장 |
| `{"skin": "red"}` · `{"skin": 1}` · `{"skin": ["blue"]}` · `{"skin": null}` | 400 "목록에 있는 색만 고를 수 있어요." (저장 안 함) |
| `{"hidden_widgets": ["stats", "room", "stats"]}` | 200, `["stats", "room"]`으로 저장(중복 제거, 보낸 순서) |
| `{"hidden_widgets": ["profile"]}` · `{"hidden_widgets": "stats"}` · `{"hidden_widgets": [1]}` | 400 "사이드바 항목을 다시 골라 주세요." |
| `{"hidden_widgets": []}` | 200, 모두 보임 |
| 로그인 안 함 | 401 |

같은 요청 안에서 하나라도 틀리면 아무것도 저장하지 않는다(한 트랜잭션).

## GET /api/blogs/<아이디>

```json
{ "skin": "blue", "hidden_widgets": ["stats"],
  "popular": [{"id": 3, "title": "…", "type": "insight", "views": 42, "thumbnail": "/uploads/….png", "created_at": "…"}],
  "tags": [...], "recent_comments": [...], "stats": null, "type_counts": [...] }
```

- `popular`: `p.author_id = 블로그 AND p.is_public = 1 AND p.views >= 1 ORDER BY p.views DESC, p.created_at DESC, p.id DESC LIMIT 5`
  (관리자·주인이 봐도 같음). `thumbnail`은 `post_thumbnail(content, cover)`.
- 끈 항목: `popular`·`tags`·`recent_comments` → `[]`, `stats` → `null`. `types`를 꺼도 `type_counts`는 보냄.

## GET /api/blog

`popular`: 사이트 전체 공개 글(글쓴이가 있는 글), 같은 정렬·5개, 항목에 `author_username`·`blog_title` 추가.

## 확인 목록 (tests/smoke_blog_design.py)

1. 색 저장 → 블로그 응답 `skin`, 로그인 사용자 `blog.user.skin`
2. 틀린 색·틀린 항목 → 400, 그 요청의 다른 값도 저장 안 됨
3. 인기 글: 조회수 순·같으면 최근·5개·조회수 0 제외·비공개 제외(관리자로 봐도)
4. 끈 항목 자료 빠짐, `types`는 `type_counts` 유지
5. 사이트 인기 글: 여러 블로그 섞임, 블로그 이름 포함, 비공개 제외
6. 예전 DB(칸 없음)로 켜면 칸이 생기고 `coral`·`[]`

## 화면

- `setSkin(name)`: `coral`·빈 값·모르는 이름이면 `<html>`의 `data-skin`을 지우고, 아니면 넣음.
- `render()`: 블로그(`#/@…`)·글(`#/post/…`)이 아니면 그리기 전에 `setSkin('')`. `renderBlog`·`renderPost`는 응답 뒤 `routeSeq`가 같을 때만
  그리고 `setSkin(b.skin)`.
- 사이드바(블로그): 프로필 → 카테고리 → 글 종류(끄기 가능) → 인기 글 → 태그 → 최근 댓글 → 방문자. 항목이 비었거나 끈 항목이면 칸 없음.
- 사이드바(블로그 홈): 내 블로그 → 인기 글 → 인기 태그 → 최근 댓글 → 전체 방문자.
- 인기 글 한 줄: `<a href="#/post/ID"><span class="pop-n">순위</span><span class="pop-t"><b>제목(2줄)</b><small>(블로그 이름 ·) 조회 N</small></span>
  <img class="pop-thumb" …(있으면, 48px)></a>`. 사진 오류 → 사진만 지움.
- 배너: `room`을 끄면 `has-room`·미니룸 없이 그림.
- 꾸미기 탭(`#/manage/design`): 색 라디오 8개(`name=skin`) + 미리보기, 항목 체크박스 6개, '저장'(바뀐 것이 있을 때만). 저장 뒤 `loadBlog()`, 토스트
  "꾸미기를 저장했어요.", '내 블로그에서 보기 →' 링크.
- `--on-accent`: 라이트 #fff, 다크 #161616. 강조색 바탕 위 글자는 모두 이 변수.

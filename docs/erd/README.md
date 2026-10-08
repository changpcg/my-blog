# ERD (데이터 구조)

블로그는 SQLite DB 두 개를 씁니다. 이 폴더에는 두 DB의 구조를 PostgreSQL 문법으로 옮긴 SQL과 관계도가 있습니다.

| 파일 | 실제 DB | 만드는 코드 | 테이블 |
|---|---|---|---|
| [`blog-db.sql`](blog-db.sql) | `blog.db` (블로그 서버) | `server.py`의 `init_db()` | 12개, 관계 12개 |
| [`member-db.sql`](member-db.sql) | `php-auth/db/sqlite.db` (회원 서버) | `php-auth/src/db.php`의 `db()` | 6개, 관계 1개 |

- 두 DB는 블로그 `users.auth_uid` → 회원 서버 `users.id`로 이어집니다(서로 다른 파일이라 FK 제약은 없음).
- 날짜·시각은 SQLite처럼 문자열 또는 epoch 초로 두었고, 정해진 값 목록(글 종류·대표 색 등)은 앱이 검사하므로 SQL의 `--` 설명에 적었습니다.
- **논리 FK**: `blog_visits.blog_id`, `comment_pw_fails.comment_id`는 실제 DB에 FK 제약이 없고 앱이 지킵니다(회원·댓글을 지울 때 함께 지우거나 15분 뒤 지움).
- 테이블·컬럼 이름과 순서는 실제 DB와 같습니다(2026-10-08에 두 DB를 새로 만들어 비교, PostgreSQL 16에서 두 SQL 실행 확인).

## Crowfoot 문서

[Crowfoot](https://crowfoot.java21.net/)(무료 온라인 ERD 툴)의 **나만의 블로그** 워크스페이스에 같은 내용의 문서가 있습니다.

- 나만의 블로그 — 블로그 DB (blog.db)
- 나만의 블로그 — 회원 DB (php-auth)

다시 만들 때: 워크스페이스 ERD 탭 → **SQL 가져오기** → 데이터베이스 종류 **PostgreSQL** → SQL 파일 내용을 붙여 넣고 미리보기(테이블·관계 수 확인) → 문서 만들기.

Crowfoot은 가져올 때 FK 컬럼마다 인덱스를 더합니다(`idx_posts_author_id`, `idx_comments_post_id` 등 8개). 이 인덱스들은 **아직 실제 blog.db에는 없고**, 글·댓글이 많아지면 필요한 개선 후보입니다.

DB 구조를 바꾸면(`init_db()`·`db()`에 칸·표 추가) 이 폴더의 SQL과 아래 관계도, Crowfoot 문서를 함께 고칩니다.

## 블로그 DB 관계도

```mermaid
erDiagram
    users ||--o{ posts : "글쓴이"
    users |o--o{ comments : "회원 댓글"
    posts ||--o{ comments : "댓글"
    comments |o--o{ comments : "답글"
    posts ||--o{ likes : "공감"
    users ||--o{ likes : "공감한 회원"
    users ||--o{ neighbors : "추가한 회원"
    users ||--o{ neighbors : "이웃 블로그"
    users ||--o{ sessions : "로그인 세션"
    users |o--o{ files : "올린 파일"
    users ||--o{ blog_visits : "블로그별 방문(논리 FK)"
    comments ||--o{ comment_pw_fails : "비밀번호 틀린 기록(논리 FK)"

    users {
        BIGINT id PK "회원 번호"
        TEXT username UK "아이디"
        TEXT nickname "닉네임"
        TEXT password_hash "비밀번호 해시"
        TEXT role "역할 admin·member"
        TEXT created_at "가입 시각"
        TEXT watchlist "관심 종목"
        BIGINT auth_uid UK "회원 서버 회원 번호"
        TEXT room_bg "미니룸 배경"
        TEXT room_char "미니룸 캐릭터"
        TEXT skin "대표 색"
        TEXT hidden_widgets "숨긴 사이드바 항목"
        TEXT auth_joined "회원 서버 가입 시각"
        BIGINT auth_nick_at "닉네임 동기화 시각"
        TEXT blog_title "블로그 이름"
        TEXT blog_desc "블로그 소개"
        TEXT avatar "프로필 사진"
        TEXT categories "카테고리 목록"
    }
    posts {
        BIGINT id PK "글 번호"
        TEXT title "제목"
        TEXT content "본문"
        TEXT category "카테고리"
        TEXT tags "태그"
        INTEGER is_public "공개 여부"
        BIGINT views "조회수"
        TEXT created_at "작성 시각"
        TEXT updated_at "수정 시각"
        TEXT type "글 종류"
        BIGINT author_id FK "글쓴이"
        TEXT cover "대표 사진"
    }
    comments {
        BIGINT id PK "댓글 번호"
        BIGINT post_id FK "글 번호"
        TEXT name "이름"
        TEXT password_hash "삭제 비밀번호 해시"
        TEXT content "내용"
        TEXT created_at "작성 시각"
        BIGINT user_id FK "회원 번호"
        BIGINT parent_id FK "부모 댓글 번호"
        INTEGER deleted "삭제 표시"
    }
    likes {
        BIGINT post_id PK, FK "글 번호"
        BIGINT user_id PK, FK "공감한 회원"
        TEXT created_at "공감한 시각"
    }
    neighbors {
        BIGINT user_id PK, FK "추가한 회원"
        BIGINT blog_id PK, FK "이웃 블로그"
        TEXT created_at "추가한 시각"
    }
    sessions {
        TEXT token PK "세션 토큰"
        BIGINT user_id FK "회원 번호"
        DOUBLE expires "만료 시각"
    }
    files {
        TEXT stored_name PK "저장 이름"
        TEXT original_name "원래 파일 이름"
        BIGINT size "크기"
        BIGINT user_id FK "올린 회원"
        TEXT created_at "올린 시각"
    }
    blog_visits {
        TEXT day PK "날짜"
        BIGINT blog_id PK, FK "블로그 주인"
        TEXT visitor PK "방문자"
    }
    visits {
        TEXT day PK "날짜"
        TEXT visitor PK "방문자"
    }
    comment_pw_fails {
        BIGINT comment_id FK "댓글 번호"
        TEXT ip "IP"
        BIGINT at "틀린 시각"
    }
    settings {
        TEXT key PK "설정 이름"
        TEXT value "값"
    }
    sso_nonces {
        TEXT nonce PK "입장권 번호"
        BIGINT expires "만료 시각"
    }
```

## 회원 DB 관계도

```mermaid
erDiagram
    users ||--o{ social_accounts : "SNS 연결"

    users {
        BIGINT id PK "회원 번호"
        TEXT username UK "아이디(대소문자 구분 없음)"
        TEXT password_hash "비밀번호 해시"
        TEXT nickname "닉네임"
        TEXT bio "자기소개"
        TEXT created_at "가입 시각"
        INTEGER session_ver "세션 버전"
        BIGINT nickname_at "닉네임 바꾼 시각"
    }
    social_accounts {
        TEXT provider PK "SNS 종류"
        TEXT provider_uid PK "SNS 회원 번호"
        BIGINT user_id FK "회원 번호"
        TEXT created_at "연결한 시각"
    }
    login_attempts {
        BIGINT id PK "번호"
        TEXT username "아이디"
        TEXT ip "IP"
        BIGINT created_at "시각"
    }
    signup_log {
        BIGINT id PK "번호"
        TEXT ip "IP"
        TEXT kind "결과"
        BIGINT created_at "시각"
    }
    sso_used_nonces {
        TEXT nonce PK "표 번호"
        BIGINT expires "만료 시각"
    }
    bridge_cache {
        TEXT key PK "항목"
        TEXT value "값"
        BIGINT fetched_at "가져온 시각"
    }
```

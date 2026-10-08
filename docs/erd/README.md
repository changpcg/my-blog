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

| 문서 | 테이블 | 요구사항 · 그룹 | 배포한 DB |
|---|---|---|---|
| 나만의 블로그 — 블로그 DB (blog.db) | 12개, 관계 12개 | 13개(테이블 11 + 문서 전체 2) · 5개 | PostgreSQL #1 |
| 나만의 블로그 — 회원 DB (php-auth) | 6개, 관계 1개 | 6개 · 3개 | PostgreSQL #2 |

Crowfoot은 SQL을 가져올 때 FK 컬럼마다 인덱스를 더합니다(`idx_posts_author_id`, `idx_comments_post_id` 등 8개). 같은 이름의 인덱스 8개를 2026-10-08부터 블로그가 켤 때 실제 blog.db에도 만듭니다(`server.py`의 `FK_INDEXES`, 요구사항 NFR-18).

### 요구사항과 그룹

요구사항 제목 앞에 [requirements.md](../../requirements.md)의 ID를 붙였습니다(Crowfoot 번호 REQ-001…은 문서마다 따로 매김). 모든 테이블이 근거 요구사항에 연결돼 있고, 테이블 그룹은 요구사항의 도메인을 따릅니다. 업무 규칙은 Crowfoot의 각 요구사항 내용에 한 줄씩 적었습니다.

| 문서 | 그룹 | 요구사항 | 테이블 |
|---|---|---|---|
| 블로그 DB | 회원·블로그 | BLOG-02 회원마다 개인 블로그 | `users` |
| 블로그 DB | 회원·블로그 | AUTH-08·11 블로그 로그인 2주 유지 | `sessions` |
| 블로그 DB | 회원·블로그 | SEC-07 입장권 위조·재사용 막기 | `sso_nonces` |
| 블로그 DB | 글 | BLOG-05 마크다운 글쓰기 | `posts` |
| 블로그 DB | 글 | BLOG-06 사진과 파일 올리기 | `files` |
| 블로그 DB | 댓글·소통 | BLOG-08·SOC-01 댓글과 답글 | `comments` |
| 블로그 DB | 댓글·소통 | SEC-03 댓글 비밀번호 틀림 잠금 | `comment_pw_fails` |
| 블로그 DB | 댓글·소통 | SOC-02 공감 | `likes` |
| 블로그 DB | 댓글·소통 | SOC-03 이웃 | `neighbors` |
| 블로그 DB | 방문 통계 | BLOG-11 방문자 수 | `blog_visits`, `visits` |
| 블로그 DB | 사이트 설정 | BLOG-16 사이트 설정 | `settings` |
| 블로그 DB | (문서 전체) | NFR-08 데이터 보존(표·칸은 더하기만), NFR-18 연결 칸(FK) 인덱스 | — |
| 회원 DB | 회원 | AUTH-01·05 아이디·비밀번호 가입·로그인 | `users` |
| 회원 DB | 회원 | AUTH-06·07 SNS 가입·로그인·연결 | `social_accounts` |
| 회원 DB | 보안 | SEC-03 로그인 무차별 대입 막기 | `login_attempts` |
| 회원 DB | 보안 | SEC-14 자동·대량 가입 막기 | `signup_log` |
| 회원 DB | 보안 | AUTH-13 함께 로그아웃(1회용 표) | `sso_used_nonces` |
| 회원 DB | 연동 | AUTH-14 블로그의 회원가입 허용 따르기 | `bridge_cache` |

### PostgreSQL 배포 (2026-10-08)

- Crowfoot이 내어 주는 PostgreSQL DB 두 개(커넥션 'PostgreSQL #1'·'PostgreSQL #2')에 두 문서를 배포했습니다(블로그 DB 111문장·회원 DB 42문장, 실패 0). 빈 DB에 구조(표·관계·인덱스·설명)만 만들었고 자료는 넣지 않았습니다.
- **블로그는 계속 SQLite(`blog.db`, `php-auth/db/sqlite.db`)를 씁니다.** PostgreSQL DB는 설계를 실제 DB로 확인하고 Crowfoot에서 구조를 비교하는 데 씁니다.
- 접속 주소·계정·비밀번호는 Crowfoot의 데이터베이스 탭에서만 봅니다. 공개 저장소이므로 여기에 적지 않습니다.
- 배포 뒤 문서 → DB 비교(plan_migration): 블로그 DB는 차이 0. 회원 DB는 `users`·`social_accounts`의 `created_at` 기본값을 다시 설정하는 ALTER 2개가 나오지만, Crowfoot이 DB의 `to_char(…)` 기본값을 닫는 괄호 없이 읽어서 생기는 차이이고 실제 DB 기본값은 문서와 같습니다(같은 문장을 PostgreSQL 16에서 실행해 확인).
- DB → 문서 동기화(plan_sync·apply_sync)는 하지 않습니다. 위 기본값과 문자열 기본값(`'insight'` 같은 따옴표)을 문서와 다르게 읽어 문서를 망가뜨릴 수 있습니다.

### 구조를 바꿀 때

DB 구조를 바꾸면(`init_db()`·`db()`에 칸·표 추가) 이 폴더의 SQL과 아래 관계도, Crowfoot 문서를 함께 고칩니다. Crowfoot 문서는 PostgreSQL DB에 연결돼 있으므로 새 문서를 만들지 않고 기존 문서를 고친 뒤, plan_migration으로 바뀌는 ALTER 문을 확인하고 apply_migration으로 PostgreSQL에도 반영합니다(칸·표는 더하기만, NFR-08). 새 테이블은 근거 요구사항에 연결해 그룹을 채웁니다.

처음부터 새 시안을 만들 때만: 워크스페이스 ERD 탭 → **SQL 가져오기** → 데이터베이스 종류 **PostgreSQL** → SQL 파일 내용을 붙여 넣고 미리보기(테이블·관계 수 확인) → 다른 이름으로 문서 만들기.

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

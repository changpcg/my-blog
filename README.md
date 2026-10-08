# 나의 블로그

티스토리 스타일의 개인 블로그입니다. Python 3만 있으면 추가 설치 없이 실행됩니다.
화면 라이브러리와 글꼴을 저장소 안에 넣어 두어 **인터넷이 끊겨도** 글 목록·본문·글쓰기가 그대로 동작합니다
(날씨·시세·맛집·SNS 로그인처럼 바깥 정보를 가져오는 기능만 인터넷이 필요합니다).

## 실행

```bash
python3 server.py
```

브라우저에서 http://localhost:8000 접속 → 오른쪽 위 **로그인** → 아이디 `admin`, 비밀번호 `admin1234`

macOS에서는 Finder에서 **`start-blog.command`를 더블클릭**하면 회원 서버(8080)와 블로그(8000)를 함께 켜고 브라우저를 열어 줍니다.
끄려면 열린 터미널 창에서 Ctrl + C (회원 서버도 함께 꺼짐).

비밀번호 바꾸기:

```bash
BLOG_PASSWORD=원하는비밀번호 python3 server.py
```

## 기능

**글 종류 (4가지)**

| 종류 | 화면 |
|---|---|
| 💡 인사이트 | 한 줄 목록 (오른쪽에 대표 사진) |
| ❓ 자주 묻는 질문 | 질문을 누르면 답변이 펼쳐지는 목록 |
| 📖 용어 사전 | ㄱㄴㄷ / ABC 색인 + 용어 카드 |
| ☕️ 일상 | 한 줄 목록 (카테고리 없이도 작성 가능) |

**내 블로그 (네이버 블로그처럼)**

- 가입하면 바로 내 블로그가 생겨요: 주소는 `#/@아이디`
- 블로그마다 이름·소개·프로필 사진·카테고리·방문자 수가 따로
- **블로그 관리** (`#/manage`): 방문 통계와 많이 본 글, 글 여러 개를 한 번에 공개/비공개/삭제, 내 글에 달린 댓글 관리, 카테고리 추가·이름 바꾸기·순서·삭제, 미니룸, 꾸미기, 블로그 정보
- **꾸미기** (블로그 관리 → 🎨 꾸미기): 대표 색 8가지(내 블로그·내 글 화면에만 적용, 방문자에게도 보임, 다크 모드는 밝은 버전), 사이드바·배너 항목(미니룸·글 종류·인기 글·태그·최근 댓글·방문자 수) 켜고 끄기
- **인기 글**: 블로그 사이드바와 블로그 홈 사이드바에 조회수 많은 공개 글 5개
- **블로그 홈** (`#/`): 모든 블로그의 새 글과 블로그 둘러보기
- 관리자는 오른쪽 위 메뉴 → **사이트 설정**에서 사이트 이름, 회원가입 허용, 회원 관리

**회원**

- 누구나 회원가입(아이디·닉네임·비밀번호) 후 글쓰기, 이미지 올리기, 회원 댓글 달기
- 내 글만 수정·삭제 / 비공개 글은 나와 관리자만 보기
- 관리자(`admin`): 모든 글 관리, 회원 탈퇴 처리, 회원가입 열기·닫기 (블로그 설정)
- 로그인 상태는 서버를 다시 켜도 유지 (2주)
- 비회원도 이름·비밀번호로 댓글 가능

**카테고리 (3가지)**: 마케팅, AI/기술, 데이터. 바꾸려면 `server.py`의 `CATEGORIES`를 고치세요.

- 글쓰기/수정/삭제 (마크다운 + 실시간 미리보기, 임시 저장, 공개/비공개)
- 글쓰기 화면: 사이드바 없이 넓게, 따라오는 도구 모음, 글자 수, **발행**을 누르면 카테고리·공개·태그·대표 사진(본문 사진 중에서)을 고르는 발행 설정 창, 저장하지 않고 나가면 확인
- 이미지 업로드 (붙여넣기, 드래그 앤 드롭, 버튼)
- 카테고리, 태그, 검색, 페이지 나누기
- 댓글 (이름 + 비밀번호, 작성자 본인 또는 관리자만 삭제)
- 방문자 수 (Today / Yesterday / Total), 조회수
- 글 읽기: 읽는 시간, 목차(소제목 2개 이상), 읽은 만큼 차는 막대, 맨 위로, 사진 크게 보기, 코드 언어 표시·복사
- 글 아래: 공감·공유하기, 작성자 카드(이웃 추가), 같은 카테고리 글 4개 사진 카드, 이전 글/다음 글
- 블로그 이름·소개·닉네임·프로필 이미지 설정
- 다크 모드, 모바일 화면 대응, 얇은 선과 여백 위주의 담백한 디자인

## 파일 구조

| 파일 | 역할 |
|---|---|
| `server.py` | API 서버 + SQLite 저장 |
| `static/` | 화면 (HTML, CSS, JS) |
| `static/vendor/` | 내장 라이브러리·글꼴 (marked·DOMPurify·highlight.js·Pretendard, 출처·라이선스·확인값은 그 안 README) |
| `blog.db` | 글·댓글 데이터 (처음 실행 시 생성) |
| `uploads/` | 업로드한 이미지 |
| `php-auth/` | 회원 서버 (PHP: 회원가입·로그인·SNS 로그인) |
| `tools/backup.py`, `tools/restore.py` | 백업·복원 도구 |
| `backups/` | 백업 (자동·수동, git에 올라가지 않음) |
| `deploy/` | 인터넷 공개 안내와 Nginx·systemd 예시 |
| `tests/` | 스모크 테스트 |
| `requirements.md`, `specs/`, `.specify/`, `CLAUDE.md` | 개발 문서 (아래 '개발 문서와 작업 규칙') |
| `docs/erd/` | ERD — 블로그·회원 DB 구조 (SQL·관계도) |

## 백업·복원

블로그는 회원 번호로 계정을 찾으므로 **blog.db와 회원 DB는 항상 함께** 백업·복원해야 합니다. 아래 도구가 둘을 함께 다룹니다.

- **자동**: `start-blog.command`로 켜면 그날 백업이 없을 때 하나 만들고, 켜 둔 동안 날짜가 바뀌면 또 만듭니다. 최근 14개만 남깁니다.
- **지금 바로**: `backup-blog.command` 더블클릭(또는 `python3 tools/backup.py`). 블로그를 켠 채로 해도 됩니다.
- **들어가는 것**: `blog.db`, 회원 DB(`php-auth/db/sqlite.db`), 서명 키(`sso.key`), SNS 설정(`oauth.config.php`), `deploy.config.json`, `uploads/`.
  바뀌지 않은 사진은 앞 백업과 하드 링크로 이어 용량을 거의 쓰지 않습니다. 백업 폴더는 나만 열 수 있게 만들어집니다(비밀번호 해시·키가 들어 있음).
- **되돌리기**: 블로그와 회원 서버를 끄고(터미널에서 Ctrl + C) `python3 tools/restore.py`로 목록을 본 뒤
  `python3 tools/restore.py backups/<폴더>`. 되돌리기 전 상태는 `…_before-restore` 폴더로 남고, 중간에 실패하면 그 상태로 자동으로 돌려놓습니다.
  이 컴퓨터의 설정 파일(`deploy.config.json`·`oauth.config.php`)은 그대로 둡니다(백업 것으로 바꾸려면 `--with-config`).
  백업 위치를 바꿨다면 `--dest 그 폴더`도 붙이세요.
- **백업 위치 바꾸기**: 컴퓨터 디스크가 고장 나도 남도록 외장 디스크나 iCloud Drive 폴더를 쓰려면 `start-blog.command`·`backup-blog.command`를
  텍스트 편집기로 열어 `cd` 줄 아래에 `export MYBLOG_BACKUP_DIR="/Volumes/외장디스크/blog-backups"`를 넣습니다(터미널에서는 `--dest 폴더`).
- 점검: `python3 tests/smoke_backup.py` (임시 폴더에서 백업·복원을 해 보고, 실제 자료는 건드리지 않음)

## 다른 기기에서 접속하기

같은 와이파이의 휴대폰·다른 컴퓨터에서 보려면:

```bash
HOST=0.0.0.0 BLOG_PASSWORD=비밀번호 python3 server.py
```

그다음 `http://이 컴퓨터의 IP:8000`으로 접속합니다. 인터넷 전체에 공개하려면 아래 '실행 모드'의 공개 모드를 쓰세요.

## 실행 모드 (개발 / 공개)

| 모드 | 켜는 법 | 특징 |
|---|---|---|
| 개발 모드 (기본) | 지금처럼 `python3 server.py` + `php -S` | http://localhost, 설정 파일 없어도 됨 |
| 공개 모드 | `deploy.config.json`에 `"public_mode": true` | https 전용·Secure 쿠키·HSTS, 관리자 비밀번호 12자 이상 필수, 회원 서버는 Nginx + PHP-FPM |

- 두 서버는 `deploy.config.json` 한 파일을 함께 읽습니다(예시: `deploy.config.example.json`, 실제 파일은 git에 올라가지 않음).
- 인터넷 공개(VPS·Nginx·HTTPS) 순서는 **[deploy/README.md](deploy/README.md)** 에 있습니다.
- 회원가입 보호(두 모드 공통): 같은 곳(IP)에서 1시간 3개·사이트 전체 1시간 30개까지, 숨은 칸·최소 3초로 자동 가입을 막습니다.
  개발 중 가입 테스트를 자주 하면 `deploy.config.json`에 `{"signup": {"per_ip_per_hour": 50}}`처럼 한도를 올리세요.
- 점검: `python3 tests/smoke_public_deploy.py` (코드를 임시 폴더에 복사해 공개·개발 모드를 확인, 실제 DB는 건드리지 않음)
- 화면(004) 점검: `python3 tests/smoke_reading_ui.py` (php 없이, 대표 사진·관련 글 규칙과 본문 20만 자 상한, 실제 DB는 건드리지 않음)
- DB 인덱스 점검: `python3 tests/smoke_db_indexes.py` (연결 칸 인덱스 8개와 조회 계획, 실제 DB는 건드리지 않음)
- 글쓰기(005)·꾸미기(006)·내장 파일(007) 점검: `python3 tests/smoke_editor_cover.py`, `python3 tests/smoke_blog_design.py`, `python3 tests/smoke_offline_assets.py` (모두 php 없이, 실제 DB는 건드리지 않음)

## 회원가입·로그인 (PHP와 합침)

회원가입과 로그인은 `php-auth` (PHP + SQLite)가 맡습니다. 두 서버를 함께 켜 두세요.

```bash
cd ~/Documents/my-blog && BLOG_PASSWORD='비밀번호' python3 server.py      # 블로그 8000
cd ~/Documents/my-blog/php-auth && php -S localhost:8080 -t public      # 회원 8080
```

- 블로그의 **로그인/회원가입** → PHP 페이지(아이디·비밀번호·닉네임·자기소개) → 끝나면 블로그로 돌아와 로그인됨
- 처음 들어오면 블로그가 자동으로 생기고, 자기소개가 블로그 소개가 됩니다
- PHP는 서명한 1회용 입장권(5분)을 블로그에 넘기고, 블로그는 `php-auth/db/sso.key`로 서명을 확인합니다
- 관리자(`admin`)와 예전 블로그 계정은 로그인 화면 아래 **관리자 · 예전 블로그 계정으로 로그인**을 씁니다
- 예전 블로그 계정과 같은 아이디로 PHP에 가입하면, 예전 블로그 비밀번호를 한 번 입력해 연결합니다

## 개발 문서와 작업 규칙

코드와 개발 문서가 이 저장소 하나에 있습니다(예전 문서 저장소 blog-project를 2026-10-08에 기록과 함께 합침).
저장소는 공개입니다: https://github.com/changpcg/my-blog — SNS 키·서명 키·DB·업로드·백업·배포 설정은 `.gitignore`로 빠져 있으니 올리지 마세요.

| 위치 | 내용 |
|---|---|
| `requirements.md` | 요구사항 정의서 — 요구사항 ID·완료 기준·남은 과제 (원본: Claude Docs 문서 '나만의 블로그 요구사항 정의서') |
| `.specify/memory/constitution.md` | 헌법 — 개발 원칙 (서버가 최종 판단, 설치 없이 돈다, 데이터 보존 등) |
| `specs/001-…/` ~ `specs/008-…/` | 기능별 설계 문서 (spec·plan·tasks, [GitHub Spec Kit](https://github.com/github/spec-kit)) |
| `.claude/skills/speckit-*` | Claude Code에서 쓰는 Spec Kit 명령 |
| `CLAUDE.md` | 작업 규칙 요약 |
| `docs/erd/` | ERD — 두 DB의 구조(PostgreSQL 문법 SQL과 관계도). [Crowfoot](https://crowfoot.java21.net/) '나만의 블로그' 워크스페이스에도 같은 문서가 있고, 요구사항·그룹을 연결해 Crowfoot의 PostgreSQL DB 두 개에 배포함(설계 확인용 — 블로그는 계속 SQLite 사용) |

- 새 기능은 Claude Code에서 `/speckit-specify 만들 기능 설명` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` 순서로 만듭니다(다음 번호 009).
- **코드가 바뀔 때마다 이 README.md와 requirements.md를 같은 커밋에서 함께 고치고, 커밋하면 바로 GitHub(changpcg/my-blog)에 올립니다** (헌법 원칙 V, 요구사항 NFR-17).
- 실제 자료를 건드리지 않는 점검을 한 번에:

```bash
for t in reading_ui editor_cover blog_design offline_assets backup db_indexes public_deploy; do python3 tests/smoke_$t.py || break; done
```

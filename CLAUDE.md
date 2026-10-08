# 나만의 블로그 — 작업 규칙

이 저장소(my-blog) 하나에 블로그 코드와 개발 문서가 모두 있습니다. 대답·문서·커밋 메시지·화면 문구는 한국어로 씁니다.

## 어디에 무엇이

| 위치 | 내용 |
| --- | --- |
| `server.py`, `static/` | 블로그 서버(Python 3.9 표준 라이브러리)와 화면(바닐라 JS, 라이브러리는 `static/vendor/`) |
| `php-auth/` | 회원 서버(PHP 8) |
| `tools/`, `deploy/`, `tests/` | 백업·복원 도구, 공개 운영 안내·예시, 스모크 테스트 |
| `README.md` | 실행 방법·기능·파일 구조·점검 명령 |
| `requirements.md` | 요구사항 정의서(ID·완료 기준·남은 과제). 원본은 Claude Docs 문서 [나만의 블로그 요구사항 정의서](https://claude.ai/artifact/RwM5NYppuiRaTd2v61Phud) |
| `.specify/memory/constitution.md` | 헌법(개발 원칙). 계획마다 Constitution Check |
| `specs/<번호>-<이름>/` | 기능별 spec·plan·tasks (GitHub Spec Kit) |
| `.claude/skills/speckit-*` | `/speckit-specify` 같은 Spec Kit 명령 |
| `docs/erd/` | ERD — 블로그·회원 DB 구조(PostgreSQL 문법 SQL, 관계도). Crowfoot '나만의 블로그' 워크스페이스에 같은 문서 |

## 코드가 바뀔 때마다 (필수)

코드·화면·설정·실행 방법이 바뀌는 커밋에는 아래 문서 갱신을 **같은 커밋에** 넣습니다. 작은 수정도 같습니다(헌법 원칙 V, NFR-17).

1. `README.md` — 실행 방법, 기능 목록, 파일 구조, 점검 명령 중 달라진 것.
2. `requirements.md` — 관련 ID 행의 요구사항·완료 기준, 1장 범위·구성 표, 7장 남은 과제 체크. 새 기능은 새 ID를 받습니다.
3. 원본 Claude Docs 문서도 같은 내용으로 고칩니다.
4. 기능 작업이면 `specs/<번호>-<이름>/tasks.md` 체크와 spec의 Status.
5. DB 구조를 바꾸면(`server.py`의 `init_db()`, `php-auth/src/db.php`) `docs/erd/`의 SQL·관계도와 Crowfoot 문서도 함께 고칩니다.

문서와 동작이 다르면 버그로 보고 함께 고칩니다. 커밋한 뒤에는 바로 GitHub에 올립니다(아래 '커밋과 GitHub').

## 기능 개발 순서 (Spec Kit)

`/speckit-specify` → (`/speckit-clarify`) → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`

번호는 `specs/`의 가장 큰 번호 + 1이고(다음은 009), 지금 작업 중인 기능은 `.specify/feature.json`(git 제외)에 적힙니다.

## 코드 규칙 요약 (자세한 것은 헌법)

- 블로그 서버는 Python 3.9 표준 라이브러리만, 회원 서버는 PHP 8 + pdo_sqlite·mbstring(SNS 로그인만 curl). 화면 라이브러리는 `static/vendor/` 안의 것만 씁니다.
- 권한·입력 검증은 서버에서 합니다(화면 검사는 안내용).
- DB는 칸·표를 더하기만 합니다. 실제 `blog.db`·`php-auth/db/`를 지우거나 덮어쓰지 않고, 위험한 작업 전에는 `python3 tools/backup.py`.
- `static/`의 CSS·JS를 고치면 `static/index.html`의 `?v=` 숫자를 올립니다.

## 점검

```bash
for t in reading_ui editor_cover blog_design offline_assets backup public_deploy; do python3 tests/smoke_$t.py || break; done
```

위 테스트는 코드를 임시 폴더에 복사해 빈 포트에서 돌리므로 실제 자료를 건드리지 않습니다(`public_deploy`의 회원 서버 부분은 php가 있어야 돎).
`smoke_security_gaps.py`(001)·`smoke_member_lifecycle.py`(002)는 켜 둔 블로그(8000)·회원 서버(8080)에 직접 요청해 테스트 회원·댓글을 만들었다 지우므로 필요할 때만 돌립니다.

## 커밋과 GitHub

- 메시지는 한국어 `종류(기능 번호): 내용` 꼴 — 예: `feat(009): …`, `fix: …`, `docs: …`.
- 커밋 전에 위 점검을 돌리고, 실패하면 커밋하지 않습니다.
- 커밋하면 **바로 GitHub(`changpcg/my-blog`)에 올립니다** — GitHub Desktop의 Repository → Push(또는 `git push`).
  문서만 바뀐 커밋도 같고, 올리지 않은 커밋을 남기지 않습니다. 올린 뒤 `origin/main`이 내 `main`과 같은지 확인합니다.
- 저장소는 **공개**입니다. 비밀값(SNS 키 `php-auth/oauth.config.php`, `php-auth/db/`의 회원 DB·`sso.key`, `blog.db`, `deploy.config.json`, `uploads/`, `backups/`)은 커밋하지 않습니다(모두 `.gitignore`에 있음). 커밋 전에 `git status`로 새 파일을 확인하고, 테스트·예시에는 진짜 비밀번호·키를 쓰지 않습니다.

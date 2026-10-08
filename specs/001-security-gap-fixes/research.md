# Research: 001-security-gap-fixes

현재 코드(`~/Documents/my-blog`, 2026-10-07 기준)를 읽고 정한 결정들.

## R1. 댓글 비밀번호 전송 방식

- **현재**: `app.js` 619행 `api(\`comments/${id}?password=${enc(pw)}\`, {method:'DELETE'})`,
  `server.py` `api_DELETE_comments`가 `q.get("password")`로 확인.
- **Decision**: `DELETE /api/comments/{id}`에 JSON 본문 `{"password": "..."}`. 쿼리에 `password`가
  있으면 비밀번호를 확인하지 않고 400 "비밀번호는 주소에 넣을 수 없어요. 화면을 새로 고친 뒤 다시
  시도해 주세요."
- **Rationale**: `api()` 헬퍼가 이미 `body`를 JSON으로 보내고, `Handler.body()`가 메서드와 무관하게
  Content-Length로 읽으므로 변경이 가장 작다. 예전 화면이 열려 있던 사용자에게는 새로 고침 안내.
- **Alternatives**: `POST /api/comments/{id}/delete` 새 경로 → 경로가 늘고 기존 권한 로직 중복. 기각.

## R2. 잠금 기록 저장 위치와 규칙

- **Decision**: blog.db 새 표 `comment_pw_fails(comment_id, ip, at)` + 색인 `(comment_id, at)`.
  확인 순서: ① 15분 지난 기록 삭제 ② 그 댓글·IP 실패 수 ≥ 5 또는 댓글 전체 ≥ 20이면 429와 남은 분
  ③ 비밀번호 확인, 틀리면 기록 추가 + `time.sleep(0.5)` + 403 ④ 맞으면 그 댓글 기록 삭제.
  남은 시간 = 그 범위의 가장 이른 실패 + 900초 − 지금, 분 단위 올림.
- **IP**: `self.client_address[0]`. 헌법상 배포 범위 밖이므로 `X-Forwarded-For`는 믿지 않는다.
- **Rationale**: SEC-03(PHP 로그인)과 같은 15분·5회 규칙으로 사용자 이해가 쉽다. 메모리가 아닌 DB라
  서버를 다시 켜도 유지(Edge case). 잠금은 비밀번호 경로에만 적용되어 FR-006 충족.
- **Alternatives**: 지연만(블로그 로그인처럼) → 헌법 "횟수 제한 또는 지연"은 충족하나 4자리 비밀번호면
  하루 17만 번 시도 가능. 기각.

## R3. 로그아웃 표를 회원에 묶기

- **현재**: `make_logout_ticket()` payload `{act, exp, nonce(8바이트)}`. `api_POST_logout`은 세션을
  먼저 지우고 로그인 여부와 관계없이 표를 만든다. 화면이 `location.href = .../sso_logout.php?t=...`로 이동,
  PHP는 GET으로 서명·만료만 확인.
- **Decision**:
  - 블로그: 세션을 지우기 **전에** `self.user`를 읽고, `auth_uid`가 있을 때만
    `{act:"logout", uid:auth_uid, exp:+60, nonce:16바이트}` 표를 만든다. 응답
    `{"ok", "auth_url", "auth_logout": {"action": ".../sso_logout.php", "t": "..."}}` (없으면 null).
  - 화면: 숨은 `<form method="post" action=auth_logout.action><input name="t"></form>`를 만들어 submit.
  - PHP: `REQUEST_METHOD !== 'POST'`면 아무것도 하지 않고 블로그로. 서명·act·exp 확인 후
    `(int)$data['uid'] === (int)($_SESSION['uid'] ?? 0)`이고 nonce가 `sso_used_nonces`에 없을 때만
    nonce를 기록하고 로그아웃. 만료 기록은 매번 정리.
- **CSRF 토큰을 따로 쓰지 않는 이유**: 서명된 1회용 표 자체가 "블로그가 이 회원을 위해 방금 만든 요청"의
  증거이고, 남이 가진 표는 uid가 달라 무효. 블로그(8000)와 회원 서버(8080)는 같은 site(포트 무시)라
  SameSite=Lax 쿠키가 POST에 실린다.
- **Alternatives**: 블로그 서버가 PHP를 서버 간 호출 → PHP 세션 쿠키는 브라우저에만 있어 불가. 기각.

## R4. 탈퇴 시 댓글 처리 순서

- **현재**: `DELETE FROM comments WHERE user_id = ?` 한 줄 → 답글이 달린 댓글도 바로 삭제.
- **Decision** (`api_DELETE_users`, 그 회원 글의 댓글을 지운 다음):
  1. 그 회원의 답글 삭제: `DELETE ... WHERE user_id = ? AND parent_id IS NOT NULL`
  2. 그 회원의 댓글 중 살아 있는 답글이 있는 것 → `UPDATE ... SET deleted=1, name='', content='', password_hash='', user_id=NULL`
  3. 나머지 그 회원 댓글 삭제
  4. 영향받은 부모 중 살아 있는 답글이 없는 `deleted=1` 자리와 그 아래 삭제된 답글 정리
     (기존 `api_DELETE_comments` 정리 규칙과 같게 — 공통 함수 `_tidy_deleted_parent(conn, parent_id)`로 뽑음)
- **user_id를 NULL로**: 지운 회원 번호가 남지 않게(헌법 IV 일관성). 화면은 `deleted`면 이름·내용을
  보내지 않으므로 표시 변화 없음.

## R5. 이미 생긴 고아 답글 복구

- **Decision**: `init_db`에 `settings.key = 'restored_orphan_replies'` 1회 마이그레이션. 실행 전
  고아가 1건 이상이면 `blog.db`를 `blog.backup-before-reply-restore.db`로 복사(기존 백업 관례와 같은
  이름 형식). 고아 답글의 `parent_id`마다 같은 id로 자리 행을 넣는다:
  `INSERT INTO comments (id, post_id, name, password_hash, content, created_at, user_id, parent_id, deleted)
   VALUES (?, ?, '', '', '', MIN(답글 created_at), NULL, NULL, 1)`.
- **Rationale**: 남의 답글을 지우지 않고(헌법 IV) 화면·숫자를 동시에 맞춘다. SQLite AUTOINCREMENT는
  명시 id 삽입을 허용하고, 그 id는 예전에 쓰였으므로 충돌하지 않는다.
- **Alternatives**: 고아 답글 삭제 → 다른 회원의 글이 사라짐. 기각.

# Quickstart: 001-security-gap-fixes 검증

## 준비

```bash
cd ~/Documents/my-blog
cp blog.db blog.backup-before-001.db && cp -R php-auth/db php-auth/db.backup-before-001
python3 server.py                                   # 터미널 1
php -S localhost:8080 -t php-auth/public            # 터미널 2
```

계약 상세는 [contracts/blog-api.md](./contracts/blog-api.md), [contracts/sso-logout.md](./contracts/sso-logout.md).

## US1 댓글 비밀번호

1. 로그아웃 상태에서 아무 공개 글에 이름 `손님`, 비밀번호 `pw1234`로 댓글 작성 → 댓글 id 확인
   (`curl -s 'localhost:8000/api/comments?post=<글id>'`).
2. 주소 방식 거절:
   `curl -s -X DELETE 'localhost:8000/api/comments/<id>?password=pw1234'` → 400, 댓글 그대로.
3. 틀린 비밀번호 5번:
   `for i in 1 2 3 4 5; do curl -s -o /dev/null -w '%{http_code} %{time_total}\n' -X DELETE -H 'Content-Type: application/json' -d '{"password":"x"}' localhost:8000/api/comments/<id>; done`
   → 모두 `403`, 시간 0.5초 이상.
4. 6번째는 맞는 비밀번호로 → `429`, "N분 뒤" 문구.
5. 서버를 껐다 켜도 4와 같음.
6. 블로그 주인(또는 admin)으로 로그인해 화면에서 그 댓글 삭제 → 성공.
7. 새 댓글로 맞는 비밀번호 삭제(화면) → 성공, 개발자 도구 Network에서 요청 주소에 비밀번호 없음.

## US2 로그아웃 표

1. 회원 A로 회원 페이지 로그인 → 블로그 들어가기 → 블로그에서 로그아웃 → 두 곳 모두 로그아웃, 블로그 홈.
2. 블로그에 로그인 안 한 상태: `curl -s -X POST localhost:8000/api/logout` → `"auth_logout": null`.
3. A로 다시 블로그 로그인 후 브라우저 개발자 도구에서 `fetch('/api/logout',{method:'POST'}).then(r=>r.json())`
   → 받은 `t`를 메모(이때 A 블로그는 로그아웃됨).
   다른 브라우저에서 회원 B로 회원 페이지 로그인 →
   `curl`이 아니라 그 브라우저 콘솔(회원 페이지 탭)에서 폼 POST로 `t` 제출 → B는 로그인 유지.
4. A 브라우저(회원 페이지 로그인 상태)에서 같은 `t`를 두 번 제출 → 첫 번째에만 로그아웃,
   다시 로그인 후 두 번째 제출은 효과 없음.
5. `http://localhost:8080/sso_logout.php?t=<t>` GET 주소를 열기 → 로그아웃 안 됨.
6. admin으로 블로그 로그인 후 로그아웃 → 블로그만 로그아웃, 오류 없음.
7. 회원 서버를 끈 채 A로 로그아웃 → 1.5초 안에 블로그만 로그아웃.

## US3 탈퇴 회원 댓글

1. 회원 X가 회원 Y의 글에 댓글, 회원 Z(또는 방문자)가 그 댓글에 답글, X가 Z의 다른 댓글에 답글.
2. admin → 사이트 설정 → X 탈퇴.
3. Y의 글: "삭제된 댓글입니다" 아래 Z의 답글 보임, X의 답글은 없음.
4. 글 카드 댓글 수 = 글 화면에 보이는 살아 있는 댓글 수, Y의 블로그 관리 → 댓글 목록에 Z의 답글 있음.
5. 고아 답글 복구: 백업 DB(`blog.backup-before-orphan-cleanup.db`)를 임시 폴더에 복사해 그 DB로 서버 실행 →
   `sqlite3 blog.db "SELECT COUNT(*) FROM comments c WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM comments)"` = 0,
   `blog.backup-before-reply-restore.db` 생성 확인.

## 마무리

- 기존 blog.db로 켰을 때 글·댓글·로그인(2주) 유지 확인
- requirements.md 갱신(T030) 후 문서 저장소 커밋

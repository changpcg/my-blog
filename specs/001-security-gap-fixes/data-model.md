# Data Model: 001-security-gap-fixes

모든 변경은 표 **추가**만 한다(헌법 IV). 기존 표의 칸은 바꾸지 않는다.

## blog.db

### comment_pw_fails (새 표)

| 칸 | 형식 | 설명 |
| --- | --- | --- |
| comment_id | INTEGER NOT NULL | 비밀번호를 틀린 댓글 |
| ip | TEXT NOT NULL | 요청한 접속 주소 (`client_address[0]`) |
| at | INTEGER NOT NULL | 실패 시각 (유닉스 초) |

- 색인: `idx_comment_pw_fails (comment_id, at)`
- 규칙: 15분(900초)이 지난 행은 확인할 때마다 지운다. 삭제 성공·댓글 삭제 시 그 댓글의 행을 지운다.
- 잠금: `COUNT(ip = 요청 IP) >= 5` 또는 `COUNT(전체) >= 20` (모두 최근 900초)

### comments (기존, 상태 전이만 확장)

```text
살아 있음 (deleted=0)
  ├─ 삭제 요청, 살아 있는 답글 없음 ──────────▶ 행 삭제
  ├─ 삭제 요청, 살아 있는 답글 있음 ──────────▶ 자리 (deleted=1, name/content/password_hash='')
  └─ [새] 작성 회원 탈퇴, 남의 답글 있음 ─────▶ 자리 (deleted=1, … , user_id=NULL)
자리 (deleted=1)
  └─ 마지막 살아 있는 답글이 지워짐 ──────────▶ 자리와 그 아래 삭제된 답글 행 삭제
[새] 고아 답글(부모 행 없음) ── 1회 마이그레이션 ──▶ 같은 id로 자리 행 생성
```

### settings (기존)

- 새 키 `restored_orphan_replies = '1'`: R5 마이그레이션 완료 표시

## php-auth/db/sqlite.db

### sso_used_nonces (새 표)

| 칸 | 형식 | 설명 |
| --- | --- | --- |
| nonce | TEXT PRIMARY KEY | 이미 쓴 로그아웃 표의 1회용 번호 |
| expires | INTEGER NOT NULL | 표 만료 시각 (이 시각 이후 행은 정리) |

## 로그아웃 표 (서명된 값, 저장 안 함)

```text
base64url(JSON{act:"logout", uid:<회원 서버 회원 번호>, exp:<지금+60>, nonce:<32자 hex>}) + "." + HMAC-SHA256(sso.key)
```

- `uid`는 블로그 `users.auth_uid` (관리자·연결 안 한 예전 계정은 NULL → 표를 만들지 않음)

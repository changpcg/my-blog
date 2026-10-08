# Implementation Plan: 회원 계정을 두 서버에서 함께 관리하기

**Branch**: `002-member-lifecycle-sync` | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-member-lifecycle-sync/spec.md`

**Code root**: `~/Documents/my-blog` (GitHub `changpcg/my-blog`)

## Summary

- **US1**: 회원 서버에 `profile.php`(내 정보 수정: 닉네임·자기소개·비밀번호·탈퇴)를 더한다. 비밀번호를 바꾸면
  `users.session_ver`를 올려 다른 브라우저의 회원 페이지 세션을 끊는다. 닉네임을 바꾸면 `nickname_at`을 기록하고,
  입장권에 `nick_at`을 실어 블로그가 더 새 값일 때만 블로그 닉네임을 바꾼다.
- **US2**: 블로그에 서명된 `GET /api/bridge/signup` 응답을 더하고, 회원 서버가 1분 캐시(`bridge_cache`)로 읽어
  꺼져 있으면 일반 가입·SNS 첫 가입·아이디 중복 확인을 막는다. 못 읽으면 마지막 값, 없으면 '꺼짐'.
- **US3**: 서명된 1회용 서버 간 탈퇴 요청. 관리자 탈퇴는 블로그 → `bridge_delete.php`(회원 서버 먼저 삭제) → 블로그 삭제.
  회원 스스로 탈퇴는 회원 서버 → `POST /api/bridge/delete_member`(블로그 먼저 삭제) → 회원 서버 삭제. 상대가 응답하지
  않으면 아무것도 지우지 않는다. 입장권에 `joined`(가입 시각)를 실어 블로그가 `auth_joined`와 비교한다(번호 재사용 차단).

## Technical Context

**Language/Version**: Python 3.9+ 표준 라이브러리, PHP 8 (pdo_sqlite·mbstring, 서버 간 호출은 `file_get_contents` 스트림)

**Primary Dependencies**: 없음

**Storage**: blog.db `users`에 `auth_joined`, `auth_nick_at` 칸 추가 / sqlite.db `users`에 `session_ver`, `nickname_at` 칸,
`bridge_cache` 표 추가

**Testing**: quickstart 시나리오 + `tests/smoke_member_lifecycle.py`(표준 라이브러리)

**Target Platform**: macOS 로컬, `php -S`(단일 스레드)와 `ThreadingHTTPServer`

**Project Type**: 웹 서비스 2개

**Constraints**: php -S가 단일 스레드라, 회원 서버가 블로그를 부르는 동안 블로그가 회원 서버를 다시 부르면 안 된다
(교착). 브리지 엔드포인트는 상대를 다시 부르지 않게 설계한다. 서버 간 호출 제한시간 3초.

## Constitution Check

| 원칙 | 확인 | 결과 |
| --- | --- | --- |
| I 서버 판단 | 가입 허용·비밀번호 확인·탈퇴 확인 모두 서버 | 통과 |
| II 설치 없음 | curl 없이 스트림 사용 | 통과 |
| III 서명·1회용·POST | 브리지 요청 모두 HMAC + exp, 상태 변경(탈퇴)은 nonce 1회용 + POST, 화면 폼은 CSRF | 통과 |
| IV 데이터 보존 | 칸·표 추가만, 탈퇴는 상대 성공 후에만 로컬 삭제 | 통과 |
| V 추적 | AUTH-14·15·16, BLOG-16, SEC-02·09 갱신 작업 포함 | 통과 |
| VI 한국어·접근성 | 기존 회원 화면 스타일·라벨 재사용 | 통과 |

## Project Structure

```text
my-blog/
├── server.py                       # 칸 추가, bridge 엔드포인트 2개, api_POST_sso(joined·nick_at), api_DELETE_users(회원 서버 먼저)
├── php-auth/src/db.php             # 칸·표 추가
├── php-auth/src/auth.php           # session_ver 확인, signup_open(), delete_member_local()
├── php-auth/src/sso.php            # 입장권에 joined·nick_at, sign_bridge()/read_bridge(), blog_call()
├── php-auth/public/profile.php     # 새 화면 (정보 수정·비밀번호·탈퇴)
├── php-auth/public/bridge_delete.php # 블로그 → 회원 서버 탈퇴
├── php-auth/public/{index,register,social_signup,check_username,oauth_callback}.php  # 링크·가입 차단
└── tests/smoke_member_lifecycle.py
```

## Complexity Tracking

해당 없음.

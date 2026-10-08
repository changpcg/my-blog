#!/bin/bash
# 나만의 블로그를 이 컴퓨터에서 켭니다 (개발 모드).
# Finder에서 더블클릭하면 터미널 창이 열리고 아래가 실행돼요.
#   블로그      http://localhost:8000   (관리자: admin / 비밀번호는 BLOG_PASSWORD, 없으면 admin1234)
#   회원 서버   http://localhost:8080
# 끄기: 이 터미널 창에서 Ctrl + C (회원 서버도 함께 꺼짐)
cd "$(dirname "$0")" || exit 1

if command -v php >/dev/null 2>&1; then
  php -S localhost:8080 -t php-auth/public >/tmp/my-blog-php.log 2>&1 &
  PHP_PID=$!
  trap 'kill "$PHP_PID" 2>/dev/null' EXIT
  sleep 1
  if kill -0 "$PHP_PID" 2>/dev/null; then
    echo "회원 서버 실행 중 → http://localhost:8080"
  else
    echo "회원 서버(8080)를 켜지 못했어요. 이미 켜져 있을 수 있어요:"
    tail -3 /tmp/my-blog-php.log
  fi
else
  echo "php를 찾을 수 없어 블로그만 켭니다 (회원가입·회원 로그인은 안 돼요)."
fi

# 2초 뒤 기본 브라우저로 블로그 열기
(sleep 2; open "http://localhost:8000") &
python3 server.py

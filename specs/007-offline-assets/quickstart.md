# Quickstart: 인터넷이 끊겨도 동작 점검

1. 와이파이를 끄고(또는 비행기 모드) `start-blog.command`로 블로그를 켠다.
2. http://localhost:8000 → 글 목록·글 보기(표·코드 색)·글쓰기 미리보기가 정상인지, 글꼴이 Pretendard인지 본다.
3. 개발자 도구 네트워크 탭에서 `cdn.jsdelivr.net` 요청이 없는지 본다(날씨·시세 위젯의 바깥 요청은 실패해도 정상).
4. 회원 로그인 화면(http://localhost:8080/login.php) 글꼴이 블로그와 같은지 본다.
5. `python3 tests/smoke_offline_assets.py` → OK.

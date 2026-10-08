# Quickstart: 백업 자동화 점검

1. `start-blog.command`를 더블클릭 → 터미널에 "백업했어요: backups/…"가 보이고 블로그가 켜진다. 다시 켜면 "오늘 백업이 이미 있어요".
2. `backup-blog.command`를 더블클릭 → 새 백업 폴더가 생긴다(서버를 켠 채로).
3. 백업 폴더를 열어 `manifest.json`의 글 수·회원 수를 본다.
4. 복원 연습: 블로그와 회원 서버를 끄고(터미널에서 Ctrl + C) `python3 tools/restore.py` → 목록에서 고른 폴더로
   `python3 tools/restore.py backups/<폴더>` → `y`. 다시 켜서 글을 확인.
5. `python3 tests/smoke_backup.py` → OK.

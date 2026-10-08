#!/bin/bash
# 나만의 블로그를 지금 바로 백업합니다 (블로그를 켠 채로도 돼요).
# Finder에서 더블클릭하면 터미널 창이 열리고 아래가 실행돼요.
#   백업 위치: 이 폴더의 backups/ (바꾸려면 MYBLOG_BACKUP_DIR)
#   되돌리기: 블로그와 회원 서버를 끈 뒤 터미널에서 python3 tools/restore.py
cd "$(dirname "$0")" || exit 1
python3 tools/backup.py
echo ""
echo "백업 목록 보기·되돌리기: python3 tools/restore.py"

# Data Model: 백업 자동화

DB 스키마 변경 없음. 백업 폴더와 목록 파일만 있다.

## 백업 위치 (`backups/` 또는 `--dest`·`MYBLOG_BACKUP_DIR`, 700)

| 이름 | 뜻 | 정리 대상 |
| --- | --- | --- |
| `2026-10-08_140512/` (`-2` …) | 자동·수동 백업 | 예 (`--keep`) |
| `2026-10-08_141030_before-restore/` | 복원 직전 안전 백업 | 아니오 |
| `.tmp-…/` | 만드는 중 | 하루 지난 것만 지움 |
| `.lock` | 동시 실행 막기 | — |

## manifest.json (600)

```json
{
  "format": 1,
  "created_at": "2026-10-08T14:05:12",
  "kind": "auto",
  "app": "my-blog",
  "config_path": "deploy.config.json",
  "files": {"blog.db": {"size": 123, "sha256": "…"}, "uploads/ab…cd.png": {"size": 456, "sha256": "…"}},
  "missing": ["php-auth/oauth.config.php"],
  "raw_copies": [],
  "counts": {"posts": 23, "blog_users": 6, "members": 5, "uploads": 41}
}
```

`kind`: `auto`(--daily·systemd) · `manual` · `before-restore`. `raw_copies`: 안전 백업에서 망가진 DB를 파일째 남긴 경우 그 이름(이때 `files`에
`blog.db-wal` 같은 곁 파일도 들어감).

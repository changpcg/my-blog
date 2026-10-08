#!/usr/bin/env python3
"""나만의 블로그 백업 (008-backup-automation, 요구사항 NFR-16). 표준 라이브러리만 씁니다.

블로그 DB와 회원 DB를 함께(SQLite 온라인 백업이라 서버를 켠 채로도 됨), 서명 키·SNS 설정·배포 설정·업로드 파일까지 한 폴더에 저장합니다.

    python3 tools/backup.py              # 지금 바로 백업
    python3 tools/backup.py --daily      # 오늘 백업이 없을 때만 (start-blog.command가 씀)
    python3 tools/backup.py --keep 30    # 자동·수동 백업을 최근 30개만 남김 (기본 14, 0이면 지우지 않음)
    python3 tools/backup.py --dest /Volumes/외장디스크/blog-backups   # 또는 MYBLOG_BACKUP_DIR

복원은 tools/restore.py 를 보세요.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import time
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
FORMAT = 1
DEFAULT_KEEP = 14
# 자동·수동 백업 폴더 이름 (정리 대상). 복원 직전 안전 백업은 끝에 _before-restore가 붙어 대상이 아님
NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}(-\d+)?$")
ANY_BACKUP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}(-\d+)?(_before-restore)?$")
DB_FILES = ("blog.db", "php-auth/db/sqlite.db")
DB_SIDE_SUFFIXES = ("-wal", "-shm", "-journal")
SECRET_FILES = ("php-auth/db/sso.key", "php-auth/oauth.config.php", "deploy.config.json")
KINDS = ("auto", "manual", "before-restore")


class BackupError(Exception):
    pass


class BackupBusy(BackupError):
    pass


def default_dest(app_dir=APP_DIR):
    return Path(os.environ.get("MYBLOG_BACKUP_DIR") or (Path(app_dir) / "backups"))


def config_path(app_dir=APP_DIR):
    """블로그·회원 서버와 같은 규칙: MYBLOG_CONFIG가 있으면 그 파일"""
    return Path(os.environ.get("MYBLOG_CONFIG") or (Path(app_dir) / "deploy.config.json"))


def source_path(rel, app_dir=APP_DIR):
    """백업 안 상대 경로 → 실제 파일 경로"""
    if rel == "deploy.config.json":
        return config_path(app_dir)
    return Path(app_dir) / rel


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def is_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def ensure_private_dir(path):
    """백업 위치: 없으면 나만 쓰는 폴더(700)로 만들고, 있으면 남이 쓸 수 없는 내 폴더인지 확인 (남의 폴더 권한은 바꾸지 않음)."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        else:
            os.chmod(path, 0o700)
            return path
    st = os.stat(path)
    if not stat.S_ISDIR(st.st_mode):
        raise BackupError(f"백업 위치 {path} 가 폴더가 아니에요.")
    if hasattr(os, "geteuid"):
        if st.st_uid != os.geteuid() and not is_root():
            raise BackupError(f"백업 위치 {path} 의 주인이 내가 아니에요. 내 폴더를 고르세요.")
        if st.st_mode & 0o022:
            raise BackupError(f"백업 위치 {path} 는 다른 사람도 쓸 수 있는 폴더예요. 나만 쓰는 폴더를 고르세요(예: chmod 700).")
    return path


class Lock:
    """백업 위치 하나에 백업(또는 복원) 하나만. fcntl이 없는 운영체제에서는 잠그지 않음."""

    def __init__(self, dest):
        self.path = Path(dest) / ".lock"
        self.fd = None

    def __enter__(self):
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            self.fd = os.open(self.path, flags, 0o600)
        except OSError as e:
            raise BackupError(f"잠금 파일을 만들 수 없어요: {e}")
        try:
            os.fchmod(self.fd, 0o600)
        except (OSError, AttributeError):
            pass
        try:
            import fcntl
        except ImportError:
            return self
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            raise BackupBusy("다른 백업이나 복원이 진행 중이에요. 잠시 뒤 다시 실행하세요.")
        return self

    def __exit__(self, *exc):
        os.close(self.fd)  # 닫으면 잠금도 풀림


def sqlite_backup(src, out):
    """서버가 쓰는 중이어도 한 시점의 온전한 사본 (WAL에만 있는 최근 변경 포함). 없는 DB는 만들지 않음(mode=rw)."""
    try:
        source = sqlite3.connect(Path(src).resolve().as_uri() + "?mode=rw", uri=True, timeout=30)
    except sqlite3.Error as e:
        raise BackupError(f"{src} 를 열 수 없어요: {e}")
    try:
        dest = sqlite3.connect(str(out))
        try:
            source.backup(dest)
            # 사본은 파일 하나로 완결되게 (WAL 파일이 따로 필요 없음)
            dest.execute("PRAGMA journal_mode=DELETE")
            result = dest.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise BackupError(f"{src} 사본의 무결성 검사에 실패했어요: {result}")
        finally:
            dest.close()
    except sqlite3.Error as e:
        raise BackupError(f"{src} 를 백업하지 못했어요: {e}")
    finally:
        source.close()


def count(db_path, sql):
    try:
        conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            return conn.execute(sql).fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def read_manifest(folder):
    try:
        with open(Path(folder) / "manifest.json", encoding="utf-8") as f:
            m = json.load(f)
        return m if isinstance(m, dict) and m.get("format") == FORMAT and isinstance(m.get("files"), dict) else None
    except (OSError, ValueError):
        return None


def backup_sort_key(p):
    """'2026-10-08_140512-10'이 '-2' 뒤에 오도록 숫자로 비교"""
    m = re.match(r"^(\d{4}-\d{2}-\d{2}_\d{6})(?:-(\d+))?", p.name)
    return (m.group(1), int(m.group(2) or 1), p.name) if m else (p.name, 0, p.name)


def list_backups(dest, regular_only=False):
    """완성된 백업 폴더 (오래된 것부터). 읽을 수 없는 항목은 건너뜀."""
    dest = Path(dest)
    pattern = NAME_RE if regular_only else ANY_BACKUP_RE
    out = []
    try:
        entries = list(dest.iterdir())
    except OSError:
        return []
    for p in entries:
        try:
            if pattern.match(p.name) and p.is_dir() and not p.is_symlink() and (p / "manifest.json").is_file():
                out.append(p)
        except OSError:
            continue
    return sorted(out, key=backup_sort_key)


def has_backup_today(dest, today=None):
    today = (today or datetime.now()).strftime("%Y-%m-%d") + "_"
    return any(p.name.startswith(today) for p in list_backups(dest, regular_only=True))


def unique_folder_name(dest, base):
    name, n = base, 1
    while (Path(dest) / name).exists():
        n += 1
        name = f"{base}-{n}" if not base.endswith("_before-restore") else base.replace("_before-restore", f"-{n}_before-restore")
    return name


def clean_stale_tmp(dest, max_age=24 * 3600):
    for p in Path(dest).glob(".tmp-*"):
        try:
            if p.is_dir() and not p.is_symlink() and time.time() - p.stat().st_mtime > max_age:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


def rotate(dest, keep):
    """자동·수동 백업을 최근 keep개만 남김 (안전 백업·다른 이름 폴더는 건드리지 않음). (지운 이름, 경고) 목록."""
    if not keep or keep < 0:
        return [], []
    regular = list_backups(dest, regular_only=True)
    removed, warnings = [], []
    for p in regular[:-keep] if len(regular) > keep else []:
        try:
            shutil.rmtree(p)
            removed.append(p.name)
        except OSError as e:
            warnings.append(f"오래된 백업 {p.name} 을 지우지 못했어요: {e}")
    return removed, warnings


def raw_copy_db(src, out, files, rel):
    """복원 직전 안전 백업 전용: DB가 망가져 온라인 백업이 안 되면 파일 그대로(+ -wal·-shm·-journal) 남김"""
    shutil.copyfile(src, out)
    os.chmod(out, 0o600)
    files[rel] = {"size": out.stat().st_size, "sha256": sha256_of(out)}
    for suffix in DB_SIDE_SUFFIXES:
        side = Path(str(src) + suffix)
        if side.is_file():
            o = Path(str(out) + suffix)
            shutil.copyfile(side, o)
            os.chmod(o, 0o600)
            files[rel + suffix] = {"size": o.stat().st_size, "sha256": sha256_of(o)}


def _write_backup(dest, kind, app_dir, now):
    base = now.strftime("%Y-%m-%d_%H%M%S") + ("_before-restore" if kind == "before-restore" else "")
    name = unique_folder_name(dest, base)
    tmp = dest / f".tmp-{name}-{os.getpid()}"
    tmp.mkdir(mode=0o700)
    try:
        files, missing, raw = {}, [], []
        for rel in DB_FILES + SECRET_FILES:
            src = source_path(rel, app_dir)
            if not src.is_file():
                missing.append(rel)
                continue
            out = tmp / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if rel in DB_FILES:
                try:
                    sqlite_backup(src, out)
                except BackupError:
                    if kind != "before-restore":
                        raise
                    # 망가진 DB를 되돌리려는 중: 지금 상태를 그대로 남기는 것이 목적이므로 파일째 복사
                    for p in [out] + [Path(str(out) + s) for s in DB_SIDE_SUFFIXES]:
                        if p.exists():
                            p.unlink()
                    raw_copy_db(src, out, files, rel)
                    raw.append(rel)
                    continue
            else:
                shutil.copyfile(src, out)
            os.chmod(out, 0o600)
            files[rel] = {"size": out.stat().st_size, "sha256": sha256_of(out)}

        # 업로드: 앞 백업과 내용이 같으면(지금 파일·앞 백업 파일·목록의 확인값이 모두 같을 때) 하드 링크, 아니면 복사
        uploads = Path(app_dir) / "uploads"
        prev = next((p for p in reversed(list_backups(dest)) if read_manifest(p)), None)
        prev_files = (read_manifest(prev) or {}).get("files", {}) if prev else {}
        copied = linked = 0
        if uploads.is_dir():
            (tmp / "uploads").mkdir()
            for entry in sorted(os.scandir(uploads), key=lambda e: e.name):
                if not entry.is_file(follow_symlinks=False):
                    continue
                rel = f"uploads/{entry.name}"
                out = tmp / rel
                digest = sha256_of(entry.path)
                old = prev_files.get(rel)
                if old and old.get("sha256") == digest:
                    old_path = prev / rel
                    try:
                        if not old_path.is_symlink() and old_path.is_file() and sha256_of(old_path) == digest:
                            os.link(old_path, out)
                            files[rel] = {"size": old_path.stat().st_size, "sha256": digest}
                            linked += 1
                            continue
                    except OSError:
                        pass  # 다른 디스크 등 → 복사
                shutil.copy2(entry.path, out)
                files[rel] = {"size": out.stat().st_size, "sha256": sha256_of(out)}
                copied += 1
        else:
            missing.append("uploads/")

        manifest = {
            "format": FORMAT,
            "app": "my-blog",
            "kind": kind,
            "created_at": now.isoformat(timespec="seconds"),
            "created_ts": time.time(),
            "config_path": str(config_path(app_dir)),
            "files": files,
            "missing": missing,
            "raw_copies": raw,
            "counts": {
                "posts": count(tmp / "blog.db", "SELECT COUNT(*) FROM posts") if "blog.db" in files else None,
                "blog_users": count(tmp / "blog.db", "SELECT COUNT(*) FROM users") if "blog.db" in files else None,
                "members": count(tmp / "php-auth/db/sqlite.db", "SELECT COUNT(*) FROM users")
                if "php-auth/db/sqlite.db" in files else 0,
                "uploads": sum(1 for k in files if k.startswith("uploads/")),
                "uploads_copied": copied,
                "uploads_linked": linked,
            },
            "total_size": sum(f["size"] for f in files.values()),
        }
        mpath = tmp / "manifest.json"
        fd = os.open(mpath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        os.rename(tmp, dest / name)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return dest / name, manifest


def has_anything(app_dir=APP_DIR):
    """백업할 자료가 하나라도 있는지 (복원 직전 안전 백업을 건너뛸지 정할 때)"""
    app_dir = Path(app_dir)
    if any(source_path(rel, app_dir).is_file() for rel in DB_FILES + SECRET_FILES):
        return True
    up = app_dir / "uploads"
    return up.is_dir() and any(e.is_file(follow_symlinks=False) for e in os.scandir(up))


def make_backup(dest=None, kind="manual", app_dir=APP_DIR, keep=None, now=None, locked=False):
    """백업을 하나 만들고 (폴더 경로, manifest, 지운 옛 백업 이름 목록, 경고 목록)을 돌려줌.

    locked=True: 부르는 쪽(복원)이 이미 백업 위치를 잠갔음.
    복원 직전 안전 백업(kind='before-restore')은 blog.db가 없어도 있는 것만 남기고, 망가진 DB는 파일째 남김.
    """
    if kind not in KINDS:
        raise BackupError(f"백업 종류가 올바르지 않아요: {kind}")
    app_dir = Path(app_dir)
    dest = ensure_private_dir(dest or default_dest(app_dir))
    if kind != "before-restore" and not source_path("blog.db", app_dir).is_file():
        raise BackupError("blog.db가 없어요. 블로그를 한 번 켠 뒤 백업하세요.")
    now = now or datetime.now()

    def work():
        clean_stale_tmp(dest)
        folder, manifest = _write_backup(dest, kind, app_dir, now)
        removed, warnings = rotate(dest, DEFAULT_KEEP if keep is None else keep) if kind != "before-restore" else ([], [])
        return folder, manifest, removed, warnings

    if locked:
        return work()
    with Lock(dest):
        return work()


def summary(folder, manifest):
    c = manifest["counts"]
    members = f" · 회원 {c['members']}명" if c.get("members") else ""
    return (f"{folder} (글 {c.get('posts') or 0}개{members} · 사진·파일 {c.get('uploads', 0)}개, "
            f"{human_size(manifest.get('total_size', 0))})")


def main(argv=None):
    ap = argparse.ArgumentParser(description="나만의 블로그 백업: 두 DB·키·설정·업로드를 함께 저장")
    ap.add_argument("--daily", action="store_true", help="오늘 백업이 이미 있으면 건너뜀")
    ap.add_argument("--keep", type=int, default=DEFAULT_KEEP, help=f"자동·수동 백업을 최근 몇 개 남길지 (기본 {DEFAULT_KEEP}, 0이면 지우지 않음)")
    ap.add_argument("--dest", help="백업 위치 (기본: 블로그 폴더의 backups/ 또는 MYBLOG_BACKUP_DIR)")
    ap.add_argument("--kind", choices=("auto", "manual"), help="목록에 보일 종류 (기본: --daily면 auto, 아니면 manual)")
    ap.add_argument("--quiet", action="store_true", help="건너뛸 때는 아무것도 출력하지 않음")
    ap.add_argument("--allow-root", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    dest = Path(args.dest) if args.dest else default_dest()
    if is_root() and not args.allow_root:
        print("root로 실행하면 백업 폴더의 주인이 root가 되어 블로그 사용자의 다음 백업·정리가 실패해요. "
              "블로그 사용자로 실행하세요 (예: sudo -u myblog python3 tools/backup.py …).", file=sys.stderr)
        return 1
    try:
        if args.daily:
            if not source_path("blog.db").is_file():
                if not args.quiet:
                    print("아직 백업할 블로그 자료가 없어요(블로그를 처음 켜는 중).")
                return 0
            if has_backup_today(dest):
                if not args.quiet:
                    print(f"오늘 백업이 이미 있어요: {dest}")
                return 0
        kind = args.kind or ("auto" if args.daily else "manual")
        folder, manifest, removed, warnings = make_backup(dest, kind=kind, keep=args.keep)
    except BackupBusy as e:
        print(str(e), file=sys.stderr)
        return 1
    except (BackupError, OSError) as e:
        print(f"백업하지 못했어요: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("백업을 그만뒀어요. 만들던 폴더는 지웠어요.", file=sys.stderr)
        return 130
    print(f"백업했어요: {summary(folder, manifest)}")
    if removed:
        print(f"오래된 백업 {len(removed)}개를 정리했어요 (최근 {args.keep}개만 남김).")
    for w in warnings:
        print(f"주의: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

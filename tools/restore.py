#!/usr/bin/env python3
"""나만의 블로그 복원 (008-backup-automation, 요구사항 NFR-16). 표준 라이브러리만 씁니다.

백업한 그때 그대로(블로그 DB·회원 DB·서명 키·업로드를 함께) 되돌립니다. 되돌리기 전에 지금 상태를 안전 백업으로 남기고,
중간에 실패하면 그 안전 백업으로 다시 돌려놓습니다. 이 컴퓨터의 설정 파일(deploy.config.json·oauth.config.php)은 그대로 둡니다
(없을 때만 백업에서 가져옴, 바꾸려면 --with-config).

    python3 tools/restore.py                             # 백업 목록과 사용법
    python3 tools/restore.py backups/2026-10-08_140512   # 그 백업으로 되돌림 (블로그·회원 서버를 끈 뒤)

공개 운영(VPS)에서는 두 서비스를 멈추고 블로그 사용자로 실행합니다:
    sudo systemctl stop my-blog php8.3-fpm
    sudo -u myblog python3 tools/restore.py --dest /var/backups/my-blog /var/backups/my-blog/<폴더>
    sudo systemctl start php8.3-fpm my-blog
"""
import argparse
import contextlib
import os
import re
import secrets
import shutil
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup  # noqa: E402  (같은 tools 폴더)

# 복원할 수 있는 경로만 (목록 파일이 바뀌어도 블로그 폴더 밖이나 다른 파일을 덮지 못하게)
DB_SIDE = {db + s for db in backup.DB_FILES for s in backup.DB_SIDE_SUFFIXES}
ALLOWED = set(backup.DB_FILES + backup.SECRET_FILES) | DB_SIDE
CONFIG_FILES = ("php-auth/oauth.config.php", "deploy.config.json")  # 이 컴퓨터의 설정: 기본은 그대로 둠
UPLOAD_RE = re.compile(r"uploads/[A-Za-z0-9][A-Za-z0-9._-]{0,200}")
DEFAULT_PHP_SOCKET = "/run/php/my-blog.sock"  # deploy/php-fpm-my-blog.conf.example


class RestoreError(Exception):
    pass


def owned_by_me(path):
    if not hasattr(os, "geteuid") or os.geteuid() == 0:
        return True
    return os.lstat(path).st_uid == os.geteuid()


def check_backup(folder):
    """목록 파일·경로·주인·확인값 검사. DB·키·설정이 다르면 거절, 업로드만 다르면 그 목록을 돌려줌 (manifest, 문제 업로드)."""
    folder = Path(folder)
    m = backup.read_manifest(folder)
    if not m:
        raise RestoreError(f"{folder} 에 백업 목록 파일(manifest.json)이 없거나 읽을 수 없어요.")
    if "blog.db" not in m["files"]:
        raise RestoreError("이 백업에는 blog.db가 없어요.")
    if not owned_by_me(folder) or not owned_by_me(folder / "manifest.json"):
        raise RestoreError(f"{folder} 의 주인이 내가 아니에요. 내가 만든 백업만 되돌릴 수 있어요.")
    bad_uploads = []
    for rel, info in m["files"].items():
        is_upload = bool(UPLOAD_RE.fullmatch(rel))
        if rel not in ALLOWED and not is_upload:
            raise RestoreError(f"이 백업은 손상됐거나 바뀌었어요: 알 수 없는 경로 {rel}")
        fp = folder / rel
        ok = fp.is_file() and not fp.is_symlink() and owned_by_me(fp) \
            and fp.stat().st_size == info.get("size") and backup.sha256_of(fp) == info.get("sha256")
        if not ok:
            if is_upload:
                bad_uploads.append(rel)
                continue
            raise RestoreError(f"이 백업은 손상됐거나 바뀌었어요: {rel} 의 확인값이 달라요(또는 파일이 없어요).")
    return m, bad_uploads


def busy_reasons(ports, php_socket=DEFAULT_PHP_SOCKET):
    """켜져 있는 서버 (localhost가 가리키는 모든 주소: 맥의 php -S localhost는 ::1에 열릴 수 있음)"""
    addrs = {"127.0.0.1", "::1"}
    try:
        addrs.update(info[4][0] for info in socket.getaddrinfo("localhost", None))
    except OSError:
        pass
    reasons = []
    for port in ports:
        for addr in sorted(addrs):
            family = socket.AF_INET6 if ":" in addr else socket.AF_INET
            try:
                with socket.socket(family, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect((addr, port))
                reasons.append(f"포트 {port}")
                break
            except OSError:
                continue
    if php_socket and os.path.exists(php_socket) and hasattr(socket, "AF_UNIX"):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(php_socket)
            reasons.append("회원 서버(PHP-FPM)")
        except (ConnectionRefusedError, FileNotFoundError):
            pass  # 소켓 파일만 남음 = 꺼짐
        except OSError:
            reasons.append(f"회원 서버(PHP-FPM) 소켓 {php_socket} 을 확인할 수 없음")
    return reasons


def stage_copy(src, target, mode):
    """대상과 같은 폴더에 안 보이는 임시 파일로 복사 (처음부터 mode 권한, 이미 있는 파일·링크를 따라가지 않음)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    while True:
        tmp = target.with_name(f".{target.name}.restore-{secrets.token_hex(4)}")
        try:
            fd = os.open(tmp, flags, mode)
            break
        except FileExistsError:
            continue
    try:
        with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
            shutil.copyfileobj(inp, out, 1 << 20)
        if mode == 0o600:
            os.chmod(tmp, 0o600)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise
    return tmp


def remove_quiet(path):
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)


def apply_backup(folder, m, app_dir, bad_uploads=(), mirror_all=False):
    """1단계: 바꿀 파일을 모두 임시 파일로 준비 → 2단계: 한꺼번에 바꿔 넣음. (안내 문구 목록) 반환.

    mirror_all=False(보통 복원): 설정 파일은 이 컴퓨터 것을 그대로(없을 때만 백업에서), 백업에 없는 키·설정은 지우지 않음.
    mirror_all=True(실패 뒤 안전 백업으로 되돌리기): 모든 파일을 그 백업 그대로.
    """
    folder, app_dir = Path(folder), Path(app_dir)
    notes, staged, ops = [], [], []
    try:
        # ---- 1단계: 준비 (실패해도 아무것도 바뀌지 않음) ----
        for rel in backup.DB_FILES:
            target = backup.source_path(rel, app_dir)
            if rel in m["files"]:
                tmp = stage_copy(folder / rel, target, 0o600)
                staged.append(tmp)
                sides = []
                for suffix in backup.DB_SIDE_SUFFIXES:  # 안전 백업이 망가진 DB를 파일째 남긴 경우
                    if rel + suffix in m["files"]:
                        st = stage_copy(folder / (rel + suffix), Path(str(target) + suffix), 0o600)
                        staged.append(st)
                        sides.append((st, Path(str(target) + suffix)))
                ops.append(("db", target, tmp, sides))
            else:
                ops.append(("remove_db", target, None, []))  # 두 DB는 항상 짝을 맞춤
        for rel in backup.SECRET_FILES:
            target = backup.source_path(rel, app_dir)
            if rel in m["files"]:
                if rel in CONFIG_FILES and target.exists() and not mirror_all:
                    notes.append(f"이 컴퓨터의 {rel} 는 그대로 두었어요 (백업의 것으로 바꾸려면 --with-config).")
                    continue
                tmp = stage_copy(folder / rel, target, 0o600)
                staged.append(tmp)
                ops.append(("file", target, tmp, []))
            elif mirror_all and target.exists():
                ops.append(("remove", target, None, []))
        uploads = app_dir / "uploads"
        uploads.mkdir(exist_ok=True)
        keep = set()
        for rel, info in m["files"].items():
            if not UPLOAD_RE.fullmatch(rel):
                continue
            name = rel.split("/", 1)[1]
            keep.add(name)
            target = uploads / name
            same = target.is_file() and not target.is_symlink() and target.stat().st_size == info["size"] \
                and backup.sha256_of(target) == info["sha256"]
            if same:
                continue
            if rel in bad_uploads:
                notes.append(f"백업 속 {name} 파일이 손상돼 되돌리지 못했어요 (그 사진·파일만 안 보일 수 있어요).")
                continue
            tmp = stage_copy(folder / rel, target, 0o644)
            staged.append(tmp)
            ops.append(("file", target, tmp, []))
        extra = [Path(e.path) for e in os.scandir(uploads)
                 if e.name not in keep and (e.is_file(follow_symlinks=False) or e.is_symlink())
                 and Path(e.path) not in staged]
    except BaseException:
        for t in staged:
            remove_quiet(t)
        raise
    # ---- 2단계: 바꿔 넣기 (이름 바꾸기·지우기만이라 빠름) ----
    try:
        for kind, target, tmp, sides in ops:
            if kind in ("db", "remove_db"):
                for suffix in backup.DB_SIDE_SUFFIXES:  # 낡은 WAL이 새 DB에 덧씌워지지 않게
                    remove_quiet(str(target) + suffix)
                if kind == "db":
                    os.replace(tmp, target)
                    for st, side_target in sides:
                        os.replace(st, side_target)
                else:
                    remove_quiet(target)
            elif kind == "file":
                os.replace(tmp, target)
            elif kind == "remove":
                remove_quiet(target)
        for p in extra:
            remove_quiet(p)
    except BaseException:
        for t in staged:
            remove_quiet(t)
        raise
    return notes


def restore(folder, app_dir=backup.APP_DIR, dest=None, log=print, checked=None, with_config=False):
    """백업 그대로 되돌림. (manifest, 안전 백업 폴더 또는 None, 안내 문구 목록) 반환.

    checked: 방금 check_backup()으로 확인한 (manifest, 문제 업로드). 없으면 여기서 확인.
    """
    folder, app_dir = Path(folder), Path(app_dir)
    m, bad_uploads = checked or check_backup(folder)
    dest = backup.ensure_private_dir(dest or backup.default_dest(app_dir))
    with contextlib.ExitStack() as stack:
        # 복원하는 동안 자동 백업이 끼어들어 섞인 상태를 백업하거나, 되돌리는 백업을 정리하지 못하게
        stack.enter_context(backup.Lock(dest))
        src_parent = folder.resolve().parent
        if src_parent != dest.resolve() and (src_parent / ".lock").exists():
            stack.enter_context(backup.Lock(src_parent))
        safety = None
        if backup.has_anything(app_dir):
            safety, safety_m, _, _ = backup.make_backup(dest, kind="before-restore", app_dir=app_dir, locked=True)
            log(f"지금 상태를 안전 백업으로 남겼어요: {safety}")
        try:
            notes = apply_backup(folder, m, app_dir, bad_uploads, mirror_all=with_config)
        except BaseException as e:
            if safety is None:
                raise RestoreError(f"되돌리지 못했어요: {e}")
            try:
                apply_backup(safety, safety_m, app_dir, mirror_all=True)
            except BaseException as e2:
                raise RestoreError(
                    f"되돌리다 실패했고({e}), 원래 상태로 돌려놓는 것도 실패했어요({e2}). "
                    f"서버를 켜지 말고 다음을 실행하세요: python3 tools/restore.py --with-config {safety}")
            raise RestoreError(f"되돌리지 못해 원래 상태로 돌려놓았어요: {e}")
    return m, safety, notes


def print_list(dest):
    items = backup.list_backups(dest)
    if not items:
        print(f"백업이 없어요: {dest}")
        return
    print(f"백업 위치: {dest}")
    kinds = {"auto": "자동", "manual": "수동", "before-restore": "복원 직전"}
    for p in reversed(items):
        m = backup.read_manifest(p) or {}
        c = m.get("counts", {})
        print(f"  {p.name:<38} {kinds.get(m.get('kind'), '?'):<5} 글 {c.get('posts') or 0:>4}개 · 회원 {c.get('members') or 0:>3}명 · "
              f"{backup.human_size(m.get('total_size', 0))}")
    print("\n되돌리려면: python3 tools/restore.py <백업 폴더>   (블로그와 회원 서버를 먼저 끄세요)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="나만의 블로그 복원: 백업한 그때 그대로 되돌림")
    ap.add_argument("folder", nargs="?", help="되돌릴 백업 폴더 (없으면 목록)")
    ap.add_argument("--yes", action="store_true", help="묻지 않고 바로 되돌림")
    ap.add_argument("--dest", help="백업 위치 (목록·안전 백업용, 기본: backups/ 또는 MYBLOG_BACKUP_DIR)")
    ap.add_argument("--with-config", action="store_true", help="이 컴퓨터의 설정 파일(deploy.config.json·oauth.config.php)도 백업 그대로")
    ap.add_argument("--ports", default=None, help="켜져 있으면 안 되는 서버 포트 (기본: PORT 또는 8000, 그리고 8080)")
    ap.add_argument("--php-socket", default=DEFAULT_PHP_SOCKET, help="공개 운영의 PHP-FPM 소켓 (있으면 꺼져 있는지 확인, ''이면 건너뜀)")
    ap.add_argument("--allow-root", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    dest = Path(args.dest) if args.dest else backup.default_dest()
    if not args.folder:
        print_list(dest)
        return 0
    if backup.is_root() and not args.allow_root:
        print("root로 실행하면 되돌린 파일의 주인이 root가 되어 블로그가 쓸 수 없어요. "
              "블로그 사용자로 실행하세요 (예: sudo -u myblog python3 tools/restore.py …).", file=sys.stderr)
        return 1
    folder = Path(args.folder)
    try:
        checked = check_backup(folder)
    except (RestoreError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    m, bad_uploads = checked
    ports = [int(p) for p in (args.ports or f"{os.environ.get('PORT') or 8000},8080").split(",") if p.strip()]
    busy = busy_reasons(ports, args.php_socket)
    if busy:
        print(f"서버가 켜져 있어요({', '.join(busy)}). 블로그와 회원 서버를 끈 뒤 다시 실행하세요.", file=sys.stderr)
        return 1
    c = m.get("counts", {})
    print(f"되돌릴 백업: {folder.name} ({m.get('created_at')}, 글 {c.get('posts') or 0}개 · 회원 {c.get('members') or 0}명 · "
          f"사진·파일 {c.get('uploads') or 0}개)")
    print("블로그 DB·회원 DB·서명 키·업로드가 이 백업 그대로 바뀌어요. 되돌리기 전에 지금 상태를 안전 백업으로 남겨요.")
    if not args.with_config:
        print("이 컴퓨터의 설정 파일(deploy.config.json·oauth.config.php)은 그대로 둬요.")
    if bad_uploads:
        print(f"주의: 백업 속 사진·파일 {len(bad_uploads)}개가 손상돼 있어요. 그 파일만 빼고 되돌려요.")
    if not args.yes:
        try:
            answer = input("되돌릴까요? (y/N) ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes", "예", "ㅇ"):
            print("그만뒀어요. 아무것도 바뀌지 않았어요.")
            return 1
    try:
        _, safety, notes = restore(folder, dest=dest, checked=checked, with_config=args.with_config)
    except (RestoreError, backup.BackupError, OSError) as e:
        print(str(e) if isinstance(e, RestoreError) else f"되돌리지 못했어요: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("그만뒀어요.", file=sys.stderr)
        return 130
    for n in notes:
        print(n)
    print("되돌렸어요." + (f" 되돌리기 전 상태는 {safety} 에 있어요." if safety else "") + " 블로그를 다시 켜세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

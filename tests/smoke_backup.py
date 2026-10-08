"""008-backup-automation 점검 (표준 라이브러리만): tools/backup.py · tools/restore.py.

실제 blog.db를 건드리지 않도록 server.py·static·tools를 임시 폴더에 복사해 그 안에서 백업·복원합니다(php 없이, 회원 DB는 직접 만듦).

    python3 tests/smoke_backup.py
"""
import base64
import contextlib
import hashlib
import http.cookiejar
import json
import os
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "Smoke2026backup"
PNG = "data:image/png;base64," + base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc00000030101005d8b7dd30000000049454e44ae426082")).decode()
CLEAR_ENV = ("BLOG_PASSWORD", "AUTH_URL", "BLOG_URL", "HOST", "PORT", "MYBLOG_CONFIG", "MYBLOG_BACKUP_DIR")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class App:
    """임시 폴더의 블로그 하나 (서버 켜고 끄기, 도구 실행)"""

    def __init__(self, with_php=True):
        self.dir = Path(tempfile.mkdtemp(prefix="myblog-008-"))
        shutil.copy2(ROOT / "server.py", self.dir)
        shutil.copytree(ROOT / "static", self.dir / "static")
        shutil.copytree(ROOT / "tools", self.dir / "tools")
        self.port = free_port()
        self.proc = None
        self.env = {k: v for k, v in os.environ.items() if k not in CLEAR_ENV}
        self.php_conn = None
        if with_php:
            (self.dir / "php-auth" / "db").mkdir(parents=True)
            (self.dir / "php-auth" / "db" / "sso.key").write_text("ab" * 32)
            os.chmod(self.dir / "php-auth" / "db" / "sso.key", 0o600)
            (self.dir / "php-auth" / "oauth.config.php").write_text("<?php return ['naver' => ['client_id' => 'x']];\n")
            (self.dir / "deploy.config.json").write_text(json.dumps({"public_mode": False}))

    def start(self):
        env = dict(self.env, PORT=str(self.port), HOST="127.0.0.1", BLOG_PASSWORD=PASSWORD)
        self.proc = subprocess.Popen([sys.executable, "-B", "server.py"], cwd=self.dir, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        end = time.time() + 15
        while time.time() < end:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/blog", timeout=1) as r:
                    if r.status == 200:
                        return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("블로그 서버가 켜지지 않음")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None

    def login(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        assert self.api("POST", "login", {"username": "admin", "password": PASSWORD})[0] == 200

    def api(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with self.op.open(req) as r:
                return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")

    def tool(self, name, *args, stdin=None):
        if hasattr(os, "geteuid") and os.geteuid() == 0 and "--no-allow-root" not in args:
            args += ("--allow-root",)  # 시험 환경이 root일 때만 (두 도구 모두 root 실행을 막음)
        args = tuple(a for a in args if a != "--no-allow-root")
        r = subprocess.run([sys.executable, "-B", f"tools/{name}.py", *args], cwd=self.dir, env=self.env,
                           capture_output=True, text=True, input=stdin, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def make_php_db(self, members=("mate1", "mate2"), wal_member="walonly"):
        """회원 DB(WAL 모드)를 만들고, 마지막 회원은 합치지 않은 WAL에만 남긴 채 연결을 열어 둠"""
        db = self.dir / "php-auth" / "db" / "sqlite.db"
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE)")
        conn.executemany("INSERT INTO users (username) VALUES (?)", [(m,) for m in members])
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("INSERT INTO users (username) VALUES (?)", (wal_member,))
        conn.commit()
        self.php_conn = conn  # 닫으면 합쳐지므로 열어 둠
        return db

    def posts(self):
        with contextlib.closing(sqlite3.connect(self.dir / "blog.db")) as c, c:
            return c.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    def cleanup(self):
        self.stop()
        if self.php_conn:
            self.php_conn.close()
        shutil.rmtree(self.dir, ignore_errors=True)


class Backup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App()
        cls.app.start()
        cls.app.login()
        cls.uploads = [cls.app.api("POST", "upload", {"data": PNG, "name": f"b{i}.png"})[1]["url"] for i in range(2)]
        s, r = cls.app.api("POST", "posts", {"type": "daily", "title": "백업될 글", "content": f"![]({cls.uploads[0]})",
                                             "category": "", "tags": "", "is_public": True})
        assert s in (200, 201), r
        cls.post_id = r["id"]
        cls.php_db = cls.app.make_php_db()
        cls.dest = cls.app.dir / "backups"

    @classmethod
    def tearDownClass(cls):
        cls.app.cleanup()

    def backups(self, regular_only=False):
        import re
        pat = r"^\d{4}-\d{2}-\d{2}_\d{6}(-\d+)?$" if regular_only else r"^\d{4}-\d{2}-\d{2}_\d{6}(-\d+)?(_before-restore)?$"
        return sorted(p for p in self.dest.iterdir() if p.is_dir() and re.match(pat, p.name)) if self.dest.exists() else []

    def latest(self):
        sys.path.insert(0, str(self.app.dir / "tools"))
        import backup  # noqa
        return sorted(self.backups(True), key=backup.backup_sort_key)[-1]

    def test_1_contents_permissions_wal(self):
        self.assertTrue(Path(str(self.php_db) + "-wal").stat().st_size > 0, "시험 조건: 회원 DB에 합치지 않은 WAL이 있음")
        code, out = self.app.tool("backup")  # 서버가 켜진 채로
        self.assertEqual(code, 0, out)
        self.assertIn("백업했어요", out)
        folder = self.latest()
        m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        want = {"blog.db", "php-auth/db/sqlite.db", "php-auth/db/sso.key", "php-auth/oauth.config.php", "deploy.config.json"}
        self.assertTrue(want <= set(m["files"]), m["files"].keys())
        self.assertEqual({k for k in m["files"] if k.startswith("uploads/")},
                         {"uploads/" + u.rsplit("/", 1)[1] for u in self.uploads})
        for rel, info in m["files"].items():
            self.assertEqual(sha(folder / rel), info["sha256"], rel)
        # 두 DB 무결성 + WAL에만 있던 회원도 들어감
        for rel in ("blog.db", "php-auth/db/sqlite.db"):
            with contextlib.closing(sqlite3.connect(folder / rel)) as c, c:
                self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with contextlib.closing(sqlite3.connect(folder / "php-auth/db/sqlite.db")) as c, c:
            names = [r[0] for r in c.execute("SELECT username FROM users ORDER BY id")]
        self.assertEqual(names, ["mate1", "mate2", "walonly"])
        self.assertFalse((folder / "php-auth/db/sqlite.db-wal").exists(), "사본은 파일 하나로 완결")
        self.assertEqual(m["counts"]["posts"], self.app.posts())
        self.assertEqual(m["counts"]["members"], 3)
        # 권한: 위치·폴더 700, 비밀·DB·목록 600
        self.assertEqual(mode(self.dest), 0o700)
        self.assertEqual(mode(folder), 0o700)
        for rel in want | {"manifest.json"}:
            self.assertEqual(mode(folder / rel), 0o600, rel)
        self.assertEqual(sha(folder / "php-auth/db/sso.key"), sha(self.app.dir / "php-auth/db/sso.key"))

    def test_2_daily_and_rotation(self):
        self.app.tool("backup")
        n = len(self.backups(True))
        code, out = self.app.tool("backup", "--daily")
        self.assertEqual(code, 0, out)
        self.assertIn("오늘 백업이 이미 있어요", out)
        self.assertEqual(len(self.backups(True)), n, "오늘 것이 있으면 새로 만들지 않음")
        code, out = self.app.tool("backup", "--daily", "--quiet")
        self.assertEqual((code, out.strip()), (0, ""))
        # 어제 백업만 있으면 새로 만듦
        for p in self.backups(True):
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            p.rename(p.with_name(yesterday + p.name[10:]))
        code, out = self.app.tool("backup", "--daily")
        self.assertIn("백업했어요", out)
        # 정리: 일반 백업은 최근 3개만, 안전 백업·다른 폴더는 그대로
        (self.dest / "내 메모").mkdir()
        safe = self.dest / "2000-01-01_000000_before-restore"
        shutil.copytree(self.backups(True)[0], safe)
        for _ in range(4):
            self.assertEqual(self.app.tool("backup", "--keep", "3")[0], 0)
        self.assertEqual(len(self.backups(True)), 3)
        self.assertTrue(safe.exists() and (self.dest / "내 메모").exists())
        self.assertFalse(list(self.dest.glob(".tmp-*")), "임시 폴더 없음")

    def test_3_upload_hard_links(self):
        self.app.tool("backup")
        a = self.latest()
        self.app.tool("backup")
        b = self.latest()
        name = self.uploads[0].rsplit("/", 1)[1]
        self.assertEqual((a / "uploads" / name).stat().st_ino, (b / "uploads" / name).stat().st_ino, "바뀌지 않은 업로드는 하드 링크")
        new = self.app.api("POST", "upload", {"data": PNG, "name": "new.png"})[1]["url"].rsplit("/", 1)[1]
        self.app.tool("backup")
        c = self.latest()
        m = json.loads((c / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["counts"]["uploads_copied"], 1, "새 파일만 복사")
        self.assertTrue((c / "uploads" / new).is_file())
        self.assertEqual((b / "uploads" / name).stat().st_ino, (c / "uploads" / name).stat().st_ino)

    def test_4_restore_refuses_running_server(self):
        self.app.tool("backup")
        folder = self.latest()
        before = sha(self.app.dir / "blog.db")
        n = len(self.backups())
        code, out = self.app.tool("restore", str(folder), "--yes", "--ports", str(self.app.port))
        self.assertEqual(code, 1, out)
        self.assertIn("서버가 켜져 있어요", out)
        self.assertEqual(sha(self.app.dir / "blog.db"), before)
        self.assertEqual(len(self.backups()), n, "안전 백업도 만들지 않음")

    def test_5_restore_refuses_tampered(self):
        self.app.tool("backup")
        good = self.latest()
        bad = self.dest / "1999-01-01_000000"
        shutil.copytree(good, bad)
        (bad / "php-auth/db/sso.key").write_text("tampered")
        before = sha(self.app.dir / "blog.db")
        code, out = self.app.tool("restore", str(bad), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 1, out)
        self.assertIn("손상됐거나 바뀌었어요", out)
        # 목록 파일에 블로그 폴더 밖 경로를 넣어도 거절
        shutil.rmtree(bad)
        shutil.copytree(good, bad)
        m = json.loads((bad / "manifest.json").read_text(encoding="utf-8"))
        (bad / "evil.txt").write_text("x")
        m["files"]["../evil.txt"] = {"size": 1, "sha256": sha(bad / "evil.txt")}
        (bad / "manifest.json").write_text(json.dumps(m))
        code, out = self.app.tool("restore", str(bad), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 1, out)
        self.assertIn("알 수 없는 경로", out)
        self.assertEqual(sha(self.app.dir / "blog.db"), before)
        shutil.rmtree(bad)

    def test_6_restore_roundtrip(self):
        code, out = self.app.tool("backup")
        folder = self.latest()
        m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        posts = self.app.posts()
        key = sha(self.app.dir / "php-auth/db/sso.key")
        self.app.stop()
        self.app.php_conn.close()
        self.app.php_conn = None
        # 사고: 글 삭제, 업로드 추가, 키 바뀜, SNS 설정 지움, 낡은 WAL 찌꺼기
        with contextlib.closing(sqlite3.connect(self.app.dir / "blog.db")) as c, c:
            c.execute("DELETE FROM posts WHERE id = ?", (self.post_id,))
        (self.app.dir / "uploads" / ("f" * 32 + ".png")).write_bytes(b"extra")
        (self.app.dir / "php-auth/db/sso.key").write_text("cd" * 32)
        (self.app.dir / "php-auth/oauth.config.php").unlink()
        (self.app.dir / "blog.db-wal").write_bytes(b"garbage")
        with contextlib.closing(sqlite3.connect(self.app.dir / "php-auth/db/sqlite.db")) as c, c:
            c.execute("INSERT INTO users (username) VALUES ('after-backup')")
        code, out = self.app.tool("restore")
        self.assertEqual(code, 0)
        self.assertIn(folder.name, out, "목록에 보임")
        code, out = self.app.tool("restore", str(folder), "--ports", str(free_port()), stdin="n\n")
        self.assertEqual(code, 1)
        self.assertIn("아무것도 바뀌지 않았어요", out)
        self.assertEqual(self.app.posts(), posts - 1)
        code, out = self.app.tool("restore", str(folder), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 0, out)
        self.assertIn("되돌렸어요", out)
        self.assertEqual(self.app.posts(), posts, "지운 글이 돌아옴")
        self.assertEqual(sha(self.app.dir / "php-auth/db/sso.key"), key)
        self.assertTrue((self.app.dir / "php-auth/oauth.config.php").is_file())
        self.assertFalse((self.app.dir / "blog.db-wal").exists(), "낡은 WAL 지움")
        self.assertFalse((self.app.dir / "uploads" / ("f" * 32 + ".png")).exists(), "백업에 없던 업로드 치움")
        self.assertEqual(sorted(p.name for p in (self.app.dir / "uploads").iterdir()),
                         sorted(k.split("/", 1)[1] for k in m["files"] if k.startswith("uploads/")))
        with contextlib.closing(sqlite3.connect(self.app.dir / "php-auth/db/sqlite.db")) as c, c:
            self.assertEqual([r[0] for r in c.execute("SELECT username FROM users ORDER BY id")], ["mate1", "mate2", "walonly"])
        # 안전 백업에는 되돌리기 전 상태
        safety = [p for p in self.backups() if p.name.endswith("_before-restore") and not p.name.startswith("2000")][-1]
        sm = json.loads((safety / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(sm["kind"], "before-restore")
        self.assertIn("uploads/" + "f" * 32 + ".png", sm["files"])
        self.assertIn("php-auth/oauth.config.php", sm["missing"])
        self.assertEqual(sm["counts"]["members"], 4)
        # 서버를 다시 켜면 그대로 동작
        self.app.start()
        self.app.login()
        s, p = self.app.api("GET", f"posts/{self.post_id}")
        self.assertEqual((s, p.get("title")), (200, "백업될 글"))


class MinimalApp(unittest.TestCase):
    """회원 서버를 한 번도 켜지 않아 회원 DB·키·설정·업로드가 없는 블로그"""

    def test_missing_optional_files(self):
        app = App(with_php=False)
        try:
            code, out = app.tool("backup", "--daily")
            self.assertEqual(code, 0, out)
            self.assertIn("아직 백업할 블로그 자료가 없어요", out)
            code, out = app.tool("backup")
            self.assertEqual(code, 1)
            self.assertIn("blog.db가 없어요", out)
            app.start()
            app.stop()
            code, out = app.tool("backup")
            self.assertEqual(code, 0, out)
            folder = next((app.dir / "backups").glob("20*"))
            m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(set(m["missing"]) >= {"php-auth/db/sqlite.db", "php-auth/db/sso.key",
                                                  "php-auth/oauth.config.php", "deploy.config.json"}, m["missing"])
            # 백업에 없던 설정 파일은 기본으로 그대로 둠 (이 컴퓨터의 설정), --with-config면 백업 그대로(지움)
            (app.dir / "php-auth").mkdir(exist_ok=True)
            (app.dir / "php-auth/oauth.config.php").write_text("<?php return [];")
            code, out = app.tool("restore", str(folder), "--yes", "--ports", str(free_port()))
            self.assertEqual(code, 0, out)
            self.assertTrue((app.dir / "php-auth/oauth.config.php").exists())
            code, out = app.tool("restore", str(folder), "--yes", "--with-config", "--ports", str(free_port()))
            self.assertEqual(code, 0, out)
            self.assertFalse((app.dir / "php-auth/oauth.config.php").exists())
        finally:
            app.cleanup()


class RestoreRobustness(unittest.TestCase):
    """복원이 실패하거나 지금 자료가 망가져 있어도 안전한지 (서버는 끈 상태)"""

    def setUp(self):
        self.app = App()
        self.app.start()
        self.app.login()
        self.upload = self.app.api("POST", "upload", {"data": PNG, "name": "r.png"})[1]["url"].rsplit("/", 1)[1]
        self.app.stop()
        self.app.make_php_db()
        self.app.php_conn.close()
        self.app.php_conn = None
        code, out = self.app.tool("backup")
        assert code == 0, out
        self.dest = self.app.dir / "backups"
        self.folder = sorted(self.dest.glob("20*"))[-1]
        sys.path.insert(0, str(self.app.dir / "tools"))
        for name in ("backup", "restore"):
            sys.modules.pop(name, None)
        import backup as backup_mod  # noqa
        import restore as restore_mod  # noqa
        self.backup_mod, self.restore_mod = backup_mod, restore_mod

    def tearDown(self):
        sys.path.remove(str(self.app.dir / "tools"))
        for name in ("backup", "restore"):
            sys.modules.pop(name, None)
        self.app.cleanup()

    def add_member(self, name):
        with contextlib.closing(sqlite3.connect(self.app.dir / "php-auth/db/sqlite.db")) as c, c:
            c.execute("INSERT INTO users (username) VALUES (?)", (name,))

    def members(self, db):
        with contextlib.closing(sqlite3.connect(db)) as c:
            return [r[0] for r in c.execute("SELECT username FROM users ORDER BY id")]

    def dump(self, db):
        with contextlib.closing(sqlite3.connect(db)) as c:
            return "\n".join(c.iterdump())

    def safety(self):
        return sorted(p for p in self.dest.iterdir() if p.name.endswith("_before-restore"))

    def test_missing_blog_db_still_makes_safety(self):
        self.add_member("after")
        (self.app.dir / "uploads" / ("e" * 32 + ".png")).write_bytes(b"new upload")
        (self.app.dir / "blog.db").rename(self.app.dir / "blog.db.moved")
        code, out = self.app.tool("restore", str(self.folder), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 0, out)
        [safe] = self.safety()
        sm = json.loads((safe / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("after", self.members(safe / "php-auth/db/sqlite.db"), "되돌리기 전 회원이 안전 백업에 남음")
        self.assertIn("uploads/" + "e" * 32 + ".png", sm["files"])
        self.assertIn("blog.db", sm["missing"])

    def test_corrupt_live_db_raw_safety(self):
        (self.app.dir / "blog.db").write_bytes(b"this is not a database" * 100)
        code, out = self.app.tool("restore", str(self.folder), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 0, out)
        with contextlib.closing(sqlite3.connect(self.app.dir / "blog.db")) as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        [safe] = self.safety()
        sm = json.loads((safe / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(sm["raw_copies"], ["blog.db"], "망가진 DB는 파일째 남김")
        self.assertEqual((safe / "blog.db").read_bytes(), b"this is not a database" * 100)

    def test_failure_midway_rolls_back(self):
        self.add_member("after")
        before_blog = self.dump(self.app.dir / "blog.db")
        real_replace = os.replace
        state = {"failed": False}

        def flaky_replace(src, dst, *a, **k):
            if not state["failed"] and str(dst).endswith("sqlite.db"):
                state["failed"] = True
                raise OSError(28, "No space left on device")
            return real_replace(src, dst, *a, **k)

        self.restore_mod.os.replace = flaky_replace
        try:
            with self.assertRaises(self.restore_mod.RestoreError) as cm:
                self.restore_mod.restore(self.folder, app_dir=self.app.dir, dest=self.dest, log=lambda *_: None)
        finally:
            self.restore_mod.os.replace = real_replace
        self.assertIn("원래 상태로 돌려놓았어요", str(cm.exception))
        self.assertEqual(self.dump(self.app.dir / "blog.db"), before_blog, "blog.db 내용도 되돌리기 전 그대로")
        self.assertIn("after", self.members(self.app.dir / "php-auth/db/sqlite.db"))
        leftovers = [p for p in self.app.dir.rglob(".*restore-*")]
        self.assertEqual(leftovers, [], "임시 파일 없음")

    def test_lock_blocks_restore(self):
        before = sha(self.app.dir / "blog.db")
        with self.backup_mod.Lock(self.dest):
            code, out = self.app.tool("restore", str(self.folder), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 1, out)
        self.assertIn("진행 중", out)
        self.assertEqual(sha(self.app.dir / "blog.db"), before)
        self.assertEqual(self.safety(), [])

    def test_config_kept_unless_with_config(self):
        cfg = self.app.dir / "deploy.config.json"
        cfg.write_text(json.dumps({"public_mode": True, "blog_url": "https://blog.example.com"}))
        code, out = self.app.tool("restore", str(self.folder), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 0, out)
        self.assertIn("그대로 두었어요", out)
        self.assertTrue(json.loads(cfg.read_text())["public_mode"], "공개 서버 설정이 바뀌지 않음")
        code, out = self.app.tool("restore", str(self.folder), "--yes", "--with-config", "--ports", str(free_port()))
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(cfg.read_text()), {"public_mode": False})

    def test_corrupt_upload_in_backup(self):
        rel = "uploads/" + self.upload
        (self.folder / rel).write_bytes(b"damaged")  # 하드 링크라면 같은 파일을 쓰는 다른 백업도 함께 바뀜
        # 다음 백업은 망가진 파일을 이어 쓰지 않고 지금 파일에서 새로 복사
        code, out = self.app.tool("backup")
        self.assertEqual(code, 0, out)
        newest = sorted((p for p in self.dest.glob("20*") if p != self.folder), key=lambda p: p.name)[-1]
        self.assertNotEqual((newest / rel).stat().st_ino, (self.folder / rel).stat().st_ino)
        self.assertEqual(sha(newest / rel), sha(self.app.dir / rel))
        # 망가진 업로드가 있는 백업도 나머지는 되돌림 (그 파일만 빠짐)
        (self.app.dir / rel).unlink()
        self.add_member("after")
        code, out = self.app.tool("restore", str(self.folder), "--yes", "--ports", str(free_port()))
        self.assertEqual(code, 0, out)
        self.assertIn("손상돼", out)
        self.assertNotIn("after", self.members(self.app.dir / "php-auth/db/sqlite.db"))

    def test_unsafe_dest_and_root(self):
        shared = Path(tempfile.mkdtemp(prefix="shared-"))
        try:
            os.chmod(shared, 0o777)
            code, out = self.app.tool("backup", "--dest", str(shared))
            self.assertEqual(code, 1, out)
            self.assertIn("다른 사람도 쓸 수 있는", out)
            self.assertEqual(mode(shared), 0o777, "남의 폴더 권한은 바꾸지 않음")
        finally:
            shutil.rmtree(shared, ignore_errors=True)
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            code, out = self.app.tool("backup", "--no-allow-root")
            self.assertEqual(code, 1)
            self.assertIn("root로 실행하면", out)

    def test_busy_port_on_ipv6_localhost(self):
        try:
            srv = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            srv.bind(("::1", 0))
        except OSError:
            self.skipTest("이 환경은 IPv6가 없어요")
        srv.listen(1)
        try:
            port = srv.getsockname()[1]
            code, out = self.app.tool("restore", str(self.folder), "--yes", "--ports", str(port))
            self.assertEqual(code, 1, out)
            self.assertIn("서버가 켜져 있어요", out)
        finally:
            srv.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

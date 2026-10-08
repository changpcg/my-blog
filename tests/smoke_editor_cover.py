"""005-editor-publish-flow 점검 (표준 라이브러리만): 글의 대표 사진(cover) 저장 규칙.

실제 blog.db를 건드리지 않도록 server.py·static을 임시 폴더에 복사해 빈 포트에 블로그를 띄웁니다.

    python3 tests/smoke_editor_cover.py

발행 설정 창·넓은 편집 화면·나가기 경고는 specs/005-editor-publish-flow/quickstart.md의 화면 점검으로 확인합니다.
"""
import base64
import http.cookiejar
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Smoke2026editor"
PNG = "data:image/png;base64," + base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc00000030101005d8b7dd30000000049454e44ae426082")).decode()
CLEAR_ENV = ("BLOG_PASSWORD", "AUTH_URL", "BLOG_URL", "HOST", "PORT", "MYBLOG_CONFIG")
COVER_ERR = "대표 사진은 본문에 있는 사진 중에서 골라 주세요."


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Client:
    def __init__(self, base):
        self.base = base
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def api(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + "/api/" + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with self.op.open(req) as r:
                return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")


class EditorCover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="myblog-005-")
        shutil.copy2(os.path.join(ROOT, "server.py"), cls.dir)
        shutil.copytree(os.path.join(ROOT, "static"), os.path.join(cls.dir, "static"))
        cls.port = free_port()
        cls.proc = cls.start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.admin = Client(cls.base)
        s, _ = cls.admin.api("POST", "login", {"username": "admin", "password": PASSWORD})
        assert s == 200, "관리자 로그인 실패"
        cls.up = [cls.admin.api("POST", "upload", {"data": PNG, "name": f"c{i}.png"})[1]["url"] for i in range(3)]

    @classmethod
    def start(cls):
        env = {k: v for k, v in os.environ.items() if k not in CLEAR_ENV}
        env.update({"PORT": str(cls.port), "HOST": "127.0.0.1", "BLOG_PASSWORD": PASSWORD})
        proc = subprocess.Popen([sys.executable, "-B", "server.py"], cwd=cls.dir, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        # 포트를 먼저 잡고 DB 준비(init_db)를 한 뒤 요청을 받으므로, 실제 응답이 올 때까지 기다림
        end = time.time() + 15
        while time.time() < end:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/api/blog", timeout=1) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        return proc

    @classmethod
    def stop(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        shutil.rmtree(cls.dir, ignore_errors=True)

    NOT_SENT = object()

    def post(self, title, content, cover=NOT_SENT, method="POST", pid=None):
        body = {"type": "insight", "title": title, "content": content, "category": "마케팅", "tags": "", "is_public": True}
        if cover is not self.NOT_SENT:
            body["cover"] = cover
        return self.admin.api(method, "posts" + (f"/{pid}" if pid else ""), body)

    def thumb(self, pid):
        s, r = self.admin.api("GET", "posts?size=100")
        self.assertEqual(s, 200)
        return {p["id"]: p for p in r["posts"]}[pid]["thumbnail"]

    def test_1_chosen_cover(self):
        a, b, _ = self.up
        s, r = self.post("두 번째 사진을 대표로", f"![1]({a})\n\n![2]({b})", cover=b)
        self.assertIn(s, (200, 201), r)
        self.assertEqual(self.thumb(r["id"]), b)
        s, p = self.admin.api("GET", f"posts/{r['id']}")
        self.assertEqual(p["cover"], b, "글 보기는 고른 값을 그대로 줌(편집 화면용)")
        # 같은 카테고리 다른 글의 관련 글 카드에도 고른 사진
        s, other = self.post("관련 글 확인용", "본문")
        s, p = self.admin.api("GET", f"posts/{other['id']}")
        rel = {x["id"]: x for x in p["related"]}
        self.assertEqual(rel[r["id"]]["thumbnail"], b)

    def test_2_none_and_auto(self):
        a, b, _ = self.up
        s, r = self.post("사진 없이", f"![1]({a})", cover="none")
        self.assertIn(s, (200, 201), r)
        self.assertIsNone(self.thumb(r["id"]))
        s, r2 = self.post("자동", f"![1]({a})\n![2]({b})", cover="")
        self.assertEqual(self.thumb(r2["id"]), a)
        s, r3 = self.post("값 없음 = 자동", f"![2]({b})")
        self.assertEqual(self.thumb(r3["id"]), b)

    def test_3_rejects_bad_cover(self):
        a, b, c = self.up
        bad = [c, "https://example.com/x.png", "/uploads/../etc/passwd.png", "javascript:alert(1)", 123, ["x"], None]
        before = self.admin.api("GET", "posts?size=100")[1]["total"]
        for value in bad:
            s, r = self.post("잘못된 대표 사진", f"![1]({a})", cover=value)
            self.assertEqual(s, 400, f"{value!r} 는 거절")
            self.assertEqual(r.get("error"), COVER_ERR)
        self.assertEqual(self.admin.api("GET", "posts?size=100")[1]["total"], before, "거절된 글은 저장 안 됨")
        # 코드 블록 속 사진은 본문 사진이 아님
        s, r = self.post("코드 속 사진", f"```\n![x]({c})\n```\n![1]({a})", cover=c)
        self.assertEqual(s, 400)

    def test_4_removed_cover_falls_back(self):
        a, b, _ = self.up
        s, r = self.post("대표 사진 지우기", f"![1]({a})\n![2]({b})", cover=b)
        pid = r["id"]
        self.assertEqual(self.thumb(pid), b)
        # 고른 사진(b)을 본문에서 빼고 저장: 그대로 b를 보내면 거절, 자동으로 보내면 저장
        s, _ = self.post("대표 사진 지우기", f"![1]({a})", cover=b, method="PUT", pid=pid)
        self.assertEqual(s, 400)
        s, _ = self.post("대표 사진 지우기", f"![1]({a})", cover="", method="PUT", pid=pid)
        self.assertEqual(s, 200)
        self.assertEqual(self.thumb(pid), a)

    def test_5_old_db_gets_cover_column(self):
        """예전 blog.db(cover 칸 없음)로 켜도 칸이 더해지고 글은 그대로"""
        self.stop()
        db = os.path.join(self.dir, "blog.db")
        with sqlite3.connect(db) as conn:
            n = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            cols = [r[1] for r in conn.execute("PRAGMA table_info(posts)")]
            self.assertIn("cover", cols)
            # 칸을 지운 예전 모양으로 되돌림 (SQLite 3.35+ DROP COLUMN, 안 되면 건너뜀)
            try:
                conn.execute("ALTER TABLE posts DROP COLUMN cover")
            except sqlite3.OperationalError:
                self.skipTest("이 SQLite는 DROP COLUMN을 못 해요")
        type(self).proc = self.start()
        with sqlite3.connect(db) as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(posts)")]
            self.assertIn("cover", cols)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], n)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM posts WHERE cover != ''").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

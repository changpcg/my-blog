"""006-blog-design-skin 점검 (표준 라이브러리만): 대표 색·사이드바 항목 저장 규칙, 인기 글, 끈 항목 자료 빼기.

실제 blog.db를 건드리지 않도록 server.py·static을 임시 폴더에 복사해 빈 포트에 블로그를 띄웁니다.

    python3 tests/smoke_blog_design.py

꾸미기 화면·색 적용·인기 글 모양은 specs/006-blog-design-skin/quickstart.md의 화면 점검으로 확인합니다.
"""
import base64
import hashlib
import http.cookiejar
import json
import os
import secrets
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
PASSWORD = "Smoke2026design"
MEMBER_PW = "member-pass-2026"
PNG = "data:image/png;base64," + base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc00000030101005d8b7dd30000000049454e44ae426082")).decode()
CLEAR_ENV = ("BLOG_PASSWORD", "AUTH_URL", "BLOG_URL", "HOST", "PORT", "MYBLOG_CONFIG")
SKIN_ERR = "목록에 있는 색만 고를 수 있어요."
WIDGET_ERR = "사이드바 항목을 다시 골라 주세요."
ALL_WIDGETS = ["room", "types", "popular", "tags", "comments", "stats"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def hash_pw(pw):
    """server.py hash_pw와 같은 형식 (시험용 회원을 DB에 직접 넣을 때)"""
    salt = secrets.token_hex(8)
    return f"{salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 100_000).hex()}"


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


class BlogDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="myblog-006-")
        shutil.copy2(os.path.join(ROOT, "server.py"), cls.dir)
        shutil.copytree(os.path.join(ROOT, "static"), os.path.join(cls.dir, "static"))
        cls.db = os.path.join(cls.dir, "blog.db")
        cls.port = free_port()
        cls.proc = cls.start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.admin = Client(cls.base)
        s, _ = cls.admin.api("POST", "login", {"username": "admin", "password": PASSWORD})
        assert s == 200, "관리자 로그인 실패"
        # 비교를 쉽게: 예시 글 조회수는 0으로
        with sqlite3.connect(cls.db) as conn:
            conn.execute("UPDATE posts SET views = 0")
            conn.execute(
                "INSERT INTO users (username, nickname, password_hash, role, created_at, blog_title, blog_desc, avatar, categories) "
                "VALUES ('designmate', '디자인메이트', ?, 'member', '2026-10-08T00:00:00', '메이트 블로그', '', '', '[]')",
                (hash_pw(MEMBER_PW),),
            )
        cls.member = Client(cls.base)
        s, _ = cls.member.api("POST", "login", {"username": "designmate", "password": MEMBER_PW})
        assert s == 200, "시험 회원 로그인 실패"
        cls.guest = Client(cls.base)
        cls.img = cls.admin.api("POST", "upload", {"data": PNG, "name": "pop.png"})[1]["url"]

    @classmethod
    def start(cls):
        env = {k: v for k, v in os.environ.items() if k not in CLEAR_ENV}
        env.update({"PORT": str(cls.port), "HOST": "127.0.0.1", "BLOG_PASSWORD": PASSWORD})
        proc = subprocess.Popen([sys.executable, "-B", "server.py"], cwd=cls.dir, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
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

    def write(self, who, title, views, public=True, content="본문", type_="insight"):
        # 관리자 블로그는 카테고리가 있어 골라야 함, 시험 회원 블로그는 카테고리가 없음
        category = "마케팅" if who is self.admin else ""
        s, r = who.api("POST", "posts", {"type": type_, "title": title, "content": content, "category": category,
                                          "tags": "디자인", "is_public": public})
        self.assertIn(s, (200, 201), r)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE posts SET views = ? WHERE id = ?", (views, r["id"]))
        return r["id"]

    def test_1_skin_saved(self):
        s, r = self.admin.api("PUT", "me", {"skin": "blue"})
        self.assertEqual(s, 200, r)
        self.assertEqual(self.guest.api("GET", "blogs/admin")[1]["skin"], "blue", "방문자에게도 그 색")
        self.assertEqual(self.admin.api("GET", "blog")[1]["user"]["skin"], "blue", "로그인 사용자 정보에도")
        self.assertEqual(self.guest.api("GET", "blogs/designmate")[1]["skin"], "coral", "다른 블로그는 기본색")
        self.admin.api("PUT", "me", {"skin": "coral"})

    def test_2_rejects_bad_values(self):
        for value in ["red", 1, ["blue"], None, "BLUE", " blue", "coral" * 50, {"k": "blue"}]:
            s, r = self.admin.api("PUT", "me", {"skin": value})
            self.assertEqual(s, 400, f"{value!r} 는 거절")
            self.assertEqual(r.get("error"), SKIN_ERR)
        for value in [["profile"], "stats", [1], [None], {"stats": True}, ["stats", "nope"]]:
            s, r = self.admin.api("PUT", "me", {"hidden_widgets": value})
            self.assertEqual(s, 400, f"{value!r} 는 거절")
            self.assertEqual(r.get("error"), WIDGET_ERR)
        # 한 요청 안에서 하나라도 틀리면 아무것도 저장 안 함
        before = self.guest.api("GET", "blogs/admin")[1]
        s, _ = self.admin.api("PUT", "me", {"blog_desc": "바뀌면 안 됨", "skin": "green", "hidden_widgets": ["bad"]})
        self.assertEqual(s, 400)
        after = self.guest.api("GET", "blogs/admin")[1]
        self.assertEqual((after["blog_desc"], after["skin"]), (before["blog_desc"], before["skin"]))
        # 같은 이름은 한 번만, 보낸 순서대로
        s, _ = self.admin.api("PUT", "me", {"hidden_widgets": ["stats", "room", "stats"]})
        self.assertEqual(s, 200)
        self.assertEqual(self.guest.api("GET", "blogs/admin")[1]["hidden_widgets"], ["stats", "room"])
        self.admin.api("PUT", "me", {"hidden_widgets": []})
        # 로그인하지 않으면 401
        self.assertEqual(self.guest.api("PUT", "me", {"skin": "blue"})[0], 401)

    def test_3_popular_in_blog(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE posts SET views = 0")
        ids = {
            "a5": self.write(self.member, "조회 5", 5),
            "b9": self.write(self.member, "조회 9 먼저 쓴 글", 9, content=f"![p]({self.img})"),
            "c9": self.write(self.member, "조회 9 나중 쓴 글", 9),
            "zero": self.write(self.member, "조회 0", 0),
            "secret": self.write(self.member, "비공개 조회 100", 100, public=False),
            "d1": self.write(self.member, "조회 1", 1),
            "e2": self.write(self.member, "조회 2", 2),
            "f3": self.write(self.member, "조회 3", 3),
        }
        want = [ids["c9"], ids["b9"], ids["a5"], ids["f3"], ids["e2"]]
        for who, name in ((self.guest, "방문자"), (self.member, "주인"), (self.admin, "관리자")):
            pop = who.api("GET", "blogs/designmate")[1]["popular"]
            self.assertEqual([p["id"] for p in pop], want, f"{name}가 봐도 같은 순서·공개 글만")
        pop = self.guest.api("GET", "blogs/designmate")[1]["popular"]
        self.assertEqual(pop[1]["thumbnail"], self.img, "대표 사진은 BLOG-20 규칙")
        self.assertIsNone(pop[0]["thumbnail"])
        self.assertEqual(set(pop[0]), {"id", "title", "type", "views", "thumbnail", "created_at"}, "블로그 안에서는 블로그 이름 없이")
        self.assertNotIn(ids["secret"], [p["id"] for p in pop])
        self.assertNotIn(ids["zero"], [p["id"] for p in pop])

    def test_4_hidden_widgets_drop_data(self):
        pid = self.write(self.admin, "댓글·태그가 생기는 글", 7)
        s, r = self.guest.api("POST", "comments", {"post_id": pid, "name": "방문자", "password": "pw1234", "content": "잘 봤어요"})
        self.assertIn(s, (200, 201), r)
        s, _ = self.admin.api("PUT", "me", {"hidden_widgets": ALL_WIDGETS})
        self.assertEqual(s, 200)
        b = self.guest.api("GET", "blogs/admin")[1]
        self.assertEqual(b["hidden_widgets"], ALL_WIDGETS)
        self.assertIsNone(b["stats"], "방문자 수 자료 없음")
        self.assertEqual((b["popular"], b["tags"], b["recent_comments"]), ([], [], []))
        self.assertTrue(b["type_counts"], "글 종류 탭이 쓰는 자료는 그대로")
        s, _ = self.admin.api("PUT", "me", {"hidden_widgets": []})
        b = self.guest.api("GET", "blogs/admin")[1]
        self.assertIsNotNone(b["stats"])
        self.assertTrue(b["popular"] and b["tags"] and b["recent_comments"], "다시 켜면 자료가 돌아옴")

    def test_5_site_popular(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE posts SET views = 0")
        top = self.write(self.member, "사이트에서 가장 많이 본 글", 500)
        second = self.write(self.admin, "관리자 블로그 인기 글", 300)
        hidden = self.write(self.admin, "비공개 999", 999, public=False)
        for who in (self.guest, self.admin):
            pop = who.api("GET", "blog")[1]["popular"]
            self.assertEqual([p["id"] for p in pop[:2]], [top, second])
            self.assertNotIn(hidden, [p["id"] for p in pop])
        pop = self.guest.api("GET", "blog")[1]["popular"]
        self.assertEqual((pop[0]["blog_title"], pop[0]["author_username"]), ("메이트 블로그", "designmate"))
        self.assertLessEqual(len(pop), 5)

    def test_6_old_db_and_bad_stored_values(self):
        """예전 blog.db(칸 없음)로 켜도 칸이 더해지고, DB에 이상한 값이 있어도 기본값으로 응답"""
        self.stop()
        with sqlite3.connect(self.db) as conn:
            try:
                conn.execute("ALTER TABLE users DROP COLUMN skin")
                conn.execute("ALTER TABLE users DROP COLUMN hidden_widgets")
            except sqlite3.OperationalError:
                type(self).proc = self.start()
                self.skipTest("이 SQLite는 DROP COLUMN을 못 해요")
        type(self).proc = self.start()
        with sqlite3.connect(self.db) as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
            self.assertIn("skin", cols)
            self.assertIn("hidden_widgets", cols)
        b = self.guest.api("GET", "blogs/admin")[1]
        self.assertEqual((b["skin"], b["hidden_widgets"]), ("coral", []))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE users SET skin = 'zzz', hidden_widgets = 'not json' WHERE username = 'admin'")
        b = self.guest.api("GET", "blogs/admin")[1]
        self.assertEqual((b["skin"], b["hidden_widgets"]), ("coral", []))
        with sqlite3.connect(self.db) as conn:
            conn.execute("""UPDATE users SET hidden_widgets = '["stats", "evil", 3, "stats"]' WHERE username = 'admin'""")
        self.assertEqual(self.guest.api("GET", "blogs/admin")[1]["hidden_widgets"], ["stats"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

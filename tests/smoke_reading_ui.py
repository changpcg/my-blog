"""004-reading-ui-refresh 점검 (표준 라이브러리만).

실제 blog.db를 건드리지 않도록 server.py·static을 임시 폴더에 복사해 빈 포트에 블로그를 띄우고,
글 목록의 대표 사진(thumbnail)과 글 보기의 관련 글(related) 규칙을 확인합니다. 끝나면 서버를 끄고 임시 폴더를 지웁니다.

    python3 tests/smoke_reading_ui.py

화면 동작(목차·진행 막대·맨 위로·공유·사진 크게 보기·코드 복사·375px 넘침)은
specs/004-reading-ui-refresh/quickstart.md의 손 점검 목록으로 확인합니다.
"""
import base64
import http.cookiejar
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Smoke2026reading"
# 1×1 PNG
PNG = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360f8cfc00000030101005d8b7dd30000000049454e44ae426082"
    )
).decode()
CLEAR_ENV = ("BLOG_PASSWORD", "AUTH_URL", "BLOG_URL", "HOST", "PORT", "MYBLOG_CONFIG")


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


class ReadingUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="myblog-004-")
        shutil.copy2(os.path.join(ROOT, "server.py"), cls.dir)
        shutil.copytree(os.path.join(ROOT, "static"), os.path.join(cls.dir, "static"))
        port = free_port()
        env = {k: v for k, v in os.environ.items() if k not in CLEAR_ENV}
        env.update({"PORT": str(port), "HOST": "127.0.0.1", "BLOG_PASSWORD": PASSWORD})
        cls.proc = subprocess.Popen([sys.executable, "-B", "server.py"], cwd=cls.dir, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        end = time.time() + 15
        while time.time() < end:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
                break
            except OSError:
                time.sleep(0.1)
        cls.base = f"http://127.0.0.1:{port}"
        cls.admin = Client(cls.base)
        status, _ = cls.admin.api("POST", "login", {"username": "admin", "password": PASSWORD})
        assert status == 200, "관리자 로그인 실패"
        up = [cls.admin.api("POST", "upload", {"data": PNG, "name": f"p{i}.png"})[1]["url"] for i in range(3)]
        cls.up = up
        h = up[0][len("/uploads/"):]

        def post(title, content, category="마케팅", ptype="insight", public=True):
            s, r = cls.admin.api("POST", "posts", {"type": ptype, "title": title, "content": content,
                                                   "category": category, "tags": "", "is_public": public})
            assert s in (200, 201), r
            return r["id"]

        # 같은 블로그·종류·카테고리(마케팅 인사이트) 글 여러 개 + 다른 카테고리·종류 글
        cls.ids = {
            "md_spaces": post("띄어쓰기 사진", f"첫 문단\n\n![사진]( {up[0]} \"제목\" )\n\n둘째 문단"),
            "html_img": post("HTML 사진", f'<p><img alt="x" src="{up[1]}"></p>\n\n본문 글자'),
            "external": post("외부 사진만", "![외부](https://example.com/track.png)\n\n본문"),
            "file_link": post("첨부 파일만", f"[📎 보고서 (1KB)](/uploads/{h[:-4]}.pdf)\n\n본문"),
            "in_code": post("코드 속 사진", f"```md\n![a]({up[2]})\n```\n\n본문"),
            "in_comment": post("주석·두 겹 코드 속 사진", f"<!-- ![a]({up[2]}) -->\n\n``![b]({up[2]})``\n\n본문"),
            "stray_fence": post("문장 중간 ``` 기호", f"설명에 ``` 기호가 있어요\n\n![a]({up[1]})"),
            "private": post("비공개 사진 글", f"![비공개]({up[2]})", public=False),
            "other_cat": post("다른 카테고리", f"![a]({up[0]})", category="데이터"),
            "other_type": post("다른 종류", f"![a]({up[0]})", ptype="faq"),
            "newest": post("가장 새 글", "본문만 있어요"),
        }

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def listed(self, client):
        s, r = client.api("GET", "posts?size=50")
        self.assertEqual(s, 200)
        return {p["id"]: p for p in r["posts"]}

    def test_1_thumbnail_rules(self):
        posts = self.listed(self.admin)
        ids = self.ids
        self.assertEqual(posts[ids["md_spaces"]]["thumbnail"], self.up[0], "마크다운 사진(띄어쓰기·제목 포함)")
        self.assertEqual(posts[ids["html_img"]]["thumbnail"], self.up[1], "HTML <img>")
        self.assertIsNone(posts[ids["external"]]["thumbnail"], "외부 주소 사진은 대표 사진으로 쓰지 않음")
        self.assertIsNone(posts[ids["file_link"]]["thumbnail"], "첨부 파일 링크는 사진이 아님")
        self.assertIsNone(posts[ids["in_code"]]["thumbnail"], "코드 블록 속 예시는 사진이 아님")
        self.assertIsNone(posts[ids["in_comment"]]["thumbnail"], "HTML 주석·두 겹 인라인 코드 속 예시도 아님")
        self.assertEqual(posts[ids["stray_fence"]]["thumbnail"], self.up[1], "문장 중간의 ```는 코드 블록이 아님")
        self.assertIsNone(posts[ids["newest"]]["thumbnail"])

    def test_2_excerpt_has_no_html(self):
        ex = self.listed(self.admin)[self.ids["html_img"]]["excerpt"]
        self.assertNotIn("<", ex)
        self.assertNotIn("img", ex)
        self.assertIn("본문 글자", ex)

    def test_3_related_cards(self):
        s, p = self.admin.api("GET", f"posts/{self.ids['newest']}")
        self.assertEqual(s, 200)
        rel = p["related"]
        self.assertLessEqual(len(rel), 4, "관련 글은 최대 4개")
        self.assertEqual(len(rel), 4)
        got = [r["id"] for r in rel]
        self.assertEqual(got, sorted(got, reverse=True), "최신순")
        self.assertNotIn(self.ids["newest"], got, "지금 글은 빼고")
        self.assertNotIn(self.ids["other_cat"], got, "같은 카테고리만")
        self.assertNotIn(self.ids["other_type"], got, "같은 종류만")
        for r in rel:
            self.assertEqual(set(r), {"id", "title", "created_at", "type", "is_public", "thumbnail"})
        self.assertIn(self.ids["private"], got, "관리자에게는 비공개 글도")
        by = {r["id"]: r for r in rel}
        self.assertEqual(by[self.ids["private"]]["thumbnail"], self.up[2])
        self.assertFalse(by[self.ids["private"]]["is_public"])

    def test_4_private_hidden_from_visitor(self):
        visitor = Client(self.base)
        s, p = visitor.api("GET", f"posts/{self.ids['newest']}")
        self.assertEqual(s, 200)
        got = [r["id"] for r in p["related"]]
        self.assertNotIn(self.ids["private"], got, "방문자에게 비공개 글은 안 보임")
        self.assertEqual(len(got), 4)
        self.assertNotIn(self.ids["private"], self.listed(visitor))

    def test_5b_content_cap_and_speed(self):
        """본문은 20만 자까지, 일부러 만든 긴 본문도 목록을 느리게 만들지 않음 (정규식 시간이 길이에 비례)"""
        s, r = self.admin.api("POST", "posts", {"type": "daily", "title": "너무 긴 글", "content": "가" * 200_001,
                                                "category": "", "tags": "", "is_public": True})
        self.assertEqual(s, 400)
        self.assertIn("20만 자", r.get("error", ""))
        for title, content in (("img 반복", "<img " * 40_000), ("괄호 반복", "![" * 100_000), ("태그 반복", "<a" * 100_000)):
            s, r = self.admin.api("POST", "posts", {"type": "daily", "title": title, "content": content,
                                                    "category": "", "tags": "", "is_public": False})
            self.assertIn(s, (200, 201), r)
        t = time.time()
        s, _ = self.admin.api("GET", "posts?size=50")
        self.assertEqual(s, 200)
        self.assertLess(time.time() - t, 2.0, "긴 본문이 있어도 목록은 2초 안에")

    def test_5_index_loads_new_assets(self):
        with urllib.request.urlopen(self.base + "/") as r:
            html = r.read().decode()
        with urllib.request.urlopen(self.base + "/app.js") as r:
            js = r.read().decode()
        self.assertIn("/app.js?v=20", html, "고친 화면 파일을 새로 받도록 버전 올림")
        for hook in ("postRowHtml", "buildToc", "startReadingTools", "sharePost", "openLightbox", "copyCode"):
            self.assertIn(hook, js)


if __name__ == "__main__":
    unittest.main(verbosity=2)

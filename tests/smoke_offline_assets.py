"""007-offline-assets 점검 (표준 라이브러리만): 화면 라이브러리·글꼴을 저장소 안 파일에서만 부르는지.

실제 blog.db를 건드리지 않도록 server.py·static을 임시 폴더에 복사해 빈 포트에 블로그를 띄웁니다.

    python3 tests/smoke_offline_assets.py

인터넷을 끊은 브라우저로 보는 점검은 specs/007-offline-assets/quickstart.md에 있습니다.
"""
import email.utils
import glob
import hashlib
import os
import re
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
VENDOR = os.path.join(ROOT, "static", "vendor")
CLEAR_ENV = ("BLOG_PASSWORD", "AUTH_URL", "BLOG_URL", "HOST", "PORT", "MYBLOG_CONFIG")
IMMUTABLE = "public, max-age=31536000, immutable"
LICENSES = ["marked-12.0.2/LICENSE.md", "dompurify-3.1.6/LICENSE", "highlight-11.9.0/LICENSE", "pretendard-1.3.9/LICENSE.txt"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def fetch(url, headers=None):
    """(상태, 머리글 dict(소문자), 본문)"""
    try:
        with OPENER.open(urllib.request.Request(url, headers=headers or {})) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


class OfflineAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="myblog-007-")
        shutil.copy2(os.path.join(ROOT, "server.py"), cls.dir)
        shutil.copytree(os.path.join(ROOT, "static"), os.path.join(cls.dir, "static"))
        cls.port = free_port()
        env = {k: v for k, v in os.environ.items() if k not in CLEAR_ENV}
        env.update({"PORT": str(cls.port), "HOST": "127.0.0.1", "BLOG_PASSWORD": "Smoke2026offline"})
        cls.proc = subprocess.Popen([sys.executable, "-B", "server.py"], cwd=cls.dir, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        cls.base = f"http://127.0.0.1:{cls.port}"
        end = time.time() + 15
        while time.time() < end:
            try:
                if fetch(cls.base + "/api/blog")[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_1_no_cdn_in_code(self):
        files = [os.path.join(ROOT, "static", "index.html")] + glob.glob(os.path.join(ROOT, "static", "*.js")) \
            + glob.glob(os.path.join(ROOT, "static", "*.css")) + glob.glob(os.path.join(ROOT, "php-auth", "src", "*.php")) \
            + glob.glob(os.path.join(ROOT, "php-auth", "public", "*.php")) + glob.glob(os.path.join(ROOT, "php-auth", "public", "*.css"))
        for fp in files:
            with open(fp, encoding="utf-8") as f:
                text = f.read()
            for cdn in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "fonts.googleapis.com"):
                self.assertNotIn(cdn, text, f"{os.path.relpath(fp, ROOT)}에 CDN 주소({cdn})가 남아 있어요")
        html = fetch(self.base + "/")[2].decode()
        refs = re.findall(r'<(?:script|link)\b[^>]*?\b(?:src|href)="([^"]+)"', html)
        self.assertTrue(refs)
        self.assertEqual([r for r in refs if re.match(r"(?i)(https?:)?//", r)], [], "화면이 바깥 주소 파일을 부름")

    def test_2_all_page_assets_load(self):
        html = fetch(self.base + "/")[2].decode()
        want = {".js": "text/javascript", ".css": "text/css"}
        for ref in re.findall(r'<(?:script|link)\b[^>]*?\b(?:src|href)="([^"]+)"', html):
            status, headers, body = fetch(self.base + ref)
            self.assertEqual(status, 200, ref)
            ext = os.path.splitext(ref.split("?")[0])[1]
            self.assertTrue(headers.get("content-type", "").startswith(want[ext]), f"{ref}: {headers.get('content-type')}")
            self.assertGreater(len(body), 100, ref)
        # 글꼴 CSS가 가리키는 글꼴 파일
        css = fetch(self.base + "/vendor/pretendard-1.3.9/pretendard.css")[2].decode()
        self.assertIn("font-family: 'Pretendard'", css)
        fonts = set(re.findall(r"url\('\./([^']+)'\)", css))
        self.assertEqual(fonts, {"PretendardVariable.woff2"})
        status, headers, body = fetch(self.base + "/vendor/pretendard-1.3.9/PretendardVariable.woff2")
        self.assertEqual((status, headers.get("content-type")), (200, "font/woff2"))
        self.assertEqual(body[:4], b"wOF2", "woff2 파일")

    def test_3_cache_and_cors(self):
        url = self.base + "/vendor/pretendard-1.3.9/PretendardVariable.woff2"
        status, headers, _ = fetch(url, {"Origin": "http://localhost:8080"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("cache-control"), IMMUTABLE)
        self.assertEqual(headers.get("access-control-allow-origin"), "*")
        self.assertNotIn("set-cookie", headers, "내장 파일 응답에 쿠키 없음")
        # 바뀌지 않았으면 304 + 같은 머리글
        since = headers.get("last-modified") or email.utils.formatdate(time.time(), usegmt=True)
        status, headers, _ = fetch(url, {"If-Modified-Since": since})
        self.assertEqual(status, 304)
        self.assertEqual(headers.get("cache-control"), IMMUTABLE)
        # 없는 파일·폴더 목록: 404, 1년 캐시·CORS 없음
        for path in ("/vendor/nope.js", "/vendor/", "/vendor/marked-12.0.2/"):
            status, headers, body = fetch(self.base + path)
            self.assertEqual(status, 404, path)
            self.assertNotEqual(headers.get("cache-control"), IMMUTABLE, path)
            self.assertNotIn("access-control-allow-origin", headers, path)
            self.assertNotIn(b"marked.min.js", body, "폴더 목록을 보여 주지 않음")
        # 그 밖의 화면 파일·API는 지금처럼
        status, headers, _ = fetch(self.base + "/app.js")
        self.assertEqual((status, headers.get("cache-control")), (200, "no-cache"))
        self.assertNotIn("access-control-allow-origin", headers)
        status, headers, _ = fetch(self.base + "/api/blog")
        self.assertNotEqual(headers.get("cache-control"), IMMUTABLE)
        self.assertNotIn("access-control-allow-origin", headers)
        # ..로 내장 폴더를 빠져나간 주소는 내장 파일 규칙을 받지 않음
        status, headers, _ = fetch(self.base + "/vendor/%2e%2e/index.html")
        self.assertNotEqual(headers.get("cache-control"), IMMUTABLE)

    def test_4_checksums_and_licenses(self):
        with open(os.path.join(VENDOR, "README.md"), encoding="utf-8") as f:
            listed = re.findall(r"^([0-9a-f]{64})\s+(\S+)$", f.read(), re.M)
        self.assertEqual(len(listed), 7)
        for digest, rel in listed:
            with open(os.path.join(VENDOR, rel), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), digest, f"{rel} 파일이 문서의 확인값과 달라요")
        for rel in LICENSES:
            self.assertGreater(os.path.getsize(os.path.join(VENDOR, rel)), 500, f"{rel} 라이선스")
        # 문서에 없는 파일이 끼어 있지 않음
        actual = sorted(os.path.relpath(p, VENDOR) for p in glob.glob(os.path.join(VENDOR, "**", "*"), recursive=True)
                        if os.path.isfile(p))
        expected = sorted([rel for _, rel in listed] + LICENSES + ["README.md"])
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)

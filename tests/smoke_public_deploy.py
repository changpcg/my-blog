"""003-public-deploy-readiness 점검 (표준 라이브러리만).

실제 blog.db·회원 DB를 건드리지 않도록 코드를 임시 폴더에 복사하고, 빈 포트에 블로그(python3)와
회원 서버(php -S)를 직접 띄워 공개 모드·개발 모드를 확인합니다. 끝나면 서버를 끄고 임시 폴더를 지웁니다.

    python3 tests/smoke_public_deploy.py

- 공개 모드는 '믿는 프록시(127.0.0.1)가 보낸 X-Forwarded-Proto: https'로 https를 흉내 냅니다.
- 회원 서버의 공개 모드 점검은 php -S에서 ALLOW_PHP_DEV_SERVER=1(로컬 점검용 예외)로 띄웁니다.
- php가 없으면 회원 서버 점검은 건너뜁니다. 자동 가입 방지 대기(3초)가 있어 1분쯤 걸립니다.
"""
import json
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
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHP = shutil.which("php")
STRONG = "StrongPass2026a"
STRONG2 = "OtherStrong2026b"
PUBLIC = {"public_mode": True, "blog_url": "https://blog.test", "auth_url": "https://auth.test", "trusted_proxies": ["127.0.0.1"]}
HTTPS = {"X-Forwarded-Proto": "https"}
F1 = "가입을 처리하지 못했어요"
F3 = "너무 빨리 보냈어요"
F4 = "1시간 안에 가입을 너무 많이 했어요"
F5 = "지금 가입이 몰려 잠시 막아 두었어요"
CLEAR_ENV = ("BLOG_PASSWORD", "AUTH_URL", "BLOG_URL", "HOST", "PORT", "MYBLOG_CONFIG", "ALLOW_PHP_DEV_SERVER")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port, proc, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


class App:
    """임시 폴더에 복사한 앱 하나. 블로그·회원 서버 프로세스를 띄우고 끈다."""

    def __init__(self, config):
        self.dir = tempfile.mkdtemp(prefix="myblog-003-")
        shutil.copy2(os.path.join(ROOT, "server.py"), self.dir)
        shutil.copytree(os.path.join(ROOT, "static"), self.path("static"))
        for sub in ("src", "public"):
            shutil.copytree(os.path.join(ROOT, "php-auth", sub), self.path("php-auth", sub))
        # 가짜 네이버 키 (실제 SNS로는 나가지 않음, 시작 주소만 확인)
        with open(self.path("php-auth", "oauth.config.php"), "w", encoding="utf-8") as f:
            f.write("<?php return ['naver' => ['client_id' => 'test-id', 'client_secret' => 'test-secret']];\n")
        self.bport, self.aport = free_port(), free_port()
        self.procs = []
        self.write_config(config)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    @property
    def blog(self):
        return f"http://127.0.0.1:{self.bport}"

    @property
    def auth(self):
        return f"http://127.0.0.1:{self.aport}"

    def write_config(self, config, name="deploy.config.json"):
        text = json.dumps(config).replace("{BPORT}", str(self.bport)).replace("{APORT}", str(self.aport))
        with open(self.path(name), "w", encoding="utf-8") as f:
            f.write(text)
        return name

    def _env(self, extra):
        env = {k: v for k, v in os.environ.items() if k not in CLEAR_ENV}
        env.update(extra)
        return env

    def _blog_proc(self, password, config, port):
        env = self._env({"PORT": str(port), "HOST": "127.0.0.1", "MYBLOG_CONFIG": self.path(config)})
        if password is not None:
            env["BLOG_PASSWORD"] = password
        log = open(self.path(f"blog-{port}-{len(self.procs)}.log"), "w+", encoding="utf-8")
        p = subprocess.Popen([sys.executable, "-B", "server.py"], cwd=self.dir, env=env, stdout=log, stderr=subprocess.STDOUT)
        p.log = log
        self.procs.append(p)
        return p

    def run_blog(self, password, config="deploy.config.json", port=None):
        port = port or self.bport
        p = self._blog_proc(password, config, port)
        if not wait_port(port, p):
            p.log.seek(0)
            raise AssertionError("블로그가 켜지지 않음:\n" + p.log.read())
        return p

    def blog_start_fail(self, password, config="deploy.config.json"):
        """켜지지 않아야 하는 경우: (종료 코드, 출력)."""
        p = self._blog_proc(password, config, free_port())
        try:
            code = p.wait(15)
        except subprocess.TimeoutExpired:
            p.kill()
            code = None
        p.log.seek(0)
        return code, p.log.read()

    def run_php(self, allow_dev=False, config="deploy.config.json", port=None):
        port = port or self.aport
        env = self._env({"MYBLOG_CONFIG": self.path(config)})
        if allow_dev:
            env["ALLOW_PHP_DEV_SERVER"] = "1"
        p = subprocess.Popen(
            [PHP, "-S", f"127.0.0.1:{port}", "-t", "php-auth/public"], cwd=self.dir, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.procs.append(p)
        if not wait_port(port, p):
            raise AssertionError("회원 서버(php -S)가 켜지지 않음")
        return p

    @staticmethod
    def stop(p):
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()

    def close(self):
        for p in self.procs:
            self.stop(p)
            if getattr(p, "log", None):
                p.log.close()
        shutil.rmtree(self.dir, ignore_errors=True)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Resp:
    def __init__(self, status, headers, text):
        self.status, self.headers, self.text = status, headers, text

    def json(self):
        return json.loads(self.text)

    def cookies(self):
        return self.headers.get_all("Set-Cookie") or []


class Web:
    """머리글을 고정해 두고 쿠키를 직접 다루는 작은 클라이언트 (Secure 쿠키도 http로 다시 보냄)."""

    def __init__(self, base, headers=None):
        self.base, self.headers, self.cookies = base, dict(headers or {}), {}
        self.op = urllib.request.build_opener(_NoRedirect, urllib.request.ProxyHandler({}))

    def req(self, method, path, js=None, form=None, headers=None):
        h = {**self.headers, **(headers or {})}
        data = None
        if js is not None:
            data, h["Content-Type"] = json.dumps(js).encode(), "application/json"
        elif form is not None:
            data, h["Content-Type"] = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
        if self.cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        try:
            r = self.op.open(urllib.request.Request(self.base + path, data=data, headers=h, method=method), timeout=20)
        except urllib.error.HTTPError as e:
            r = e
        for c in r.headers.get_all("Set-Cookie") or []:
            name, _, value = c.split(";", 1)[0].partition("=")
            if value in ("", "deleted") or "max-age=0" in c.lower():
                self.cookies.pop(name.strip(), None)
            else:
                self.cookies[name.strip()] = value.strip()
        return Resp(r.status, r.headers, r.read().decode("utf-8", "replace"))


# ---------------------------------------------------------------- 블로그: 공개 모드 (US1·US2·US3)
class BlogPublicMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App(PUBLIC)

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def web(self, headers=HTTPS, port=None):
        return Web(f"http://127.0.0.1:{port or self.app.bport}", headers)

    def test_1_refuses_bad_settings(self):
        """US1-1·2, FR-002·003: 약한 비밀번호·깨진 설정이면 종료 코드 78, DB를 만들지 않음."""
        for pw, needle in ((None, "BLOG_PASSWORD"), ("admin1234", "admin1234"), ("short1pw", "12자 이상")):
            code, out = self.app.blog_start_fail(pw)
            self.assertEqual(code, 78, out)
            self.assertIn("서버를 켜지 않았어요", out)
            self.assertIn(needle, out)
        self.app.write_config({"public_mode": True, "blog_url": "https://blog.test"}, "broken.json")
        with open(self.app.path("broken.json"), "a", encoding="utf-8") as f:
            f.write(",")  # JSON을 깨뜨림
        code, out = self.app.blog_start_fail(STRONG, "broken.json")
        self.assertEqual(code, 78, out)
        self.assertIn("읽을 수 없어요", out)
        self.app.write_config({**PUBLIC, "auth_url": "https://blog.test/"}, "same.json")
        code, out = self.app.blog_start_fail(STRONG, "same.json")
        self.assertIn("서로 다른 주소", out)
        self.assertFalse(os.path.exists(self.app.path("blog.db")), "설정 오류인데 blog.db를 만들면 안 됨")

    def test_2_strong_password_starts(self):
        """US1-3: 강한 비밀번호로 켜지고 admin1234는 거절."""
        type(self).blog_proc = self.app.run_blog(STRONG)
        w = self.web()
        self.assertEqual(w.req("POST", "/api/login", js={"username": "admin", "password": "admin1234"}).status, 401)
        r = w.req("POST", "/api/login", js={"username": "admin", "password": STRONG})
        self.assertEqual(r.status, 200)
        self.assertTrue(any(c.startswith("session=") and "Secure" in c for c in r.cookies()), r.cookies())
        type(self).admin_cookies = dict(w.cookies)

    def test_3_https_gate(self):
        """US2-1·2, FR-005·006: http는 308, https는 HSTS와 Secure 쿠키, 머리글이 없으면 500."""
        http = self.web({"X-Forwarded-Proto": "http"})
        r = http.req("GET", "/api/blog?x=1")
        self.assertEqual(r.status, 308)
        self.assertEqual(r.headers["Location"], "https://blog.test/api/blog?x=1")
        self.assertEqual(http.req("HEAD", "/").status, 308)
        self.assertEqual(http.req("POST", "/api/login", js={}).status, 308)
        https = self.web()
        r = https.req("GET", "/")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers["Strict-Transport-Security"], "max-age=31536000")
        r = https.req("GET", "/api/blog")
        self.assertTrue(any(c.startswith("vid=") and "Secure" in c for c in r.cookies()), r.cookies())
        r = https.req("HEAD", "/")
        self.assertEqual(r.status, 200)
        self.assertIn("Strict-Transport-Security", r.headers)
        r = self.web({}).req("GET", "/")
        self.assertEqual(r.status, 500)
        self.assertIn("X-Forwarded-Proto", r.text)
        for p in ("/blog.db", "/deploy.config.json", "/php-auth/db/sso.key", "/../blog.db", "/server.py"):
            self.assertEqual(https.req("GET", p).status, 404, p)  # SC-004

    def test_4_untrusted_peer_is_not_https(self):
        """US3-2: 믿는 프록시가 아닌 곳의 X-Forwarded-Proto·X-Forwarded-For는 믿지 않음."""
        self.app.write_config({**PUBLIC, "trusted_proxies": ["127.0.0.2"]}, "untrusted.json")
        port = free_port()
        self.app.run_blog(STRONG, "untrusted.json", port)
        r = self.web(HTTPS, port).req("GET", "/")
        self.assertEqual(r.status, 308)

    def test_5_admin_status(self):
        """FR-008: 관리자 상태 — 공개 모드 복사본은 https://auth.test에 실제로 갈 수 없어 auth는 null."""
        self.assertEqual(self.web().req("GET", "/api/admin/status").status, 403)
        w = self.web()
        w.cookies = dict(self.admin_cookies)
        r = w.req("GET", "/api/admin/status")
        self.assertEqual(r.status, 200, r.text)
        j = r.json()
        self.assertEqual(j["deploy"], {"public_mode": True, "blog_url": "https://blog.test", "auth_url": "https://auth.test"})
        self.assertIsNone(j["auth"])

    def test_6_comment_lock_uses_real_ip(self):
        """US3-1, FR-011: 믿는 프록시가 알려 준 방문자 IP마다 댓글 비밀번호 잠금."""
        admin = self.web()
        admin.cookies = dict(self.admin_cookies)
        r = admin.req("POST", "/api/posts", js={"title": "잠금 점검", "type": "daily", "content": "본문"})
        self.assertEqual(r.status, 201, r.text)
        pid = r.json()["id"]
        guest = self.web()
        self.assertEqual(guest.req("POST", "/api/comments", js={"post_id": pid, "name": "손님", "password": "right-pw", "content": "안녕"}).status, 201)
        data = guest.req("GET", f"/api/comments?post={pid}").json()
        rows = data["comments"] if isinstance(data, dict) else data
        cid = rows[-1]["id"]
        a, b = "203.0.113.10", "203.0.113.20"
        for _ in range(5):
            r = self.web({**HTTPS, "X-Forwarded-For": a}).req("DELETE", f"/api/comments/{cid}", js={"password": "wrong"})
            self.assertEqual(r.status, 403, r.text)
        self.assertEqual(self.web({**HTTPS, "X-Forwarded-For": a}).req("DELETE", f"/api/comments/{cid}", js={"password": "wrong"}).status, 429)
        self.assertEqual(self.web({**HTTPS, "X-Forwarded-For": b}).req("DELETE", f"/api/comments/{cid}", js={"password": "wrong"}).status, 403)
        # 왼쪽에 가짜 값을 넣어도 오른쪽(프록시가 붙인 실제 IP)으로 셈
        self.assertEqual(self.web({**HTTPS, "X-Forwarded-For": f"{b}, {a}"}).req("DELETE", f"/api/comments/{cid}", js={"password": "wrong"}).status, 429)

    def test_7_password_change_ends_admin_sessions(self):
        """US1-4, FR-004: 비밀번호를 바꿔 다시 켜면 예전 관리자 세션이 끊김."""
        self.app.stop(self.blog_proc)
        self.app.run_blog(STRONG2)
        w = self.web()
        w.cookies = dict(self.admin_cookies)
        j = w.req("GET", "/api/blog").json()
        self.assertFalse(j["is_admin"])
        self.assertIsNone(j["user"])
        self.assertEqual(self.web().req("POST", "/api/login", js={"username": "admin", "password": STRONG}).status, 401)
        self.assertEqual(self.web().req("POST", "/api/login", js={"username": "admin", "password": STRONG2}).status, 200)


# ---------------------------------------------------------------- 회원 서버: 공개 모드 (US2)
@unittest.skipUnless(PHP, "php가 없어 회원 서버 점검을 건너뜀")
class AuthPublicMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App(PUBLIC)

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def web(self, headers=HTTPS, port=None):
        return Web(f"http://127.0.0.1:{port or self.app.aport}", headers)

    def test_1_dev_server_refused(self):
        """FR-009: 공개 모드에서 php -S는 거절 (예외 변수 없을 때)."""
        p = self.app.run_php(allow_dev=False)
        r = self.web().req("GET", "/login.php")
        self.assertEqual(r.status, 503)
        self.assertIn("php -S", r.text)
        self.app.stop(p)

    def test_2_https_gate(self):
        """US2-1·2: http는 308, https는 HSTS와 Secure 세션 쿠키."""
        type(self).php_proc = self.app.run_php(allow_dev=True)
        r = self.web({"X-Forwarded-Proto": "http"}).req("GET", "/login.php?return=blog")
        self.assertEqual(r.status, 308)
        self.assertEqual(r.headers["Location"], "https://auth.test/login.php?return=blog")
        r = self.web().req("GET", "/login.php")
        self.assertEqual(r.status, 200, r.text[:300])
        self.assertEqual(r.headers["Strict-Transport-Security"], "max-age=31536000")
        self.assertTrue(any(c.startswith("AUTHSESS=") and "secure" in c.lower() for c in r.cookies()), r.cookies())
        self.assertEqual(self.web({}).req("GET", "/login.php").status, 308, "머리글이 없으면 https가 아님")

    def test_3_callback_from_auth_url(self):
        """FR-007·US2-4: SNS 콜백 주소는 auth_url에서."""
        r = self.web().req("GET", "/oauth_start.php?provider=naver")
        self.assertEqual(r.status, 302, r.text[:300])
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers["Location"]).query)
        self.assertEqual(q["redirect_uri"], ["https://auth.test/oauth_callback.php"])

    def test_4_private_files(self):
        """SC-004: 공개 폴더 밖 파일은 주소로 열리지 않음."""
        for p in ("/db/sqlite.db", "/db/sso.key", "/oauth.config.php", "/../deploy.config.json", "/../src/config.php"):
            self.assertEqual(self.web().req("GET", p).status, 404, p)

    def test_5_broken_config(self):
        """FR-002: 설정이 틀리면 회원 서버는 503 (DB를 열지 않음)."""
        self.app.write_config({"public_mode": True, "blog_url": "http://blog.test", "auth_url": "https://auth.test"}, "bad.json")
        port = free_port()
        self.app.run_php(allow_dev=True, config="bad.json", port=port)
        r = self.web(HTTPS, port).req("GET", "/login.php")
        self.assertEqual(r.status, 503)
        self.assertIn("회원 서버 설정을 확인", r.text)
        self.assertNotIn("blog_url", r.text, "방문자에게 설정 내용을 보이면 안 됨")


# ---------------------------------------------------------------- 가입 보호: 개발 모드 (US4)
def signup_page(app, ip):
    w = Web(app.auth, {"X-Forwarded-For": ip})
    r = w.req("GET", "/register.php")
    csrf = re.search(r'name="csrf" value="([^"]+)"', r.text)
    token = re.search(r'name="form_token" value="([^"]+)"', r.text)
    return w, (csrf.group(1) if csrf else ""), (token.group(1) if token else ""), r


def signup_check(w, csrf, username):
    return w.req("POST", "/register.php", form={"csrf": csrf, "action": "check", "username": username})


def signup_submit(w, csrf, token, username, website="", with_token=True):
    form = {"csrf": csrf, "action": "signup", "username": username, "password": "pass1234word",
            "password2": "pass1234word", "nickname": "점검", "bio": "", "website": website}
    if with_token:
        form["form_token"] = token
    return w.req("POST", "/register.php", form=form)


def uname(tag):
    return f"t{tag}{os.getpid() % 10000}{int(time.time() * 1000) % 100000}"[:20]


@unittest.skipUnless(PHP, "php가 없어 가입 보호 점검을 건너뜀")
class SignupGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App({
            "blog_url": "http://127.0.0.1:{BPORT}", "auth_url": "http://127.0.0.1:{APORT}",
            "trusted_proxies": ["127.0.0.1"], "signup": {"per_ip_per_hour": 3, "site_per_hour": 4},
        })
        cls.app.run_blog("devpass1234")
        cls.app.run_php()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def test_1_bot_checks(self):
        """US4-3, FR-013: 숨은 칸·토큰 없음·3초 미만은 가입 안 됨."""
        fast = signup_page(self.app, "198.51.100.1")
        self.assertTrue(fast[2], "가입 폼에 form_token이 있어야 함")
        self.assertIn('name="website"', fast[3].text)
        u_fast = uname("f")
        signup_check(fast[0], fast[1], u_fast)
        r = signup_submit(fast[0], fast[1], fast[2], u_fast)
        self.assertEqual(r.status, 200)
        self.assertIn(F3, r.text)
        honey = signup_page(self.app, "198.51.100.2")
        notok = signup_page(self.app, "198.51.100.3")
        u_h, u_n = uname("h"), uname("n")
        signup_check(honey[0], honey[1], u_h)
        signup_check(notok[0], notok[1], u_n)
        time.sleep(3.2)
        r = signup_submit(honey[0], honey[1], honey[2], u_h, website="http://spam.example")
        self.assertIn(F1, r.text)
        r = signup_submit(notok[0], notok[1], notok[2], u_n, with_token=False)
        self.assertIn(F1, r.text)
        # 같은 화면에서 3초가 지난 뒤 다시 누르면 사람은 가입됨 (토큰 유지)
        r = signup_submit(fast[0], fast[1], fast[2], u_fast)
        self.assertEqual(r.status, 302, r.text[:400])

    def test_2_ip_and_site_limits(self):
        """US4-1·2, FR-012: 같은 IP 1시간 3개(앞 테스트의 1개는 다른 IP), 전체 4개 한도."""
        plan = [("203.0.113.1", 302), ("203.0.113.1", 302), ("203.0.113.1", 302), ("203.0.113.1", F4), ("203.0.113.2", F5)]
        pages = []
        for ip, _ in plan:
            w, csrf, token, _r = signup_page(self.app, ip)
            u = uname("l")
            time.sleep(0.002)
            signup_check(w, csrf, u)
            pages.append((w, csrf, token, u))
        time.sleep(3.2)
        for (ip, want), (w, csrf, token, u) in zip(plan, pages):
            r = signup_submit(w, csrf, token, u)
            if want == 302:
                self.assertEqual(r.status, 302, f"{ip}: {r.text[:300]}")
            else:
                self.assertIn(want, r.text, ip)
        # 한도에 걸린 IP는 가입 화면 대신 안내
        r = signup_page(self.app, "203.0.113.1")[3]
        self.assertIn(F4, r.text)
        self.assertNotIn('name="form_token"', r.text)

    def test_3_admin_status(self):
        """FR-008·014: 관리자 가입 현황(IP 없음)과 콜백 주소."""
        w = Web(self.app.blog)
        self.assertEqual(w.req("POST", "/api/login", js={"username": "admin", "password": "devpass1234"}).status, 200)
        r = w.req("GET", "/api/admin/status")
        self.assertEqual(r.status, 200, r.text)
        j = r.json()
        self.assertFalse(j["deploy"]["public_mode"])
        a = j["auth"]
        self.assertTrue(a and a["ok"], r.text)
        self.assertEqual(a["signups"]["created"], 4)
        self.assertGreaterEqual(a["signups"]["blocked"]["limit_ip"], 1)
        self.assertGreaterEqual(a["signups"]["blocked"]["limit_site"], 1)
        self.assertGreaterEqual(a["signups"]["blocked"]["bot"], 3)
        self.assertTrue(a["signups"]["site_limited_now"])
        self.assertEqual(a["sns"]["callback_url"], f"{self.app.auth}/oauth_callback.php")
        self.assertEqual(a["sns"]["providers"], ["naver"])
        self.assertNotRegex(r.text, r"203\.0\.113|198\.51\.100", "IP가 보이면 안 됨")


@unittest.skipUnless(PHP, "php가 없어 가입 보호 점검을 건너뜀")
class SignupWithoutTrustedProxy(unittest.TestCase):
    """US3-2: 믿는 프록시가 없으면(개발 기본) X-Forwarded-For를 바꿔도 같은 IP로 셈."""

    @classmethod
    def setUpClass(cls):
        cls.app = App({"blog_url": "http://127.0.0.1:{BPORT}", "auth_url": "http://127.0.0.1:{APORT}"})
        cls.app.run_blog("devpass1234")
        cls.app.run_php()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def test_xff_ignored(self):
        pages = []
        for i in range(4):
            w, csrf, token, _r = signup_page(self.app, f"192.0.2.{i + 1}")
            u = uname("x")
            time.sleep(0.002)
            signup_check(w, csrf, u)
            pages.append((w, csrf, token, u))
        time.sleep(3.2)
        results = [signup_submit(*p) for p in pages]
        self.assertEqual([r.status for r in results[:3]], [302, 302, 302])
        self.assertIn(F4, results[3].text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

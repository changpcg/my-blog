"""001-security-gap-fixes 스모크 테스트 (표준 라이브러리만).

블로그(8000)와 회원 서버(8080)를 켠 상태에서:
    python3 tests/smoke_security_gaps.py

회원 로그아웃 표 테스트까지 하려면 회원 서버 계정 두 개를 환경변수로 알려 주세요.
    MEMBER_A=아이디:비밀번호 MEMBER_B=아이디:비밀번호 python3 tests/smoke_security_gaps.py
(공개 글이 하나 이상 있어야 하고, 테스트 댓글은 끝나면 지워집니다. 잠금 테스트 댓글은 관리자 없이
 지울 수 없어 15분 뒤 비밀번호로 지우거나 블로그 주인이 지워야 합니다.)
"""
import http.cookiejar
import json
import os
import re
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

BLOG = os.environ.get("BLOG_URL", "http://localhost:8000")
PHP = os.environ.get("AUTH_URL", "http://localhost:8080")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), _NoRedirect)


def req(op, url, form=None, js=None, method=None):
    headers, data = {}, None
    if js is not None:
        data, headers["Content-Type"] = json.dumps(js).encode(), "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
    try:
        r = op.open(urllib.request.Request(url, data=data, headers=headers, method=method))
    except urllib.error.HTTPError as e:
        r = e
    return r.status, r.headers.get("Location"), r.read().decode()


def first_public_post(op):
    _, _, body = req(op, BLOG + "/api/posts")
    return json.loads(body)["posts"][0]["id"]


def guest_comment(op, pid, pw):
    req(op, BLOG + "/api/comments", js={"post_id": pid, "name": "스모크", "password": pw, "content": "테스트"}, method="POST")
    _, _, body = req(op, BLOG + f"/api/comments?post={pid}")
    return json.loads(body)[-1]["id"]


class CommentPassword(unittest.TestCase):
    def setUp(self):
        self.op = client()
        self.pid = first_public_post(self.op)

    def delete(self, cid, pw):
        return req(self.op, BLOG + f"/api/comments/{cid}", js={"password": pw}, method="DELETE")

    def test_password_in_url_rejected(self):
        cid = guest_comment(self.op, self.pid, "smoke1234")
        s, _, _ = req(self.op, BLOG + f"/api/comments/{cid}?password=smoke1234", method="DELETE")
        self.assertEqual(s, 400)
        self.assertEqual(self.delete(cid, "smoke1234")[0], 200)

    def test_lock_after_five_wrong(self):
        cid = guest_comment(self.op, self.pid, "smoke5678")
        for _ in range(5):
            t = time.time()
            self.assertEqual(self.delete(cid, "wrong")[0], 403)
            self.assertGreaterEqual(time.time() - t, 0.5)
        s, _, body = self.delete(cid, "smoke5678")
        self.assertEqual(s, 429)
        self.assertIn("분 뒤", json.loads(body)["error"])


class LogoutTicket(unittest.TestCase):
    def test_anonymous_gets_no_ticket(self):
        _, _, body = req(client(), BLOG + "/api/logout", js={}, method="POST")
        self.assertIsNone(json.loads(body)["auth_logout"])

    @unittest.skipUnless(os.environ.get("MEMBER_A") and os.environ.get("MEMBER_B"), "MEMBER_A·MEMBER_B 없음")
    def test_ticket_bound_and_single_use(self):
        def php_login(op, cred, blog=False):
            user, pw = cred.split(":", 1)
            q = "?return=blog" if blog else ""
            _, _, page = req(op, PHP + "/login.php" + q)
            csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
            return req(op, PHP + "/login.php" + q, form={"csrf": csrf, "username": user, "password": pw})[1]

        def php_in(op):
            return "환영해요" not in req(op, PHP + "/index.php")[2]

        a, b = client(), client()
        loc = php_login(a, os.environ["MEMBER_A"], blog=True)
        ticket = urllib.parse.unquote(loc.split("t=", 1)[1])
        self.assertIn(req(a, BLOG + "/api/sso", js={"ticket": ticket}, method="POST")[0], (200, 201))
        php_login(b, os.environ["MEMBER_B"])
        out = json.loads(req(a, BLOG + "/api/logout", js={}, method="POST")[2])["auth_logout"]
        action, t = out["action"], out["t"]
        req(b, action, form={"t": t})
        self.assertTrue(php_in(b), "다른 회원의 표로 로그아웃되면 안 됨")
        req(a, action + "?t=" + urllib.parse.quote(t))
        self.assertTrue(php_in(a), "GET 링크로 로그아웃되면 안 됨")
        req(a, action, form={"t": t})
        self.assertFalse(php_in(a), "본인 표 POST는 로그아웃")
        php_login(a, os.environ["MEMBER_A"])
        req(a, action, form={"t": t})
        self.assertTrue(php_in(a), "이미 쓴 표는 다시 못 씀")


if __name__ == "__main__":
    unittest.main(verbosity=2)

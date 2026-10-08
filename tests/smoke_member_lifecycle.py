"""002-member-lifecycle-sync 스모크 테스트 (표준 라이브러리만).

블로그(8000)와 회원 서버(8080)를 켜고, 사이트 설정에서 회원가입 허용이 켜진 상태에서:
    python3 tests/smoke_member_lifecycle.py

테스트용 회원을 하나 가입시켜 내 정보 수정·비밀번호 변경·블로그 입장·스스로 탈퇴까지 확인하고,
마지막에 그 회원은 탈퇴로 지워집니다.
"""
import http.cookiejar
import json
import os
import re
import secrets
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
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _NoRedirect)


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


def csrf(op, page):
    return re.search(r'name="csrf" value="([^"]+)"', req(op, f"{PHP}/{page}")[2]).group(1)


def logged_in(op):
    return "환영해요" not in req(op, PHP + "/index.php")[2]


def login(op, user, pw, blog=False):
    q = "?return=blog" if blog else ""
    return req(op, f"{PHP}/login.php{q}", form={"csrf": csrf(op, "login.php" + q), "username": user, "password": pw})[1]


def profile(op, **form):
    form["csrf"] = csrf(op, "profile.php")
    return req(op, PHP + "/profile.php", form=form)


class MemberLifecycle(unittest.TestCase):
    def test_full_cycle(self):
        user, pw, pw2 = "smk" + secrets.token_hex(4), "smokepass1", "smokepass2"
        a = client()
        page = req(a, PHP + "/register.php")[2]
        t = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        # 003 자동 가입 방지: 폼 토큰과 빈 숨은 칸을 보내고, 화면을 연 뒤 3초가 지나야 받음
        m = re.search(r'name="form_token" value="([^"]+)"', page)
        guard = {"form_token": m.group(1), "website": ""} if m else {}
        req(a, PHP + "/register.php", form={"csrf": t, "action": "check", "username": user})
        time.sleep(3.1)
        s, _, _ = req(a, PHP + "/register.php", form={
            "csrf": t, "action": "signup", "username": user, "password": pw, "password2": pw, "nickname": "스모크", "bio": "",
            **guard})
        self.assertEqual(s, 302, "가입 (회원가입 허용이 켜져 있어야 함)")

        # 닉네임 수정 → 블로그 입장 때 반영
        profile(a, action="profile", nickname="스모크2", bio="소개")
        loc = login(a, user, pw, blog=True) or ""
        if "t=" not in loc:  # 이미 로그인된 상태면 '블로그 들어가기' 버튼
            loc = req(a, PHP + "/login.php?return=blog", form={"csrf": csrf(a, "login.php?return=blog")})[1]
        ticket = urllib.parse.unquote(loc.split("t=", 1)[1])
        self.assertIn(req(a, BLOG + "/api/sso", js={"ticket": ticket}, method="POST")[0], (200, 201))
        me = json.loads(req(a, BLOG + "/api/blog")[2])["user"]
        self.assertEqual(me["nickname"], "스모크2")

        # 비밀번호 변경 → 다른 브라우저 회원 페이지 로그인 끊김
        b = client()
        login(b, user, pw)
        self.assertTrue(logged_in(b))
        profile(a, action="password", current_password=pw, new_password=pw2, new_password2=pw2)
        self.assertTrue(logged_in(a))
        self.assertFalse(logged_in(b))

        # 스스로 탈퇴 → 블로그 계정도 사라짐
        profile(a, action="delete", confirm_password=pw2)
        self.assertFalse(logged_in(a))
        c = client()
        login(c, user, pw2)
        self.assertFalse(logged_in(c), "탈퇴 후 로그인되면 안 됨")
        s, _, _ = req(c, BLOG + f"/api/blogs/{user}")
        self.assertEqual(s, 404, "블로그도 사라져야 함")

    def test_bridge_rejects_unsigned(self):
        op = client()
        self.assertEqual(req(op, PHP + "/bridge_delete.php", form={"t": "a.b"})[0], 400)
        self.assertEqual(req(op, BLOG + "/api/bridge/delete_member", js={"t": "a.b"}, method="POST")[0], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)

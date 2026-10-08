#!/usr/bin/env python3
"""티스토리 스타일 블로그 서버 (Python 표준 라이브러리만 사용)

실행:  python3 server.py
접속:  http://localhost:8000
관리자: 아이디 admin / 비밀번호는 환경변수 BLOG_PASSWORD (기본값: admin1234)
다른 기기에서 접속하려면: HOST=0.0.0.0 python3 server.py
"""
import base64
import hashlib
import hmac
import html
import ipaddress
import json
import os
import posixpath
import re
import secrets
import shutil
import sqlite3
import sys
import time
import threading
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlsplit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "blog.db")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
DEFAULT_PASSWORD = "admin1234"
PASSWORD = os.environ.get("BLOG_PASSWORD", DEFAULT_PASSWORD)
# 회원가입·로그인은 PHP(php-auth)가 맡음. 블로그는 PHP가 서명한 입장권을 확인해서 로그인시킴.
# 블로그·회원 서버 주소(BLOG_URL·AUTH_URL)는 아래 '배포 설정'에서 정함
SSO_KEY_PATH = os.path.join(BASE_DIR, "php-auth", "db", "sso.key")
ADMIN_USERNAME = "admin"
USERNAME_RE = re.compile(r"^[a-z0-9_]{4,20}$")
PAGE_SIZE = 8
SESSION_TTL = 60 * 60 * 24 * 14
# 방문자 댓글 삭제 비밀번호: 15분 안에 같은 IP 5번, IP와 관계없이 20번 틀리면 잠금 (SEC-03과 같은 규칙)
PW_WINDOW = 15 * 60
PW_MAX_PER_IP = 5
PW_MAX_ALL = 20
POST_TYPES = {"insight": "인사이트", "faq": "자주 묻는 질문", "glossary": "용어 사전", "daily": "일상"}
CATEGORIES = ["마케팅", "AI/기술", "데이터"]
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
# 첨부할 수 있는 파일 (확장자 → 내려받을 때의 형식). HTML·SVG·JS처럼 브라우저가 실행할 수 있는 형식은 받지 않음
FILE_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json",
    ".zip": "application/zip",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".hwp": "application/x-hwp",
    ".hwpx": "application/hwp+zip",
    ".key": "application/x-iwork-keynote-sffkey",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
}
IMAGE_MAX = 10 * 1024 * 1024
FILE_MAX = 30 * 1024 * 1024

# ---------- 배포 설정 (003): 블로그와 회원 서버가 함께 읽는 deploy.config.json ----------
# 파일이 없으면 개발 모드(지금과 같음). 공개 모드는 이 파일의 public_mode로만 켠다.
# 관리자 비밀번호 같은 비밀값은 이 파일에 넣지 않는다(BLOG_PASSWORD 환경변수).
CONFIG_PATH = os.environ.get("MYBLOG_CONFIG") or os.path.join(BASE_DIR, "deploy.config.json")
CONFIG_EXIT = 78  # 설정 오류로 켜지 않을 때의 종료 코드 (systemd가 다시 켜지 않게)
LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def load_config():
    """deploy.config.json 읽기 → (내용 dict, 오류 문구 목록). 파일이 없으면 빈 설정."""
    if not os.path.exists(CONFIG_PATH):
        return {}, []
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return {}, [f"배포 설정 파일(deploy.config.json)을 읽을 수 없어요: {e}. JSON 형식을 확인해 주세요."]
    if not isinstance(data, dict):
        return {}, ["배포 설정 파일(deploy.config.json)을 읽을 수 없어요: 맨 바깥이 { } 가 아니에요. JSON 형식을 확인해 주세요."]
    return data, []


def https_origin(url):
    """'https://호스트[:포트]' 꼴(경로·쿼리·조각·사용자 정보 없음)이면 정리한 주소, 아니면 None."""
    try:
        u = urlsplit(str(url))
        port = u.port
    except ValueError:
        return None
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        return None
    if u.path not in ("", "/") or u.query or u.fragment or "@" in u.netloc:
        return None
    host = u.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    return f"https://{host}" + (f":{port}" if port else "")


def ip_obj(text):
    """IP 주소 문자열 → ipaddress 객체(IPv4로 표현된 IPv6는 IPv4로), 아니면 None."""
    try:
        a = ipaddress.ip_address(str(text).strip())
    except ValueError:
        return None
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a


def build_settings(raw, env):
    """설정 파일 내용 + 환경변수 → (설정 dict, 오류 문구 목록). 순서는 specs/003 contracts/deploy-config.md."""
    errors = []

    def bad(key, rule):
        errors.append(f"deploy.config.json의 {key} 값이 올바르지 않아요: {rule}.")

    public = raw.get("public_mode")
    public = False if public is None else public
    if not isinstance(public, bool):
        bad("public_mode", "true 또는 false로 적어 주세요")
        public = False

    urls = {}
    for key, env_name, default, example in (
        ("blog_url", "BLOG_URL", "http://localhost:8000", "blog"),
        ("auth_url", "AUTH_URL", "http://localhost:8080", "auth"),
    ):
        file_val = raw.get(key)
        if file_val is not None and not isinstance(file_val, str):
            bad(key, "주소를 문자열로 적어 주세요")
            file_val = None
        env_val = (env.get(env_name) or "").strip()
        if public:
            value = (file_val or "").strip().rstrip("/")
            if not https_origin(value):
                errors.append(
                    f"공개 모드에서는 {key}에 https 주소만 넣어 주세요(예: https://{example}.example.com, 경로 없이)."
                )
            if env_val and env_val.rstrip("/") != value:
                errors.append(
                    f"공개 모드에서는 주소를 deploy.config.json 한 곳에만 넣어 주세요. "
                    f"환경변수 {env_name}을 지우거나 파일과 같게 맞춰 주세요."
                )
        else:
            value = (env_val or (file_val or "").strip() or default).rstrip("/")
        urls[key] = value
    if public:
        b, a = https_origin(urls["blog_url"]), https_origin(urls["auth_url"])
        if b and a and b == a:
            errors.append("블로그와 회원 서버는 서로 다른 주소를 써야 해요(예: blog.·auth. 하위 도메인).")

    tp = raw.get("trusted_proxies")
    if tp is None:
        tp = ["127.0.0.1", "::1"] if public else []
    proxies = set()
    if not isinstance(tp, list):
        bad("trusted_proxies", 'IP 주소 목록으로 적어 주세요(예: ["127.0.0.1"])')
    else:
        for item in tp:
            a = ip_obj(item) if isinstance(item, str) else None
            if a is None:
                bad("trusted_proxies", f"{item!r}은(는) IP 주소가 아니에요(범위 표기는 쓸 수 없어요)")
            else:
                proxies.add(a)
        if public and not tp:
            errors.append(
                "공개 모드에서는 믿는 프록시(trusted_proxies)를 하나 이상 적어 주세요(같은 서버의 Nginx면 127.0.0.1)."
            )

    sg = raw.get("signup")
    sg = {} if sg is None else sg
    if not isinstance(sg, dict):
        bad("signup", "{ } 안에 per_ip_per_hour·site_per_hour·bot_check를 적어 주세요")
        sg = {}

    def int_in(name, default, lo, hi):
        v = sg.get(name)
        v = default if v is None else v
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            bad(f"signup.{name}", f"{lo}~{hi} 사이의 정수로 적어 주세요")
            return default
        return v

    per_ip = int_in("per_ip_per_hour", 3, 1, 1000)
    site = int_in("site_per_hour", 30, 1, 100000)
    if site < per_ip:
        bad("signup.site_per_hour", "per_ip_per_hour 이상이어야 해요")
    bot = sg.get("bot_check")
    bot = True if bot is None else bot
    if not isinstance(bot, bool):
        bad("signup.bot_check", "true 또는 false로 적어 주세요")
        bot = True
    if public and bot is False:
        errors.append("공개 모드에서는 자동 가입 방지(signup.bot_check)를 끌 수 없어요.")

    return {
        "public_mode": public,
        "blog_url": urls["blog_url"],
        "auth_url": urls["auth_url"],
        "trusted_proxies": proxies,
        "signup": {"per_ip_per_hour": per_ip, "site_per_hour": site, "bot_check": bot},
    }, errors


_RAW_CONFIG, CONFIG_ERRORS = load_config()
SETTINGS, _SETTING_ERRORS = build_settings(_RAW_CONFIG, os.environ)
CONFIG_ERRORS = CONFIG_ERRORS + _SETTING_ERRORS
PUBLIC_MODE = SETTINGS["public_mode"]
BLOG_URL = SETTINGS["blog_url"]
AUTH_URL = SETTINGS["auth_url"]
TRUSTED_PROXIES = SETTINGS["trusted_proxies"]


def is_trusted(ip):
    """바로 앞 접속(ip)이 믿는 프록시인지 (정규화해서 비교)."""
    a = ip_obj(ip)
    return a is not None and a in TRUSTED_PROXIES


_WARNED = set()


def warn_once(msg):
    """운영자용 안내를 서버 출력에 한 번만."""
    if msg not in _WARNED:
        _WARNED.add(msg)
        print(msg, file=sys.stderr, flush=True)


def check_config():
    """켜기 전에 확인할 설정 문제 목록(한국어). 비어 있으면 켜도 됨. DB는 건드리지 않는다."""
    problems = list(CONFIG_ERRORS)
    if PUBLIC_MODE:
        if HOST not in LOOPBACK_HOSTS:
            problems.append("공개 모드에서는 블로그 서버를 127.0.0.1에만 열어요. HOST 환경변수를 지우거나 127.0.0.1로 바꿔 주세요.")
        # 관리자 비밀번호 (US1): 기본값으로 돌아가는 일을 공개 모드에서는 허용하지 않음
        pw = os.environ.get("BLOG_PASSWORD")
        if not pw:
            problems.append(
                "공개 모드에서는 관리자 비밀번호를 정해야 해요. BLOG_PASSWORD 환경변수(예: /etc/my-blog/blog.env)에 넣어 주세요."
            )
        elif pw == DEFAULT_PASSWORD:
            problems.append("기본 관리자 비밀번호(admin1234)는 공개 모드에서 쓸 수 없어요.")
        elif len(pw) < 12 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
            problems.append("관리자 비밀번호는 12자 이상, 영문과 숫자를 함께 넣어 주세요.")
    return problems


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def columns(conn, table):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


# 자주 찾는 연결 칸(FK)의 인덱스 (NFR-18). 글·댓글이 많아져도 글 목록의 댓글 수, 블로그별 글·방문,
# 회원 탈퇴 정리가 표 전체를 훑지 않게 한다. 이름은 docs/erd(Crowfoot 문서)와 같다.
FK_INDEXES = (
    ("idx_posts_author_id", "posts", "author_id"),
    ("idx_comments_post_id", "comments", "post_id"),
    ("idx_comments_user_id", "comments", "user_id"),
    ("idx_comments_parent_id", "comments", "parent_id"),
    ("idx_likes_user_id", "likes", "user_id"),
    ("idx_sessions_user_id", "sessions", "user_id"),
    ("idx_files_user_id", "files", "user_id"),
    ("idx_blog_visits_blog_id", "blog_visits", "blog_id"),
)


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                is_public INTEGER NOT NULL DEFAULT 1,
                views INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS visits (day TEXT, visitor TEXT, PRIMARY KEY (day, visitor));
            CREATE TABLE IF NOT EXISTS likes (
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                PRIMARY KEY (post_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS neighbors (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                blog_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, blog_id)
            );
            CREATE INDEX IF NOT EXISTS idx_neighbors_blog ON neighbors (blog_id);
            CREATE TABLE IF NOT EXISTS sso_nonces (nonce TEXT PRIMARY KEY, expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS blog_visits (
                day TEXT, blog_id INTEGER, visitor TEXT, PRIMARY KEY (day, blog_id, visitor)
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                nickname TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS files (
                stored_name TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                size INTEGER NOT NULL,
                user_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            """
        )
        defaults = {
            "blog_title": "나의 블로그",
            "blog_desc": "일상과 생각을 기록하는 공간",
            "nickname": "블로그 주인",
            "avatar": "",
            "allow_signup": "1",
            "stock_codes": "005930,000660",
            "naver_client_id": "",
            "naver_client_secret": "",
            "google_places_key": "",
        }
        for k, v in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))

        # 관리자 계정: 아이디 admin, 비밀번호는 실행할 때 정한 BLOG_PASSWORD
        admin = conn.execute("SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        nickname = conn.execute("SELECT value FROM settings WHERE key = 'nickname'").fetchone()[0]
        if admin:
            admin_id = admin["id"]
            # 비밀번호가 바뀌었으면(예전 해시로 확인 안 됨) 예전 관리자 로그인을 모두 끊음 (003 US1)
            old_hash = conn.execute("SELECT password_hash FROM users WHERE id = ?", (admin_id,)).fetchone()[0]
            if not check_pw(PASSWORD, old_hash):
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (admin_id,))
            conn.execute("UPDATE users SET password_hash = ?, role = 'admin' WHERE id = ?", (hash_pw(PASSWORD), admin_id))
        else:
            admin_id = conn.execute(
                "INSERT INTO users (username, nickname, password_hash, role, created_at) VALUES (?,?,?,?,?)",
                (ADMIN_USERNAME, nickname, hash_pw(PASSWORD), "admin", now_iso()),
            ).lastrowid

        # 예전 데이터 옮기기
        cols = columns(conn, "posts")
        if "type" not in cols:
            conn.execute("ALTER TABLE posts ADD COLUMN type TEXT NOT NULL DEFAULT 'insight'")
            conn.execute("UPDATE posts SET type = 'daily' WHERE category = '공지'")
        if "author_id" not in cols:
            conn.execute("ALTER TABLE posts ADD COLUMN author_id INTEGER REFERENCES users(id)")
        if "cover" not in cols:
            # 005: 대표 사진 ('' 자동, 'none' 사진 없이, 본문 속 업로드 사진 주소)
            conn.execute("ALTER TABLE posts ADD COLUMN cover TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE posts SET author_id = ? WHERE author_id IS NULL", (admin_id,))
        if "watchlist" not in columns(conn, "users"):
            conn.execute("ALTER TABLE users ADD COLUMN watchlist TEXT")
        if "user_id" not in columns(conn, "comments"):
            conn.execute("ALTER TABLE comments ADD COLUMN user_id INTEGER REFERENCES users(id)")
        ccols = columns(conn, "comments")
        if "parent_id" not in ccols:
            # 답글: 어느 댓글에 단 답글인지 (1단계만)
            conn.execute("ALTER TABLE comments ADD COLUMN parent_id INTEGER REFERENCES comments(id)")
        if "deleted" not in ccols:
            # 답글이 달린 댓글을 지우면 '삭제된 댓글입니다'로 남김
            conn.execute("ALTER TABLE comments ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")
        # 예전 고정 카테고리 정리는 딱 한 번만 (이제 카테고리는 블로그마다 따로)
        if not conn.execute("SELECT 1 FROM settings WHERE key = 'migrated_categories'").fetchone():
            conn.execute(
                f"UPDATE posts SET category = '' WHERE category NOT IN ({','.join('?' * len(CATEGORIES))})", CATEGORIES
            )
            conn.execute("INSERT INTO settings VALUES ('migrated_categories', '1')")
        # 회원마다 자기 블로그: 이름·소개·프로필 사진·카테고리
        ucols = columns(conn, "users")
        if "auth_uid" not in ucols:
            # PHP 회원 번호와 연결 (이름이 아니라 번호로 연결해서, 같은 아이디로 남의 계정에 들어갈 수 없게)
            conn.execute("ALTER TABLE users ADD COLUMN auth_uid INTEGER")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_auth_uid ON users (auth_uid)")
        # 미니룸: 기본 목록에서 고른 배경·캐릭터 (없으면 내 방 + 곰)
        for col, default in (("room_bg", "room"), ("room_char", "bear")):
            if col not in ucols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT '{default}'")
        # 006: 블로그 꾸미기 — 대표 색, 끈 사이드바·배너 항목(JSON 목록)
        for col, default in (("skin", "coral"), ("hidden_widgets", "[]")):
            if col not in ucols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT '{default}'")
        # 002: 회원 서버 가입 시각(번호 재사용 구분)·회원 페이지에서 닉네임 바꾼 시각
        if "auth_joined" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN auth_joined TEXT")
        if "auth_nick_at" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN auth_nick_at INTEGER NOT NULL DEFAULT 0")
        for col in ("blog_title", "blog_desc", "avatar", "categories"):
            if col not in ucols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        site = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}
        conn.execute(
            "UPDATE users SET blog_title = ?, blog_desc = ?, avatar = ? WHERE id = ? AND blog_title IS NULL",
            (site["blog_title"], site["blog_desc"], site["avatar"], admin_id),
        )
        conn.execute("UPDATE users SET blog_title = nickname || '의 블로그' WHERE blog_title IS NULL")
        conn.execute("UPDATE users SET blog_desc = '' WHERE blog_desc IS NULL")
        conn.execute("UPDATE users SET avatar = '' WHERE avatar IS NULL")
        conn.execute("UPDATE users SET categories = ? WHERE categories IS NULL", (json.dumps(CATEGORIES, ensure_ascii=False),))
        if not conn.execute("SELECT 1 FROM settings WHERE key = 'seeded_v2'").fetchone():
            now = now_iso()
            for row in SAMPLE_POSTS:
                conn.execute(
                    "INSERT INTO posts (type, category, title, content, tags, author_id, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    row + (admin_id, now, now),
                )
            conn.execute("INSERT INTO settings VALUES ('seeded_v2', '1')")
        # 예전 회원 삭제가 남긴 찌꺼기 정리는 딱 한 번만: 없는 글·회원에 붙은 공감, 없는 글에 달린 댓글
        if not conn.execute("SELECT 1 FROM settings WHERE key = 'cleaned_orphans'").fetchone():
            conn.execute(
                "DELETE FROM likes WHERE post_id NOT IN (SELECT id FROM posts) OR user_id NOT IN (SELECT id FROM users)"
            )
            conn.execute("DELETE FROM comments WHERE post_id NOT IN (SELECT id FROM posts)")
            conn.execute("INSERT INTO settings VALUES ('cleaned_orphans', '1')")
        # 방문자 댓글 비밀번호 실패 기록 (잠금용)
        conn.execute("CREATE TABLE IF NOT EXISTS comment_pw_fails (comment_id INTEGER NOT NULL, ip TEXT NOT NULL, at INTEGER NOT NULL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_pw_fails ON comment_pw_fails (comment_id, at)")
        # 연결 칸 인덱스: 위에서 칸을 더한 뒤에 만들고, 이미 있으면 그대로 둔다(기존 DB의 자료는 바꾸지 않음)
        for name, table, col in FK_INDEXES:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({col})")
        conn.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))


def restore_orphan_replies():
    """예전 회원 탈퇴가 부모 댓글만 지워 남은 답글: 같은 번호로 '삭제된 댓글' 자리를 되살려 다시 보이게 (딱 한 번)."""
    with db() as conn:
        if conn.execute("SELECT 1 FROM settings WHERE key = 'restored_orphan_replies'").fetchone():
            return
        orphans = conn.execute(
            "SELECT parent_id, MIN(post_id) AS post_id, MIN(created_at) AS created_at FROM comments "
            "WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM comments) GROUP BY parent_id"
        ).fetchall()
    if orphans:
        backup = os.path.join(BASE_DIR, "blog.backup-before-reply-restore.db")
        if not os.path.exists(backup):
            shutil.copy2(DB_PATH, backup)
    with db() as conn:
        for o in orphans:
            conn.execute(
                "INSERT INTO comments (id, post_id, name, password_hash, content, created_at, user_id, parent_id, deleted) "
                "VALUES (?, ?, '', '', '', ?, NULL, NULL, 1)",
                (o["parent_id"], o["post_id"], o["created_at"]),
            )
        conn.execute("INSERT INTO settings VALUES ('restored_orphan_replies', '1')")


def tidy_deleted_parent(conn, parent_id):
    """'삭제된 댓글' 자리에 살아 있는 답글이 하나도 없으면 자리와 그 아래 지운 답글까지 정리."""
    if parent_id is None:
        return
    if not conn.execute("SELECT 1 FROM comments WHERE parent_id = ? AND deleted = 0", (parent_id,)).fetchone():
        conn.execute("DELETE FROM comments WHERE id = ? AND deleted = 1", (parent_id,))
        conn.execute("DELETE FROM comments WHERE parent_id = ? AND deleted = 1", (parent_id,))


def pw_lock_minutes(conn, cid, ip):
    """댓글 비밀번호 잠금이면 남은 분(1 이상), 아니면 0. 15분 지난 실패 기록은 여기서 정리."""
    now = int(time.time())
    conn.execute("DELETE FROM comment_pw_fails WHERE at <= ?", (now - PW_WINDOW,))
    per_ip = conn.execute(
        "SELECT COUNT(*), MIN(at) FROM comment_pw_fails WHERE comment_id = ? AND ip = ?", (cid, ip)
    ).fetchone()
    total = conn.execute("SELECT COUNT(*), MIN(at) FROM comment_pw_fails WHERE comment_id = ?", (cid,)).fetchone()
    first = None
    if per_ip[0] >= PW_MAX_PER_IP:
        first = per_ip[1]
    if total[0] >= PW_MAX_ALL:
        first = total[1] if first is None else min(first, total[1])
    if first is None:
        return 0
    return max(1, -(-(first + PW_WINDOW - now) // 60))


SAMPLE_POSTS = [
    (
        "insight", "마케팅", "리텐션이 신규 유입보다 중요한 이유",
        "## 한 줄 요약\n\n신규 고객 한 명을 데려오는 비용은 기존 고객을 지키는 비용보다 훨씬 큽니다.\n\n"
        "## 왜 그럴까\n\n- 광고 단가는 해마다 오릅니다\n- 재구매 고객은 객단가가 높습니다\n- 만족한 고객은 스스로 추천합니다\n\n"
        "> 새는 바가지에 물을 붓기 전에, 구멍부터 막자.\n",
        "리텐션,그로스",
    ),
    (
        "faq", "AI/기술", "생성형 AI는 회사 데이터를 학습하나요?",
        "서비스와 요금제에 따라 다릅니다. 대부분의 기업용 요금제는 **입력한 데이터를 모델 학습에 쓰지 않는다**고 약관에 명시합니다.\n\n"
        "도입 전에 이용 약관의 *데이터 사용* 항목을 꼭 확인하세요.",
        "생성형AI,보안",
    ),
    (
        "faq", "데이터", "대시보드는 얼마나 자주 봐야 하나요?",
        "지표의 성격에 맞추세요. 매출·장애처럼 바로 대응해야 하는 지표는 매일, 리텐션·LTV처럼 천천히 움직이는 지표는 주 단위나 월 단위로 보면 충분합니다.",
        "대시보드",
    ),
    (
        "glossary", "마케팅", "CTR (Click Through Rate)",
        "**클릭률.** 광고나 링크가 노출된 횟수 중 실제로 클릭된 비율입니다.\n\n`CTR = 클릭 수 ÷ 노출 수 × 100`\n\n"
        "예: 1,000번 노출되어 25번 클릭되면 CTR은 2.5%입니다.",
        "광고,지표",
    ),
    (
        "glossary", "AI/기술", "LLM (Large Language Model)",
        "**대규모 언어 모델.** 방대한 텍스트로 학습해 사람처럼 글을 이해하고 만들어 내는 AI 모델입니다.",
        "생성형AI",
    ),
    (
        "glossary", "데이터", "코호트 (Cohort)",
        "**같은 시기에 같은 경험을 한 사용자 묶음.** 예를 들어 '9월 가입자'가 하나의 코호트입니다. 코호트별로 리텐션을 비교하면 제품 개선 효과를 확인할 수 있습니다.",
        "분석,리텐션",
    ),
    (
        "daily", "", "블로그를 새로 단장했어요",
        "인사이트, 자주 묻는 질문, 용어 사전, 일상 네 가지로 글을 나눴습니다. 앞으로 마케팅·AI/기술·데이터 이야기를 꾸준히 기록할게요. ☕️",
        "일상",
    ),
]


def hash_pw(pw):
    salt = secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"


def check_pw(pw, stored):
    if not stored or "$" not in stored:
        return False
    salt, h = stored.split("$", 1)
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex(), h)


def norm_tags(raw):
    seen = []
    for t in re.split(r"[,#]", raw or ""):
        t = t.strip()
        if t and t not in seen:
            seen.append(t)
    return ",".join(seen[:20])


# 004: 목록·관련 글 대표 사진 = 본문 사진 중 이 블로그에 올린 사진(/uploads/)의 첫 번째.
# 마크다운 ![](주소 "제목")·<주소>·띄어쓰기와 HTML <img src>를 모두 찾고, 외부 주소 사진(추적 위험)과
# 코드(``` ~~~ 블록·인라인)·HTML 주석 속 예시는 쓰지 않음.
# 정규식은 모두 다음 구분 문자([ ] < > ( ) 줄바꿈)에서 멈추게 써서, 일부러 만든 긴 본문에도 걸리는 시간이 길이에 비례만 함
THUMB_RE = re.compile(
    r"(?:!\[[^\[\]\n]*\]\(\s*<?|(?i:<img\b)[^<>]*?\s(?i:src)\s*=\s*[\"']?)"
    r"(/uploads/[0-9a-f]{32}\.(?:png|jpg|gif|webp))(?=[\s)>\"'])"
)
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,}).*?(?:^[ \t]{0,3}\1|\Z)", re.S | re.M)
COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
INLINE_CODE_RE = re.compile(r"``(?:[^`\n]|`(?!`))*?``|`[^`\n]*`")
TAG_RE = re.compile(r"</?[a-zA-Z][^<>]*>")
MD_NOISE_RE = re.compile(r"!\[[^\[\]]*\]\([^()]*\)|[#>*_`~|\-\[\]]|\((?:http|/uploads/)[^()]*\)|📎")
POST_MAX_CHARS = 200_000  # 본문 최대 글자 수 (요약·대표 사진 계산이 느려지지 않게)


def _image_text(text):
    """사진을 찾을 본문: 코드(``` ~~~ 블록·인라인)와 HTML 주석 속 예시는 뺌"""
    return INLINE_CODE_RE.sub(" ", COMMENT_RE.sub(" ", FENCE_RE.sub(" ", text or "")))


def first_upload_image(text):
    """대표 사진 주소 (없으면 None)"""
    m = THUMB_RE.search(_image_text(text))
    return m.group(1) if m else None


def upload_images(text):
    """005: 본문에 있는 이 블로그 업로드 사진 주소들 (나온 순서, 중복 없이) — 대표 사진 선택지·검사용"""
    seen = []
    for m in THUMB_RE.finditer(_image_text(text)):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


COVER_RE = re.compile(r"/uploads/[0-9a-f]{32}\.(?:png|jpg|gif|webp)")


def post_thumbnail(text, cover=""):
    """005: 목록·관련 글 대표 사진. 고른 사진이 본문에 남아 있으면 그 사진, 'none'이면 없음, 그 밖에는 자동(첫 업로드 사진)"""
    if cover == "none":
        return None
    if cover and COVER_RE.fullmatch(cover) and cover in upload_images(text):
        return cover
    return first_upload_image(text)


def strip_tags_outside_code(text):
    """HTML 태그(사진 등)는 빼되, 인라인 코드 안의 <글자>는 남김"""
    out, last = [], 0
    for m in INLINE_CODE_RE.finditer(text):
        out.append(TAG_RE.sub(" ", text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(TAG_RE.sub(" ", text[last:]))
    return "".join(out)


def post_dict(row, full=False):
    d = dict(row)
    d["tags"] = [t for t in d["tags"].split(",") if t]
    d["is_public"] = bool(d["is_public"])
    if not full:
        text = d.pop("content")
        d["thumbnail"] = post_thumbnail(text, d.get("cover") or "")
        plain = strip_tags_outside_code(COMMENT_RE.sub(" ", FENCE_RE.sub(" ", text)))
        plain = MD_NOISE_RE.sub(" ", plain)
        d["excerpt"] = re.sub(r"\s+", " ", plain).strip()[:160]
    return d


# 글 목록·상세에서 함께 가져오는 작성자 정보
POST_SELECT = (
    "SELECT p.*, u.nickname AS author_nickname, u.role AS author_role, u.username AS author_username, "
    "u.blog_title AS author_blog_title, u.avatar AS author_avatar, "
    "(SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.deleted = 0) AS comment_count, "
    "(SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS like_count "
    "FROM posts p LEFT JOIN users u ON u.id = p.author_id"
)


# ---------- 주가 (네이버 증권 실시간 시세, 지연 0초 / 서버 캐시 4초) ----------
# 방문자가 아무리 많아도 네이버에는 4초에 한 번, 필요한 종목을 한꺼번에 묻는다.
REALTIME_URL = "https://polling.finance.naver.com/api/realtime/domestic/{kind}/{codes}"
SEARCH_URL = "https://ac.stock.naver.com/ac?q={q}&target=stock"
QUOTE_TTL = 4
QUOTES = {}  # (kind, code) -> (가져온 시각, 시세)
QUOTE_LOCK = threading.Lock()
INDEXES = ["KOSPI", "KOSDAQ"]
DIRECTION = {"1": "up", "2": "up", "3": "flat", "4": "down", "5": "down"}
MAX_WATCH = 12


def http_json(url, headers=None, body=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"User-Agent": "Mozilla/5.0", **({"Content-Type": "application/json"} if body is not None else {}), **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------- 맛집: 네이버 검색 API(장소·블로그 후기) + 구글 Places API(평점·리뷰) ----------
SECRET_KEYS = ("naver_client_id", "naver_client_secret", "google_places_key")
FOOD_CACHE = {}  # 요청 → (시각, 결과). 같은 검색은 10분 동안 다시 묻지 않아 사용량 절약
FOOD_TTL = 600
FOOD_LOCK = threading.Lock()


def strip_tags(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def cached(key, fn):
    now = time.time()
    with FOOD_LOCK:
        hit = FOOD_CACHE.get(key)
        if hit and now - hit[0] < FOOD_TTL:
            return hit[1]
    value = fn()
    with FOOD_LOCK:
        FOOD_CACHE[key] = (now, value)
        if len(FOOD_CACHE) > 500:
            FOOD_CACHE.pop(next(iter(FOOD_CACHE)))
    return value


def api_error_message(e, service):
    code = getattr(e, "code", None)
    if code in (400, 401, 403):
        return f"{service} 키가 올바르지 않거나 이 기능이 켜져 있지 않습니다. 블로그 설정에서 키를 확인해 주세요."
    if code == 429:
        return f"{service} 하루 사용량을 다 썼습니다. 내일 다시 시도해 주세요."
    return f"{service}에 연결하지 못했습니다."


def naver_search(keys, kind, query, display):
    url = f"https://openapi.naver.com/v1/search/{kind}.json?query={quote(query)}&display={display}"
    if kind == "blog":
        url += "&sort=sim"
    return http_json(url, {"X-Naver-Client-Id": keys["naver_client_id"], "X-Naver-Client-Secret": keys["naver_client_secret"]})


def google_places(key, query, max_count=1):
    return http_json(
        "https://places.googleapis.com/v1/places:searchText",
        {
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,"
            "places.googleMapsUri,places.reviews,places.primaryTypeDisplayName",
        },
        {"textQuery": query, "languageCode": "ko", "regionCode": "KR", "maxResultCount": max_count},
    ).get("places", [])


def google_summary(p):
    return {
        "name": (p.get("displayName") or {}).get("text"),
        "address": p.get("formattedAddress"),
        "rating": p.get("rating"),
        "count": p.get("userRatingCount", 0),
        "url": p.get("googleMapsUri"),
        "category": (p.get("primaryTypeDisplayName") or {}).get("text", ""),
        "reviews": [
            {
                "author": (r.get("authorAttribution") or {}).get("displayName", ""),
                "rating": r.get("rating"),
                "text": ((r.get("text") or r.get("originalText") or {}).get("text") or "")[:600],
                "when": r.get("relativePublishTimeDescription", ""),
            }
            for r in (p.get("reviews") or [])[:5]
        ],
    }


def map_links(query):
    q = quote(query)
    return {
        "naver": f"https://map.naver.com/p/search/{q}",
        "kakao": f"https://map.kakao.com/?q={q}",
        "google": f"https://www.google.com/maps/search/?api=1&query={q}",
    }


def to_quote(d, kind):
    return {
        "code": d.get("itemCode"),
        "name": d.get("stockName") or d.get("itemCode"),
        "price": d.get("closePrice"),
        "change": d.get("compareToPreviousClosePrice"),
        "ratio": d.get("fluctuationsRatio"),
        "direction": DIRECTION.get((d.get("compareToPreviousPrice") or {}).get("code"), "flat"),
        "high": d.get("highPrice"),
        "low": d.get("lowPrice"),
        "is_open": d.get("marketStatus") == "OPEN",
        "traded_at": d.get("localTradedAt"),
        "is_index": kind == "index",
    }


def get_quotes(kind, codes):
    """캐시에 없거나 4초가 지난 종목만 한 번의 요청으로 새로 가져온다."""
    now = time.time()
    with QUOTE_LOCK:
        stale = [c for c in codes if now - QUOTES.get((kind, c), (0, None))[0] >= QUOTE_TTL]
    if stale:
        try:
            data = http_json(REALTIME_URL.format(kind=kind, codes=",".join(stale)))
            got = {d.get("itemCode"): to_quote(d, kind) for d in data.get("datas", [])}
        except Exception:  # noqa: 실패하면 직전 값을 그대로 쓰고, 없으면 '불러오지 못함'
            got = {}
        with QUOTE_LOCK:
            for c in stale:
                if c in got:
                    QUOTES[(kind, c)] = (now, got[c])
                elif (kind, c) not in QUOTES:
                    QUOTES[(kind, c)] = (now - QUOTE_TTL + 2, {"code": c, "name": c, "error": True, "is_index": kind == "index"})
    with QUOTE_LOCK:
        return [QUOTES[(kind, c)][1] for c in codes if (kind, c) in QUOTES]


def norm_stock_codes(raw, limit=MAX_WATCH):
    codes = []
    for c in re.split(r"[,\s]+", str(raw or "")):
        if re.fullmatch(r"\d{6}", c) and c not in codes:
            codes.append(c)
    return codes[:limit]


def load_categories(raw):
    try:
        cats = json.loads(raw or "[]")
        return [str(c) for c in cats if isinstance(c, str)]
    except ValueError:
        return []


BLOG_FIELDS = (
    "u.id, u.username, u.nickname, u.role, u.blog_title, u.blog_desc, u.avatar, u.categories, u.auth_uid, "
    "u.room_bg, u.room_char, u.skin, u.hidden_widgets"
)
# 미니룸 기본 목록 (그림은 static/miniroom.js). 여기 없는 값은 저장하지 않음
ROOM_BGS = ("room", "forest", "beach", "night", "cafe", "library")
ROOM_CHARS = ("bear", "cat", "rabbit", "penguin", "dog", "robot")


# 006 블로그 꾸미기: 대표 색 (색 값은 static/style.css) · 끌 수 있는 사이드바·배너 항목
SKINS = ("coral", "blue", "green", "teal", "purple", "pink", "mustard", "ink")
WIDGET_KEYS = ("room", "types", "popular", "tags", "comments", "stats")
POPULAR_LIMIT = 5


def load_hidden_widgets(raw):
    """DB의 끈 항목 목록(JSON). 모르는 이름·형식 오류는 버린다."""
    try:
        items = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(items, list):
        return []
    out = []
    for k in items:
        if isinstance(k, str) and k in WIDGET_KEYS and k not in out:
            out.append(k)
    return out


def blog_dict(row, public=False):
    d = dict(row)
    d["categories"] = load_categories(d.get("categories"))
    if "skin" in d and d["skin"] not in SKINS:
        d["skin"] = "coral"
    if "hidden_widgets" in d:
        d["hidden_widgets"] = load_hidden_widgets(d["hidden_widgets"])
    if public:
        d.pop("auth_uid", None)  # 다른 사람에게 보여 줄 때는 연결 정보 빼기
    return d


def popular_posts(conn, blog_id=None):
    """인기 글: 공개 글 중 조회수 1 이상, 조회수 많은 순(같으면 최근 글) 5개. 보는 사람과 관계없이 같다."""
    where, args = "p.is_public = 1 AND p.views >= 1", []
    if blog_id is not None:
        where += " AND p.author_id = ?"
        args.append(blog_id)
    rows = conn.execute(
        "SELECT p.id, p.title, p.type, p.views, p.created_at, p.content, p.cover, u.username AS author_username, "
        f"u.blog_title FROM posts p JOIN users u ON u.id = p.author_id WHERE {where} "
        "ORDER BY p.views DESC, p.created_at DESC, p.id DESC LIMIT ?",
        args + [POPULAR_LIMIT],
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["thumbnail"] = post_thumbnail(d.pop("content"), d.pop("cover") or "")
        if blog_id is not None:  # 그 블로그 안이면 블로그 이름은 필요 없음
            d.pop("author_username")
            d.pop("blog_title")
        out.append(d)
    return out


def sso_key():
    """PHP와 함께 쓰는 서명 키. 없으면 만든다 (먼저 만든 쪽 것을 둘 다 씀)."""
    os.makedirs(os.path.dirname(SSO_KEY_PATH), exist_ok=True)
    if not os.path.exists(SSO_KEY_PATH):
        try:
            fd = os.open(SSO_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    with open(SSO_KEY_PATH, encoding="utf-8") as f:
        key = f.read().strip()
    if len(key) < 32:
        raise ApiError(500, "로그인 연결 키(sso.key)가 올바르지 않습니다.")
    return key.encode()


def make_logout_ticket(auth_uid):
    """PHP 회원 페이지도 함께 로그아웃시키는 1분짜리 서명 표.
    회원 번호(uid)를 넣어 그 회원에게만 통하고, PHP가 nonce를 기록해 한 번만 쓰임."""
    payload = base64.urlsafe_b64encode(json.dumps(
        {"act": "logout", "uid": int(auth_uid), "exp": int(time.time()) + 60, "nonce": secrets.token_hex(16)}
    ).encode()).decode().rstrip("=")
    return payload + "." + hmac.new(sso_key(), payload.encode(), hashlib.sha256).hexdigest()


def read_ticket(ticket):
    """PHP가 만든 입장권 확인. 서명·만료를 검사하고 내용(dict)을 돌려줌."""
    try:
        payload, sig = str(ticket).split(".", 1)
        good = hmac.new(sso_key(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(good, sig):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, TypeError):
        raise ApiError(400, "로그인 정보가 올바르지 않아요. 다시 로그인해 주세요.")
    if not isinstance(data, dict) or int(data.get("exp", 0)) < time.time():
        raise ApiError(400, "로그인 시간이 지났어요. 다시 로그인해 주세요.")
    if not USERNAME_RE.match(str(data.get("username", ""))) or not data.get("nonce"):
        raise ApiError(400, "로그인 정보가 올바르지 않아요.")
    return data


def sign_bridge(data):
    """회원 서버와 주고받는 서명 값 (act로 용도 구분, 1분 만료)."""
    data = {**data, "exp": int(time.time()) + 60}
    payload = base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False).encode()).decode().rstrip("=")
    return payload + "." + hmac.new(sso_key(), payload.encode(), hashlib.sha256).hexdigest()


def read_bridge(token, act):
    """서명·act·만료가 맞으면 내용(dict), 아니면 None."""
    try:
        payload, sig = str(token).split(".", 1)
        if not hmac.compare_digest(hmac.new(sso_key(), payload.encode(), hashlib.sha256).hexdigest(), sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("act") != act or int(data.get("exp", 0)) < time.time():
        return None
    return data


def auth_post(path, form):
    """회원 서버(PHP) 호출 (3초). (상태코드, JSON) 또는 연결 실패면 None. 프록시는 쓰지 않음."""
    req = urllib.request.Request(
        AUTH_URL + path, data=urlencode(form).encode(), headers={"Accept": "application/json"}, method="POST"
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=3) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return None


def delete_blog_account(uid):
    """블로그 계정 하나와 그 글·댓글·공감·이웃·세션·파일 정리 (관리자 탈퇴·회원 스스로 탈퇴 공통)."""
    with db() as conn:
        # (foreign_keys가 꺼져 있어 ON DELETE CASCADE가 안 돌아감. 글을 지우기 전에 그 글에 달린 댓글·공감부터)
        conn.execute("DELETE FROM comments WHERE post_id IN (SELECT id FROM posts WHERE author_id = ?)", (uid,))
        conn.execute("DELETE FROM likes WHERE user_id = ? OR post_id IN (SELECT id FROM posts WHERE author_id = ?)", (uid, uid))
        conn.execute("DELETE FROM posts WHERE author_id = ?", (uid,))
        # 이 회원의 답글은 지우고, 남의 답글이 달린 이 회원의 댓글은 '삭제된 댓글입니다' 자리로 남김
        parents = [r[0] for r in conn.execute(
            "SELECT DISTINCT parent_id FROM comments WHERE user_id = ? AND parent_id IS NOT NULL", (uid,)
        ).fetchall()]
        conn.execute("DELETE FROM comments WHERE user_id = ? AND parent_id IS NOT NULL", (uid,))
        conn.execute(
            "UPDATE comments SET deleted = 1, name = '', content = '', password_hash = '', user_id = NULL "
            "WHERE user_id = ? AND id IN (SELECT parent_id FROM comments WHERE parent_id IS NOT NULL AND deleted = 0)",
            (uid,),
        )
        conn.execute("DELETE FROM comments WHERE parent_id IN (SELECT id FROM comments WHERE user_id = ?)", (uid,))
        conn.execute("DELETE FROM comments WHERE user_id = ?", (uid,))
        for parent_id in parents:
            tidy_deleted_parent(conn, parent_id)
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM blog_visits WHERE blog_id = ?", (uid,))
        conn.execute("DELETE FROM neighbors WHERE user_id = ? OR blog_id = ?", (uid, uid))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        # 올린 파일: 남은 글·댓글·프로필·사이트 설정 어디에도 안 쓰이면 기록과 실제 파일을 지움.
        # 다른 곳에 주소가 붙어 있으면 깨지지 않게 파일은 남기고 주인만 비움
        gone_files = []
        for (name,) in conn.execute("SELECT stored_name FROM files WHERE user_id = ?", (uid,)).fetchall():
            url = f"/uploads/{name}"
            in_use = conn.execute(
                "SELECT 1 FROM posts WHERE instr(content, ?) UNION ALL SELECT 1 FROM comments WHERE instr(content, ?) "
                "UNION ALL SELECT 1 FROM users WHERE avatar = ? UNION ALL SELECT 1 FROM settings WHERE value = ? LIMIT 1",
                (url, url, url, url),
            ).fetchone()
            if in_use:
                conn.execute("UPDATE files SET user_id = NULL WHERE stored_name = ?", (name,))
            else:
                conn.execute("DELETE FROM files WHERE stored_name = ?", (name,))
                gone_files.append(name)
    # 실제 파일은 DB 정리가 끝난(커밋된) 뒤에 지움
    for name in gone_files:
        try:
            os.remove(os.path.join(UPLOAD_DIR, os.path.basename(name)))
        except FileNotFoundError:
            pass


class ApiError(Exception):
    def __init__(self, status, msg):
        self.status, self.msg = status, msg


class Handler(SimpleHTTPRequestHandler):
    # 007: Python 3.9의 mimetypes는 운영체제에 따라 woff2를 모를 수 있어 직접 정함
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".woff2": "font/woff2", ".js": "text/javascript", ".css": "text/css", ".md": "text/plain; charset=utf-8",
    }

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC_DIR, **kw)

    def log_message(self, fmt, *args):
        pass

    def send_response(self, code, message=None):
        self.status_code = code
        super().send_response(code, message)

    @staticmethod
    def is_vendor(path):
        """내장 라이브러리·글꼴 주소인지 (파일을 찾을 때처럼 %xx·..를 풀어서 판단)"""
        return posixpath.normpath(unquote(path)).startswith("/vendor/")

    def list_directory(self, path):
        # 화면 폴더(/vendor/ 등)의 파일 목록은 보여 주지 않음
        self.send_error(404)
        return None

    def end_headers(self):
        if getattr(self, "vendor", False) and getattr(self, "status_code", 0) in (200, 304):
            # 007: 내장 라이브러리·글꼴은 버전 이름 폴더라 내용이 바뀌지 않음 → 1년 캐시.
            # 회원 화면(다른 주소)이 글꼴을 쓸 수 있게 다른 주소도 허용 (쿠키 없는 공개 파일)
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("Access-Control-Allow-Origin", "*")
        elif getattr(self, "revalidate", False):
            self.send_header("Cache-Control", "no-cache")
        if getattr(self, "https_ok", False):
            # 공개 모드 + https: 브라우저가 다음부터 https로만 오게 (003 US2)
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        super().end_headers()

    def send_header(self, keyword, value):
        # 공개 모드에서는 모든 쿠키(session·vid·seen_*·지우기 쿠키)를 https로만 보내게 (003 US2)
        if PUBLIC_MODE and keyword.lower() == "set-cookie" and "; secure" not in value.lower():
            value = f"{value}; Secure"
        super().send_header(keyword, value)

    # ---------- 공개 모드 관문·실제 방문자 IP (003) ----------
    def client_ip(self):
        """실제 방문자 IP: 믿는 프록시에서 온 요청만 X-Forwarded-For를 오른쪽부터 읽어 믿는 프록시가 아닌 첫 IP."""
        peer = self.client_address[0]
        if not is_trusted(peer):
            return peer
        hops = [h.strip() for h in self.headers.get("X-Forwarded-For", "").split(",") if h.strip()]
        for hop in reversed(hops):
            a = ip_obj(hop)
            if a is None:
                return peer
            if a not in TRUSTED_PROXIES:
                return str(a)
        return peer

    def public_gate(self):
        """공개 모드에서 https가 아니면 같은 경로의 https 공개 주소로 308. 응답을 보냈으면 True."""
        if not PUBLIC_MODE:
            return False
        trusted = is_trusted(self.client_address[0])
        proto = self.headers.get("X-Forwarded-Proto")
        if trusted and proto is None:
            # 설정 실수(무한 이동 대신 안내): Nginx가 X-Forwarded-Proto를 보내지 않음
            warn_once("앞단 웹 서버가 X-Forwarded-Proto를 보내지 않아요. "
                      "Nginx 설정에 proxy_set_header X-Forwarded-Proto $scheme; 을 넣어 주세요.")
            self.send_json({"error": "서버 설정 오류: 앞단 웹 서버가 X-Forwarded-Proto를 보내지 않아요. Nginx 설정을 확인해 주세요."}, 500)
            return True
        if trusted and proto.split(",")[0].strip().lower() == "https":
            self.https_ok = True
            return False
        self.send_response(308)
        self.send_header("Location", BLOG_URL + (self.path if self.path.startswith("/") else "/"))
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    # ---------- 공통 ----------
    def cookie(self, name):
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return c[name].value if name in c else None

    @property
    def user(self):
        """로그인한 사용자 (없으면 None). 요청마다 한 번만 조회."""
        if not hasattr(self, "_user"):
            self._user = None
            tok = self.cookie("session")
            if tok:
                with db() as conn:
                    row = conn.execute(
                        f"SELECT {BLOG_FIELDS} FROM sessions s JOIN users u ON u.id = s.user_id "
                        "WHERE s.token = ? AND s.expires > ?",
                        (tok, time.time()),
                    ).fetchone()
                self._user = blog_dict(row) if row else None
        return self._user

    def is_admin(self):
        return bool(self.user and self.user["role"] == "admin")

    def require_login(self):
        if not self.user:
            raise ApiError(401, "로그인이 필요합니다.")

    def require_admin(self):
        if not self.is_admin():
            raise ApiError(403, "관리자만 할 수 있습니다.")

    def visible(self):
        """지금 사용자가 볼 수 있는 글 조건 (posts 별칭은 p)."""
        if self.is_admin():
            return "1=1", []
        if self.user:
            return "(p.is_public = 1 OR p.author_id = ?)", [self.user["id"]]
        return "p.is_public = 1", []

    def can_edit(self, post):
        return bool(self.user and (self.is_admin() or post["author_id"] == self.user["id"]))

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > FILE_MAX * 4 // 3 + 1024 * 1024:  # base64로 오면 약 1.33배
            raise ApiError(413, "요청이 너무 큽니다.")
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            raise ApiError(400, "잘못된 요청입니다.")

    def send_json(self, data, status=200, headers=None):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def route(self, method):
        self.vendor = False  # 요청마다 새로 정함 (연결을 다시 쓰더라도 API 응답에 1년 캐시가 붙지 않게)
        if self.public_gate():
            return
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            if method != "GET":
                return self.send_error(405)
            if url.path.startswith("/uploads/"):
                return self.serve_upload(url.path)
            self.revalidate = True  # 화면 파일은 항상 최신 버전을 확인
            self.vendor = self.is_vendor(url.path)  # 내장 라이브러리·글꼴 (007)
            return super().do_GET()
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        parts = [p for p in url.path[5:].split("/") if p]
        try:
            fn = getattr(self, f"api_{method}_{parts[0] if parts else ''}", None)
            if not fn:
                raise ApiError(404, "없는 주소입니다.")
            fn(parts[1:], q)
        except ApiError as e:
            self.send_json({"error": e.msg}, e.status)
        except (ValueError, IndexError):
            self.send_json({"error": "잘못된 요청입니다."}, 400)
        except Exception as e:  # noqa
            self.send_json({"error": f"서버 오류: {e}"}, 500)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def do_HEAD(self):
        # HEAD도 공개 모드 관문을 거친 뒤 화면 파일 머리글만 (SimpleHTTPRequestHandler 기본 동작)
        self.vendor = False
        if self.public_gate():
            return
        self.revalidate = True
        self.vendor = self.is_vendor(urlparse(self.path).path)
        super().do_HEAD()

    def serve_upload(self, path):
        name = os.path.basename(path)
        fp = os.path.join(UPLOAD_DIR, name)
        if not os.path.isfile(fp):
            return self.send_error(404)
        with open(fp, "rb") as f:
            data = f.read()
        ext = os.path.splitext(name)[1].lower()
        image_ctype = {v: k for k, v in IMAGE_TYPES.items()}.get(ext)
        self.send_response(200)
        self.send_header("Content-Type", image_ctype or FILE_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if not image_ctype:
            # 이미지가 아닌 파일은 항상 '다운로드'로, 올린 사람이 붙인 원래 이름으로
            with db() as conn:
                row = conn.execute("SELECT original_name FROM files WHERE stored_name = ?", (name,)).fetchone()
            original = row["original_name"] if row else name
            fallback = re.sub(r"[^\w.\-]", "_", original.encode("ascii", "ignore").decode()) or name
            self.send_header(
                "Content-Disposition", f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(original)}"
            )
        self.send_header("Cache-Control", "public, max-age=31536000")
        self.end_headers()
        self.wfile.write(data)

    # ---------- 회원 ----------
    def start_session(self, user_id, status=200, extra=None):
        tok = secrets.token_urlsafe(32)
        with db() as conn:
            conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (tok, user_id, time.time() + SESSION_TTL))
        self.send_json(
            {"ok": True, **(extra or {})},
            status,
            headers={"Set-Cookie": f"session={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}"},
        )

    def api_POST_signup(self, _, __):
        raise ApiError(410, "회원가입은 회원 페이지(PHP)에서 해 주세요.")

    def api_POST_sso(self, _, __):
        """PHP 입장권으로 로그인. 처음이면 블로그를 만들어 주고, 같은 아이디의 예전 블로그 계정은 비밀번호로 연결."""
        b = self.body()
        t = read_ticket(b.get("ticket", ""))
        uid, username = int(t["uid"]), t["username"]
        nickname = str(t.get("nickname", "")).strip()[:20] or username
        with db() as conn:
            conn.execute("DELETE FROM sso_nonces WHERE expires < ?", (time.time(),))
            if conn.execute("SELECT 1 FROM sso_nonces WHERE nonce = ?", (t["nonce"],)).fetchone():
                raise ApiError(400, "이미 쓴 로그인 정보예요. 다시 로그인해 주세요.")
            linked = conn.execute("SELECT id, auth_joined, auth_nick_at FROM users WHERE auth_uid = ?", (uid,)).fetchone()
            created = False
            joined = str(t.get("joined", ""))
            nick_at = int(t.get("nick_at", 0) or 0)
            if linked:
                blog_uid = linked["id"]
                # 회원 DB를 새로 만들어 번호가 다시 쓰이면, 다른 사람이 예전 블로그로 들어오지 못하게
                if linked["auth_joined"] and joined and linked["auth_joined"] != joined:
                    raise ApiError(409, "회원 정보가 블로그 기록과 맞지 않아요. 관리자에게 문의해 주세요.")
                # 회원 페이지에서 닉네임을 바꿨으면 블로그 닉네임도 맞춤 (블로그에서 바꾼 닉네임은 그대로)
                if nick_at > (linked["auth_nick_at"] or 0):
                    conn.execute("UPDATE users SET nickname = ?, auth_nick_at = ? WHERE id = ?", (nickname, nick_at, blog_uid))
            else:
                same = conn.execute("SELECT id, password_hash, role, auth_uid FROM users WHERE username = ?", (username,)).fetchone()
                if same:
                    # 블로그에 같은 아이디가 이미 있음: 그 계정 비밀번호를 알아야만 연결 (남의 블로그를 가로채지 못하게)
                    if same["role"] == "admin" or same["auth_uid"] is not None:
                        raise ApiError(409, "블로그에서 쓸 수 없는 아이디예요. 다른 아이디로 가입해 주세요.")
                    if not check_pw(str(b.get("password", "")), same["password_hash"]):
                        if b.get("password"):
                            time.sleep(0.5)
                        self.send_json(
                            {"error": "같은 아이디의 블로그가 이미 있어요. 그 블로그의 예전 비밀번호를 입력하면 연결돼요.",
                             "need_link": True, "username": username},
                            409,
                        )
                        return
                    conn.execute("UPDATE users SET auth_uid = ? WHERE id = ?", (uid, same["id"]))
                    blog_uid = same["id"]
                else:
                    allowed = conn.execute("SELECT value FROM settings WHERE key = 'allow_signup'").fetchone()[0] == "1"
                    if not allowed:
                        raise ApiError(403, "지금은 새 블로그를 만들 수 없어요.")
                    blog_uid = conn.execute(
                        "INSERT INTO users (username, nickname, password_hash, role, created_at, blog_title, blog_desc, "
                        "avatar, categories, auth_uid) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (username, nickname, "!", "member", now_iso(), f"{nickname}의 블로그",
                         str(t.get("bio", "")).strip()[:200], "", json.dumps(CATEGORIES, ensure_ascii=False), uid),
                    ).lastrowid
                    created = True
            if joined:
                conn.execute("UPDATE users SET auth_joined = ? WHERE id = ? AND auth_joined IS NULL", (joined, blog_uid))
            if created or not linked:
                conn.execute("UPDATE users SET auth_nick_at = MAX(auth_nick_at, ?) WHERE id = ?", (nick_at, blog_uid))
            # 입장권은 한 번만 (성공했을 때 소모)
            conn.execute("INSERT INTO sso_nonces VALUES (?, ?)", (t["nonce"], int(t["exp"])))
        self.start_session(blog_uid, 201 if created else 200, {"new": created})

    def api_POST_login(self, _, __):
        b = self.body()
        username = str(b.get("username", "")).strip().lower()
        with db() as conn:
            row = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = ? AND auth_uid IS NULL", (username,)
            ).fetchone()
        if not row or not check_pw(str(b.get("password", "")), row["password_hash"]):
            time.sleep(0.5)
            raise ApiError(401, "아이디 또는 비밀번호가 틀렸습니다.")
        self.start_session(row["id"])

    def api_POST_logout(self, _, __):
        me = self.user  # 세션을 지우기 전에 누구인지 확인
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (self.cookie("session") or "",))
        # 회원 페이지(PHP)와 연결된 회원만 함께 로그아웃: 화면이 이 표를 POST 폼으로 회원 서버에 보냄 (주소에 안 실림)
        auth_logout = None
        if me and me.get("auth_uid"):
            try:
                auth_logout = {"action": f"{AUTH_URL}/sso_logout.php", "t": make_logout_ticket(me["auth_uid"])}
            except Exception:  # noqa: 키 파일을 못 읽으면 블로그만 로그아웃
                auth_logout = None
        self.send_json(
            {"ok": True, "auth_url": AUTH_URL, "auth_logout": auth_logout},
            headers={"Set-Cookie": "session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"},
        )

    def api_PUT_me(self, parts, _):
        """내 정보·내 블로그 정보 수정. 보낸 항목만 바꿈."""
        self.require_login()
        if parts and parts[0] == "categories":
            return self.save_categories()
        b = self.body()
        uid = self.user["id"]
        with db() as conn:
            if "nickname" in b:
                nickname = str(b["nickname"]).strip()
                if not 2 <= len(nickname) <= 20:
                    raise ApiError(400, "닉네임은 2~20자로 정해 주세요.")
                conn.execute("UPDATE users SET nickname = ? WHERE id = ?", (nickname, uid))
            if "blog_title" in b:
                title = str(b["blog_title"]).strip()
                if not 1 <= len(title) <= 40:
                    raise ApiError(400, "블로그 이름은 1~40자로 정해 주세요.")
                conn.execute("UPDATE users SET blog_title = ? WHERE id = ?", (title, uid))
            if "blog_desc" in b:
                conn.execute("UPDATE users SET blog_desc = ? WHERE id = ?", (str(b["blog_desc"]).strip()[:200], uid))
            if "room_bg" in b or "room_char" in b:
                bg, ch = str(b.get("room_bg", "")), str(b.get("room_char", ""))
                if ("room_bg" in b and bg not in ROOM_BGS) or ("room_char" in b and ch not in ROOM_CHARS):
                    raise ApiError(400, "목록에 있는 배경과 캐릭터만 고를 수 있어요.")
                if "room_bg" in b:
                    conn.execute("UPDATE users SET room_bg = ? WHERE id = ?", (bg, uid))
                if "room_char" in b:
                    conn.execute("UPDATE users SET room_char = ? WHERE id = ?", (ch, uid))
            if "skin" in b:
                if not isinstance(b["skin"], str) or b["skin"] not in SKINS:
                    raise ApiError(400, "목록에 있는 색만 고를 수 있어요.")
                conn.execute("UPDATE users SET skin = ? WHERE id = ?", (b["skin"], uid))
            if "hidden_widgets" in b:
                items = b["hidden_widgets"]
                if not isinstance(items, list) or not all(isinstance(k, str) and k in WIDGET_KEYS for k in items):
                    raise ApiError(400, "사이드바 항목을 다시 골라 주세요.")
                items = list(dict.fromkeys(items))  # 같은 이름은 한 번만 (보낸 순서 유지)
                conn.execute("UPDATE users SET hidden_widgets = ? WHERE id = ?", (json.dumps(items), uid))
            if "avatar" in b:
                avatar = str(b["avatar"]).strip()
                if avatar and not re.fullmatch(r"/uploads/[0-9a-f]{32}\.(png|jpg|gif|webp)", avatar):
                    raise ApiError(400, "프로필 사진을 다시 올려 주세요.")
                conn.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar, uid))
            new_pw = str(b.get("new_password", ""))
            if new_pw:
                linked = conn.execute("SELECT auth_uid FROM users WHERE id = ?", (uid,)).fetchone()["auth_uid"]
                if linked is not None:
                    raise ApiError(400, "비밀번호는 회원 페이지(PHP)에서 관리해요.")
                if self.is_admin():
                    raise ApiError(400, "관리자 비밀번호는 서버를 켤 때 BLOG_PASSWORD로 바꿉니다.")
                cur = conn.execute("SELECT password_hash FROM users WHERE id = ?", (uid,)).fetchone()
                if not check_pw(str(b.get("current_password", "")), cur["password_hash"]):
                    raise ApiError(403, "현재 비밀번호가 틀렸습니다.")
                if len(new_pw) < 8:
                    raise ApiError(400, "새 비밀번호는 8자 이상이어야 합니다.")
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_pw(new_pw), uid))
        self.send_json({"ok": True})

    def save_categories(self):
        """카테고리 목록 저장. renames {예전: 새이름}이면 그 글들도 옮기고, 지운 카테고리의 글은 '미분류'로."""
        b = self.body()
        cats = []
        for c in b.get("categories", []):
            c = str(c).strip()[:20]
            if c and c not in cats:
                cats.append(c)
        if len(cats) > 30:
            raise ApiError(400, "카테고리는 30개까지 만들 수 있어요.")
        uid = self.user["id"]
        with db() as conn:
            for old, new in (b.get("renames") or {}).items():
                if new in cats:
                    conn.execute("UPDATE posts SET category = ? WHERE author_id = ? AND category = ?", (new, uid, str(old)))
            if cats:
                conn.execute(
                    f"UPDATE posts SET category = '' WHERE author_id = ? AND category NOT IN ({','.join('?' * len(cats))})",
                    [uid] + cats,
                )
            else:
                conn.execute("UPDATE posts SET category = '' WHERE author_id = ?", (uid,))
            conn.execute("UPDATE users SET categories = ? WHERE id = ?", (json.dumps(cats, ensure_ascii=False), uid))
        self.send_json({"categories": cats})

    def api_GET_users(self, parts, _):
        if not parts:
            # 회원 목록은 관리자만
            self.require_admin()
            with db() as conn:
                rows = conn.execute(
                    "SELECT u.id, u.username, u.nickname, u.role, u.created_at, "
                    "(SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id) AS post_count "
                    "FROM users u ORDER BY u.id"
                ).fetchall()
            return self.send_json([dict(r) for r in rows])
        cond, args = self.visible()
        with db() as conn:
            row = conn.execute(
                f"SELECT u.id, u.nickname, u.role, u.created_at, "
                f"(SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND {cond}) AS post_count "
                f"FROM users u WHERE u.id = ?",
                args + [int(parts[0])],
            ).fetchone()
        if not row:
            raise ApiError(404, "없는 회원입니다.")
        self.send_json(dict(row))

    def api_DELETE_users(self, parts, _):
        self.require_admin()
        uid = int(parts[0])
        with db() as conn:
            row = conn.execute("SELECT role, auth_uid FROM users WHERE id = ?", (uid,)).fetchone()
        if not row:
            raise ApiError(404, "없는 회원입니다.")
        if row["role"] == "admin":
            raise ApiError(400, "관리자 계정은 삭제할 수 없습니다.")
        if row["auth_uid"] is not None:
            # 회원 서버(PHP) 계정부터 지우고, 성공했을 때만 블로그를 지움 (한쪽만 남지 않게)
            r = auth_post("/bridge_delete.php", {"t": sign_bridge(
                {"act": "delete_member", "uid": int(row["auth_uid"]), "nonce": secrets.token_hex(16)}
            )})
            if r is None or r[0] != 200 or not r[1].get("ok"):
                raise ApiError(503, "회원 서버에 연결할 수 없어 탈퇴를 진행하지 않았어요. 회원 서버를 켠 뒤 다시 시도해 주세요.")
        delete_blog_account(uid)
        self.send_json({"ok": True})

    # ---------- 관리자: 공개 주소·SNS 콜백·가입 현황 (003) ----------
    def api_GET_admin(self, parts, _):
        """사이트 설정 화면용. 회원 서버 상태는 서명된 bridge_status.php로 받음(연결 실패면 null)."""
        if parts != ["status"]:
            raise ApiError(404, "없는 주소입니다.")
        self.require_admin()
        auth = None
        try:
            r = auth_post("/bridge_status.php", {"t": sign_bridge({"act": "auth_status"})})
        except ApiError:
            r = None
        if r and r[0] == 200 and isinstance(r[1], dict) and r[1].get("ok"):
            auth = r[1]
        self.send_json({"deploy": {"public_mode": PUBLIC_MODE, "blog_url": BLOG_URL, "auth_url": AUTH_URL}, "auth": auth})

    # ---------- 회원 서버와 주고받기 (서명된 요청만) ----------
    def api_GET_bridge(self, parts, _):
        """회원 서버가 '회원가입 허용' 값을 읽어 감 (서명해서 줌)."""
        if parts != ["signup"]:
            raise ApiError(404, "없는 주소입니다.")
        with db() as conn:
            allow = conn.execute("SELECT value FROM settings WHERE key = 'allow_signup'").fetchone()[0] == "1"
        self.send_json({"t": sign_bridge({"act": "signup_state", "allow": allow})})

    def api_POST_bridge(self, parts, _):
        """회원 서버에서 회원이 스스로 탈퇴할 때 블로그 계정을 먼저 지움. 여기서는 회원 서버를 다시 부르지 않음."""
        if parts != ["delete_member"]:
            raise ApiError(404, "없는 주소입니다.")
        b = self.body()
        data = read_bridge(b.get("t", "") if isinstance(b, dict) else "", "delete_member")
        if not data or int(data.get("uid", 0)) <= 0 or len(str(data.get("nonce", ""))) < 16:
            raise ApiError(400, "서명이 올바르지 않아요.")
        with db() as conn:
            conn.execute("DELETE FROM sso_nonces WHERE expires < ?", (time.time(),))
            if conn.execute("SELECT 1 FROM sso_nonces WHERE nonce = ?", (data["nonce"],)).fetchone():
                raise ApiError(400, "이미 처리한 요청이에요.")
            conn.execute("INSERT INTO sso_nonces VALUES (?, ?)", (data["nonce"], int(data["exp"])))
            row = conn.execute("SELECT id, role FROM users WHERE auth_uid = ?", (int(data["uid"]),)).fetchone()
        if row and row["role"] == "admin":
            raise ApiError(400, "관리자 계정은 탈퇴할 수 없어요.")
        if row:
            delete_blog_account(row["id"])
        self.send_json({"ok": True, "deleted": bool(row)})

    # ---------- 블로그들 ----------
    def visitor_id(self):
        """방문자 쿠키 (없으면 새로 만들고, 응답에 붙일 Set-Cookie를 돌려줌)."""
        vid = self.cookie("vid")
        if vid:
            return vid, {}
        vid = uuid.uuid4().hex
        return vid, {"Set-Cookie": f"vid={vid}; Path=/; Max-Age=31536000; SameSite=Lax"}

    def record_blog_visit(self, conn, blog_id, visitor):
        if self.user and self.user["id"] == blog_id:
            return  # 내 블로그를 내가 본 건 세지 않음
        conn.execute("INSERT OR IGNORE INTO blog_visits VALUES (?, ?, ?)", (date.today().isoformat(), blog_id, visitor))

    def blog_stats(self, conn, blog_id):
        today = date.today().isoformat()
        q = "SELECT COUNT(*) FROM blog_visits WHERE blog_id = ?"
        return {
            "today": conn.execute(q + " AND day = ?", (blog_id, today)).fetchone()[0],
            "yesterday": conn.execute(q + " AND day = date(?, '-1 day')", (blog_id, today)).fetchone()[0],
            "total": conn.execute(q, (blog_id,)).fetchone()[0],
        }

    def api_GET_blogs(self, parts, q):
        cond, args = self.visible()
        if not parts:
            # 블로그 둘러보기: 공개 글이 있는 블로그를 최근 글 순으로
            with db() as conn:
                rows = conn.execute(
                    f"SELECT {BLOG_FIELDS}, COUNT(p.id) AS post_count, MAX(p.created_at) AS last_post_at "
                    f"FROM users u JOIN posts p ON p.author_id = u.id AND p.is_public = 1 "
                    f"GROUP BY u.id ORDER BY last_post_at DESC LIMIT ?",
                    (min(50, int(q.get("size", 20))),),
                ).fetchall()
            return self.send_json([blog_dict(r, public=True) for r in rows])
        username = parts[0].lstrip("@").lower()
        vid, set_cookie = self.visitor_id()
        with db() as conn:
            row = conn.execute(f"SELECT {BLOG_FIELDS}, u.created_at FROM users u WHERE u.username = ?", (username,)).fetchone()
            if not row:
                raise ApiError(404, "없는 블로그예요.")
            blog = blog_dict(row, public=True)
            bid = blog["id"]
            if q.get("visit") == "1":
                self.record_blog_visit(conn, bid, vid)
            where, wargs = f"WHERE p.author_id = ? AND {cond}", [bid] + args
            cat_n = dict(conn.execute(f"SELECT category, COUNT(*) FROM posts p {where} GROUP BY category", wargs).fetchall())
            blog["category_counts"] = [{"name": c, "count": cat_n.get(c, 0)} for c in blog["categories"]]
            if cat_n.get(""):
                blog["category_counts"].append({"name": "", "count": cat_n[""]})
            type_n = dict(conn.execute(f"SELECT type, COUNT(*) FROM posts p {where} GROUP BY type", wargs).fetchall())
            blog["type_counts"] = [{"key": k, "name": v, "count": type_n.get(k, 0)} for k, v in POST_TYPES.items()]
            blog["total_posts"] = conn.execute(f"SELECT COUNT(*) FROM posts p {where}", wargs).fetchone()[0]
            tag_count = {}
            for r in conn.execute(f"SELECT tags FROM posts p {where}", wargs):
                for t in filter(None, r["tags"].split(",")):
                    tag_count[t] = tag_count.get(t, 0) + 1
            blog["tags"] = [{"name": n, "count": c} for n, c in sorted(tag_count.items(), key=lambda x: -x[1])[:30]]
            blog["recent_comments"] = [
                dict(r)
                for r in conn.execute(
                    f"SELECT c.id, c.post_id, c.name, substr(c.content, 1, 40) AS content FROM comments c "
                    f"JOIN posts p ON p.id = c.post_id {where} AND c.deleted = 0 ORDER BY c.id DESC LIMIT 5",
                    wargs,
                )
            ]
            blog["stats"] = self.blog_stats(conn, bid)
            blog["popular"] = popular_posts(conn, bid)
        # 006: 주인이 끈 사이드바 항목은 자료도 보내지 않음 (글 종류는 위쪽 종류 탭이 쓰므로 그대로)
        hidden = blog["hidden_widgets"]
        for key, field, empty in (("popular", "popular", []), ("tags", "tags", []), ("comments", "recent_comments", []),
                                  ("stats", "stats", None)):
            if key in hidden:
                blog[field] = empty
        blog["is_owner"] = bool(self.user and self.user["id"] == bid)
        with db() as conn:
            blog["neighbor_count"] = conn.execute("SELECT COUNT(*) FROM neighbors WHERE blog_id = ?", (bid,)).fetchone()[0]
            blog["is_neighbor"] = bool(self.user and conn.execute(
                "SELECT 1 FROM neighbors WHERE user_id = ? AND blog_id = ?", (self.user["id"], bid)
            ).fetchone())
        self.send_json(blog, headers=set_cookie)

    # ---------- 이웃 ----------
    def api_GET_neighbors(self, _, __):
        """내 이웃 목록 (최근 글 순)."""
        self.require_login()
        with db() as conn:
            rows = conn.execute(
                f"SELECT {BLOG_FIELDS}, n.created_at AS since, "
                f"(SELECT MAX(p.created_at) FROM posts p WHERE p.author_id = u.id AND p.is_public = 1) AS last_post_at, "
                f"(SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND p.is_public = 1) AS post_count "
                f"FROM neighbors n JOIN users u ON u.id = n.blog_id WHERE n.user_id = ? "
                f"ORDER BY last_post_at DESC NULLS LAST, n.created_at DESC",
                (self.user["id"],),
            ).fetchall()
        self.send_json([blog_dict(r, public=True) for r in rows])

    def api_POST_neighbors(self, parts, _):
        """이웃 추가·취소: POST /api/neighbors/<아이디> (누를 때마다 추가 ↔ 취소)."""
        if not self.user:
            raise ApiError(401, "이웃을 추가하려면 로그인하세요.")
        if not parts:
            raise ApiError(400, "어느 블로그인지 알려 주세요.")
        username = parts[0].lstrip("@").lower()
        with db() as conn:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not row:
                raise ApiError(404, "없는 블로그예요.")
            if row["id"] == self.user["id"]:
                raise ApiError(400, "내 블로그는 이웃으로 추가할 수 없어요.")
            gone = conn.execute(
                "DELETE FROM neighbors WHERE user_id = ? AND blog_id = ?", (self.user["id"], row["id"])
            ).rowcount
            if not gone:
                conn.execute("INSERT OR IGNORE INTO neighbors VALUES (?, ?, ?)", (self.user["id"], row["id"], now_iso()))
            count = conn.execute("SELECT COUNT(*) FROM neighbors WHERE blog_id = ?", (row["id"],)).fetchone()[0]
        self.send_json({"is_neighbor": not gone, "count": count})

    # ---------- 블로그 관리 (내 블로그) ----------
    def api_GET_manage(self, parts, q):
        self.require_login()
        uid = self.user["id"]
        what = parts[0] if parts else "stats"
        with db() as conn:
            if what == "stats":
                days = [
                    {"day": r["day"], "count": r["n"]}
                    for r in conn.execute(
                        "SELECT day, COUNT(*) AS n FROM blog_visits WHERE blog_id = ? AND day >= date(?, '-6 day') "
                        "GROUP BY day ORDER BY day",
                        (uid, date.today().isoformat()),
                    )
                ]

                def one(sql):
                    return conn.execute(sql, (uid,)).fetchone()[0]

                top = conn.execute(
                    "SELECT id, title, views, type FROM posts WHERE author_id = ? ORDER BY views DESC, id DESC LIMIT 5", (uid,)
                ).fetchall()
                return self.send_json({
                    **self.blog_stats(conn, uid),
                    "week": days,
                    "posts": one("SELECT COUNT(*) FROM posts WHERE author_id = ?"),
                    "public_posts": one("SELECT COUNT(*) FROM posts WHERE author_id = ? AND is_public = 1"),
                    "views": one("SELECT COALESCE(SUM(views), 0) FROM posts WHERE author_id = ?"),
                    "comments": one("SELECT COUNT(*) FROM comments c JOIN posts p ON p.id = c.post_id WHERE p.author_id = ? AND c.deleted = 0"),
                    "likes": one("SELECT COUNT(*) FROM likes l JOIN posts p ON p.id = l.post_id WHERE p.author_id = ?"),
                    "neighbors": one("SELECT COUNT(*) FROM neighbors WHERE blog_id = ?"),
                    "top_posts": [dict(r) for r in top],
                })
            if what == "comments":
                page = max(1, int(q.get("page", 1) or 1))
                total = conn.execute(
                    "SELECT COUNT(*) FROM comments c JOIN posts p ON p.id = c.post_id WHERE p.author_id = ? AND c.deleted = 0", (uid,)
                ).fetchone()[0]
                rows = conn.execute(
                    "SELECT c.id, c.post_id, c.content, c.created_at, c.user_id, COALESCE(u.nickname, c.name) AS name, "
                    "p.title AS post_title FROM comments c JOIN posts p ON p.id = c.post_id "
                    "LEFT JOIN users u ON u.id = c.user_id WHERE p.author_id = ? AND c.deleted = 0 ORDER BY c.id DESC LIMIT 20 OFFSET ?",
                    (uid, (page - 1) * 20),
                ).fetchall()
                return self.send_json(
                    {"comments": [dict(r) for r in rows], "page": page, "pages": max(1, -(-total // 20)), "total": total}
                )
        raise ApiError(404, "없는 주소입니다.")

    def api_POST_manage(self, parts, _):
        """글 여러 개를 한꺼번에: 공개/비공개 바꾸기, 삭제 (내 글만)."""
        self.require_login()
        b = self.body()
        ids = [int(i) for i in b.get("ids", [])][:200]
        if not ids:
            raise ApiError(400, "글을 골라 주세요.")
        marks = ",".join("?" * len(ids))
        mine, margs = "author_id = ?", [self.user["id"]]
        with db() as conn:
            if parts and parts[0] == "visibility":
                n = conn.execute(
                    f"UPDATE posts SET is_public = ? WHERE id IN ({marks}) AND {mine}",
                    [1 if b.get("is_public") else 0] + ids + margs,
                ).rowcount
            elif parts and parts[0] == "delete":
                own = [r[0] for r in conn.execute(f"SELECT id FROM posts WHERE id IN ({marks}) AND {mine}", ids + margs)]
                if own:
                    om = ",".join("?" * len(own))
                    conn.execute(f"DELETE FROM comments WHERE post_id IN ({om})", own)
                    conn.execute(f"DELETE FROM likes WHERE post_id IN ({om})", own)
                    conn.execute(f"DELETE FROM posts WHERE id IN ({om})", own)
                n = len(own)
            else:
                raise ApiError(404, "없는 주소입니다.")
        self.send_json({"changed": n})

    # ---------- 사이트 정보 (블로그 홈) ----------
    def api_GET_blog(self, _, __):
        visitor = self.cookie("vid")
        set_cookie = {}
        if not visitor:
            visitor = uuid.uuid4().hex
            set_cookie = {"Set-Cookie": f"vid={visitor}; Path=/; Max-Age=31536000; SameSite=Lax"}
        today = date.today().isoformat()
        cond, args = self.visible()
        where = f"WHERE {cond}"
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO visits VALUES (?, ?)", (today, visitor))
            settings = {
                r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings") if r["key"] not in ("seeded_v2", "migrated_categories")
            }
            # API 키는 절대 화면으로 보내지 않고, 등록됐는지 여부만 알려줌
            keys = {k: settings.pop(k, "") for k in SECRET_KEYS}
            settings["food_ready"] = {
                "naver": bool(keys["naver_client_id"] and keys["naver_client_secret"]),
                "google": bool(keys["google_places_key"]),
            }
            type_n = dict(conn.execute(f"SELECT type, COUNT(*) FROM posts p {where} GROUP BY type", args).fetchall())
            types = [{"key": k, "name": v, "count": type_n.get(k, 0)} for k, v in POST_TYPES.items()]
            total_posts = conn.execute(f"SELECT COUNT(*) FROM posts p {where}", args).fetchone()[0]
            tag_count = {}
            for r in conn.execute(f"SELECT tags FROM posts p {where}", args):
                for t in filter(None, r["tags"].split(",")):
                    tag_count[t] = tag_count.get(t, 0) + 1
            recent_comments = [
                dict(r)
                for r in conn.execute(
                    f"SELECT c.id, c.post_id, c.name, substr(c.content, 1, 40) AS content, c.created_at "
                    f"FROM comments c JOIN posts p ON p.id = c.post_id {where} AND c.deleted = 0 ORDER BY c.id DESC LIMIT 5",
                    args,
                )
            ]
            popular = popular_posts(conn)
            today_n = conn.execute("SELECT COUNT(*) FROM visits WHERE day = ?", (today,)).fetchone()[0]
            yest = conn.execute("SELECT COUNT(*) FROM visits WHERE day = date(?, '-1 day')", (today,)).fetchone()[0]
            total_n = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        tags = sorted(tag_count.items(), key=lambda x: -x[1])[:30]
        settings["allow_signup"] = settings.get("allow_signup") == "1"
        self.send_json(
            {
                **settings,
                "user": self.user,
                "auth_url": AUTH_URL,
                "is_admin": self.is_admin(),
                "types": types,
                "total_posts": total_posts,
                "tags": [{"name": n, "count": c} for n, c in tags],
                "recent_comments": recent_comments,
                "popular": popular,
                "stats": {"today": today_n, "yesterday": yest, "total": total_n},
            },
            headers=set_cookie,
        )

    def api_PUT_blog(self, _, __):
        self.require_admin()
        b = self.body()
        with db() as conn:
            for k in ("blog_title", "blog_desc"):
                if k in b:
                    conn.execute("UPDATE settings SET value = ? WHERE key = ?", (str(b[k])[:300], k))
            for k in SECRET_KEYS:
                v = str(b.get(k, "")).strip()
                if v == "-":  # '-'를 넣으면 등록된 키 삭제
                    conn.execute("UPDATE settings SET value = '' WHERE key = ?", (k,))
                elif v:
                    conn.execute("UPDATE settings SET value = ? WHERE key = ?", (v[:200], k))
            if "stock_codes" in b:
                codes = norm_stock_codes(b["stock_codes"])
                conn.execute("UPDATE settings SET value = ? WHERE key = 'stock_codes'", (",".join(codes),))
            if "allow_signup" in b:
                conn.execute("UPDATE settings SET value = ? WHERE key = 'allow_signup'", ("1" if b["allow_signup"] else "0",))
        self.send_json({"ok": True})

    # ---------- 주가 ----------
    def default_watchlist(self, conn):
        return norm_stock_codes(conn.execute("SELECT value FROM settings WHERE key = 'stock_codes'").fetchone()[0])

    def api_GET_stocks(self, parts, q):
        if parts and parts[0] == "search":
            return self.search_stocks(q.get("q", ""))
        with db() as conn:
            codes = norm_stock_codes(q["codes"]) if "codes" in q else self.default_watchlist(conn)
        with ThreadPoolExecutor(max_workers=2) as pool:
            idx = pool.submit(get_quotes, "index", INDEXES)
            stocks = pool.submit(get_quotes, "stock", codes) if codes else None
            quotes = idx.result() + (stocks.result() if stocks else [])
        self.send_json({"quotes": quotes, "refresh": QUOTE_TTL + 1})

    def search_stocks(self, query):
        query = query.strip()[:30]
        if not query:
            return self.send_json([])
        try:
            items = http_json(SEARCH_URL.format(q=quote(query))).get("items", [])
        except Exception:  # noqa
            raise ApiError(502, "종목 검색이 잠시 안 됩니다.")
        out = [
            {"code": i["code"], "name": i["name"], "market": i.get("typeName", "")}
            for i in items
            if i.get("nationCode") == "KOR" and re.fullmatch(r"\d{6}", str(i.get("code", "")))
        ]
        self.send_json(out[:8])

    # 관심 종목: 로그인한 회원은 계정에 저장, 손님은 기본 목록(브라우저에 따로 저장)
    def api_GET_watchlist(self, _, __):
        with db() as conn:
            if self.user:
                row = conn.execute("SELECT watchlist FROM users WHERE id = ?", (self.user["id"],)).fetchone()
                if row["watchlist"] is not None:
                    return self.send_json({"codes": norm_stock_codes(row["watchlist"]), "source": "user", "logged_in": True})
            self.send_json({"codes": self.default_watchlist(conn), "source": "default", "logged_in": bool(self.user)})

    def api_PUT_watchlist(self, _, __):
        self.require_login()
        codes = norm_stock_codes(",".join(map(str, self.body().get("codes", []))))
        with db() as conn:
            conn.execute("UPDATE users SET watchlist = ? WHERE id = ?", (",".join(codes), self.user["id"]))
        self.send_json({"codes": codes})

    # ---------- 맛집 ----------
    def food_keys(self):
        with db() as conn:
            return {k: conn.execute("SELECT value FROM settings WHERE key = ?", (k,)).fetchone()[0] for k in SECRET_KEYS}

    def api_GET_food(self, parts, q):
        # 외부 API 사용량(구글은 유료 가능)을 지키려고 로그인한 회원만 사용
        if not self.user:
            raise ApiError(401, "맛집 검색은 로그인한 회원만 쓸 수 있어요.")
        keys = self.food_keys()
        has_naver = bool(keys["naver_client_id"] and keys["naver_client_secret"])
        has_google = bool(keys["google_places_key"])
        query = str(q.get("q", "")).strip()[:50]
        if not query:
            raise ApiError(400, "식당 이름이나 '지역 + 음식'으로 검색해 주세요.")
        if parts and parts[0] == "detail":
            return self.food_detail(keys, has_naver, has_google, query, str(q.get("address", "")).strip()[:100])

        places, errors = [], []
        if has_naver:
            try:
                items = cached(("nlocal", query), lambda: naver_search(keys, "local", query, 5)).get("items", [])
                places = [
                    {
                        "name": strip_tags(i.get("title")),
                        "category": i.get("category", ""),
                        "address": i.get("roadAddress") or i.get("address", ""),
                        "link": i.get("link", ""),
                        "phone": i.get("telephone", ""),
                    }
                    for i in items
                ]
            except Exception as e:  # noqa
                errors.append(api_error_message(e, "네이버 검색 API"))
        elif has_google:
            try:
                found = cached(("gsearch", query), lambda: google_places(keys["google_places_key"], query, 5))
                places = [
                    {"name": g["name"], "category": g["category"], "address": g["address"], "rating": g["rating"], "count": g["count"]}
                    for g in map(google_summary, found)
                ]
            except Exception as e:  # noqa
                errors.append(api_error_message(e, "구글 Places API"))
        self.send_json(
            {"places": places, "naver": has_naver, "google": has_google, "errors": errors, "links": map_links(query)}
        )

    def food_detail(self, keys, has_naver, has_google, name, address):
        # 블로그 검색은 '식당 이름 + 구/동'으로 해야 다른 지점 글이 덜 섞임
        words = [w for w in address.split() if len(w) > 1 and not re.search(r"(특별시|광역시|특별자치시|도)$", w)]
        area = next((w for suffix in ("구", "군", "시", "동", "읍", "면") for w in words if w.endswith(suffix)), "")
        blog_q = f"{area} {name} 후기".strip()
        out = {"blogs": [], "google": None, "errors": [], "links": map_links(f"{name} {area}".strip()), "blog_query": blog_q}
        if has_naver:
            try:
                items = cached(("nblog", blog_q), lambda: naver_search(keys, "blog", blog_q, 10)).get("items", [])
                out["blogs"] = [
                    {
                        "title": strip_tags(i.get("title")),
                        "summary": strip_tags(i.get("description"))[:200],
                        "blogger": i.get("bloggername", ""),
                        "date": i.get("postdate", ""),
                        "link": i.get("link", ""),
                    }
                    for i in items
                ]
            except Exception as e:  # noqa
                out["errors"].append(api_error_message(e, "네이버 검색 API"))
        if has_google:
            try:
                found = cached(("gdetail", name, address), lambda: google_places(keys["google_places_key"], f"{name} {address}".strip()))
                out["google"] = google_summary(found[0]) if found else None
            except Exception as e:  # noqa
                out["errors"].append(api_error_message(e, "구글 Places API"))
        self.send_json(out)

    # ---------- 글 ----------
    def api_GET_posts(self, parts, q):
        if parts:
            return self.get_post(int(parts[0]))
        cond, args = self.visible()
        conds = [cond]
        if q.get("type") in POST_TYPES:
            conds.append("p.type = ?")
            args.append(q["type"])
        if "category" in q:
            conds.append("p.category = ?")
            args.append("" if q["category"] == "-" else q["category"])  # '-'는 미분류
        if q.get("author"):
            conds.append("p.author_id = ?")
            args.append(int(q["author"]))
        if q.get("neighbors") == "1":
            # 이웃 새 글: 내가 이웃으로 추가한 블로그의 (공개) 글만
            if not self.user:
                raise ApiError(401, "이웃 새 글은 로그인하면 볼 수 있어요.")
            conds.append("p.author_id IN (SELECT blog_id FROM neighbors WHERE user_id = ?) AND p.is_public = 1")
            args.append(self.user["id"])
        if q.get("blog"):
            conds.append("p.author_id = (SELECT id FROM users WHERE username = ?)")
            args.append(q["blog"].lstrip("@").lower())
        if q.get("tag"):
            conds.append("(',' || p.tags || ',') LIKE ?")
            args.append(f"%,{q['tag']},%")
        if q.get("q"):
            conds.append("(p.title LIKE ? OR p.content LIKE ?)")
            args += [f"%{q['q']}%"] * 2
        where = "WHERE " + " AND ".join(conds)
        page = max(1, int(q.get("page", 1) or 1))
        size = min(200, max(1, int(q.get("size", PAGE_SIZE) or PAGE_SIZE)))
        order = "p.title COLLATE NOCASE" if q.get("sort") == "title" else "p.created_at DESC, p.id DESC"
        with db() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM posts p {where}", args).fetchone()[0]
            rows = conn.execute(
                f"{POST_SELECT} {where} ORDER BY {order} LIMIT ? OFFSET ?", args + [size, (page - 1) * size]
            ).fetchall()
        self.send_json(
            {
                "posts": [post_dict(r, full=q.get("full") == "1") for r in rows],
                "page": page,
                "pages": max(1, -(-total // size)),
                "total": total,
            }
        )

    def get_post(self, pid):
        cond, args = self.visible()
        with db() as conn:
            row = conn.execute(f"{POST_SELECT} WHERE p.id = ? AND {cond}", [pid] + args).fetchone()
            if not row:
                raise ApiError(404, "글을 찾을 수 없습니다.")
            seen_key = f"seen_{pid}"
            headers = {}
            if not self.cookie(seen_key) and not self.can_edit(row):
                conn.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (pid,))
                headers["Set-Cookie"] = f"{seen_key}=1; Path=/; Max-Age=86400; SameSite=Lax"
                row = conn.execute(f"{POST_SELECT} WHERE p.id = ?", (pid,)).fetchone()
            vid, vcookie = self.visitor_id()
            if row["author_id"]:
                self.record_blog_visit(conn, row["author_id"], vid)
            if vcookie and "Set-Cookie" not in headers:
                headers.update(vcookie)
            same = f"{cond} AND p.type = ? AND p.author_id = ?"
            sargs = args + [row["type"], row["author_id"]]
            prev = conn.execute(
                f"SELECT p.id, p.title FROM posts p WHERE (p.created_at, p.id) < (?, ?) AND {same} "
                f"ORDER BY p.created_at DESC, p.id DESC LIMIT 1",
                [row["created_at"], pid] + sargs,
            ).fetchone()
            nxt = conn.execute(
                f"SELECT p.id, p.title FROM posts p WHERE (p.created_at, p.id) > (?, ?) AND {same} "
                f"ORDER BY p.created_at, p.id LIMIT 1",
                [row["created_at"], pid] + sargs,
            ).fetchone()
            # 004: 같은 블로그·종류·카테고리에서 볼 수 있는 글 최신순 4개 (사진 카드용 대표 사진 포함)
            related = conn.execute(
                f"SELECT p.id, p.title, p.created_at, p.type, p.is_public, p.content, p.cover FROM posts p "
                f"WHERE p.category = ? AND p.id != ? AND {same} ORDER BY p.created_at DESC, p.id DESC LIMIT 4",
                [row["category"], pid] + sargs,
            ).fetchall()
        d = post_dict(row, full=True)
        d["can_edit"] = self.can_edit(row)
        d["liked"] = False
        if self.user:
            with db() as conn:
                d["liked"] = bool(conn.execute(
                    "SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?", (pid, self.user["id"])
                ).fetchone())
        d["prev"] = dict(prev) if prev else None
        d["next"] = dict(nxt) if nxt else None
        d["related"] = [
            {
                "id": r["id"], "title": r["title"], "created_at": r["created_at"], "type": r["type"],
                "is_public": bool(r["is_public"]), "thumbnail": post_thumbnail(r["content"], r["cover"] or ""),
            }
            for r in related
        ]
        self.send_json(d, headers=headers)

    def read_post_body(self, author_id):
        b = self.body()
        title = str(b.get("title", "")).strip()
        if not title:
            raise ApiError(400, "제목을 입력하세요.")
        ptype = str(b.get("type", ""))
        if ptype not in POST_TYPES:
            raise ApiError(400, "글 종류를 선택하세요.")
        content = str(b.get("content", ""))
        if len(content) > POST_MAX_CHARS:
            raise ApiError(400, f"본문은 {POST_MAX_CHARS // 10000}만 자까지 쓸 수 있어요. 글을 나눠서 올려 주세요.")
        cat = str(b.get("category", ""))
        with db() as conn:
            row = conn.execute("SELECT categories FROM users WHERE id = ?", (author_id,)).fetchone()
        allowed = load_categories(row["categories"] if row else "[]")
        if cat and cat not in allowed:
            raise ApiError(400, "블로그에 없는 카테고리예요. 블로그 관리에서 먼저 만들어 주세요.")
        if not cat and allowed and ptype != "daily":
            raise ApiError(400, "카테고리를 선택하세요.")
        # 005: 대표 사진은 자동('')·사진 없이('none')·본문에 있는 업로드 사진만
        cover = b.get("cover", "")
        if not isinstance(cover, str) or (cover not in ("", "none") and cover not in upload_images(content)):
            raise ApiError(400, "대표 사진은 본문에 있는 사진 중에서 골라 주세요.")
        return (
            ptype,
            title[:200],
            content,
            cat,
            norm_tags(str(b.get("tags", ""))),
            1 if b.get("is_public", True) else 0,
            cover,
        )

    def editable_post(self, pid):
        self.require_login()
        with db() as conn:
            row = conn.execute("SELECT id, author_id FROM posts WHERE id = ?", (pid,)).fetchone()
        if not row:
            raise ApiError(404, "글을 찾을 수 없습니다.")
        if not self.can_edit(row):
            raise ApiError(403, "내가 쓴 글만 고칠 수 있습니다.")
        return row

    def api_POST_posts(self, parts, _):
        if parts:
            if len(parts) == 2 and parts[1] == "like":
                return self.toggle_like(int(parts[0]))
            raise ApiError(404, "없는 주소입니다.")
        self.require_login()
        fields = self.read_post_body(self.user["id"])
        now = now_iso()
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO posts (type, title, content, category, tags, is_public, cover, author_id, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                fields + (self.user["id"], now, now),
            )
        self.send_json({"id": cur.lastrowid}, 201)

    def api_PUT_posts(self, parts, _):
        pid = int(parts[0])
        post = self.editable_post(pid)
        fields = self.read_post_body(post["author_id"])
        with db() as conn:
            conn.execute(
                "UPDATE posts SET type=?, title=?, content=?, category=?, tags=?, is_public=?, cover=?, updated_at=? WHERE id=?",
                fields + (now_iso(), pid),
            )
        self.send_json({"id": pid})

    def toggle_like(self, pid):
        if not self.user:
            raise ApiError(401, "공감하려면 로그인하세요.")
        uid = self.user["id"]
        with db() as conn:
            self.visible_post(conn, pid)
            gone = conn.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (pid, uid)).rowcount
            if not gone:
                # (post_id, user_id)가 기본 키라 한 글에 한 번만 들어감
                conn.execute("INSERT OR IGNORE INTO likes VALUES (?, ?, ?)", (pid, uid, now_iso()))
            count = conn.execute("SELECT COUNT(*) FROM likes WHERE post_id = ?", (pid,)).fetchone()[0]
        self.send_json({"liked": not gone, "count": count})

    def api_DELETE_posts(self, parts, _):
        pid = int(parts[0])
        self.editable_post(pid)
        with db() as conn:
            conn.execute("DELETE FROM comments WHERE post_id = ?", (pid,))
            conn.execute("DELETE FROM likes WHERE post_id = ?", (pid,))
            conn.execute("DELETE FROM posts WHERE id = ?", (pid,))
        self.send_json({"ok": True})

    # ---------- 댓글 ----------
    def visible_post(self, conn, pid):
        cond, args = self.visible()
        if not conn.execute(f"SELECT 1 FROM posts p WHERE p.id = ? AND {cond}", [pid] + args).fetchone():
            raise ApiError(404, "글을 찾을 수 없습니다.")

    def api_GET_comments(self, _, q):
        pid = int(q.get("post", 0))
        me = self.user["id"] if self.user else None
        with db() as conn:
            self.visible_post(conn, pid)
            rows = conn.execute(
                "SELECT c.id, c.name, c.content, c.created_at, c.user_id, c.parent_id, c.deleted, u.nickname AS user_nickname "
                "FROM comments c LEFT JOIN users u ON u.id = c.user_id WHERE c.post_id = ? ORDER BY c.id",
                (pid,),
            ).fetchall()
            owner = conn.execute("SELECT author_id FROM posts WHERE id = ?", (pid,)).fetchone()["author_id"]
        blog_owner = me is not None and owner == me
        out = []
        for r in rows:
            d = dict(r)
            if d["user_id"]:
                d["name"] = d["user_nickname"] or d["name"]
            d["is_member"] = bool(d["user_id"])
            # 회원 댓글: 본인·관리자만 / 손님 댓글: 비밀번호로 누구나 시도
            d["can_delete"] = self.is_admin() or blog_owner or (d["user_id"] is not None and d["user_id"] == me)
            d["guest"] = d["user_id"] is None
            del d["user_nickname"]
            d["deleted"] = bool(d["deleted"])
            if d["deleted"]:
                # 지운 댓글은 내용·이름을 보내지 않고 자리만 남김 (답글이 어디에 달렸는지 보이게)
                d.update(name="", content="", can_delete=False, guest=False, is_member=False)
            out.append(d)
        self.send_json(out)

    def api_POST_comments(self, _, __):
        b = self.body()
        pid = int(b.get("post_id", 0))
        parent = b.get("parent_id")
        parent = int(parent) if parent not in (None, "", 0) else None
        content = str(b.get("content", "")).strip()[:2000]
        if self.user:
            name, pw_hash, uid = self.user["nickname"], "", self.user["id"]
            if not content:
                raise ApiError(400, "내용을 입력하세요.")
        else:
            name = str(b.get("name", "")).strip()[:30]
            pw = str(b.get("password", ""))
            if not (name and pw and content):
                raise ApiError(400, "이름, 비밀번호, 내용을 모두 입력하세요.")
            pw_hash, uid = hash_pw(pw), None
        with db() as conn:
            self.visible_post(conn, pid)
            if parent is not None:
                # 답글은 같은 글의 '댓글'에만 (답글의 답글은 불가 = 1단계)
                p = conn.execute("SELECT post_id, parent_id, deleted FROM comments WHERE id = ?", (parent,)).fetchone()
                if not p or p["post_id"] != pid:
                    raise ApiError(400, "답글을 달 댓글이 없어요.")
                if p["parent_id"] is not None:
                    raise ApiError(400, "답글에는 답글을 달 수 없어요.")
                if p["deleted"]:
                    raise ApiError(400, "삭제된 댓글에는 답글을 달 수 없어요.")
            conn.execute(
                "INSERT INTO comments (post_id, name, password_hash, content, user_id, parent_id, created_at) VALUES (?,?,?,?,?,?,?)",
                (pid, name, pw_hash, content, uid, parent, now_iso()),
            )
        self.send_json({"ok": True}, 201)

    def api_DELETE_comments(self, parts, q):
        cid = int(parts[0])
        if "password" in q:
            raise ApiError(400, "비밀번호는 주소에 넣을 수 없어요. 화면을 새로 고친 뒤 다시 시도해 주세요.")
        b = self.body()
        pw = str(b.get("password", "")) if isinstance(b, dict) else ""
        ip = self.client_ip()  # 003: 믿는 프록시 뒤에서도 실제 방문자 IP로 잠금
        wrong = False
        with db() as conn:
            row = conn.execute(
                "SELECT c.password_hash, c.user_id, c.parent_id, c.deleted, p.author_id AS post_author FROM comments c "
                "JOIN posts p ON p.id = c.post_id WHERE c.id = ?",
                (cid,),
            ).fetchone()
            if not row or row["deleted"]:
                raise ApiError(404, "댓글을 찾을 수 없어요.")
            mine = self.user and self.user["id"] in (row["user_id"], row["post_author"])
            if not (self.is_admin() or mine):
                if row["user_id"] is not None:
                    raise ApiError(403, "지울 권한이 없습니다.")
                # 방문자 댓글: 잠금 확인 → 비밀번호 확인 (틀리면 기록)
                left = pw_lock_minutes(conn, cid, ip)
                if left:
                    raise ApiError(429, f"비밀번호를 여러 번 틀렸어요. {left}분 뒤에 다시 시도해 주세요.")
                if not check_pw(pw, row["password_hash"]):
                    conn.execute("INSERT INTO comment_pw_fails VALUES (?, ?, ?)", (cid, ip, int(time.time())))
                    wrong = True
            if not wrong:
                conn.execute("DELETE FROM comment_pw_fails WHERE comment_id = ?", (cid,))
        if wrong:
            time.sleep(0.5)
            raise ApiError(403, "비밀번호가 맞지 않아요.")
        with db() as conn:
            has_replies = conn.execute("SELECT 1 FROM comments WHERE parent_id = ? AND deleted = 0", (cid,)).fetchone()
            if has_replies:
                # 답글이 있으면 자리만 남김
                conn.execute("UPDATE comments SET deleted = 1, content = '', name = '', password_hash = '' WHERE id = ?", (cid,))
            else:
                conn.execute("DELETE FROM comments WHERE id = ?", (cid,))
                # 지운 답글이 마지막이었고 원래 댓글이 이미 지워진 상태면 그것도 정리
                tidy_deleted_parent(conn, row["parent_id"])
        self.send_json({"ok": True})

    # ---------- 이미지 업로드 ----------
    def api_POST_upload(self, _, __):
        """사진은 본문에 바로 보이고, 그 밖의 파일은 첨부(다운로드)로 저장."""
        self.require_login()
        b = self.body()
        m = re.match(r"data:([\w/+.-]*);base64,(.*)", str(b.get("data", "")), re.S)
        if not m:
            raise ApiError(400, "파일을 읽지 못했습니다.")
        original = os.path.basename(str(b.get("name", "")).strip())[:120] or "file"
        ext = os.path.splitext(original)[1].lower()
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except ValueError:
            raise ApiError(400, "파일을 읽지 못했습니다.")
        if m.group(1) in IMAGE_TYPES:
            if len(raw) > IMAGE_MAX:
                raise ApiError(413, "사진은 10MB까지 올릴 수 있습니다.")
            name, is_image = uuid.uuid4().hex + IMAGE_TYPES[m.group(1)], True
        elif ext in FILE_TYPES:
            if len(raw) > FILE_MAX:
                raise ApiError(413, "파일은 30MB까지 올릴 수 있습니다.")
            name, is_image = uuid.uuid4().hex + ext, False
        else:
            raise ApiError(
                400, "올릴 수 없는 형식입니다. 사진(PNG·JPG·GIF·WEBP)이나 PDF·한글·오피스·ZIP·TXT 파일을 올려 주세요."
            )
        with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
            f.write(raw)
        with db() as conn:
            conn.execute(
                "INSERT INTO files VALUES (?, ?, ?, ?, ?)", (name, original, len(raw), self.user["id"], now_iso())
            )
        self.send_json({"url": f"/uploads/{name}", "name": original, "size": len(raw), "is_image": is_image}, 201)


if __name__ == "__main__":
    # 설정부터 확인: 문제가 있으면 DB·업로드 폴더를 열기 전에 안내만 하고 끝냄 (종료 코드 78)
    problems = check_config()
    if problems:
        print("서버를 켜지 않았어요. 아래 설정을 고쳐 주세요.")
        for problem in problems:
            print(f" - {problem}")
        raise SystemExit(CONFIG_EXIT)
    # 포트부터 잡아 본다: 이미 켜져 있으면 데이터베이스(관리자 비밀번호 포함)를 건드리지 않고 안내만 하고 끝냄
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        if e.errno in (48, 98):  # macOS / 리눅스의 '이미 사용 중'
            print(f"블로그가 이미 실행 중이에요 → http://localhost:{PORT}")
            print("다시 켜려면: 블로그를 실행 중인 터미널에서 Ctrl + C로 끈 뒤 다시 실행하세요.")
            raise SystemExit(1)
        raise
    init_db()
    restore_orphan_replies()
    if PUBLIC_MODE:
        print(f"블로그 실행 중 (공개 모드) → {BLOG_URL}  (내부 {HOST}:{PORT})")
        print(f"회원 서버: {AUTH_URL}")
        print(f"SNS 개발자 콘솔에 등록할 콜백 주소: {AUTH_URL}/oauth_callback.php")
    else:
        print(f"블로그 실행 중 → http://localhost:{PORT}")
        if HOST != "127.0.0.1":
            print(f"같은 와이파이의 다른 기기에서도 접속할 수 있습니다 (주소: 이 컴퓨터의 IP:{PORT})")
        if PASSWORD == DEFAULT_PASSWORD:
            print("관리자 아이디: admin / 비밀번호: admin1234  (BLOG_PASSWORD 환경변수로 바꾸세요)")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n블로그를 껐어요.")

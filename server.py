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
import json
import os
import re
import secrets
import sqlite3
import time
import threading
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "blog.db")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
PASSWORD = os.environ.get("BLOG_PASSWORD", "admin1234")
# 회원가입·로그인은 PHP(php-auth)가 맡음. 블로그는 PHP가 서명한 입장권을 확인해서 로그인시킴
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8080").rstrip("/")
SSO_KEY_PATH = os.path.join(BASE_DIR, "php-auth", "db", "sso.key")
ADMIN_USERNAME = "admin"
USERNAME_RE = re.compile(r"^[a-z0-9_]{4,20}$")
PAGE_SIZE = 8
SESSION_TTL = 60 * 60 * 24 * 14
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


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def columns(conn, table):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


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
        conn.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))


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


def post_dict(row, full=False):
    d = dict(row)
    d["tags"] = [t for t in d["tags"].split(",") if t]
    d["is_public"] = bool(d["is_public"])
    if not full:
        text = d.pop("content")
        img = re.search(r"!\[[^\]]*\]\(([^)\s]+)", text)
        d["thumbnail"] = img.group(1) if img else None
        plain = re.sub(r"```.*?```", " ", text, flags=re.S)
        plain = re.sub(r"!\[[^\]]*\]\([^)]*\)|[#>*_`~|\-\[\]]|\((?:http|/uploads/)[^)]*\)|📎", " ", plain)
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
    "u.room_bg, u.room_char"
)
# 미니룸 기본 목록 (그림은 static/miniroom.js). 여기 없는 값은 저장하지 않음
ROOM_BGS = ("room", "forest", "beach", "night", "cafe", "library")
ROOM_CHARS = ("bear", "cat", "rabbit", "penguin", "dog", "robot")


def blog_dict(row, public=False):
    d = dict(row)
    d["categories"] = load_categories(d.get("categories"))
    if public:
        d.pop("auth_uid", None)  # 다른 사람에게 보여 줄 때는 연결 정보 빼기
    return d


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


def make_logout_ticket():
    """PHP 회원 페이지도 함께 로그아웃시키는 1분짜리 서명 표 (다른 사이트가 남을 로그아웃시키지 못하게 서명)."""
    payload = base64.urlsafe_b64encode(json.dumps(
        {"act": "logout", "exp": int(time.time()) + 60, "nonce": secrets.token_hex(8)}
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


class ApiError(Exception):
    def __init__(self, status, msg):
        self.status, self.msg = status, msg


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC_DIR, **kw)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        if getattr(self, "revalidate", False):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

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
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            if method != "GET":
                return self.send_error(405)
            if url.path.startswith("/uploads/"):
                return self.serve_upload(url.path)
            self.revalidate = True  # 화면 파일은 항상 최신 버전을 확인
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
            linked = conn.execute("SELECT id FROM users WHERE auth_uid = ?", (uid,)).fetchone()
            created = False
            if linked:
                blog_uid = linked["id"]
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
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (self.cookie("session") or "",))
        # 블로그에서 로그아웃하면 회원 페이지(PHP)도 함께: 브라우저가 이 주소를 거쳐 블로그로 돌아옴
        try:
            auth_logout = f"{AUTH_URL}/sso_logout.php?t={quote(make_logout_ticket())}"
        except Exception:  # noqa: 키 파일을 못 읽으면 블로그만 로그아웃
            auth_logout = None
        self.send_json(
            {"ok": True, "auth_url": AUTH_URL, "auth_logout_url": auth_logout},
            headers={"Set-Cookie": "session=; Path=/; Max-Age=0"},
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
            row = conn.execute("SELECT role FROM users WHERE id = ?", (uid,)).fetchone()
            if not row:
                raise ApiError(404, "없는 회원입니다.")
            if row["role"] == "admin":
                raise ApiError(400, "관리자 계정은 삭제할 수 없습니다.")
            # 탈퇴시킨 회원의 글·댓글도 함께 정리
            # (foreign_keys가 꺼져 있어 ON DELETE CASCADE가 안 돌아감. 글을 지우기 전에 그 글에 달린 댓글·공감부터)
            conn.execute("DELETE FROM comments WHERE post_id IN (SELECT id FROM posts WHERE author_id = ?)", (uid,))
            conn.execute("DELETE FROM likes WHERE user_id = ? OR post_id IN (SELECT id FROM posts WHERE author_id = ?)", (uid, uid))
            conn.execute("DELETE FROM posts WHERE author_id = ?", (uid,))
            conn.execute("DELETE FROM comments WHERE user_id = ?", (uid,))
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
        self.send_json({"ok": True})

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
            related = conn.execute(
                f"SELECT p.id, p.title, p.created_at FROM posts p WHERE p.category = ? AND p.id != ? AND {same} "
                f"ORDER BY p.created_at DESC LIMIT 5",
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
        d["related"] = [dict(r) for r in related]
        self.send_json(d, headers=headers)

    def read_post_body(self, author_id):
        b = self.body()
        title = str(b.get("title", "")).strip()
        if not title:
            raise ApiError(400, "제목을 입력하세요.")
        ptype = str(b.get("type", ""))
        if ptype not in POST_TYPES:
            raise ApiError(400, "글 종류를 선택하세요.")
        cat = str(b.get("category", ""))
        with db() as conn:
            row = conn.execute("SELECT categories FROM users WHERE id = ?", (author_id,)).fetchone()
        allowed = load_categories(row["categories"] if row else "[]")
        if cat and cat not in allowed:
            raise ApiError(400, "블로그에 없는 카테고리예요. 블로그 관리에서 먼저 만들어 주세요.")
        if not cat and allowed and ptype != "daily":
            raise ApiError(400, "카테고리를 선택하세요.")
        return (
            ptype,
            title[:200],
            str(b.get("content", "")),
            cat,
            norm_tags(str(b.get("tags", ""))),
            1 if b.get("is_public", True) else 0,
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
                "INSERT INTO posts (type, title, content, category, tags, is_public, author_id, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                fields + (self.user["id"], now, now),
            )
        self.send_json({"id": cur.lastrowid}, 201)

    def api_PUT_posts(self, parts, _):
        pid = int(parts[0])
        post = self.editable_post(pid)
        fields = self.read_post_body(post["author_id"])
        with db() as conn:
            conn.execute(
                "UPDATE posts SET type=?, title=?, content=?, category=?, tags=?, is_public=?, updated_at=? WHERE id=?",
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
        with db() as conn:
            row = conn.execute(
                "SELECT c.password_hash, c.user_id, c.parent_id, c.deleted, p.author_id AS post_author FROM comments c "
                "JOIN posts p ON p.id = c.post_id WHERE c.id = ?",
                (cid,),
            ).fetchone()
            if not row or row["deleted"]:
                raise ApiError(404, "댓글이 없습니다.")
            mine = self.user and self.user["id"] in (row["user_id"], row["post_author"])
            guest_ok = row["user_id"] is None and check_pw(q.get("password", ""), row["password_hash"])
            if not (self.is_admin() or mine or guest_ok):
                raise ApiError(403, "비밀번호가 틀렸거나 지울 권한이 없습니다.")
            has_replies = conn.execute("SELECT 1 FROM comments WHERE parent_id = ? AND deleted = 0", (cid,)).fetchone()
            if has_replies:
                # 답글이 있으면 자리만 남김
                conn.execute("UPDATE comments SET deleted = 1, content = '', name = '', password_hash = '' WHERE id = ?", (cid,))
            else:
                conn.execute("DELETE FROM comments WHERE id = ?", (cid,))
                # 지운 답글이 마지막이었고 원래 댓글이 이미 지워진 상태면 그것도 정리
                if row["parent_id"] is not None and not conn.execute(
                    "SELECT 1 FROM comments WHERE parent_id = ? AND deleted = 0", (row["parent_id"],)
                ).fetchone():
                    conn.execute("DELETE FROM comments WHERE id = ? AND deleted = 1", (row["parent_id"],))
                    conn.execute("DELETE FROM comments WHERE parent_id = ? AND deleted = 1", (row["parent_id"],))
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
    print(f"블로그 실행 중 → http://localhost:{PORT}")
    if HOST != "127.0.0.1":
        print(f"같은 와이파이의 다른 기기에서도 접속할 수 있습니다 (주소: 이 컴퓨터의 IP:{PORT})")
    if PASSWORD == "admin1234":
        print("관리자 아이디: admin / 비밀번호: admin1234  (BLOG_PASSWORD 환경변수로 바꾸세요)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n블로그를 껐어요.")

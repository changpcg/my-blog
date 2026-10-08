"""NFR-18 점검 (표준 라이브러리만): 연결 칸(FK) 인덱스 8개가 만들어지고, 자주 쓰는 조회가 그 인덱스를 쓰는지.

실제 blog.db를 건드리지 않도록 server.py를 임시 폴더에 복사해 그 안에서 init_db()를 부릅니다.

    python3 tests/smoke_db_indexes.py
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAR_ENV = ("BLOG_PASSWORD", "AUTH_URL", "BLOG_URL", "HOST", "PORT", "MYBLOG_CONFIG")
EXPECTED = {
    "idx_posts_author_id": ("posts", ["author_id"]),
    "idx_comments_post_id": ("comments", ["post_id"]),
    "idx_comments_user_id": ("comments", ["user_id"]),
    "idx_comments_parent_id": ("comments", ["parent_id"]),
    "idx_likes_user_id": ("likes", ["user_id"]),
    "idx_sessions_user_id": ("sessions", ["user_id"]),
    "idx_files_user_id": ("files", ["user_id"]),
    "idx_blog_visits_blog_id": ("blog_visits", ["blog_id"]),
}


class DbIndexes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="myblog-idx-")
        shutil.copy2(os.path.join(ROOT, "server.py"), cls.dir)
        cls.db_path = os.path.join(cls.dir, "blog.db")
        cls.init_db()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    @classmethod
    def init_db(cls):
        env = {k: v for k, v in os.environ.items() if k not in CLEAR_ENV}
        out = subprocess.run([sys.executable, "-B", "-c", "import server; server.init_db()"], cwd=cls.dir, env=env,
                             capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError("init_db 실패: " + out.stderr[-800:])

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def indexes(self, conn):
        found = {}
        for name, table in conn.execute("SELECT name, tbl_name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"):
            cols = [r[2] for r in conn.execute(f"PRAGMA index_info({name})")]
            found[name] = (table, cols)
        return found

    def plan(self, conn, sql, args=()):
        return " | ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql, args))

    def test_1_fresh_db_has_all_fk_indexes(self):
        found = self.indexes(self.connect())
        for name, want in EXPECTED.items():
            self.assertEqual(found.get(name), want, f"{name} 인덱스")

    def test_2_queries_use_indexes(self):
        conn = self.connect()
        cases = [
            ("SELECT p.id, (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.deleted = 0) FROM posts p",
             (), "idx_comments_post_id"),
            ("SELECT id FROM posts WHERE author_id = ? ORDER BY id DESC", (1,), "idx_posts_author_id"),
            ("SELECT 1 FROM comments WHERE parent_id = ? AND deleted = 0", (1,), "idx_comments_parent_id"),
            ("DELETE FROM comments WHERE user_id = ?", (1,), "idx_comments_user_id"),
            ("SELECT COUNT(*) FROM blog_visits WHERE blog_id = ?", (1,), "idx_blog_visits_blog_id"),
            ("DELETE FROM likes WHERE user_id = ?", (1,), "idx_likes_user_id"),
            ("DELETE FROM sessions WHERE user_id = ?", (1,), "idx_sessions_user_id"),
            ("SELECT stored_name FROM files WHERE user_id = ?", (1,), "idx_files_user_id"),
        ]
        for sql, args, index in cases:
            plan = self.plan(conn, sql, args)
            self.assertIn(index, plan, f"{sql} → {plan}")

    def test_3_existing_db_keeps_data_and_gets_indexes(self):
        # 인덱스가 없던 예전 DB를 흉내: 인덱스를 지우고 자료를 넣은 뒤 다시 켬
        conn = sqlite3.connect(self.db_path)
        try:
            for name in EXPECTED:
                conn.execute(f"DROP INDEX IF EXISTS {name}")
            admin = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()[0]
            pid = conn.execute("SELECT id FROM posts ORDER BY id LIMIT 1").fetchone()[0]
            conn.execute("INSERT INTO comments (post_id, name, password_hash, content, created_at, user_id) "
                         "VALUES (?, '관리자', '', '점검 댓글', '2026-10-08T00:00:00', ?)", (pid, admin))
            conn.execute("INSERT INTO blog_visits VALUES ('2026-10-08', ?, 'v1')", (admin,))
            conn.commit()
            before = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("users", "posts", "comments", "likes", "blog_visits")]
        finally:
            conn.close()
        self.assertEqual(self.indexes(self.connect()).keys() & EXPECTED.keys(), set())
        type(self).init_db()
        conn = self.connect()
        self.assertEqual(self.indexes(conn).keys() & EXPECTED.keys(), EXPECTED.keys(), "다시 켜면 인덱스가 생김")
        after = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("users", "posts", "comments", "likes", "blog_visits")]
        self.assertEqual(before, after, "자료는 그대로")
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)

<?php
declare(strict_types=1);

/**
 * SQLite 연결. db/sqlite.db 파일과 테이블이 없으면 자동으로 만든다.
 *
 * SQL 인젝션 방지:
 *  - 모든 쿼리는 prepare() + 자리표시자(?)로 실행하고, 사용자 입력을 SQL 문자열에 이어 붙이지 않는다.
 *  - ATTR_EMULATE_PREPARES = false: PHP가 흉내 내는 방식이 아니라 SQLite 자체의 바인딩을 쓴다.
 */
function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    // 웹으로 열리는 public/ 폴더 바깥에 두어 브라우저에서 DB 파일을 내려받을 수 없게 함
    $dir = dirname(__DIR__) . '/db';
    if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) {
        throw new RuntimeException('db 폴더를 만들 수 없습니다.');
    }

    $pdo = new PDO('sqlite:' . $dir . '/sqlite.db', null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    $pdo->exec('PRAGMA foreign_keys = ON');
    $pdo->exec('PRAGMA journal_mode = WAL');

    // 고정된 SQL만 실행 (사용자 입력 없음)
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT    NOT NULL,
            nickname      TEXT    NOT NULL,
            bio           TEXT    NOT NULL DEFAULT \'\',
            created_at    TEXT    NOT NULL DEFAULT (datetime(\'now\', \'localtime\'))
        )'
    );
    // 로그인 실패 기록: 비밀번호를 마구 대입하는 공격을 막는 데 사용
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS login_attempts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL COLLATE NOCASE,
            ip         TEXT    NOT NULL,
            created_at INTEGER NOT NULL
        )'
    );
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_attempts ON login_attempts (username, ip, created_at)');
    // SNS 계정 연결 (한 SNS 계정은 회원 한 명에게만)
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS social_accounts (
            provider     TEXT    NOT NULL,
            provider_uid TEXT    NOT NULL,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at   TEXT    NOT NULL DEFAULT (datetime(\'now\', \'localtime\')),
            PRIMARY KEY (provider, provider_uid),
            UNIQUE (user_id, provider)
        )'
    );
    // 이미 쓴 '함께 로그아웃' 표 번호: 같은 표를 두 번 쓸 수 없게 (만료되면 정리)
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS sso_used_nonces (
            nonce   TEXT    PRIMARY KEY,
            expires INTEGER NOT NULL
        )'
    );
    // 002: 비밀번호를 바꾸면 다른 브라우저 로그인을 끊는 번호, 닉네임 바꾼 시각
    $cols = $pdo->query('PRAGMA table_info(users)')->fetchAll(PDO::FETCH_COLUMN, 1);
    if (!in_array('session_ver', $cols, true)) {
        $pdo->exec('ALTER TABLE users ADD COLUMN session_ver INTEGER NOT NULL DEFAULT 0');
    }
    if (!in_array('nickname_at', $cols, true)) {
        $pdo->exec('ALTER TABLE users ADD COLUMN nickname_at INTEGER NOT NULL DEFAULT 0');
    }
    // 003: 가입 기록 (횟수 제한·가입 현황용, 24시간만 보관, 회원 번호와 잇지 않음)
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS signup_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ip         TEXT    NOT NULL,
            kind       TEXT    NOT NULL,
            created_at INTEGER NOT NULL
        )'
    );
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_signup_kind ON signup_log (kind, created_at)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_signup_ip ON signup_log (ip, kind, created_at)');
    // 블로그에서 읽어 온 값 잠깐 기억 (회원가입 허용 등)
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS bridge_cache (
            key        TEXT    PRIMARY KEY,
            value      TEXT    NOT NULL,
            fetched_at INTEGER NOT NULL
        )'
    );

    return $pdo;
}

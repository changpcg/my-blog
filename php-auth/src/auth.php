<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/sso.php';
require_once __DIR__ . '/oauth.php';

const USERNAME_PATTERN = '/^[a-z0-9_]{4,20}$/';
const MAX_FAILS = 5;            // 이 횟수만큼 틀리면
const LOCK_SECONDS = 15 * 60;   // 15분 동안 로그인 잠금

// ---------- 세션 ----------
// HttpOnly: 자바스크립트로 쿠키를 못 훔치게 / SameSite=Lax: 다른 사이트에서 몰래 보내는 요청 차단
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'secure' => !empty($_SERVER['HTTPS']),
    'httponly' => true,
    'samesite' => 'Lax',
]);
session_name('AUTHSESS');
session_start();

// 어느 페이지든 처음 열리면 db/sqlite.db와 테이블을 바로 만들어 둠
db();

// ---------- 출력 ----------
/** 화면에 내보내는 모든 값은 이 함수로 감싸서 XSS(스크립트 끼워 넣기)를 막는다. */
function h(?string $s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function redirect(string $to): never
{
    header('Location: ' . $to);
    exit;
}

/** 한 번만 보여 줄 안내 메시지 */
function flash(?string $msg = null): ?string
{
    if ($msg !== null) {
        $_SESSION['flash'] = $msg;
        return null;
    }
    $m = $_SESSION['flash'] ?? null;
    unset($_SESSION['flash']);
    return $m;
}

// ---------- CSRF (다른 사이트가 내 이름으로 폼을 보내는 공격) 방지 ----------
function csrf_token(): string
{
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
}

function check_csrf(): void
{
    $sent = $_POST['csrf'] ?? '';
    if (!is_string($sent) || !hash_equals(csrf_token(), $sent)) {
        http_response_code(400);
        exit('잘못된 요청입니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.');
    }
}

// ---------- 회원 ----------
function current_user(): ?array
{
    if (empty($_SESSION['uid'])) {
        return null;
    }
    $st = db()->prepare('SELECT id, username, nickname, bio, created_at, session_ver, nickname_at FROM users WHERE id = ?');
    $st->execute([$_SESSION['uid']]);
    $user = $st->fetch();
    // 탈퇴했거나, 다른 곳에서 비밀번호를 바꿨으면 이 브라우저 로그인은 끝
    if (!$user || (int)$user['session_ver'] !== (int)($_SESSION['ver'] ?? 0)) {
        unset($_SESSION['uid'], $_SESSION['ver']);
        return null;
    }
    return $user;
}

function login_user(int $uid): void
{
    // 로그인할 때 세션 번호를 새로 발급해서 '세션 고정' 공격을 막음
    session_regenerate_id(true);
    $_SESSION['uid'] = $uid;
    $st = db()->prepare('SELECT session_ver FROM users WHERE id = ?');
    $st->execute([$uid]);
    $_SESSION['ver'] = (int)$st->fetchColumn();
}

// ---------- 회원가입 허용 (블로그 사이트 설정을 따름) ----------
const SIGNUP_CACHE_SECONDS = 60;

/**
 * 지금 새 가입을 받는지. 블로그가 서명해 준 값을 1분 동안 기억해 씀.
 * 블로그에 물어볼 수 없으면 마지막으로 받은 값, 한 번도 못 받았으면 '닫힘'(안전한 쪽).
 */
function signup_open(): bool
{
    $pdo = db();
    $st = $pdo->prepare("SELECT value, fetched_at FROM bridge_cache WHERE key = 'signup'");
    $st->execute();
    $row = $st->fetch();
    if ($row && (int)$row['fetched_at'] > time() - SIGNUP_CACHE_SECONDS) {
        return $row['value'] === '1';
    }
    $r = blog_call('GET', '/api/bridge/signup');
    $data = ($r && $r[0] === 200 && is_string($r[1]['t'] ?? null)) ? read_bridge($r[1]['t'], 'signup_state') : null;
    if ($data === null) {
        return $row ? $row['value'] === '1' : false;
    }
    $value = !empty($data['allow']) ? '1' : '0';
    $pdo->prepare("INSERT OR REPLACE INTO bridge_cache (key, value, fetched_at) VALUES ('signup', ?, ?)")
        ->execute([$value, time()]);
    return $value === '1';
}

const SIGNUP_CLOSED_MESSAGE = '지금은 새 가입을 받지 않아요. 이미 가입한 회원은 로그인할 수 있어요.';

/** 회원 서버에서 회원 한 명을 지움 (SNS 연결은 외래 키로 함께, 로그인 실패 기록도) */
function delete_member_local(int $uid): bool
{
    $pdo = db();
    $st = $pdo->prepare('SELECT username FROM users WHERE id = ?');
    $st->execute([$uid]);
    $username = $st->fetchColumn();
    if ($username === false) {
        return false;
    }
    $pdo->beginTransaction();
    $pdo->prepare('DELETE FROM social_accounts WHERE user_id = ?')->execute([$uid]);
    $pdo->prepare('DELETE FROM login_attempts WHERE username = ?')->execute([$username]);
    $pdo->prepare('DELETE FROM users WHERE id = ?')->execute([$uid]);
    $pdo->commit();
    return true;
}

/** 폼 값 하나를 문자열로 (배열 등 이상한 값은 빈 문자열) */
function post_str(string $key): string
{
    $v = $_POST[$key] ?? '';
    return is_string($v) ? $v : '';
}

/**
 * 회원가입 입력 검사. 문제가 있으면 [항목 => 메시지] 배열을 돌려줌.
 */
function validate_signup(string $username, string $password, string $password2, string $nickname, string $bio): array
{
    $errors = validate_profile($username, $nickname, $bio);
    $pwLen = mb_strlen($password);
    if ($pwLen < 8 || strlen($password) > 72) { // bcrypt는 72바이트까지만 씀
        $errors['password'] = '비밀번호는 8자 이상, 72바이트 이하여야 해요.';
    } elseif (!preg_match('/[A-Za-z]/', $password) || !preg_match('/\d/', $password)) {
        $errors['password'] = '비밀번호에 영문과 숫자를 함께 넣어 주세요.';
    }
    if ($password !== $password2) {
        $errors['password2'] = '비밀번호가 서로 달라요.';
    }
    return $errors;
}

/** 아이디·닉네임·자기소개 검사 (일반 가입과 SNS 가입 공통) */
function validate_profile(string $username, string $nickname, string $bio): array
{
    $errors = [];
    if (!preg_match(USERNAME_PATTERN, $username)) {
        $errors['username'] = '아이디는 영문 소문자·숫자·밑줄(_)로 4~20자여야 해요.';
    } elseif (in_array($username, RESERVED_USERNAMES, true)) {
        $errors['username'] = '쓸 수 없는 아이디예요. 다른 아이디를 골라 주세요.';
    }
    $nickLen = mb_strlen($nickname);
    if ($nickLen < 2 || $nickLen > 20) {
        $errors['nickname'] = '닉네임은 2~20자로 정해 주세요.';
    }
    if (mb_strlen($bio) > 300) {
        $errors['bio'] = '자기소개는 300자까지 쓸 수 있어요.';
    }
    return $errors;
}

// ---------- 아이디 중복 확인 ----------
const CHECK_LIMIT = 30;          // 5분에 30번까지만 확인 (아이디 목록을 긁어 가지 못하게)
const CHECK_WINDOW = 5 * 60;

/**
 * 아이디를 쓸 수 있는지 확인. ['ok' => bool, 'message' => string]
 * 쓸 수 있으면 세션에 '확인된 아이디'로 기억해 두고, 가입할 때 같은 아이디인지 다시 본다.
 */
function check_username(string $username): array
{
    $username = strtolower(trim($username));
    unset($_SESSION['checked_username']);

    $now = time();
    $recent = array_filter($_SESSION['username_checks'] ?? [], fn($t) => $t > $now - CHECK_WINDOW);
    if (count($recent) >= CHECK_LIMIT) {
        return ['ok' => false, 'message' => '확인을 너무 많이 했어요. 잠시 뒤에 다시 시도해 주세요.'];
    }
    $recent[] = $now;
    $_SESSION['username_checks'] = array_values($recent);

    if (!preg_match(USERNAME_PATTERN, $username)) {
        return ['ok' => false, 'message' => '아이디는 영문 소문자·숫자·밑줄(_)로 4~20자여야 해요.'];
    }
    if (in_array($username, RESERVED_USERNAMES, true)) {
        return ['ok' => false, 'message' => '쓸 수 없는 아이디예요. 다른 아이디를 골라 주세요.'];
    }
    $st = db()->prepare('SELECT 1 FROM users WHERE username = ?');
    $st->execute([$username]);
    if ($st->fetchColumn()) {
        return ['ok' => false, 'message' => '이미 사용 중인 아이디예요.'];
    }
    $_SESSION['checked_username'] = $username;
    return ['ok' => true, 'message' => '사용할 수 있는 아이디예요.'];
}

/** 이 아이디로 중복 확인을 통과했는지 */
function username_checked(string $username): bool
{
    return isset($_SESSION['checked_username']) && hash_equals($_SESSION['checked_username'], strtolower(trim($username)));
}

/** 가입. 성공하면 새 회원 번호, 아이디가 겹치면 null. SNS로만 가입하면 비밀번호 없음(null) */
function create_user(string $username, ?string $password, string $nickname, string $bio): ?int
{
    $pdo = db();
    $st = $pdo->prepare('INSERT INTO users (username, password_hash, nickname, bio) VALUES (?, ?, ?, ?)');
    try {
        $st->execute([$username, $password === null ? '' : password_hash($password, PASSWORD_DEFAULT), $nickname, $bio]);
    } catch (PDOException $e) {
        if (str_contains($e->getMessage(), 'UNIQUE')) {
            return null; // 같은 시간에 같은 아이디로 가입한 경우까지 안전하게 처리
        }
        throw $e;
    }
    return (int)$pdo->lastInsertId();
}

function client_ip(): string
{
    return (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');
}

/** 최근 15분 동안 이 아이디+IP로 틀린 횟수 */
function recent_fails(string $username): int
{
    $st = db()->prepare('SELECT COUNT(*) FROM login_attempts WHERE username = ? AND ip = ? AND created_at > ?');
    $st->execute([$username, client_ip(), time() - LOCK_SECONDS]);
    return (int)$st->fetchColumn();
}

/**
 * 로그인 시도. 성공하면 회원 번호, 실패하면 오류 메시지 문자열.
 */
function attempt_login(string $username, string $password)
{
    $username = strtolower(trim($username));
    if (recent_fails($username) >= MAX_FAILS) {
        return '로그인을 너무 많이 실패했어요. 15분 뒤에 다시 시도해 주세요.';
    }
    $st = db()->prepare('SELECT id, password_hash FROM users WHERE username = ?');
    $st->execute([$username]);
    $row = $st->fetch();

    // 없는 아이디여도 비밀번호 확인과 비슷한 시간을 써서, 아이디가 있는지 없는지 알아낼 수 없게 함
    $hash = ($row['password_hash'] ?? '') !== '' ? $row['password_hash'] : password_hash('no-such-user', PASSWORD_DEFAULT);
    $ok = password_verify($password, $hash) && $row && $row['password_hash'] !== '';

    if (!$ok) {
        $ins = db()->prepare('INSERT INTO login_attempts (username, ip, created_at) VALUES (?, ?, ?)');
        $ins->execute([$username, client_ip(), time()]);
        return '아이디 또는 비밀번호가 맞지 않아요.';
    }

    // 성공하면 실패 기록을 지우고, 더 강한 방식이 나왔으면 비밀번호 해시를 새로 저장
    db()->prepare('DELETE FROM login_attempts WHERE username = ? AND ip = ?')->execute([$username, client_ip()]);
    if (password_needs_rehash($row['password_hash'], PASSWORD_DEFAULT)) {
        db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')
            ->execute([password_hash($password, PASSWORD_DEFAULT), $row['id']]);
    }
    return (int)$row['id'];
}

/** 화면 위아래 공통 틀 */
function page_start(string $title): void
{
    echo '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width, initial-scale=1">'
        . '<title>' . h($title) . '</title>'
        . '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">'
        . '<link rel="stylesheet" href="style.css"></head><body><main class="wrap">'
        // 어느 회원 화면에서든 블로그 첫 화면으로 돌아가는 버튼
        . '<nav class="top-nav"><a class="back-home" href="' . h(BLOG_URL) . '/#/">← 블로그 홈으로</a></nav>';
    $msg = flash();
    if ($msg) {
        echo '<p class="flash" role="status">' . h($msg) . '</p>';
    }
}

function page_end(): void
{
    echo '</main></body></html>';
}

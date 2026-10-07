<?php
declare(strict_types=1);

/**
 * 블로그(Python, 8000번)와 계정 합치기.
 *
 * 회원가입·로그인은 여기(PHP)에서만 한다. 로그인에 성공하면 블로그로 '입장권(ticket)'을 들려 보내고,
 * 블로그는 입장권의 서명을 확인한 뒤 자기 세션을 만든다.
 *
 * 입장권 = base64url(JSON) + "." + HMAC-SHA256 서명 (16진수)
 *  - 서명 키: db/sso.key (PHP와 블로그가 같은 파일을 읽음, 처음 필요할 때 자동 생성)
 *  - 5분 안에, 한 번만 쓸 수 있음 (nonce를 블로그가 기억)
 *  - 주소의 # 뒤에 실어 보내서 서버 기록이나 다른 사이트로 새지 않게 함
 */

// 블로그 주소. 다른 곳에서 돌릴 때는 BLOG_URL 환경변수로 바꿈 (여기로만 돌려보내서 '열린 리다이렉트'를 막음)
define('BLOG_URL', rtrim(getenv('BLOG_URL') ?: 'http://localhost:8000', '/'));
const TICKET_TTL = 300;

// 블로그 주소(@아이디)나 관리 기능과 헷갈리는 아이디는 가입 불가
const RESERVED_USERNAMES = ['admin', 'administrator', 'root', 'manage', 'settings', 'login', 'signup', 'write', 'system'];

function sso_key(): string
{
    $path = dirname(__DIR__) . '/db/sso.key';
    if (!is_file($path)) {
        // 'x' 모드: 이미 있으면 실패 → 블로그와 동시에 만들어도 한쪽 키만 남음
        $fh = @fopen($path, 'x');
        if ($fh) {
            fwrite($fh, bin2hex(random_bytes(32)));
            fclose($fh);
            chmod($path, 0600);
        }
    }
    $key = trim((string)file_get_contents($path));
    if (strlen($key) < 32) {
        throw new RuntimeException('db/sso.key가 올바르지 않습니다.');
    }
    return $key;
}

function b64url(string $s): string
{
    return rtrim(strtr(base64_encode($s), '+/', '-_'), '=');
}

function make_ticket(array $user): string
{
    $payload = b64url(json_encode([
        'uid' => (int)$user['id'],
        'username' => $user['username'],
        'nickname' => $user['nickname'],
        'bio' => $user['bio'],
        'joined' => (string)($user['created_at'] ?? ''),
        'nick_at' => (int)($user['nickname_at'] ?? 0),
        'exp' => time() + TICKET_TTL,
        'nonce' => bin2hex(random_bytes(16)),
    ], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
    return $payload . '.' . hash_hmac('sha256', $payload, sso_key());
}

/**
 * 블로그가 만든 '함께 로그아웃' 표 확인. 서명·종류·만료가 맞으면 내용(uid·nonce·exp), 아니면 null.
 * 회원 번호 확인과 1회용 확인은 sso_logout.php에서 한다.
 */
function read_logout_ticket(string $t): ?array
{
    $parts = explode('.', $t, 2);
    if (count($parts) !== 2) {
        return null;
    }
    [$payload, $sig] = $parts;
    if (!hash_equals(hash_hmac('sha256', $payload, sso_key()), $sig)) {
        return null;
    }
    $data = json_decode((string)base64_decode(strtr($payload, '-_', '+/')), true);
    if (!is_array($data) || ($data['act'] ?? '') !== 'logout' || (int)($data['exp'] ?? 0) < time()) {
        return null;
    }
    if ((int)($data['uid'] ?? 0) <= 0 || !is_string($data['nonce'] ?? null) || strlen($data['nonce']) < 16) {
        return null;
    }
    return $data;
}

/** 서버 사이에 주고받는 서명 값 만들기 (act로 용도 구분, 1분 만료) */
function sign_bridge(array $data): string
{
    $data['exp'] = $data['exp'] ?? time() + 60;
    $payload = b64url(json_encode($data, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
    return $payload . '.' . hash_hmac('sha256', $payload, sso_key());
}

/** 서명 값 확인. 서명·act·만료가 맞으면 내용, 아니면 null */
function read_bridge(string $t, string $act): ?array
{
    $parts = explode('.', $t, 2);
    if (count($parts) !== 2 || !hash_equals(hash_hmac('sha256', $parts[0], sso_key()), $parts[1])) {
        return null;
    }
    $data = json_decode((string)base64_decode(strtr($parts[0], '-_', '+/')), true);
    if (!is_array($data) || ($data['act'] ?? '') !== $act || (int)($data['exp'] ?? 0) < time()) {
        return null;
    }
    return $data;
}

/**
 * 블로그 서버 호출 (3초 제한). 성공하면 [상태코드, JSON 배열], 연결 실패면 null.
 * curl 없이 PHP 기본 기능만 사용.
 */
function blog_call(string $method, string $path, ?array $json = null): ?array
{
    $opts = ['http' => [
        'method' => $method, 'timeout' => 3, 'ignore_errors' => true,
        'header' => "Accept: application/json\r\n" . ($json !== null ? "Content-Type: application/json\r\n" : ''),
    ]];
    if ($json !== null) {
        $opts['http']['content'] = json_encode($json, JSON_UNESCAPED_UNICODE);
    }
    $body = @file_get_contents(BLOG_URL . $path, false, stream_context_create($opts));
    if ($body === false || !isset($http_response_header[0])) {
        return null;
    }
    preg_match('#\s(\d{3})\s#', $http_response_header[0] . ' ', $m);
    $data = json_decode($body, true);
    return [(int)($m[1] ?? 0), is_array($data) ? $data : []];
}

/** 로그인한 회원을 입장권과 함께 블로그로 보냄 */
function go_to_blog(array $user): never
{
    redirect(BLOG_URL . '/#/sso?t=' . rawurlencode(make_ticket($user)));
}

/** 폼과 주소에서 '블로그에서 왔다'는 표시 (blog만 허용) */
function from_blog(): bool
{
    return ($_GET['return'] ?? $_POST['return'] ?? '') === 'blog';
}

function return_field(): string
{
    return from_blog() ? '<input type="hidden" name="return" value="blog">' : '';
}

function return_qs(): string
{
    return from_blog() ? '?return=blog' : '';
}

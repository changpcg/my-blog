<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// 블로그에서 로그아웃하면 여기를 거쳐 회원 페이지(PHP)도 함께 로그아웃하고 블로그로 돌아감.
// 블로그가 sso.key로 서명한 1분짜리 표가 있어야만 로그아웃 (다른 사이트가 남을 몰래 로그아웃시키지 못하게).

$t = is_string($_GET['t'] ?? null) ? $_GET['t'] : '';
$parts = explode('.', $t, 2);
$valid = false;
if (count($parts) === 2) {
    [$payload, $sig] = $parts;
    if (hash_equals(hash_hmac('sha256', $payload, sso_key()), $sig)) {
        $data = json_decode((string)base64_decode(strtr($payload, '-_', '+/')), true);
        $valid = is_array($data) && ($data['act'] ?? '') === 'logout' && (int)($data['exp'] ?? 0) >= time();
    }
}

if ($valid) {
    $_SESSION = [];
    $p = session_get_cookie_params();
    setcookie(session_name(), '', [
        'expires' => time() - 3600, 'path' => $p['path'], 'secure' => $p['secure'],
        'httponly' => $p['httponly'], 'samesite' => $p['samesite'],
    ]);
    session_destroy();
}

// 서명이 틀려도 아무것도 하지 않고 블로그로만 돌려보냄
redirect(BLOG_URL . '/#/');

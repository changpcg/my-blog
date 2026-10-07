<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// 링크만 눌러도 로그아웃되지 않도록 POST + CSRF 토큰으로만 처리
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    redirect('index.php');
}
check_csrf();

$_SESSION = [];
$p = session_get_cookie_params();
setcookie(session_name(), '', [
    'expires' => time() - 3600, 'path' => $p['path'], 'secure' => $p['secure'],
    'httponly' => $p['httponly'], 'samesite' => $p['samesite'],
]);
session_destroy();

session_start();
flash('로그아웃했어요.');
redirect('login.php' . return_qs());

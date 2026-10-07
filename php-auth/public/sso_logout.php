<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// 블로그에서 로그아웃하면 화면이 이 주소로 '함께 로그아웃' 표를 POST로 보냄.
// 표가 지금 로그인한 회원 것이고, 서명이 맞고, 아직 안 쓴 표일 때만 회원 페이지(PHP)도 로그아웃.
// (GET 링크·다른 회원의 표·이미 쓴 표로는 아무 일도 일어나지 않음)

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    $t = is_string($_POST['t'] ?? null) ? $_POST['t'] : '';
    $data = $t !== '' ? read_logout_ticket($t) : null;
    $uid = (int)($_SESSION['uid'] ?? 0);
    if ($data !== null && $uid > 0 && (int)$data['uid'] === $uid) {
        $pdo = db();
        $pdo->prepare('DELETE FROM sso_used_nonces WHERE expires < ?')->execute([time()]);
        // 기본 키라서 같은 번호는 한 번만 들어감 → 들어갔을 때만 로그아웃
        $st = $pdo->prepare('INSERT OR IGNORE INTO sso_used_nonces (nonce, expires) VALUES (?, ?)');
        $st->execute([$data['nonce'], (int)$data['exp']]);
        if ($st->rowCount() === 1) {
            $_SESSION = [];
            $p = session_get_cookie_params();
            setcookie(session_name(), '', [
                'expires' => time() - 3600, 'path' => $p['path'], 'secure' => $p['secure'],
                'httponly' => $p['httponly'], 'samesite' => $p['samesite'],
            ]);
            session_destroy();
        }
    }
}

// 어떤 경우든 블로그 홈으로만 돌려보냄
redirect(BLOG_URL . '/#/');

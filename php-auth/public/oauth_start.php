<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// SNS 로그인 시작: ?provider=kakao|naver|google  (&link=1 이면 지금 로그인한 계정에 연결)
$p = is_string($_GET['provider'] ?? null) ? $_GET['provider'] : '';
$link = ($_GET['link'] ?? '') === '1';
$user = current_user();

if ($link && !$user) {
    redirect('login.php');
}
if (!$link && $user) {
    // 이미 로그인한 상태면 SNS를 다시 거칠 필요 없음
    redirect(from_blog() ? 'login.php?return=blog' : 'index.php');
}
if (!in_array($p, enabled_providers(), true)) {
    flash('지금은 그 SNS로 로그인할 수 없어요.');
    redirect(($link ? 'index.php' : 'login.php') . return_qs());
}

redirect(oauth_authorize_url($p, $link ? 'link' : 'login'));

<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// SNS 로그인을 마치고 돌아오는 곳 (각 SNS 개발자 센터에 등록하는 Redirect URI)
$backTo = fn(array $r) => ($r['return'] ?? '') === 'blog' ? '?return=blog' : '';
$pendingReturn = ($_SESSION['oauth']['return'] ?? '') === 'blog' ? '?return=blog' : '';

try {
    $r = oauth_finish($_GET);
} catch (Throwable $e) {
    flash($e instanceof RuntimeException ? $e->getMessage() : 'SNS 로그인 중 문제가 생겼어요. 다시 시도해 주세요.');
    redirect('login.php' . $pendingReturn);
}

$label = PROVIDERS[$r['provider']]['label'];
$owner = social_user_id($r['provider'], $r['uid']);

// ---------- 내 정보에서 'SNS 연결' ----------
if ($r['mode'] === 'link') {
    $me = current_user();
    if (!$me) {
        redirect('login.php');
    }
    if ($owner !== null && $owner !== (int)$me['id']) {
        flash("이 {$label} 계정은 이미 다른 회원과 연결돼 있어요.");
    } elseif ($owner === (int)$me['id']) {
        flash("이미 연결된 {$label} 계정이에요.");
    } elseif (in_array($r['provider'], linked_providers((int)$me['id']), true)) {
        flash("다른 {$label} 계정이 이미 연결돼 있어요.");
    } else {
        link_social((int)$me['id'], $r['provider'], $r['uid']);
        flash("{$label} 계정을 연결했어요. 다음부터 {$label}로 로그인할 수 있어요.");
    }
    redirect('index.php');
}

// ---------- SNS로 로그인 ----------
if ($owner !== null) {
    login_user($owner);
    if ($r['return'] === 'blog') {
        go_to_blog(current_user());
    }
    redirect('index.php');
}

// 처음 온 SNS 계정: 아이디·닉네임·자기소개를 받아서 가입 (15분 안에)
$_SESSION['social_pending'] = $r + ['at' => time()];
redirect('social_signup.php' . $backTo($r));

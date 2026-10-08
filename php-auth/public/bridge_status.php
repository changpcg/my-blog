<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// 블로그(관리자 사이트 설정)가 부르는 곳: 서명된 요청이면 회원 서버 상태를 알려 줌 (읽기 전용, IP 없음).
// 여기서는 블로그를 다시 부르지 않음 (php -S는 한 번에 요청 하나만 처리).
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    exit(json_encode(['ok' => false, 'error' => '잘못된 요청입니다.'], JSON_UNESCAPED_UNICODE));
}
if (read_bridge(post_str('t'), 'auth_status') === null) {
    http_response_code(400);
    exit(json_encode(['ok' => false, 'error' => '서명이 올바르지 않아요.'], JSON_UNESCAPED_UNICODE));
}
echo json_encode([
    'ok' => true,
    'public_mode' => public_mode(),
    'signups' => signup_stats(),
    'sns' => ['callback_url' => redirect_uri(), 'providers' => enabled_providers()],
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

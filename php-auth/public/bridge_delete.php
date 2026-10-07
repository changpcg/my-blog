<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// 블로그(관리자 탈퇴)가 부르는 곳: 서명된 1회용 요청이면 이 회원 서버 계정을 지움.
// 여기서는 블로그를 다시 부르지 않음 (php -S는 한 번에 요청 하나만 처리).
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$fail = function (string $msg): never {
    http_response_code(400);
    exit(json_encode(['ok' => false, 'error' => $msg], JSON_UNESCAPED_UNICODE));
};
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    $fail('잘못된 요청입니다.');
}
$data = read_bridge(post_str('t'), 'delete_member');
if ($data === null || (int)($data['uid'] ?? 0) <= 0 || !is_string($data['nonce'] ?? null) || strlen($data['nonce']) < 16) {
    $fail('서명이 올바르지 않아요.');
}
$pdo = db();
$pdo->prepare('DELETE FROM sso_used_nonces WHERE expires < ?')->execute([time()]);
$st = $pdo->prepare('INSERT OR IGNORE INTO sso_used_nonces (nonce, expires) VALUES (?, ?)');
$st->execute([$data['nonce'], (int)$data['exp']]);
if ($st->rowCount() !== 1) {
    $fail('이미 처리한 요청이에요.');
}
echo json_encode(['ok' => true, 'deleted' => delete_member_local((int)$data['uid'])], JSON_UNESCAPED_UNICODE);

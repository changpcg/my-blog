<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// 아이디 중복 확인 (회원가입 화면의 '중복 확인' 버튼이 부름). 결과는 JSON.
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    exit(json_encode(['ok' => false, 'message' => '잘못된 요청입니다.'], JSON_UNESCAPED_UNICODE));
}
check_csrf();

echo json_encode(check_username(post_str('username')), JSON_UNESCAPED_UNICODE);

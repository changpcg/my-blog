<?php
// SNS 로그인 설정 예시. 이 파일을 oauth.config.php 로 복사한 뒤 키를 넣으세요.
// 키를 비워 둔 SNS는 로그인 버튼이 나오지 않습니다.
//
// 각 개발자 센터에 등록할 "Redirect URI(콜백 주소)"는 모두 같습니다:
//   http://localhost:8080/oauth_callback.php
// (실제 도메인에 올리면 https://내도메인/oauth_callback.php 로 바꾸고, redirect_uri도 함께 바꾸세요)

return [
    'redirect_uri' => 'http://localhost:8080/oauth_callback.php',

    // 카카오: https://developers.kakao.com → 내 애플리케이션 → 앱 키의 "REST API 키"
    //   카카오 로그인 활성화 + Redirect URI 등록 + 동의항목에서 "닉네임" 설정
    'kakao' => [
        'client_id' => '',
        'client_secret' => '', // 보안 → Client Secret을 켰을 때만
    ],

    // 네이버: https://developers.naver.com → Application 등록 → 사용 API "네이버 로그인"
    //   제공 정보에서 "별명" 선택, Callback URL 등록
    'naver' => [
        'client_id' => '',
        'client_secret' => '',
    ],

    // 구글: https://console.cloud.google.com → API 및 서비스 → 사용자 인증 정보 → OAuth 클라이언트 ID (웹 애플리케이션)
    //   승인된 리디렉션 URI 등록
    'google' => [
        'client_id' => '',
        'client_secret' => '',
    ],
];

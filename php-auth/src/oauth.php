<?php
declare(strict_types=1);

/**
 * SNS 로그인 (카카오·네이버·구글, OAuth 2.0 '인가 코드' 방식).
 *
 * 1) oauth_start.php  : state(위조 방지용 무작위 값)를 세션에 저장하고 SNS 로그인 화면으로 보냄
 * 2) SNS 로그인 후     : oauth_callback.php?code=...&state=... 로 돌아옴
 * 3) oauth_callback   : state를 확인하고, code를 서버끼리 토큰으로 바꾼 뒤 SNS 회원 번호·닉네임을 받아 옴
 * 4) 연결된 회원이면 로그인, 처음이면 social_signup.php에서 아이디·닉네임·자기소개를 받아 가입
 *
 * 계정 연결은 'SNS 이름 + SNS 회원 번호'로만 한다. 이메일이 같다고 자동으로 합치지 않음 (남의 계정 가로채기 방지).
 */

const PROVIDERS = [
    'kakao' => [
        'label' => '카카오',
        'authorize_url' => 'https://kauth.kakao.com/oauth/authorize',
        'token_url' => 'https://kauth.kakao.com/oauth/token',
        'userinfo_url' => 'https://kapi.kakao.com/v2/user/me',
        'scope' => 'profile_nickname',
        'pkce' => false,
    ],
    'naver' => [
        'label' => '네이버',
        'authorize_url' => 'https://nid.naver.com/oauth2.0/authorize',
        'token_url' => 'https://nid.naver.com/oauth2.0/token',
        'userinfo_url' => 'https://openapi.naver.com/v1/nid/me',
        'scope' => '',
        'pkce' => false,
    ],
    'google' => [
        'label' => '구글',
        'authorize_url' => 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url' => 'https://oauth2.googleapis.com/token',
        'userinfo_url' => 'https://openidconnect.googleapis.com/v1/userinfo',
        'scope' => 'openid profile',
        'pkce' => true,
    ],
];

function oauth_config(): array
{
    static $cfg = null;
    if ($cfg === null) {
        $path = dirname(__DIR__) . '/oauth.config.php';
        $cfg = is_file($path) ? (require $path) : [];
    }
    return $cfg;
}

/** 키가 등록된 SNS 목록 */
function enabled_providers(): array
{
    $cfg = oauth_config();
    return array_values(array_filter(
        array_keys(PROVIDERS),
        fn($p) => !empty($cfg[$p]['client_id']) && ($p === 'kakao' || !empty($cfg[$p]['client_secret']))
    ));
}

/** 설정 파일에서 주소를 덮어쓸 수 있음 (테스트용 가짜 SNS 서버) */
function provider(string $p): array
{
    if (!isset(PROVIDERS[$p]) || !in_array($p, enabled_providers(), true)) {
        throw new InvalidArgumentException('지원하지 않는 SNS입니다.');
    }
    return array_merge(PROVIDERS[$p], oauth_config()[$p]);
}

/**
 * SNS 콜백 주소. 공개 모드: 회원 서버 공개 주소(auth_url) + /oauth_callback.php만 (oauth.config.php의 값은 무시).
 * 개발 모드: oauth.config.php에 redirect_uri가 있으면 그 값(지금 등록해 둔 SNS 설정 유지).
 */
function redirect_uri(): string
{
    $fromConfig = oauth_config()['redirect_uri'] ?? '';
    if (!public_mode() && is_string($fromConfig) && $fromConfig !== '') {
        return $fromConfig;
    }
    return app_auth_url() . '/oauth_callback.php';
}

/** 1) SNS 로그인 화면으로 보낼 주소. $mode: 'login' 또는 'link'(이미 로그인한 회원에 연결) */
function oauth_authorize_url(string $p, string $mode): string
{
    $cfg = provider($p);
    $state = bin2hex(random_bytes(16));
    $verifier = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
    $_SESSION['oauth'] = [
        'provider' => $p, 'state' => $state, 'verifier' => $verifier, 'mode' => $mode,
        'return' => from_blog() ? 'blog' : '', 'at' => time(),
    ];
    $q = [
        'response_type' => 'code',
        'client_id' => $cfg['client_id'],
        'redirect_uri' => redirect_uri(),
        'state' => $state,
    ];
    if ($cfg['scope'] !== '') {
        $q['scope'] = $cfg['scope'];
    }
    if ($cfg['pkce']) {
        $q['code_challenge'] = rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');
        $q['code_challenge_method'] = 'S256';
    }
    if ($p === 'naver' && $mode === 'link') {
        $q['auth_type'] = 'reauthenticate';
    }
    return $cfg['authorize_url'] . '?' . http_build_query($q);
}

function http_request(string $method, string $url, array $form = [], array $headers = []): array
{
    $ch = curl_init();
    $opts = [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
        CURLOPT_HTTPHEADER => array_merge(['Accept: application/json'], $headers),
        CURLOPT_PROTOCOLS => CURLPROTO_HTTPS | CURLPROTO_HTTP,
    ];
    if ($method === 'POST') {
        $opts[CURLOPT_POST] = true;
        $opts[CURLOPT_POSTFIELDS] = http_build_query($form);
    }
    curl_setopt_array($ch, $opts);
    $body = curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    $data = is_string($body) ? json_decode($body, true) : null;
    if ($status < 200 || $status >= 300 || !is_array($data)) {
        throw new RuntimeException('SNS 서버와 통신하지 못했어요.');
    }
    return $data;
}

/**
 * 3) 돌아온 code를 확인하고 SNS 회원 정보를 받아 옴.
 * 돌려주는 값: ['provider', 'uid', 'nickname', 'mode', 'return']
 */
function oauth_finish(array $query): array
{
    $saved = $_SESSION['oauth'] ?? null;
    unset($_SESSION['oauth']); // state는 한 번만 사용
    if (!$saved || time() - $saved['at'] > 600) {
        throw new RuntimeException('로그인 시간이 지났어요. 다시 시도해 주세요.');
    }
    if (!empty($query['error'])) {
        throw new RuntimeException('SNS 로그인을 취소했어요.');
    }
    $state = is_string($query['state'] ?? null) ? $query['state'] : '';
    $code = is_string($query['code'] ?? null) ? $query['code'] : '';
    if ($code === '' || !hash_equals($saved['state'], $state)) {
        throw new RuntimeException('잘못된 로그인 요청이에요. 다시 시도해 주세요.');
    }

    $p = $saved['provider'];
    $cfg = provider($p);
    $form = [
        'grant_type' => 'authorization_code',
        'client_id' => $cfg['client_id'],
        'redirect_uri' => redirect_uri(),
        'code' => $code,
    ];
    if (!empty($cfg['client_secret'])) {
        $form['client_secret'] = $cfg['client_secret'];
    }
    if ($p === 'naver') {
        $form['state'] = $state;
    }
    if ($cfg['pkce']) {
        $form['code_verifier'] = $saved['verifier'];
    }
    $token = http_request('POST', $cfg['token_url'], $form);
    if (empty($token['access_token']) || !is_string($token['access_token'])) {
        throw new RuntimeException('SNS 로그인 정보를 받지 못했어요.');
    }
    $me = http_request('GET', $cfg['userinfo_url'], [], ['Authorization: Bearer ' . $token['access_token']]);

    // SNS마다 회원 번호·닉네임이 담긴 자리가 다름
    switch ($p) {
        case 'kakao':
            $uid = $me['id'] ?? null;
            $nick = $me['kakao_account']['profile']['nickname'] ?? ($me['properties']['nickname'] ?? '');
            break;
        case 'naver':
            $uid = $me['response']['id'] ?? null;
            $nick = $me['response']['nickname'] ?? ($me['response']['name'] ?? '');
            break;
        default:
            $uid = $me['sub'] ?? null;
            $nick = $me['name'] ?? ($me['given_name'] ?? '');
    }
    if ($uid === null || $uid === '') {
        throw new RuntimeException('SNS 회원 정보를 받지 못했어요.');
    }
    return [
        'provider' => $p,
        'uid' => (string)$uid,
        'nickname' => mb_substr(trim((string)$nick), 0, 20),
        'mode' => $saved['mode'],
        'return' => $saved['return'],
    ];
}

// ---------- 회원과 SNS 계정 연결 ----------
function social_user_id(string $p, string $uid): ?int
{
    $st = db()->prepare('SELECT user_id FROM social_accounts WHERE provider = ? AND provider_uid = ?');
    $st->execute([$p, $uid]);
    $id = $st->fetchColumn();
    return $id === false ? null : (int)$id;
}

function link_social(int $userId, string $p, string $uid): void
{
    $st = db()->prepare('INSERT INTO social_accounts (provider, provider_uid, user_id) VALUES (?, ?, ?)');
    $st->execute([$p, $uid, $userId]);
}

function linked_providers(int $userId): array
{
    $st = db()->prepare('SELECT provider FROM social_accounts WHERE user_id = ? ORDER BY provider');
    $st->execute([$userId]);
    return $st->fetchAll(PDO::FETCH_COLUMN);
}

function has_password(int $userId): bool
{
    $st = db()->prepare("SELECT password_hash <> '' FROM users WHERE id = ?");
    $st->execute([$userId]);
    return (bool)$st->fetchColumn();
}

/** SNS 로그인 버튼들 */
function social_buttons(string $verb = '로그인'): string
{
    $ps = enabled_providers();
    if (!$ps) {
        return '';
    }
    $html = '<div class="sns"><p class="sns-or"><span>또는 SNS로 ' . h($verb) . '</span></p>';
    foreach ($ps as $p) {
        $html .= '<a class="sns-btn sns-' . h($p) . '" href="oauth_start.php?provider=' . h($p)
            . (from_blog() ? '&amp;return=blog' : '') . '">' . h(PROVIDERS[$p]['label']) . '로 ' . h($verb) . '</a>';
    }
    return $html . '</div>';
}

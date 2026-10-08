<?php
declare(strict_types=1);

/**
 * 배포 설정 (003): 블로그와 함께 읽는 deploy.config.json (my-blog 폴더, 웹 폴더 밖).
 *
 * - 파일이 없으면 개발 모드(지금과 같음). 공개 모드는 이 파일의 public_mode로만 켠다.
 * - 값을 정하는 순서와 오류 문구: specs/003-public-deploy-readiness/contracts/deploy-config.md
 * - PHP-FPM은 기본으로 환경변수를 지우므로(clear_env), 운영에서는 이 파일이 유일한 출처다.
 * - 관리자 비밀번호 같은 비밀값은 이 파일에 넣지 않는다.
 */

function config_path(): string
{
    $env = getenv('MYBLOG_CONFIG');
    return is_string($env) && $env !== '' ? $env : dirname(__DIR__, 2) . '/deploy.config.json';
}

/** 'https://호스트[:포트]' 꼴(경로·쿼리·조각·사용자 정보 없음)이면 정리한 주소, 아니면 null */
function https_origin(string $url): ?string
{
    $u = parse_url($url);
    if (!is_array($u) || strtolower((string)($u['scheme'] ?? '')) !== 'https' || empty($u['host'])) {
        return null;
    }
    if (isset($u['user']) || isset($u['pass']) || isset($u['query']) || isset($u['fragment'])) {
        return null;
    }
    if (($u['path'] ?? '') !== '' && $u['path'] !== '/') {
        return null;
    }
    return 'https://' . strtolower($u['host']) . (isset($u['port']) ? ':' . $u['port'] : '');
}

/** IP 주소 → 정규화한 문자열(IPv4로 표현된 IPv6는 IPv4로), 아니면 null */
function normalize_ip(string $ip): ?string
{
    $bin = @inet_pton(trim($ip));
    if ($bin === false) {
        return null;
    }
    if (strlen($bin) === 16 && substr($bin, 0, 12) === "\0\0\0\0\0\0\0\0\0\0\xff\xff") {
        $bin = substr($bin, 12);
    }
    $text = inet_ntop($bin);
    return $text === false ? null : $text;
}

/** 설정 읽기 → ['settings' => [...], 'errors' => [...]]. 요청마다 한 번만 읽는다. */
function app_settings(): array
{
    static $cache = null;
    if ($cache !== null) {
        return $cache;
    }
    $errors = [];
    $bad = function (string $key, string $rule) use (&$errors): void {
        $errors[] = "deploy.config.json의 {$key} 값이 올바르지 않아요: {$rule}.";
    };

    $raw = [];
    $path = config_path();
    if (is_file($path)) {
        $text = @file_get_contents($path);
        $data = $text === false ? null : json_decode($text, true);
        if ($text === false) {
            $errors[] = '배포 설정 파일(deploy.config.json)을 읽을 수 없어요: 파일을 열 수 없어요. 권한을 확인해 주세요.';
        } elseif (!is_array($data) || ($data !== [] && array_is_list($data))) {
            $why = json_last_error() !== JSON_ERROR_NONE ? json_last_error_msg() : '맨 바깥이 { } 가 아니에요';
            $errors[] = "배포 설정 파일(deploy.config.json)을 읽을 수 없어요: {$why}. JSON 형식을 확인해 주세요.";
        } else {
            $raw = $data;
        }
    }

    $public = $raw['public_mode'] ?? false;
    if (!is_bool($public)) {
        $bad('public_mode', 'true 또는 false로 적어 주세요');
        $public = false;
    }

    $urls = [];
    foreach ([['blog_url', 'BLOG_URL', 'http://localhost:8000', 'blog'], ['auth_url', 'AUTH_URL', 'http://localhost:8080', 'auth']] as [$key, $envName, $default, $example]) {
        $fileVal = $raw[$key] ?? null;
        if ($fileVal !== null && !is_string($fileVal)) {
            $bad($key, '주소를 문자열로 적어 주세요');
            $fileVal = null;
        }
        $fileVal = trim((string)$fileVal);
        if ($public) {
            // 공개 모드: 주소는 파일 값만 (환경변수는 쓰지 않음)
            $value = rtrim($fileVal, '/');
            if (https_origin($value) === null) {
                $errors[] = "공개 모드에서는 {$key}에 https 주소만 넣어 주세요(예: https://{$example}.example.com, 경로 없이).";
            }
        } else {
            $envVal = getenv($envName);
            $envVal = is_string($envVal) ? trim($envVal) : '';
            $value = rtrim($envVal !== '' ? $envVal : ($fileVal !== '' ? $fileVal : $default), '/');
        }
        $urls[$key] = $value;
    }
    if ($public) {
        $b = https_origin($urls['blog_url']);
        $a = https_origin($urls['auth_url']);
        if ($b !== null && $a !== null && $b === $a) {
            $errors[] = '블로그와 회원 서버는 서로 다른 주소를 써야 해요(예: blog.·auth. 하위 도메인).';
        }
    }

    $tp = $raw['trusted_proxies'] ?? ($public ? ['127.0.0.1', '::1'] : []);
    $proxies = [];
    if (!is_array($tp) || !array_is_list($tp)) {
        $bad('trusted_proxies', 'IP 주소 목록으로 적어 주세요(예: ["127.0.0.1"])');
    } else {
        foreach ($tp as $item) {
            $n = is_string($item) ? normalize_ip($item) : null;
            if ($n === null) {
                $bad('trusted_proxies', json_encode($item, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . '은(는) IP 주소가 아니에요(범위 표기는 쓸 수 없어요)');
            } else {
                $proxies[$n] = true;
            }
        }
        if ($public && $tp === []) {
            $errors[] = '공개 모드에서는 믿는 프록시(trusted_proxies)를 하나 이상 적어 주세요(같은 서버의 Nginx면 127.0.0.1).';
        }
    }

    $sg = $raw['signup'] ?? [];
    if (!is_array($sg) || ($sg !== [] && array_is_list($sg))) {
        $bad('signup', '{ } 안에 per_ip_per_hour·site_per_hour·bot_check를 적어 주세요');
        $sg = [];
    }
    $intIn = function (string $name, int $default, int $lo, int $hi) use ($sg, $bad): int {
        $v = $sg[$name] ?? $default;
        if (!is_int($v) || $v < $lo || $v > $hi) {
            $bad("signup.{$name}", "{$lo}~{$hi} 사이의 정수로 적어 주세요");
            return $default;
        }
        return $v;
    };
    $perIp = $intIn('per_ip_per_hour', 3, 1, 1000);
    $site = $intIn('site_per_hour', 30, 1, 100000);
    if ($site < $perIp) {
        $bad('signup.site_per_hour', 'per_ip_per_hour 이상이어야 해요');
    }
    $bot = $sg['bot_check'] ?? true;
    if (!is_bool($bot)) {
        $bad('signup.bot_check', 'true 또는 false로 적어 주세요');
        $bot = true;
    }
    if ($public && $bot === false) {
        $errors[] = '공개 모드에서는 자동 가입 방지(signup.bot_check)를 끌 수 없어요.';
    }

    return $cache = [
        'settings' => [
            'public_mode' => $public,
            'blog_url' => $urls['blog_url'],
            'auth_url' => $urls['auth_url'],
            'trusted_proxies' => $proxies,
            'signup' => ['per_ip_per_hour' => $perIp, 'site_per_hour' => $site, 'bot_check' => $bot],
        ],
        'errors' => $errors,
    ];
}

function config_errors(): array
{
    return app_settings()['errors'];
}

function public_mode(): bool
{
    return app_settings()['settings']['public_mode'];
}

function app_blog_url(): string
{
    return app_settings()['settings']['blog_url'];
}

function app_auth_url(): string
{
    return app_settings()['settings']['auth_url'];
}

/** ['per_ip_per_hour' => int, 'site_per_hour' => int] */
function signup_limits(): array
{
    $s = app_settings()['settings']['signup'];
    return ['per_ip_per_hour' => $s['per_ip_per_hour'], 'site_per_hour' => $s['site_per_hour']];
}

function bot_check_enabled(): bool
{
    return app_settings()['settings']['signup']['bot_check'];
}

/** 바로 앞 접속(ip)이 믿는 프록시인지 (정규화해서 비교) */
function is_trusted_proxy(string $ip): bool
{
    $n = normalize_ip($ip);
    return $n !== null && isset(app_settings()['settings']['trusted_proxies'][$n]);
}

/** 이 요청이 https로 들어왔는지: 웹 서버가 알려 준 HTTPS, 또는 믿는 프록시가 보낸 X-Forwarded-Proto */
function is_https(): bool
{
    $https = (string)($_SERVER['HTTPS'] ?? '');
    if ($https !== '' && strtolower($https) !== 'off') {
        return true;
    }
    $proto = $_SERVER['HTTP_X_FORWARDED_PROTO'] ?? null;
    return is_string($proto) && is_trusted_proxy((string)($_SERVER['REMOTE_ADDR'] ?? ''))
        && strtolower(trim(explode(',', $proto)[0])) === 'https';
}

/** 실제 방문자 IP: 믿는 프록시에서 온 요청만 X-Forwarded-For를 오른쪽부터 읽어 믿는 프록시가 아닌 첫 IP */
function client_ip(): string
{
    $peer = (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');
    if (!is_trusted_proxy($peer)) {
        return $peer;
    }
    $xff = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? '';
    $hops = array_values(array_filter(array_map('trim', explode(',', is_string($xff) ? $xff : '')), fn($h) => $h !== ''));
    foreach (array_reverse($hops) as $hop) {
        $ip = normalize_ip($hop);
        if ($ip === null) {
            return $peer;
        }
        if (!is_trusted_proxy($ip)) {
            return $ip;
        }
    }
    return $peer;
}

/**
 * 공개 모드 관문 (세션을 시작하기 전에 부름): php -S면 거절, https가 아니면 같은 경로의 https 공개 주소로 308,
 * https면 HSTS. 개발 모드에서는 아무것도 하지 않음.
 */
function enforce_public_mode(): void
{
    if (!public_mode()) {
        return;
    }
    if (PHP_SAPI === 'cli-server' && getenv('ALLOW_PHP_DEV_SERVER') !== '1') {
        stop_request(503, '공개 모드에서는 php -S로 회원 서버를 켤 수 없어요. Nginx + PHP-FPM으로 실행해 주세요(deploy/README.md).');
    }
    if (!is_https()) {
        $uri = (string)($_SERVER['REQUEST_URI'] ?? '/');
        header('Location: ' . app_auth_url() . (str_starts_with($uri, '/') ? $uri : '/'), true, 308);
        exit;
    }
    header('Strict-Transport-Security: max-age=31536000');
}

/** 요청을 여기서 끝냄: JSON 엔드포인트는 JSON, 나머지는 짧은 한국어 화면 */
function stop_request(int $status, string $msg): never
{
    http_response_code($status);
    header('Cache-Control: no-store');
    $script = basename((string)($_SERVER['SCRIPT_NAME'] ?? ''));
    if ($script === 'check_username.php' || str_starts_with($script, 'bridge_')) {
        header('Content-Type: application/json; charset=utf-8');
        exit(json_encode(['ok' => false, 'error' => $msg, 'message' => $msg], JSON_UNESCAPED_UNICODE));
    }
    header('Content-Type: text/html; charset=utf-8');
    exit('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark">'
        . '<title>회원 서버</title></head><body><main style="max-width:32rem;margin:3rem auto;padding:0 1rem;font-family:sans-serif">'
        . '<h1 style="font-size:1.25rem">잠시만요</h1><p>' . htmlspecialchars($msg, ENT_QUOTES, 'UTF-8') . '</p></main></body></html>');
}

/** 설정이 틀리면 DB를 열기 전에 503으로 멈춤. 자세한 이유는 서버 기록(error_log)에만 남김 */
function config_guard(): void
{
    $errors = config_errors();
    if (!$errors) {
        return;
    }
    foreach ($errors as $e) {
        error_log('[my-blog 회원 서버 설정] ' . $e);
    }
    stop_request(503, '회원 서버 설정을 확인하고 있어요. 잠시 뒤 다시 시도해 주세요.');
}

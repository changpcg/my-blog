<?php
declare(strict_types=1);

/**
 * 가입 보호 (003 US4): 자동 가입 방지 + 가입 횟수 제한. 외부 서비스 없이 서버에서만 확인한다(헌법 I·II).
 * 규칙과 문구: specs/003-public-deploy-readiness/contracts/signup-guard.md
 *
 * - 자동 가입 방지: 가입 화면을 열 때 발급한 1회용 폼 토큰(세션, 3초~30분) + 사람 눈에 안 보이는 칸(website)
 * - 횟수 제한: signup_log 표로 같은 IP 1시간 N개, 사이트 전체 1시간 M개 (deploy.config.json의 signup)
 */

const SIGNUP_FORM_TTL = 30 * 60;     // 가입 화면을 연 뒤 30분 안에 보내야 함
const SIGNUP_MIN_SECONDS = 3;        // 사람이 채우는 데 걸리는 최소 시간
const SIGNUP_FORMS_KEEP = 5;         // 세션당 기억하는 폼 토큰 수
const SIGNUP_LOG_KEEP = 24 * 3600;   // 가입 기록 보관 (가입 현황도 24시간)

const SIGNUP_MSG = [
    'bot' => '가입을 처리하지 못했어요. 화면을 새로 고친 뒤 다시 시도해 주세요.',
    'expired' => '가입 화면을 연 지 30분이 지났어요. 입력한 내용을 확인하고 다시 눌러 주세요.',
    'fast' => '너무 빨리 보냈어요. 입력한 내용을 확인하고 다시 눌러 주세요.',
    'limit_ip' => '이 곳에서 1시간 안에 가입을 너무 많이 했어요. 잠시 뒤 다시 시도해 주세요.',
    'limit_site' => '지금 가입이 몰려 잠시 막아 두었어요. 잠시 뒤 다시 시도해 주세요.',
];

// ---------- 자동 가입 방지 ----------

/** 세션의 폼 토큰 {토큰: 발급 시각}에서 30분 지난 것을 지우고 최근 5개만 남김 */
function signup_forms(): array
{
    $now = microtime(true);
    $forms = is_array($_SESSION['signup_forms'] ?? null) ? $_SESSION['signup_forms'] : [];
    $forms = array_filter($forms, fn($at) => is_numeric($at) && $at > $now - SIGNUP_FORM_TTL);
    asort($forms);
    $forms = array_slice($forms, -SIGNUP_FORMS_KEEP, null, true);
    $_SESSION['signup_forms'] = $forms;
    return $forms;
}

/** 폼에 넣을 토큰: 보낸 토큰이 아직 유효하면 그대로(입력 오류로 다시 그릴 때), 아니면 새로 발급 */
function signup_form_token(?string $posted = null): string
{
    $forms = signup_forms();
    if ($posted !== null && $posted !== '' && isset($forms[$posted])) {
        return $posted;
    }
    $token = bin2hex(random_bytes(16));
    $_SESSION['signup_forms'] = $forms + [$token => microtime(true)];
    signup_forms();
    return $token;
}

/** 폼에 넣는 칸 두 개: 토큰 + 사람 눈에 안 보이는 칸 (끄면 아무것도 넣지 않음) */
function signup_guard_fields(string $token): string
{
    if (!bot_check_enabled()) {
        return '';
    }
    return '<input type="hidden" name="form_token" value="' . h($token) . '">'
        . '<div class="hp-field" aria-hidden="true"><label>이 칸은 비워 두세요 '
        . '<input type="text" name="website" value="" tabindex="-1" autocomplete="off"></label></div>';
}

/**
 * 가입 POST의 자동 가입 방지 확인. 통과하면 null, 아니면 화면에 보일 문구.
 * 숨은 칸·토큰 없음·3초 미만은 'bot'으로 기록하고, 30분 만료는 사람일 수 있어 기록하지 않는다.
 */
function signup_bot_error(): ?string
{
    if (!bot_check_enabled()) {
        return null;
    }
    $website = $_POST['website'] ?? '';
    $token = $_POST['form_token'] ?? '';
    if (!is_string($website) || $website !== '' || !is_string($token) || $token === '') {
        log_signup('bot');
        return SIGNUP_MSG['bot'];
    }
    // 정리(signup_forms)보다 먼저 원래 값을 봐야 '만료'와 '모르는 토큰'을 구분할 수 있음
    $at = is_array($_SESSION['signup_forms'] ?? null) ? ($_SESSION['signup_forms'][$token] ?? null) : null;
    if (!is_numeric($at)) {
        log_signup('bot');
        return SIGNUP_MSG['bot'];
    }
    $age = microtime(true) - (float)$at;
    if ($age > SIGNUP_FORM_TTL) {
        return SIGNUP_MSG['expired'];
    }
    if ($age < SIGNUP_MIN_SECONDS) {
        log_signup('bot');
        return SIGNUP_MSG['fast'];
    }
    return null;
}

/** 가입이 끝난 폼 토큰은 다시 못 쓰게 */
function signup_token_used(): void
{
    $token = $_POST['form_token'] ?? '';
    if (is_string($token) && is_array($_SESSION['signup_forms'] ?? null)) {
        unset($_SESSION['signup_forms'][$token]);
    }
}

// ---------- 가입 횟수 제한 ----------

function log_signup(string $kind): void
{
    db()->prepare('INSERT INTO signup_log (ip, kind, created_at) VALUES (?, ?, ?)')->execute([client_ip(), $kind, time()]);
}

/** 이 방문자가 지금 가입 한도에 걸리는지: null | 'limit_ip' | 'limit_site' (가입 POST에서는 BEGIN IMMEDIATE 안에서) */
function signup_limit_kind(): ?string
{
    $limits = signup_limits();
    $since = time() - 3600;
    $st = db()->prepare("SELECT COUNT(*) FROM signup_log WHERE kind = 'ok' AND ip = ? AND created_at > ?");
    $st->execute([client_ip(), $since]);
    if ((int)$st->fetchColumn() >= $limits['per_ip_per_hour']) {
        return 'limit_ip';
    }
    $st = db()->prepare("SELECT COUNT(*) FROM signup_log WHERE kind = 'ok' AND created_at > ?");
    $st->execute([$since]);
    if ((int)$st->fetchColumn() >= $limits['site_per_hour']) {
        return 'limit_site';
    }
    return null;
}

/**
 * 한도 확인 + 계정 만들기 + 기록을 트랜잭션 하나로 (PHP-FPM 작업자 여럿이 동시에 받아도 한도를 넘지 않게).
 * $create()는 ['uid' => ?int, 'new' => bool]을 돌려준다(uid null = 아이디가 겹침).
 * 결과: ['uid' => ?int, 'error' => ?string]
 */
function create_member_guarded(callable $create): array
{
    $pdo = db();
    $pdo->exec('BEGIN IMMEDIATE');
    try {
        $pdo->prepare('DELETE FROM signup_log WHERE created_at < ?')->execute([time() - SIGNUP_LOG_KEEP]);
        $kind = signup_limit_kind();
        if ($kind !== null) {
            $pdo->exec('ROLLBACK'); // 계정은 만들지 않고 막힌 기록만 남김
            log_signup($kind);
            return ['uid' => null, 'error' => SIGNUP_MSG[$kind]];
        }
        $r = $create();
        if ($r['uid'] !== null && $r['new']) {
            log_signup('ok');
        }
        $pdo->exec('COMMIT');
        return ['uid' => $r['uid'], 'error' => null];
    } catch (Throwable $e) {
        try {
            $pdo->exec('ROLLBACK');
        } catch (Throwable) {
            // 이미 끝난 트랜잭션
        }
        throw $e;
    }
}

/** 가입 화면을 열 때 한도면 폼 대신 안내 (기록은 남기지 않음) */
function signup_limit_page(): void
{
    $kind = signup_limit_kind();
    if ($kind === null) {
        return;
    }
    page_start('회원가입');
    echo '<section class="card"><h1>회원가입</h1><p class="error-box" role="alert">' . h(SIGNUP_MSG[$kind]) . '</p>'
        . '<p class="foot"><a href="login.php' . h(return_qs()) . '">로그인으로</a></p></section>';
    page_end();
    exit;
}

/** 관리자 가입 현황 (최근 24시간, IP 없음) — bridge_status.php */
function signup_stats(): array
{
    $now = time();
    $st = db()->prepare('SELECT kind, COUNT(*) AS n FROM signup_log WHERE created_at > ? GROUP BY kind');
    $st->execute([$now - SIGNUP_LOG_KEEP]);
    $n = ['ok' => 0, 'limit_ip' => 0, 'limit_site' => 0, 'bot' => 0];
    foreach ($st->fetchAll() as $row) {
        if (isset($n[$row['kind']])) {
            $n[$row['kind']] = (int)$row['n'];
        }
    }
    $st = db()->prepare("SELECT COUNT(*) FROM signup_log WHERE kind = 'ok' AND created_at > ?");
    $st->execute([$now - 3600]);
    $limits = signup_limits();
    return [
        'window_hours' => 24,
        'created' => $n['ok'],
        'blocked' => ['limit_ip' => $n['limit_ip'], 'limit_site' => $n['limit_site'], 'bot' => $n['bot']],
        'site_limited_now' => (int)$st->fetchColumn() >= $limits['site_per_hour'],
        'limits' => $limits,
    ];
}

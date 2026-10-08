<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// SNS로 처음 들어온 사람: 아이디(중복 확인)·닉네임·자기소개만 받고 가입 (비밀번호 없음)
$pending = $_SESSION['social_pending'] ?? null;
if (!$pending || time() - $pending['at'] > 15 * 60) {
    unset($_SESSION['social_pending']);
    flash('SNS 가입 시간이 지났어요. 다시 시도해 주세요.');
    redirect('login.php' . return_qs());
}
if (current_user()) {
    redirect('index.php');
}
if (!signup_open()) {
    unset($_SESSION['social_pending']);
    flash(SIGNUP_CLOSED_MESSAGE);
    redirect('login.php' . return_qs());
}

// 003: 이 곳(IP)이나 사이트 전체가 가입 한도면 폼 대신 안내
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    signup_limit_page();
}

$label = PROVIDERS[$pending['provider']]['label'];
$errors = [];
$old = ['username' => '', 'nickname' => $pending['nickname'], 'bio' => ''];
$check = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    check_csrf();
    $username = strtolower(trim(post_str('username')));
    $nickname = trim(post_str('nickname'));
    $bio = trim(post_str('bio'));
    $old = ['username' => $username, 'nickname' => $nickname, 'bio' => $bio];

    if (post_str('action') === 'check') {
        $check = check_username($username);
    } else {
        $errors = validate_profile($username, $nickname, $bio);
        if (!isset($errors['username']) && !username_checked($username)) {
            $errors['username'] = '아이디 중복 확인을 해 주세요.';
        }
        if (!$errors) {
            // 003: 자동 가입 방지 → 한도 확인과 계정 만들기·SNS 연결을 한 트랜잭션으로
            $botError = signup_bot_error();
            $res = $botError === null
                ? create_member_guarded(function () use ($pending, $username, $nickname, $bio): array {
                    // 그사이 같은 SNS 계정으로 다른 창에서 가입했는지 다시 확인
                    $already = social_user_id($pending['provider'], $pending['uid']);
                    $uid = $already ?? create_user($username, null, $nickname, $bio);
                    if ($uid !== null && $already === null) {
                        link_social($uid, $pending['provider'], $pending['uid']);
                    }
                    return ['uid' => $uid, 'new' => $already === null];
                })
                : ['uid' => null, 'error' => $botError];
            $uid = $res['uid'];
            if ($res['error'] !== null) {
                $errors['form'] = $res['error'];
            } elseif ($uid === null) {
                unset($_SESSION['checked_username']);
                $errors['username'] = '방금 다른 사람이 이 아이디로 가입했어요. 다른 아이디로 다시 확인해 주세요.';
            } else {
                signup_token_used();
                unset($_SESSION['social_pending'], $_SESSION['checked_username'], $_SESSION['username_checks']);
                login_user($uid);
                if ($pending['return'] === 'blog') {
                    go_to_blog(current_user());
                }
                flash($nickname . '님, 가입을 환영해요!');
                redirect('index.php');
            }
        }
    }
}

if ($check === null && $old['username'] !== '' && username_checked($old['username']) && !isset($errors['username'])) {
    $check = ['ok' => true, 'message' => '사용할 수 있는 아이디예요.'];
}
$err = fn(string $k) => isset($errors[$k]) ? '<small class="error" id="' . $k . '-err">' . h($errors[$k]) . '</small>' : '';
$aria = fn(string $k) => isset($errors[$k]) ? ' aria-invalid="true" aria-describedby="' . $k . '-err"' : '';
$formToken = signup_form_token(is_string($_POST['form_token'] ?? null) ? $_POST['form_token'] : null);

page_start($label . '로 가입');
?>
<form class="card" id="signupForm" method="post" action="social_signup.php<?= return_qs() ?>" novalidate>
  <h1><span class="sns-badge sns-<?= h($pending['provider']) ?>"><?= h($label) ?></span> 계정으로 가입</h1>
  <p class="muted note"><?= h($label) ?> 인증을 마쳤어요. 사용할 아이디와 닉네임만 정하면 끝나요. 비밀번호는 필요 없어요.</p>
  <?= csrf_field() ?><?= return_field() ?><?= signup_guard_fields($formToken) ?>
  <?php if (isset($errors['form'])): ?><p class="error-box" role="alert"><?= h($errors['form']) ?></p><?php endif; ?>

  <div class="field">
    <label for="username"><span>아이디</span></label>
    <div class="with-btn">
      <input id="username" name="username" value="<?= h($old['username']) ?>" autocomplete="username" required
             minlength="4" maxlength="20" pattern="[a-z0-9_]+" autofocus aria-describedby="username-status"<?= $aria('username') ?>>
      <button class="btn small-btn" type="submit" name="action" value="check" id="checkBtn" formnovalidate>중복 확인</button>
    </div>
    <small class="hint">영문 소문자, 숫자, 밑줄(_)로 4~20자<?= $pending['return'] === 'blog' ? ' · 블로그 주소가 돼요' : '' ?></small>
    <small id="username-status" class="status <?= $check ? ($check['ok'] ? 'good' : 'bad') : '' ?>" role="status" aria-live="polite"><?= $check ? ($check['ok'] ? '✓ ' : '✕ ') . h($check['message']) : '' ?></small>
    <?= $err('username') ?>
  </div>
  <label class="field"><span>닉네임</span>
    <input name="nickname" value="<?= h($old['nickname']) ?>" required minlength="2" maxlength="20"<?= $aria('nickname') ?>>
    <?php if ($pending['nickname'] !== ''): ?><small class="hint"><?= h($label) ?>에서 가져온 이름이에요. 바꿔도 돼요.</small><?php endif; ?>
    <?= $err('nickname') ?></label>
  <label class="field"><span>자기소개 <em>(선택)</em></span>
    <textarea name="bio" rows="4" maxlength="300" placeholder="나를 한두 줄로 소개해 주세요"<?= $aria('bio') ?>><?= h($old['bio']) ?></textarea>
    <?= $err('bio') ?></label>
  <button class="btn primary" type="submit" name="action" value="signup" id="signupBtn">가입하기</button>
  <p class="foot"><a href="login.php<?= return_qs() ?>">취소</a></p>
</form>
<script src="register.js"></script>
<?php page_end();

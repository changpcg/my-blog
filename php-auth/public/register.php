<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

if (current_user()) {
    redirect(from_blog() ? 'login.php?return=blog' : 'index.php');
}

// 관리자가 블로그 사이트 설정에서 회원가입을 꺼 두었으면 가입 화면 대신 안내만
if (!signup_open()) {
    page_start('회원가입');
    echo '<section class="card"><h1>회원가입</h1><p>' . h(SIGNUP_CLOSED_MESSAGE) . '</p>'
        . '<p class="foot"><a href="login.php' . h(return_qs()) . '">로그인으로</a></p></section>';
    page_end();
    exit;
}

$errors = [];
$old = ['username' => '', 'nickname' => '', 'bio' => ''];
$check = null; // 아이디 중복 확인 결과 (자바스크립트 없이 버튼을 눌렀을 때)

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    check_csrf();
    $username = strtolower(trim(post_str('username')));
    $password = post_str('password');
    $password2 = post_str('password2');
    $nickname = trim(post_str('nickname'));
    $bio = trim(post_str('bio'));
    $old = ['username' => $username, 'nickname' => $nickname, 'bio' => $bio];

    if (post_str('action') === 'check') {
        // '중복 확인' 버튼 (자바스크립트가 꺼져 있어도 동작)
        $check = check_username($username);
    } else {
        $errors = validate_signup($username, $password, $password2, $nickname, $bio);
        // 중복 확인을 통과한 바로 그 아이디로만 가입 (확인 뒤에 아이디를 바꿨으면 다시 확인)
        if (!isset($errors['username']) && !username_checked($username)) {
            $errors['username'] = '아이디 중복 확인을 해 주세요.';
        }
        if (!$errors) {
            // 확인과 가입 사이에 누가 먼저 가입했을 수도 있어서, DB의 UNIQUE 제약으로 한 번 더 막음
            $uid = create_user($username, $password, $nickname, $bio);
            if ($uid === null) {
                unset($_SESSION['checked_username']);
                $errors['username'] = '방금 다른 사람이 이 아이디로 가입했어요. 다른 아이디로 다시 확인해 주세요.';
            } else {
                unset($_SESSION['checked_username'], $_SESSION['username_checks']);
                login_user($uid);
                if (from_blog()) {
                    go_to_blog(current_user());
                }
                flash($nickname . '님, 가입을 환영해요!');
                redirect('index.php');
            }
        }
    }
}

// 화면을 다시 그릴 때 이미 확인된 아이디면 '사용 가능' 상태로 보여 줌
if ($check === null && $old['username'] !== '' && username_checked($old['username']) && !isset($errors['username'])) {
    $check = ['ok' => true, 'message' => '사용할 수 있는 아이디예요.'];
}

/** 입력칸 아래 오류 메시지 */
$err = fn(string $k) => isset($errors[$k]) ? '<small class="error" id="' . $k . '-err">' . h($errors[$k]) . '</small>' : '';
$aria = fn(string $k) => isset($errors[$k]) ? ' aria-invalid="true" aria-describedby="' . $k . '-err"' : '';

page_start('회원가입');
?>
<form class="card" id="signupForm" method="post" action="register.php<?= return_qs() ?>" novalidate>
  <h1>회원가입</h1>
  <?php if (from_blog()): ?><p class="muted note">가입하면 바로 나만의 블로그가 생겨요. 자기소개는 블로그 소개로도 쓰여요.</p><?php endif; ?>
  <?= csrf_field() ?><?= return_field() ?>
  <?php if (enabled_providers()): ?>
  <?= str_replace('sns-or', 'sns-or top', social_buttons('3초 가입')) ?>
  <p class="sns-or"><span>또는 아이디로 가입</span></p>
  <?php endif; ?>

  <div class="field">
    <label for="username"><span>아이디</span></label>
    <div class="with-btn">
      <input id="username" name="username" value="<?= h($old['username']) ?>" autocomplete="username" required
             minlength="4" maxlength="20" pattern="[a-z0-9_]+" autofocus aria-describedby="username-status"<?= $aria('username') ?>>
      <button class="btn small-btn" type="submit" name="action" value="check" id="checkBtn" formnovalidate>중복 확인</button>
    </div>
    <small class="hint">영문 소문자, 숫자, 밑줄(_)로 4~20자</small>
    <small id="username-status" class="status <?= $check ? ($check['ok'] ? 'good' : 'bad') : '' ?>" role="status" aria-live="polite"><?= $check ? ($check['ok'] ? '✓ ' : '✕ ') . h($check['message']) : '' ?></small>
    <?= $err('username') ?>
  </div>

  <label class="field"><span>비밀번호</span>
    <input type="password" id="password" name="password" autocomplete="new-password" required minlength="8"<?= $aria('password') ?>>
    <small class="hint">영문과 숫자를 섞어 8자 이상</small><?= $err('password') ?></label>
  <label class="field"><span>비밀번호 확인</span>
    <input type="password" id="password2" name="password2" autocomplete="new-password" required aria-describedby="pw-status"<?= $aria('password2') ?>>
    <small id="pw-status" class="status" role="status" aria-live="polite"></small>
    <?= $err('password2') ?></label>

  <label class="field"><span>닉네임</span>
    <input name="nickname" value="<?= h($old['nickname']) ?>" required minlength="2" maxlength="20"<?= $aria('nickname') ?>>
    <?= $err('nickname') ?></label>
  <label class="field"><span>자기소개 <em>(선택)</em></span>
    <textarea name="bio" rows="4" maxlength="300" placeholder="나를 한두 줄로 소개해 주세요"<?= $aria('bio') ?>><?= h($old['bio']) ?></textarea>
    <?= $err('bio') ?></label>
  <button class="btn primary" type="submit" name="action" value="signup" id="signupBtn">가입하기</button>
  <p class="foot">이미 회원이신가요? <a href="login.php<?= return_qs() ?>">로그인</a></p>
</form>
<script src="register.js"></script>
<?php page_end();

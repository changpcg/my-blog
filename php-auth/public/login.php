<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

$user = current_user();

// 이미 로그인한 상태
if ($user) {
    if (!from_blog()) {
        redirect('index.php');
    }
    // 블로그에서 왔으면: 버튼을 눌러야만 블로그로 입장 (모르는 사이 로그인되지 않게)
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        check_csrf();
        go_to_blog($user);
    }
    page_start('블로그로 계속하기');
    ?>
<section class="card">
  <h1>블로그로 계속하기</h1>
  <div class="profile">
    <div class="avatar" aria-hidden="true"><?= h(mb_substr($user['nickname'], 0, 1)) ?></div>
    <div><b><?= h($user['nickname']) ?></b><p class="muted">@<?= h($user['username']) ?></p></div>
  </div>
  <form method="post" action="login.php?return=blog" class="stack">
    <?= csrf_field() ?>
    <button class="btn primary"><?= h($user['nickname']) ?>님으로 블로그 들어가기</button>
  </form>
  <form method="post" action="logout.php">
    <?= csrf_field() ?><?= return_field() ?>
    <button class="btn wide">다른 계정으로 로그인</button>
  </form>
</section>
<?php
    page_end();
    exit;
}

$error = null;
$username = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    check_csrf();
    $username = strtolower(trim(post_str('username')));
    $result = attempt_login($username, post_str('password'));
    if (is_int($result)) {
        login_user($result);
        if (from_blog()) {
            go_to_blog(current_user());
        }
        redirect('index.php');
    }
    $error = $result;
}

page_start('로그인');
?>
<form class="card" method="post" action="login.php<?= return_qs() ?>">
  <h1>로그인</h1>
  <?php if (from_blog()): ?><p class="muted note">로그인하면 블로그로 돌아가요.</p><?php endif; ?>
  <?= csrf_field() ?><?= return_field() ?>
  <?php if ($error): ?><p class="error-box" role="alert"><?= h($error) ?></p><?php endif; ?>
  <label class="field"><span>아이디</span>
    <input name="username" value="<?= h($username) ?>" autocomplete="username" required autofocus></label>
  <label class="field"><span>비밀번호</span>
    <input type="password" name="password" autocomplete="current-password" required></label>
  <button class="btn primary">로그인</button>
  <?= social_buttons('로그인') ?>
  <p class="foot">아직 회원이 아니신가요? <a href="register.php<?= return_qs() ?>">회원가입</a></p>
</form>
<?php page_end();

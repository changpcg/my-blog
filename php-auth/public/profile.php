<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

// 내 정보 수정: 닉네임·자기소개, 비밀번호(SNS 전용 회원은 처음 만들기), 회원 탈퇴
$user = current_user();
if (!$user) {
    redirect('login.php');
}
$uid = (int)$user['id'];
$hasPw = has_password($uid);
$errors = [];
$old = ['nickname' => $user['nickname'], 'bio' => $user['bio']];

/** 현재 비밀번호 확인 (로그인과 같은 15분 5번 잠금) */
$verify = function (string $pw) use ($user): ?string {
    $r = attempt_login($user['username'], $pw);
    return is_int($r) ? null : $r;
};

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    check_csrf();
    $action = post_str('action');

    if ($action === 'profile') {
        $nickname = trim(post_str('nickname'));
        $bio = trim(post_str('bio'));
        $old = ['nickname' => $nickname, 'bio' => $bio];
        $errors = array_intersect_key(validate_profile($user['username'], $nickname, $bio), ['nickname' => 1, 'bio' => 1]);
        if (!$errors) {
            $changedNick = $nickname !== $user['nickname'];
            db()->prepare('UPDATE users SET nickname = ?, bio = ?, nickname_at = CASE WHEN ? THEN ? ELSE nickname_at END WHERE id = ?')
                ->execute([$nickname, $bio, $changedNick ? 1 : 0, time(), $uid]);
            flash($changedNick ? '저장했어요. 블로그 닉네임은 다음에 블로그로 들어갈 때 바뀌어요.' : '저장했어요.');
            redirect('profile.php');
        }
    } elseif ($action === 'password') {
        $new = post_str('new_password');
        $new2 = post_str('new_password2');
        if ($hasPw && ($msg = $verify(post_str('current_password'))) !== null) {
            $errors['current_password'] = $msg;
        } else {
            $pwErrors = validate_signup($user['username'], $new, $new2, $user['nickname'], '');
            if (isset($pwErrors['password'])) {
                $errors['new_password'] = $pwErrors['password'];
            }
            if (isset($pwErrors['password2'])) {
                $errors['new_password2'] = $pwErrors['password2'];
            }
        }
        if (!$errors) {
            // 비밀번호를 바꾸면 다른 브라우저의 회원 페이지 로그인은 끊고, 이 브라우저는 유지
            db()->prepare('UPDATE users SET password_hash = ?, session_ver = session_ver + 1 WHERE id = ?')
                ->execute([password_hash($new, PASSWORD_DEFAULT), $uid]);
            login_user($uid);
            flash($hasPw ? '비밀번호를 바꿨어요. 다른 기기의 회원 페이지 로그인은 끝났어요.' : '비밀번호를 만들었어요. 이제 아이디로도 로그인할 수 있어요.');
            redirect('profile.php');
        }
    } elseif ($action === 'delete') {
        if ($hasPw) {
            $msg = $verify(post_str('confirm_password'));
            if ($msg !== null) {
                $errors['confirm'] = $msg;
            }
        } elseif (strtolower(trim(post_str('confirm_username'))) !== $user['username']) {
            $errors['confirm'] = '아이디를 정확히 입력해 주세요.';
        }
        if (!$errors) {
            // 블로그 계정부터 지우고, 성공했을 때만 회원 계정을 지움 (한쪽만 남지 않게)
            $r = blog_call('POST', '/api/bridge/delete_member', ['t' => sign_bridge([
                'act' => 'delete_member', 'uid' => $uid, 'nonce' => bin2hex(random_bytes(16)),
            ])]);
            if ($r === null || $r[0] !== 200 || empty($r[1]['ok'])) {
                $errors['confirm'] = ($r[1]['error'] ?? null) ?: '블로그 서버에 연결할 수 없어 탈퇴하지 않았어요. 잠시 뒤 다시 시도해 주세요.';
            } else {
                delete_member_local($uid);
                $_SESSION = [];
                session_regenerate_id(true);
                flash('탈퇴했어요. 그동안 고마웠어요.');
                redirect('login.php');
            }
        }
    }
}

$err = fn(string $k) => isset($errors[$k]) ? '<small class="error" id="' . $k . '-err">' . h($errors[$k]) . '</small>' : '';
$aria = fn(string $k) => isset($errors[$k]) ? ' aria-invalid="true" aria-describedby="' . $k . '-err"' : '';

page_start('내 정보 수정');
?>
<form class="card" method="post" action="profile.php">
  <h1>내 정보 수정</h1>
  <p class="muted">@<?= h($user['username']) ?> · 아이디는 바꿀 수 없어요.</p>
  <?= csrf_field() ?>
  <label class="field"><span>닉네임</span>
    <input name="nickname" value="<?= h($old['nickname']) ?>" required minlength="2" maxlength="20"<?= $aria('nickname') ?>>
    <?= $err('nickname') ?></label>
  <label class="field"><span>자기소개 <em>(선택)</em></span>
    <textarea name="bio" rows="4" maxlength="300"<?= $aria('bio') ?>><?= h($old['bio']) ?></textarea>
    <?= $err('bio') ?></label>
  <button class="btn primary" type="submit" name="action" value="profile">저장</button>
</form>

<form class="card" method="post" action="profile.php">
  <h2><?= $hasPw ? '비밀번호 바꾸기' : '비밀번호 만들기' ?></h2>
  <?php if (!$hasPw): ?><p class="muted note">SNS로 가입한 계정이에요. 비밀번호를 만들면 아이디로도 로그인할 수 있어요.</p><?php endif; ?>
  <?= csrf_field() ?>
  <?php if ($hasPw): ?>
  <label class="field"><span>현재 비밀번호</span>
    <input type="password" name="current_password" autocomplete="current-password" required<?= $aria('current_password') ?>>
    <?= $err('current_password') ?></label>
  <?php endif; ?>
  <label class="field"><span>새 비밀번호</span>
    <input type="password" name="new_password" autocomplete="new-password" required minlength="8"<?= $aria('new_password') ?>>
    <small class="hint">영문과 숫자를 섞어 8자 이상</small><?= $err('new_password') ?></label>
  <label class="field"><span>새 비밀번호 확인</span>
    <input type="password" name="new_password2" autocomplete="new-password" required<?= $aria('new_password2') ?>>
    <?= $err('new_password2') ?></label>
  <button class="btn primary" type="submit" name="action" value="password"><?= $hasPw ? '비밀번호 바꾸기' : '비밀번호 만들기' ?></button>
</form>

<form class="card" method="post" action="profile.php">
  <h2>회원 탈퇴</h2>
  <p class="muted note">회원 계정과 SNS 연결, 내 블로그의 글·댓글·공감·이웃이 모두 지워지고 되돌릴 수 없어요.</p>
  <?= csrf_field() ?>
  <?php if ($hasPw): ?>
  <label class="field"><span>비밀번호 확인</span>
    <input type="password" name="confirm_password" autocomplete="current-password" required<?= $aria('confirm') ?>>
    <?= $err('confirm') ?></label>
  <?php else: ?>
  <label class="field"><span>확인을 위해 아이디(<?= h($user['username']) ?>)를 입력해 주세요</span>
    <input name="confirm_username" autocomplete="off" required<?= $aria('confirm') ?>>
    <?= $err('confirm') ?></label>
  <?php endif; ?>
  <button class="btn danger" type="submit" name="action" value="delete">탈퇴하기</button>
</form>
<p class="foot"><a href="index.php">← 내 정보로</a></p>
<?php page_end();

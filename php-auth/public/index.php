<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/auth.php';

$user = current_user();
page_start('내 정보');

if (!$user): ?>
<section class="card">
  <h1>환영해요 👋</h1>
  <p>로그인하거나 새로 가입해 주세요.</p>
  <div class="row">
    <a class="btn primary" href="login.php">로그인</a>
    <a class="btn" href="register.php">회원가입</a>
  </div>
</section>
<?php else: ?>
<section class="card">
  <div class="profile">
    <div class="avatar" aria-hidden="true"><?= h(mb_substr($user['nickname'], 0, 1)) ?></div>
    <div>
      <h1><?= h($user['nickname']) ?></h1>
      <p class="muted">@<?= h($user['username']) ?> · <?= h(substr($user['created_at'], 0, 10)) ?> 가입</p>
    </div>
  </div>
  <h2>자기소개</h2>
  <p class="bio"><?= $user['bio'] !== '' ? nl2br(h($user['bio'])) : '<span class="muted">아직 자기소개가 없어요.</span>' ?></p>
  <?php $linked = linked_providers((int)$user['id']); $usable = enabled_providers(); ?>
  <?php if ($linked || $usable): ?>
  <h2>SNS 연결</h2>
  <ul class="sns-list">
    <?php foreach (array_unique(array_merge($linked, $usable)) as $p): ?>
      <li><span class="sns-badge sns-<?= h($p) ?>"><?= h(PROVIDERS[$p]['label']) ?></span>
        <?php if (in_array($p, $linked, true)): ?><span class="ok">✓ 연결됨</span>
        <?php else: ?><a class="btn small-btn" href="oauth_start.php?provider=<?= h($p) ?>&amp;link=1">연결하기</a><?php endif; ?>
      </li>
    <?php endforeach; ?>
  </ul>
  <?php if (!has_password((int)$user['id'])): ?><p class="muted">SNS로 가입한 계정이라 비밀번호 없이 SNS로만 로그인해요.</p><?php endif; ?>
  <?php endif; ?>
  <a class="btn primary blog-go" href="login.php?return=blog">내 블로그로 가기 →</a>
  <form method="post" action="logout.php">
    <?= csrf_field() ?>
    <button class="btn">로그아웃</button>
  </form>
</section>
<?php endif;
page_end();

'use strict';
// 회원가입 화면: 아이디 중복 확인 + 비밀번호 확인을 입력하는 즉시 보여 줌
// (자바스크립트가 없어도 서버가 같은 검사를 하므로, 이 파일은 '바로 알려 주는' 역할)
(() => {
  const form = document.getElementById('signupForm');
  const user = document.getElementById('username');
  const checkBtn = document.getElementById('checkBtn');
  const userStatus = document.getElementById('username-status');
  const pw = document.getElementById('password');
  const pw2 = document.getElementById('password2');
  const pwStatus = document.getElementById('pw-status');

  const setStatus = (el, state, text) => {
    el.className = 'status' + (state ? ' ' + state : '');
    el.textContent = text;
  };
  const markInvalid = (input, bad) => {
    if (bad) input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
  };

  // ---------- 아이디 중복 확인 ----------
  // 서버가 '사용 가능'이라고 한 아이디 (화면을 다시 그렸을 때 이미 확인된 상태면 그대로 이어감)
  let checkedName = userStatus.classList.contains('good') ? user.value.trim().toLowerCase() : null;

  user.addEventListener('input', () => {
    const v = user.value.trim().toLowerCase();
    if (checkedName !== null && v === checkedName) {
      setStatus(userStatus, 'good', '✓ 사용할 수 있는 아이디예요.');
    } else {
      checkedName = null;
      setStatus(userStatus, '', v ? '아이디 중복 확인을 눌러 주세요.' : '');
    }
    markInvalid(user, false);
  });

  async function checkUsername() {
    const v = user.value.trim().toLowerCase();
    user.value = v;
    if (!v) {
      setStatus(userStatus, 'bad', '✕ 아이디를 입력해 주세요.');
      user.focus();
      return;
    }
    checkBtn.disabled = true;
    setStatus(userStatus, '', '확인하는 중…');
    try {
      const body = new URLSearchParams({ username: v, csrf: form.csrf.value });
      const res = await fetch('check_username.php', { method: 'POST', body, credentials: 'same-origin' });
      const r = await res.json();
      // 응답을 기다리는 사이 아이디를 바꿨으면 무시
      if (user.value.trim().toLowerCase() !== v) return;
      checkedName = r.ok ? v : null;
      setStatus(userStatus, r.ok ? 'good' : 'bad', (r.ok ? '✓ ' : '✕ ') + r.message);
      markInvalid(user, !r.ok);
    } catch {
      setStatus(userStatus, 'bad', '✕ 확인하지 못했어요. 페이지를 새로고침한 뒤 다시 시도해 주세요.');
    } finally {
      checkBtn.disabled = false;
    }
  }

  checkBtn.addEventListener('click', (e) => { e.preventDefault(); checkUsername(); });
  // 아이디 칸에서 Enter를 누르면 가입이 아니라 중복 확인
  user.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); checkUsername(); }
  });

  // ---------- 비밀번호 확인: 다르면 바로 빨간색 (SNS 가입 화면에는 비밀번호 칸이 없음) ----------
  function checkPasswords() {
    if (!pw || !pw2) return true;
    if (!pw2.value) {
      setStatus(pwStatus, '', '');
      markInvalid(pw2, false);
      return true;
    }
    const same = pw.value === pw2.value;
    setStatus(pwStatus, same ? 'good' : 'bad', same ? '✓ 비밀번호가 일치해요.' : '✕ 비밀번호가 일치하지 않아요.');
    markInvalid(pw2, !same);
    return same;
  }
  if (pw && pw2) {
    pw.addEventListener('input', checkPasswords);
    pw2.addEventListener('input', checkPasswords);
  }

  // ---------- 가입 버튼: 확인을 다 통과했을 때만 보냄 ----------
  form.addEventListener('submit', (e) => {
    const action = e.submitter && e.submitter.value;
    if (action === 'check') return; // 자바스크립트가 처리하므로 여기 오지 않지만 안전하게
    const v = user.value.trim().toLowerCase();
    if (checkedName === null || v !== checkedName) {
      e.preventDefault();
      setStatus(userStatus, 'bad', '✕ 아이디 중복 확인을 해 주세요.');
      markInvalid(user, true);
      user.focus();
      return;
    }
    if (pw2 && (!pw2.value || !checkPasswords())) {
      e.preventDefault();
      if (!pw2.value) setStatus(pwStatus, 'bad', '✕ 비밀번호를 한 번 더 입력해 주세요.');
      markInvalid(pw2, true);
      pw2.focus();
    }
  });

  // 서버에서 돌아온 화면에 비밀번호 확인 칸이 비어 있으면 상태 문구도 비움
  checkPasswords();
})();

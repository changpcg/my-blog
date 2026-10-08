'use strict';

const $ = (s, el = document) => el.querySelector(s);
const main = $('#main');
let blog = null; // 사이트 정보 + 로그인한 사용자(blog.user)
let cur = null; // 지금 보고 있는 블로그 (블로그 홈에서는 null)

// ---------- 유틸 ----------
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const enc = encodeURIComponent;

function fmtDate(iso, withTime = false) {
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, '0');
  const s = `${d.getFullYear()}. ${p(d.getMonth() + 1)}. ${p(d.getDate())}.`;
  return withTime ? `${s} ${p(d.getHours())}:${p(d.getMinutes())}` : s;
}

function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove('show'), 2200);
}

async function api(path, opts = {}) {
  const res = await fetch('/api/' + path, {
    method: opts.method || 'GET',
    headers: opts.body ? { 'Content-Type': 'application/json' } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    credentials: 'same-origin',
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || '요청에 실패했습니다.');
  return data;
}

marked.setOptions({ gfm: true, breaks: true });
const IMAGE_MIME = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
const FILE_ACCEPT = '.pdf,.txt,.csv,.md,.json,.zip,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.hwp,.hwpx,.key,.mp3,.mp4';
const FILE_ICON = { pdf: '📕', zip: '🗜', hwp: '📘', hwpx: '📘', doc: '📘', docx: '📘', xls: '📗', xlsx: '📗', csv: '📗',
  ppt: '📙', pptx: '📙', key: '📙', mp3: '🎵', mp4: '🎬' };
// 마크다운 링크를 깨뜨리는 괄호를 비슷한 모양의 글자로 바꿈
const mdSafe = (s) => String(s).replace(/\[/g, '［').replace(/\]/g, '］').replace(/\(/g, '（').replace(/\)/g, '）');
const fmtSize = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + 'MB' : Math.max(1, Math.round(n / 1024)) + 'KB');

// 004: 코드 블록 위에 보여 줄 언어 이름 (글쓴이가 ```python 처럼 적은 것만, 없으면 '코드')
const CODE_LANG = {
  js: 'JavaScript', javascript: 'JavaScript', jsx: 'JSX', ts: 'TypeScript', typescript: 'TypeScript', tsx: 'TSX',
  py: 'Python', python: 'Python', sh: 'Shell', shell: 'Shell', bash: 'Bash', zsh: 'Shell', console: '터미널',
  html: 'HTML', xml: 'XML', css: 'CSS', scss: 'SCSS', json: 'JSON', yaml: 'YAML', yml: 'YAML', toml: 'TOML', ini: 'INI',
  sql: 'SQL', java: 'Java', kotlin: 'Kotlin', kt: 'Kotlin', swift: 'Swift', go: 'Go', rust: 'Rust', rs: 'Rust',
  php: 'PHP', ruby: 'Ruby', rb: 'Ruby', c: 'C', cpp: 'C++', 'c++': 'C++', cs: 'C#', csharp: 'C#', r: 'R', dart: 'Dart',
  md: 'Markdown', markdown: 'Markdown', diff: 'Diff', dockerfile: 'Dockerfile', nginx: 'Nginx',
  text: '텍스트', txt: '텍스트', plaintext: '텍스트',
};

// 본문 HTML 정리 규칙: 글 속 id·name은 'user-content-'를 붙여 화면의 id(#likeBtn·#comments 등)와 겹치지 않게,
// data-* 속성은 없앰(화면 버튼 연결에 쓰는 data-nb 등을 흉내 내지 못하게)
const PURIFY = { SANITIZE_NAMED_PROPS: true, ALLOW_DATA_ATTR: false };

function renderMd(md) {
  const html = DOMPurify.sanitize(marked.parse(md || ''), PURIFY);
  const box = document.createElement('div');
  box.innerHTML = html;
  // 글쓴이가 붙인 class는 지움(코드 언어 표시 language-* 만 남김) — 화면 부품(.code-copy·.img-zoom 등)을 흉내 내지 못하게
  box.querySelectorAll('[class]').forEach((el) => {
    const keep = el.tagName === 'CODE' ? [...el.classList].filter((c) => /^language-[\w+#.-]+$/.test(c)) : [];
    if (keep.length) el.className = keep.join(' ');
    else el.removeAttribute('class');
  });
  box.querySelectorAll('pre > code').forEach((code) => {
    const pre = code.parentElement;
    // 숨긴 코드를 복사하게 만들 수 없도록 코드 칸의 style·hidden은 지움
    [pre, code].forEach((el) => { el.removeAttribute('style'); el.removeAttribute('hidden'); });
    const m = /(?:^|\s)language-([\w+#.-]+)/.exec(code.className);
    const raw = m ? m[1] : '';
    if (window.hljs) hljs.highlightElement(code);
    const wrap = document.createElement('div');
    wrap.className = 'code-block';
    const head = document.createElement('div');
    head.className = 'code-head';
    const lang = document.createElement('span');
    lang.className = 'code-lang';
    const key = raw.toLowerCase();
    lang.textContent = raw ? (Object.prototype.hasOwnProperty.call(CODE_LANG, key) ? CODE_LANG[key] : raw) : '코드';
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'code-copy';
    copy.textContent = '복사';
    copy.setAttribute('aria-label', `${lang.textContent} 코드 복사`);
    head.append(lang, copy);
    pre.replaceWith(wrap);
    wrap.append(head, pre);
  });
  box.querySelectorAll('img').forEach((img) => {
    img.loading = 'lazy';
    img.decoding = 'async';
    if (img.closest('a')) return; // 링크가 걸린 사진은 링크 그대로
    const zoom = document.createElement('button');
    zoom.type = 'button';
    zoom.className = 'img-zoom';
    zoom.setAttribute('aria-label', img.alt ? `사진 크게 보기: ${img.alt}` : '사진 크게 보기');
    img.replaceWith(zoom);
    zoom.appendChild(img);
  });
  box.querySelectorAll('a[href^="http"]').forEach((a) => { a.target = '_blank'; a.rel = 'noopener'; });
  // 첨부 파일 링크 → 파일 카드
  box.querySelectorAll('a[href^="/uploads/"]').forEach((a) => {
    const ext = a.getAttribute('href').split('.').pop().toLowerCase();
    const m = a.textContent.replace(/^📎\s*/, '').match(/^(.*?)\s*\(([\d.]+\s*[KM]B)\)$/);
    a.className = 'file-link';
    a.setAttribute('download', '');
    a.innerHTML = `<span class="file-icon" aria-hidden="true">${FILE_ICON[ext] || '📄'}</span>
      <span class="file-info"><b>${esc(m ? m[1] : a.textContent)}</b><small>${ext.toUpperCase()}${m ? ' · ' + m[2] : ''}</small></span>
      <span class="file-down" aria-hidden="true">↓</span>`;
  });
  return box.innerHTML;
}

// 프로필 사진 (없으면 닉네임 첫 글자)
const avatarOf = (who, cls = '') => (who && who.avatar
  ? `<img class="avatar ${cls}" src="${esc(who.avatar)}" alt="">`
  : `<div class="avatar ${cls}" aria-hidden="true">${esc(((who && who.nickname) || '?').slice(0, 1))}</div>`);

// ---------- 글 종류 ----------
const TYPE_ICON = { insight: '💡', faq: '❓', glossary: '📖', daily: '☕️' };
const TYPE_INTRO = {
  insight: '생각과 분석을 담은 글',
  faq: '자주 받는 질문을 모았어요. 질문을 누르면 답변이 열려요.',
  glossary: '헷갈리는 용어를 쉽게 풀어 정리했어요.',
  daily: '소소한 일상 기록',
};
const typeName = (k) => blog.types.find((t) => t.key === k)?.name || '';
const catName = (c) => c || '미분류';
const blogHref = (username, params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
  return `#/@${username}${[...qs].length ? '?' + qs : ''}`;
};

// ---------- 006 블로그 꾸미기 ----------
// 대표 색 (값은 style.css의 [data-skin]) · 끌 수 있는 사이드바·배너 항목 (서버 SKINS·WIDGET_KEYS와 같음)
const SKINS = { coral: '코랄', blue: '파랑', green: '초록', teal: '청록', purple: '보라', pink: '분홍', mustard: '겨자', ink: '먹색' };
const WIDGETS = [
  ['room', '미니룸', '블로그 맨 위 그림'], ['types', '글 종류', '사이드바의 종류별 글 수'], ['popular', '인기 글', '조회수 많은 공개 글 5개'],
  ['tags', '태그', '많이 쓴 태그'], ['comments', '최근 댓글', '최근 댓글 5개'], ['stats', '방문자 수', 'Total·Today·Yesterday'],
];
const hasSkin = (k) => typeof k === 'string' && Object.prototype.hasOwnProperty.call(SKINS, k);
// 블로그 화면·글 화면에만 그 블로그 색 (코랄·모르는 값이면 기본색)
function setSkin(name) {
  const root = document.documentElement;
  if (hasSkin(name) && name !== 'coral') root.dataset.skin = name;
  else delete root.dataset.skin;
}
const shown = (b, key) => !(b.hidden_widgets || []).includes(key);

// 인기 글 목록 (블로그 홈은 블로그 이름도)
const popularHtml = (list, withBlog) => (list && list.length ? `
    <section class="side-box popular">
      <h2 class="side-title">인기 글</h2>
      <ol class="pop-list">${list.map((p, i) => `
        <li><a href="#/post/${p.id}">
          <span class="pop-n" aria-hidden="true">${i + 1}</span>
          <span class="pop-t"><b>${esc(p.title)}</b><small>${withBlog ? `${esc(p.blog_title)} · ` : ''}조회 ${p.views.toLocaleString()}</small></span>
          ${p.thumbnail ? `<img class="pop-thumb" src="${esc(p.thumbnail)}" alt="" width="48" height="48" loading="lazy" decoding="async">` : ''}
        </a></li>`).join('')}</ol>
    </section>` : '');

// 회원가입·로그인은 PHP 회원 페이지에서. 끝나면 #/sso 로 돌아옴
const authLink = (page) => `${blog.auth_url}/${page}.php?return=blog`;
function goAuth(page) {
  try { if (!sessionStorage.getItem('afterLogin')) sessionStorage.setItem('afterLogin', location.hash || '#/'); } catch { /* 무시 */ }
  location.href = authLink(page);
}

// ---------- 공통 레이아웃 ----------
async function loadBlog() {
  blog = await api('blog');
  $('#blogTitle').textContent = blog.blog_title;
  $('#footer').innerHTML = `© ${new Date().getFullYear()} ${esc(blog.blog_title)}`;
  document.body.classList.toggle('logged-in', !!blog.user);
  const u = blog.user;
  $('#topActions').innerHTML = u
    ? `<a class="btn primary" href="#/write">글쓰기</a>
      <details class="user-menu">
        <summary class="btn me-btn" title="내 메뉴">${avatarOf(u, 'mini')}<span>${esc(u.nickname)}</span></summary>
        <div class="menu card">
          <a href="#/@${esc(u.username)}">🏠 내 블로그</a>
          <a href="#/neighbors">👥 이웃 새 글</a>
          <a href="#/manage">🛠 블로그 관리</a>
          <a href="#/me">👤 내 정보</a>
          ${blog.is_admin ? '<a href="#/settings">⚙️ 사이트 설정</a>' : ''}
          <button type="button" id="logoutBtn">로그아웃</button>
        </div>
      </details>`
    : `<a class="btn" href="#/login">로그인</a>${blog.allow_signup ? `<a class="btn primary" href="${esc(authLink('register'))}">회원가입</a>` : ''}`;
  const lo = $('#logoutBtn');
  if (lo) lo.onclick = logout;
  // 위젯(관심 종목 등)이 로그인 상태 변화를 알 수 있게
  window.dispatchEvent(new CustomEvent('blog:user', { detail: blog.user }));
}

// 로그아웃: 블로그를 로그아웃한 뒤 회원 페이지(PHP)도 거쳐서 함께 로그아웃하고 블로그 홈으로 돌아옴
async function logout() {
  // 쓰던 글이 있으면 먼저 묻고, 나가기로 하면 다시 묻지 않게 경고를 끔
  if (leaveGuard) {
    if (!leaveGuard()) return;
    leaveGuard = null;
  }
  const r = await api('logout', { method: 'POST' });
  if (r.auth_logout && await reachable(r.auth_url)) {
    try { sessionStorage.setItem('justLoggedOut', '1'); } catch { /* 무시 */ }
    // 로그아웃 표는 주소가 아니라 POST 폼으로 보냄 (회원 서버가 확인 후 블로그 홈으로 돌려보냄)
    const f = document.createElement('form');
    f.method = 'post';
    f.action = r.auth_logout.action;
    f.hidden = true;
    const t = document.createElement('input');
    t.type = 'hidden';
    t.name = 't';
    t.value = r.auth_logout.t;
    f.appendChild(t);
    document.body.appendChild(f);
    f.submit();
    return;
  }
  // 회원 서버가 꺼져 있으면 블로그만 로그아웃
  await loadBlog();
  toast('로그아웃했습니다.');
  location.hash = '#/';
  render();
}

// 회원 서버가 켜져 있는지 (1.5초 안에 응답하면 켜짐)
async function reachable(url) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 1500);
  try {
    await fetch(url + '/login.php', { mode: 'no-cors', signal: ctl.signal, credentials: 'omit' });
    return true;
  } catch { return false; } finally { clearTimeout(timer); }
}

// 메뉴 밖을 누르거나 메뉴 항목을 누르면 닫기
document.addEventListener('click', (e) => {
  const m = $('.user-menu');
  if (m && m.open && (!m.contains(e.target) || e.target.closest('.menu a'))) m.open = false;
});

function renderTypeNav(active) {
  $('#typeNav').innerHTML = [{ key: '', name: '블로그 홈' }, ...blog.types]
    .map((t) => `<a href="#/${t.key}" class="${active !== null && (active || '') === t.key ? 'on' : ''}">${t.key ? TYPE_ICON[t.key] + ' ' : '🏠 '}${esc(t.name)}</a>`)
    .join('') + (blog.user ? `<a href="#/neighbors" class="${active === 'neighbors' ? 'on' : ''}">👥 이웃 새 글</a>` : '')
    + `<a href="#/food" class="nav-food ${active === 'food' ? 'on' : ''}">🍽 맛집</a>`;
}

// 블로그 홈 사이드바: 내 블로그 바로가기 + 사이트 전체 태그·댓글·방문자
function renderPortalSidebar() {
  const u = blog.user;
  const s = blog.stats;
  $('#sidebar').innerHTML = `
    <section class="side-box my-blog">
      ${u ? `
        ${avatarOf(u)}
        <a class="nick" href="#/@${esc(u.username)}">${esc(u.blog_title)}</a>
        <div class="desc">${esc(u.nickname)}님의 블로그</div>
        <div class="my-blog-actions">
          <a class="btn small primary" href="#/write">글쓰기</a>
          <a class="btn small" href="#/@${esc(u.username)}">내 블로그</a>
          <a class="btn small" href="#/manage">관리</a>
        </div>`
      : `
        <div class="avatar" aria-hidden="true">✍️</div>
        <div class="nick">나만의 블로그를 시작해 보세요</div>
        <div class="desc">가입하면 바로 내 블로그가 생겨요.</div>
        <div class="my-blog-actions">
          ${blog.allow_signup ? `<a class="btn small primary" href="${esc(authLink('register'))}">회원가입</a>` : ''}
          <a class="btn small" href="#/login">로그인</a>
        </div>`}
    </section>
    ${popularHtml(blog.popular, true)}
    ${blog.tags.length ? `
    <section class="side-box">
      <h2 class="side-title">인기 태그</h2>
      <div class="tag-cloud">${blog.tags.map((t) => `<a class="tag" href="#/tag/${enc(t.name)}">#${esc(t.name)}</a>`).join('')}</div>
    </section>` : ''}
    ${blog.recent_comments.length ? `
    <section class="side-box recent-c">
      <h2 class="side-title">최근 댓글</h2>
      ${blog.recent_comments.map((c) => `<a href="#/post/${c.post_id}">${esc(c.content)} <span class="count">· ${esc(c.name)}</span></a>`).join('')}
    </section>` : ''}
    <section class="side-box">
      <h2 class="side-title">전체 방문자</h2>
      ${statsHtml(s)}
    </section>`;
}

const statsHtml = (s) => `
  <div class="stats">
    <div><b>${s.total.toLocaleString()}</b><span>Total</span></div>
    <div><b>${s.today.toLocaleString()}</b><span>Today</span></div>
    <div><b>${s.yesterday.toLocaleString()}</b><span>Yesterday</span></div>
  </div>`;

// 블로그 사이드바: 그 블로그의 프로필·카테고리·글 종류·태그·댓글·방문자
function renderBlogSidebar(b, activeCat, activeType) {
  $('#sidebar').innerHTML = `
    <section class="side-box profile">
      ${avatarOf(b)}
      <div class="nick">${esc(b.nickname)}</div>
      <div class="desc">${esc(b.blog_desc)}</div>
      ${b.is_owner ? `<div class="my-blog-actions">
        <a class="btn small primary" href="#/write">글쓰기</a><a class="btn small" href="#/manage">관리</a></div>` : ''}
    </section>
    <section class="side-box">
      <h2 class="side-title">카테고리</h2>
      <ul class="cat-list">
        <li><a class="all" href="${blogHref(b.username, { type: activeType })}">전체보기 <span class="count">(${b.total_posts})</span></a></li>
        ${b.category_counts.map((c) => `
          <li><a href="${blogHref(b.username, { type: activeType, category: c.name || '-' })}" class="${activeCat === (c.name || '-') ? 'on' : ''}">
            ${esc(catName(c.name))} <span class="count">(${c.count})</span></a></li>`).join('')}
      </ul>
      ${b.is_owner ? '<a class="side-edit" href="#/manage/categories">카테고리 편집</a>' : ''}
    </section>
    ${shown(b, 'types') ? `
    <section class="side-box">
      <h2 class="side-title">글 종류</h2>
      <ul class="cat-list">
        ${b.type_counts.map((t) => `
          <li><a href="${blogHref(b.username, { type: t.key, category: activeCat })}" class="${activeType === t.key ? 'on' : ''}">
            ${TYPE_ICON[t.key]} ${esc(t.name)} <span class="count">(${t.count})</span></a></li>`).join('')}
      </ul>
    </section>` : ''}
    ${shown(b, 'popular') ? popularHtml(b.popular, false) : ''}
    ${shown(b, 'tags') && b.tags && b.tags.length ? `
    <section class="side-box">
      <h2 class="side-title">태그</h2>
      <div class="tag-cloud">${b.tags.map((t) => `<a class="tag" href="${blogHref(b.username, { tag: t.name })}">#${esc(t.name)}</a>`).join('')}</div>
    </section>` : ''}
    ${shown(b, 'comments') && b.recent_comments && b.recent_comments.length ? `
    <section class="side-box recent-c">
      <h2 class="side-title">최근 댓글</h2>
      ${b.recent_comments.map((c) => `<a href="#/post/${c.post_id}">${esc(c.content)} <span class="count">· ${esc(c.name)}</span></a>`).join('')}
    </section>` : ''}
    ${shown(b, 'stats') && b.stats ? `
    <section class="side-box">
      <h2 class="side-title">방문자</h2>
      ${statsHtml(b.stats)}
    </section>` : ''}`;
}

// 블로그 위쪽 배너 (블로그 이름·주인·소개)
const blogBanner = (b, small = false) => {
  const room = !small && shown(b, 'room');
  return `
  <header class="blog-banner card ${small ? 'small' : room ? 'has-room' : ''}">
    ${room ? `<div class="banner-room">${miniroomSvg(b.room_bg, b.room_char)}
      ${b.is_owner ? '<a class="room-edit" href="#/manage/room">미니룸 꾸미기</a>' : ''}</div>` : ''}
    <div class="banner-row">
    <a class="banner-avatar" href="#/@${esc(b.username)}">${avatarOf(b)}</a>
    <div class="banner-text">
      <a class="banner-title" href="#/@${esc(b.username)}">${esc(b.blog_title)}</a>
      <div class="banner-meta">${esc(b.nickname)} · 글 ${b.total_posts}개 · 이웃 <span class="nb-count">${b.neighbor_count || 0}</span>명</div>
      ${!small && b.blog_desc ? `<p class="banner-desc">${esc(b.blog_desc)}</p>` : ''}
    </div>
    ${b.is_owner && !small ? `<div class="banner-actions">
      <a class="btn small primary" href="#/write">글쓰기</a><a class="btn small" href="#/manage">관리</a></div>` : ''}
    ${!b.is_owner ? `<div class="banner-actions">${neighborBtn(b)}</div>` : ''}
    </div>
  </header>`;
};

// 이웃 추가·취소 버튼 (배너가 그려진 뒤 연결)
function bindNeighborButtons(b) {
  document.querySelectorAll('[data-nb]').forEach((btn) => (btn.onclick = async () => {
    if (!blog.user) { needLogin('이웃을 추가하려면 로그인하세요.'); return; }
    btn.disabled = true;
    try {
      const r = await api('neighbors/' + enc(btn.dataset.nb), { method: 'POST' });
      b.is_neighbor = r.is_neighbor;
      b.neighbor_count = r.count;
      document.querySelectorAll(`[data-nb="${btn.dataset.nb}"]`).forEach((x) => {
        x.classList.toggle('on', r.is_neighbor);
        x.setAttribute('aria-pressed', r.is_neighbor);
        x.textContent = r.is_neighbor ? '✓ 이웃' : '+ 이웃 추가';
      });
      document.querySelectorAll('.nb-count').forEach((x) => (x.textContent = r.count));
      toast(r.is_neighbor ? `${b.blog_title}을(를) 이웃으로 추가했어요.` : '이웃을 취소했어요.');
    } catch (err) { toast(err.message); } finally { btn.disabled = false; }
  }));
}

// 종류·카테고리 표시 (목록, 상세 공통)
const postLabels = (p) => `
  <span class="type-badge t-${p.type}">${TYPE_ICON[p.type]} ${esc(typeName(p.type))}</span>
  ${p.category ? `<span class="cat-badge">${esc(p.category)}</span>` : ''}`;

// 한글 초성 / 영문 첫 글자로 묶기
const CHOSUNG = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const CHO_MERGE = { 'ㄲ': 'ㄱ', 'ㄸ': 'ㄷ', 'ㅃ': 'ㅂ', 'ㅆ': 'ㅅ', 'ㅉ': 'ㅈ' };
function initialOf(word) {
  const ch = (word || '').trim().charAt(0);
  const code = ch.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) {
    const c = CHOSUNG[Math.floor((code - 0xac00) / 588)];
    return CHO_MERGE[c] || c;
  }
  if (/[a-z]/i.test(ch)) return ch.toUpperCase();
  return '#';
}
const initialRank = (k) => (/[ㄱ-ㅎ]/.test(k) ? 0 : /[A-Z]/.test(k) ? 1 : 2);

// 글 목록 한 줄 (004): 종류·카테고리 → 제목 → 요약 → 블로그·날짜·댓글·조회·공감, 오른쪽에 대표 사진(있으면)
const postRowHtml = (p, showBlog = true) => `
  <a class="post-row ${p.thumbnail ? 'has-thumb' : ''}" href="#/post/${p.id}">
    <div class="post-text">
      <div class="labels">${postLabels(p)}</div>
      <h2 class="post-title">${p.is_public ? '' : '<span class="badge">비공개</span>'}${esc(p.title)}</h2>
      ${p.excerpt ? `<p class="post-excerpt">${esc(p.excerpt)}</p>` : ''}
    </div>
    <div class="meta post-meta">
      ${showBlog ? `<span class="card-blog">${avatarOf({ avatar: p.author_avatar, nickname: p.author_nickname }, 'mini')}${esc(p.author_blog_title || p.author_nickname || '')}</span>` : ''}
      <span>${fmtDate(p.created_at)}</span><span>댓글 ${p.comment_count}</span><span>조회 ${p.views}</span>${p.like_count ? `<span class="like-n">♥ ${p.like_count}</span>` : ''}</div>
    ${p.thumbnail ? `<img class="post-thumb" src="${esc(p.thumbnail)}" alt="" width="120" height="120" loading="lazy" decoding="async">` : ''}
  </a>`;

function faqHtml(posts) {
  return `<div class="faq-list">${posts.map((p) => `
    <details class="card faq">
      <summary><span class="q">Q</span><span class="faq-title">${p.is_public ? '' : '<span class="badge">비공개</span>'}${esc(p.title)}</span>
        ${p.category ? `<span class="cat-badge">${esc(p.category)}</span>` : ''}</summary>
      <div class="faq-answer"><span class="a">A</span>
        <div><div class="content">${renderMd(p.content)}</div>
        <a class="link" href="#/post/${p.id}">자세히 보기 · ${esc(p.author_nickname || '')} · 댓글 ${p.comment_count} →</a></div>
      </div>
    </details>`).join('')}</div>`;
}

function glossaryHtml(posts) {
  const groups = {};
  posts.forEach((p) => (groups[initialOf(p.title)] ||= []).push(p));
  const keys = Object.keys(groups).sort((a, b) => initialRank(a) - initialRank(b) || a.localeCompare(b, 'ko'));
  return `
    <nav class="index-bar">${keys.map((k) => `<a href="#g-${enc(k)}" data-jump="g-${enc(k)}">${esc(k)}</a>`).join('')}</nav>
    ${keys.map((k) => `
      <section class="g-group" id="g-${enc(k)}">
        <h2 class="g-key">${esc(k)}</h2>
        <div class="g-grid">${groups[k].map((p) => `
          <a class="card g-card" href="#/post/${p.id}">
            <b>${p.is_public ? '' : '<span class="badge">비공개</span>'}${esc(p.title)}</b>
            <p>${esc(p.excerpt)}</p>
            ${p.category ? `<span class="cat-badge">${esc(p.category)}</span>` : ''}
          </a>`).join('')}</div>
      </section>`).join('')}`;
}

// 용어 사전 색인 클릭: 해시 주소를 바꾸지 않고 스크롤만
const plainClick = (e) => e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-jump]');
  if (!a || !plainClick(e)) return;
  e.preventDefault();
  jumpTo(document.getElementById(a.dataset.jump));
});

// 글 목록 가져오기 (종류에 따라 FAQ·용어 사전은 한 번에)
async function fetchPosts(params, type) {
  const p = new URLSearchParams(params);
  if (type) p.set('type', type);
  if (type === 'faq') { p.set('size', 200); p.set('full', 1); }
  if (type === 'glossary') { p.set('size', 200); p.set('sort', 'title'); }
  return api('posts?' + p);
}

function postsBody(data, type, showBlog, emptyHtml) {
  if (!data.posts.length) return emptyHtml;
  if (type === 'faq') return faqHtml(data.posts);
  if (type === 'glossary') return glossaryHtml(data.posts);
  return `<div class="post-list">${data.posts.map((p) => postRowHtml(p, showBlog)).join('')}</div>`;
}

function pagerHtml(data) {
  if (data.pages <= 1) return '';
  const [base, query] = location.hash.split('?');
  const href = (n) => { const u = new URLSearchParams(query); u.set('page', n); return `${base || '#/'}?${u}`; };
  return `<nav class="pager">${Array.from({ length: data.pages }, (_, i) =>
    `<a href="${href(i + 1)}" class="${i + 1 === data.page ? 'on' : ''}">${i + 1}</a>`).join('')}</nav>`;
}

// ---------- 블로그 홈 (모든 블로그의 새 글) ----------
async function renderPortal({ type, tag, q, page = 1 }) {
  const seq = routeSeq;
  cur = null;
  const params = { page };
  if (tag) params.tag = tag;
  if (q) params.q = q;
  const showBlogs = !type && !tag && !q && Number(page) === 1;
  const [data, blogs] = await Promise.all([fetchPosts(params, type), showBlogs ? api('blogs?size=12') : null]);
  if (seq !== routeSeq) return; // 그사이 다른 화면으로 이동함
  const heading = tag ? `#${esc(tag)}` : q ? `'${esc(q)}' 검색 결과` : type ? `${TYPE_ICON[type]} ${esc(typeName(type))}` : '새로 올라온 글';
  main.innerHTML = `
    ${showBlogs ? `
      <section class="hero card">
        <h1>${esc(blog.blog_title)}</h1>
        <p>${esc(blog.blog_desc || '여러 사람의 블로그가 모인 곳이에요.')}</p>
        ${blog.user ? `<a class="btn primary" href="#/@${esc(blog.user.username)}">내 블로그로 가기 →</a>`
          : blog.allow_signup ? `<a class="btn primary" href="${esc(authLink('register'))}">가입하고 내 블로그 만들기 →</a>` : ''}
      </section>
      ${blogs && blogs.length ? `
      <section class="blog-strip">
        <h2 class="side-title">블로그 둘러보기</h2>
        <div class="strip">${blogs.map((b) => `
          <a class="card strip-item" href="#/@${esc(b.username)}">
            ${avatarOf(b)}<b>${esc(b.blog_title)}</b><small>${esc(b.nickname)} · 글 ${b.post_count}</small>
          </a>`).join('')}</div>
      </section>` : ''}` : ''}
    <div class="list-head"><h1>${heading}</h1><span class="count">${data.total}</span></div>
    ${type ? `<p class="intro">${TYPE_INTRO[type]}</p>` : ''}
    ${postsBody(data, type, true, '<div class="empty">아직 글이 없어요.</div>')}
    ${pagerHtml(data)}`;
  renderTypeNav(tag || q ? null : type || '');
  renderPortalSidebar();
}

// ---------- 이웃 새 글 ----------
async function renderNeighbors(page = 1) {
  const seq = routeSeq;
  cur = null;
  if (!blog.user) { needLogin('이웃 새 글은 로그인하면 볼 수 있어요.'); return; }
  const [list, data] = await Promise.all([api('neighbors'), api(`posts?neighbors=1&page=${page}`)]);
  if (seq !== routeSeq) return;
  main.innerHTML = `
    <div class="list-head"><h1>👥 이웃 새 글</h1><span class="count">${data.total}</span></div>
    ${list.length ? `
      <section class="blog-strip">
        <h2 class="side-title">내 이웃 ${list.length}</h2>
        <div class="strip">${list.map((b) => `
          <div class="card strip-item">
            <a href="#/@${esc(b.username)}" class="strip-link">${avatarOf(b)}<b>${esc(b.blog_title)}</b><small>${esc(b.nickname)} · 글 ${b.post_count}</small></a>
            <button type="button" class="btn small nb-btn on" data-nb="${esc(b.username)}">✓ 이웃</button>
          </div>`).join('')}</div>
      </section>
      ${postsBody(data, null, true, '<div class="empty">이웃이 아직 글을 쓰지 않았어요.</div>')}
      ${pagerHtml(data)}`
      : `<div class="empty">아직 이웃이 없어요.<br>마음에 드는 블로그에서 <b>+ 이웃 추가</b>를 눌러 보세요.
          <br><a class="link" href="#/">블로그 둘러보기 →</a></div>`}`;
  // 여기서 이웃을 취소하면 목록을 새로 그림
  main.querySelectorAll('[data-nb]').forEach((btn) => (btn.onclick = async () => {
    if (!confirm('이웃을 취소할까요?')) return;
    try {
      await api('neighbors/' + enc(btn.dataset.nb), { method: 'POST' });
      toast('이웃을 취소했어요.');
      renderNeighbors(page);
    } catch (err) { toast(err.message); }
  }));
  renderTypeNav('neighbors');
  renderPortalSidebar();
}

// ---------- 한 사람의 블로그 ----------
async function loadCur(username, visit = false) {
  if (!cur || cur.username !== username || visit) cur = await api(`blogs/${enc(username)}${visit ? '?visit=1' : ''}`);
  return cur;
}

async function renderBlog(username, { type, category, tag, q, page = 1 }) {
  const seq = routeSeq;
  const b = await loadCur(username, Number(page) === 1 && !type && !category && !tag && !q);
  const params = { page, blog: b.username };
  if (category) params.category = category; // '-'는 미분류
  if (tag) params.tag = tag;
  if (q) params.q = q;
  const data = await fetchPosts(params, type);
  if (seq !== routeSeq) return; // 그사이 다른 화면으로 이동함 (늦게 온 블로그는 그리지도, 색을 입히지도 않음)
  document.title = b.blog_title;
  setSkin(b.skin);
  const heading = tag ? `#${esc(tag)}` : q ? `'${esc(q)}' 검색 결과`
    : category ? esc(catName(category === '-' ? '' : category)) : '전체 글';
  const empty = `<div class="empty">아직 글이 없어요.${b.is_owner ? ` <a class="link" href="#/write${type ? '?type=' + type : ''}">첫 글 쓰기 →</a>` : ''}</div>`;
  main.innerHTML = `
    ${blogBanner(b)}
    <nav class="chips blog-tabs" aria-label="글 종류">
      <a href="${blogHref(b.username, { category })}" class="chip ${!type ? 'on' : ''}">전체</a>
      ${b.type_counts.map((t) => `<a href="${blogHref(b.username, { type: t.key, category })}" class="chip ${type === t.key ? 'on' : ''}">${TYPE_ICON[t.key]} ${esc(t.name)} <small>${t.count}</small></a>`).join('')}
    </nav>
    <div class="list-head"><h1>${heading}</h1><span class="count">${data.total}</span></div>
    ${postsBody(data, type, false, empty)}
    ${pagerHtml(data)}`;
  bindNeighborButtons(b);
  renderTypeNav(null);
  renderBlogSidebar(b, category, type);
}

// ---------- 글 상세 ----------
const SHARE_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/></svg>';

// 이웃 추가 버튼 (배너·작성자 카드 공통, bindNeighborButtons가 연결)
const neighborBtn = (b) => `<button type="button" class="btn small nb-btn ${b.is_neighbor ? 'on' : ''}" data-nb="${esc(b.username)}" aria-pressed="${!!b.is_neighbor}">${b.is_neighbor ? '✓ 이웃' : '+ 이웃 추가'}</button>`;

async function renderPost(id) {
  const seq = routeSeq;
  const p = await api('posts/' + id);
  const b = await loadCur(p.author_username);
  if (seq !== routeSeq) return; // 그사이 다른 화면으로 이동함
  setSkin(b.skin);
  document.title = `${p.title} - ${b.blog_title}`;
  const isFaq = p.type === 'faq';
  main.innerHTML = `
    ${blogBanner(b, true)}
    <article class="article t-${p.type}">
      <header class="article-head">
        <div class="labels">
          <a href="${blogHref(b.username, { type: p.type })}">${postLabels(p)}</a>
        </div>
        <h1 tabindex="-1">${isFaq ? '<span class="q">Q</span>' : ''}${p.is_public ? '' : '<span class="badge">비공개</span>'}${esc(p.title)}</h1>
        <div class="row">
          <div class="meta"><a class="author-link" href="#/@${esc(b.username)}">${esc(p.author_nickname || '알 수 없음')}</a><span>${fmtDate(p.created_at, true)}</span><span>조회 ${p.views}</span><span class="read-time" id="readTime"></span></div>
          ${p.can_edit ? `<div class="admin-tools">
            <a class="btn small" href="#/edit/${p.id}">수정</a>
            <button class="btn small danger" id="delPost">삭제</button></div>` : ''}
        </div>
      </header>
      ${isFaq ? '<div class="answer-label"><span class="a">A</span> 답변</div>' : ''}
      <details class="toc" id="toc"><summary>목차 <small></small></summary><ol></ol></details>
      <div class="content ${p.type === 'glossary' ? 'definition' : ''}" id="postContent">${renderMd(p.content)}</div>
      ${p.tags.length ? `<div class="article-tags">${p.tags.map((t) => `<a class="tag" href="${blogHref(b.username, { tag: t })}">#${esc(t)}</a>`).join('')}</div>` : ''}
      <div class="post-actions">
        <button type="button" class="like-btn ${p.liked ? 'on' : ''}" id="likeBtn" aria-pressed="${p.liked}">
          <span class="heart" aria-hidden="true">${p.liked ? '♥' : '♡'}</span> 공감 <b id="likeN">${p.like_count}</b></button>
        <button type="button" class="share-btn" id="shareBtn">${SHARE_ICON} 공유하기</button>
      </div>
      <div id="shareSlot"></div>
      <section class="author-card" aria-label="글쓴이">
        <a class="author-avatar" href="#/@${esc(b.username)}" tabindex="-1" aria-hidden="true">${avatarOf(b)}</a>
        <div class="author-main">
          <a class="author-blog" href="#/@${esc(b.username)}">${esc(b.blog_title)}</a>
          <div class="author-sub">${esc(b.nickname)} · 글 ${b.total_posts}개 · 이웃 <span class="nb-count">${b.neighbor_count || 0}</span>명</div>
          ${b.blog_desc ? `<p class="author-desc">${esc(b.blog_desc)}</p>` : ''}
        </div>
        <div class="author-actions">
          ${b.is_owner ? '' : neighborBtn(b)}
          <a class="btn small" href="#/@${esc(b.username)}">블로그 가기</a>
        </div>
      </section>
      ${p.related.length ? `<section class="related" aria-labelledby="relTitle">
        <h2 class="related-title" id="relTitle"><em>${esc(catName(p.category))}</em> 카테고리의 다른 ${esc(typeName(p.type))} 글</h2>
        <div class="related-grid">${p.related.map((r) => `
          <a class="rel-card" href="#/post/${r.id}">
            <span class="rel-thumb" data-icon="${TYPE_ICON[r.type] || '📝'}">${r.thumbnail
              ? `<img src="${esc(r.thumbnail)}" alt="" loading="lazy" decoding="async">`
              : `<span aria-hidden="true">${TYPE_ICON[r.type] || '📝'}</span>`}</span>
            <span class="rel-title">${r.is_public ? '' : '<span class="badge">비공개</span>'}${esc(r.title)}</span>
            <span class="rel-date">${fmtDate(r.created_at)}</span>
          </a>`).join('')}</div>
      </section>` : ''}
      ${p.prev || p.next ? `<nav class="prevnext" aria-label="이전 글과 다음 글">
        ${p.prev ? `<a href="#/post/${p.prev.id}"><small>‹ 이전 글</small><span>${esc(p.prev.title)}</span></a>` : ''}
        ${p.next ? `<a class="next" href="#/post/${p.next.id}"><small>다음 글 ›</small><span>${esc(p.next.title)}</span></a>` : ''}
      </nav>` : ''}
      <section class="comments" id="comments"></section>
    </article>`;
  const del = $('#delPost');
  if (del) del.onclick = async () => {
    if (!confirm('이 글을 삭제할까요? 되돌릴 수 없습니다.')) return;
    await api('posts/' + id, { method: 'DELETE' });
    toast('삭제했습니다.');
    cur = null;
    location.hash = `#/@${b.username}`;
  };
  bindNeighborButtons(b);
  $('#likeBtn').onclick = async () => {
    if (!blog.user) { needLogin('공감하려면 로그인하세요.'); return; }
    const btn = $('#likeBtn');
    btn.disabled = true;
    try {
      const r = await api(`posts/${id}/like`, { method: 'POST' });
      btn.classList.toggle('on', r.liked);
      btn.setAttribute('aria-pressed', r.liked);
      btn.querySelector('.heart').textContent = r.liked ? '♥' : '♡';
      $('#likeN').textContent = r.count;
    } catch (err) { toast(err.message); } finally { btn.disabled = false; }
  };
  $('#shareBtn').onclick = () => sharePost(p.title);
  const content = $('#postContent');
  $('#readTime').textContent = `${readMinutes(content)}분 읽기`;
  buildToc(content, $('#toc'));
  startReadingTools(main.querySelector('.article'), content);
  renderTypeNav(null);
  renderBlogSidebar(b, p.category || '-', p.type);
  renderComments(id);
}

// ---------- 004: 읽기 도구 · 공유 · 사진 · 코드 ----------
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// 소제목·색인으로 이동: 주소(해시)는 그대로 두고, 화면 읽기 프로그램도 따라오게 포커스를 옮김
function jumpTo(el) {
  if (!el) return;
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
  el.focus({ preventScroll: true });
  el.scrollIntoView({ behavior: reduceMotion() ? 'auto' : 'smooth', block: 'start' });
}

// 화면 읽기 프로그램에만 들리는 안내
function announce(msg) {
  let live = $('#srStatus');
  if (!live) {
    live = document.createElement('div');
    live.id = 'srStatus';
    live.className = 'sr-only';
    live.setAttribute('role', 'status');
    document.body.appendChild(live);
  }
  live.textContent = '';
  setTimeout(() => (live.textContent = msg), 50);
}

// 읽는 시간: 공백을 뺀 글자 수 ÷ 500자, 올림, 최소 1분
const readMinutes = (el) => Math.max(1, Math.ceil(el.textContent.replace(/\s+/g, '').length / 500));

// 목차: 소제목(h2·h3)이 2개 이상일 때만. 넓은 화면은 펼치고 900px 이하는 접은 채로 시작
function buildToc(content, box) {
  const heads = [...content.querySelectorAll('h2, h3')].filter((h) => h.textContent.trim());
  if (heads.length < 2) { box.remove(); return; }
  box.querySelector('summary small').textContent = heads.length;
  box.querySelector('ol').innerHTML = heads.map((h, i) =>
    `<li class="lv${h.tagName[1]}"><a href="${esc(location.hash)}" data-toc="${i}">${esc(h.textContent.trim())}</a></li>`).join('');
  box.open = !window.matchMedia('(max-width: 900px)').matches;
  box.addEventListener('click', (e) => {
    const a = e.target.closest('[data-toc]');
    if (!a || !plainClick(e)) return;
    e.preventDefault();
    jumpTo(heads[Number(a.dataset.toc)]);
  });
}

// 읽은 만큼 차는 막대와 '맨 위로' 버튼 (글 보기에서만, 다른 화면으로 가면 stopReadingTools)
const reading = { off: null };
function readingEl(cls, html, tag = 'div') {
  let el = document.querySelector('.' + cls);
  if (!el) {
    el = document.createElement(tag);
    el.className = cls;
    el.innerHTML = html;
    document.body.appendChild(el);
  }
  return el;
}
function stopReadingTools() {
  if (reading.off) reading.off();
  reading.off = null;
}
function startReadingTools(article, content) {
  stopReadingTools();
  const bar = readingEl('read-progress', '<i></i>');
  bar.setAttribute('aria-hidden', 'true');
  const top = readingEl('to-top', '<span aria-hidden="true">↑</span>', 'button');
  top.type = 'button';
  top.setAttribute('aria-label', '맨 위로');
  top.title = '맨 위로';
  top.onclick = () => {
    window.scrollTo({ top: 0, behavior: reduceMotion() ? 'auto' : 'smooth' });
    article.querySelector('h1')?.focus({ preventScroll: true });
  };
  let frame = 0;
  const update = () => {
    frame = 0;
    const r = content.getBoundingClientRect();
    const head = 110; // 위쪽 고정 바 높이
    const total = r.height - (window.innerHeight - head);
    const done = total <= 0 ? (r.bottom <= window.innerHeight ? 1 : 0) : (head - r.top) / total;
    bar.firstChild.style.transform = `scaleX(${Math.min(1, Math.max(0, done))})`;
    top.hidden = window.scrollY < window.innerHeight;
  };
  const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
  bar.hidden = false;
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  update();
  reading.off = () => {
    window.removeEventListener('scroll', onScroll);
    window.removeEventListener('resize', onScroll);
    if (frame) cancelAnimationFrame(frame);
    bar.hidden = true;
    top.hidden = true;
  };
}

// 클립보드에 복사: 보안 연결(https·localhost)은 Clipboard API, 아니면 예전 방식. 성공하면 true
async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
  } catch { /* 아래 방식으로 다시 시도 */ }
  const active = document.activeElement;
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;';
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch { ok = false; }
  ta.remove();
  if (active && active.focus) active.focus({ preventScroll: true });
  return ok;
}

// 공유하기: 공유 창이 있으면 공유 창 → 없으면 주소 복사 → 그것도 안 되면 직접 복사 안내
async function sharePost(title) {
  const url = location.href;
  const data = { title, url };
  if (navigator.share && (!navigator.canShare || navigator.canShare(data))) {
    try { await navigator.share(data); return; } catch (err) { if (err && err.name === 'AbortError') return; }
  }
  if (await copyText(url)) { toast('주소를 복사했어요.'); return; }
  const slot = $('#shareSlot');
  if (!slot) return;
  slot.innerHTML = `<div class="share-fallback">
    <input id="shareUrl" readonly value="${esc(url)}" aria-label="글 주소" aria-describedby="shareHint">
    <small class="hint" id="shareHint">주소를 복사하지 못했어요. 직접 복사해 주세요.</small></div>`;
  const input = $('#shareUrl');
  input.focus();
  input.select();
}

// 코드 복사 버튼
async function copyCode(btn) {
  const code = btn.closest('.code-block')?.querySelector('pre');
  if (!code) return;
  if (!(await copyText(code.textContent))) { toast('복사하지 못했어요. 코드를 직접 골라 복사해 주세요.'); return; }
  btn.textContent = '복사했어요';
  btn.classList.add('done');
  announce('코드를 복사했어요.');
  clearTimeout(btn.doneTimer);
  btn.doneTimer = setTimeout(() => { btn.textContent = '복사'; btn.classList.remove('done'); }, 1600);
}

// 사진 크게 보기 (바깥·닫기 버튼·Esc로 닫고, 닫히면 원래 사진으로 포커스)
let lightbox = null;
function openLightbox(btn) {
  const img = btn.querySelector('img');
  if (!img) return;
  if (!lightbox) {
    lightbox = document.createElement('dialog');
    lightbox.className = 'lightbox';
    lightbox.setAttribute('aria-label', '사진 크게 보기');
    lightbox.innerHTML = `<figure class="lb-figure"><img class="lb-img" alt=""><figcaption class="lb-cap"></figcaption></figure>
      <button type="button" class="lb-close" aria-label="닫기">✕</button>`;
    document.body.appendChild(lightbox);
    lightbox.addEventListener('click', (e) => { if (!e.target.closest('.lb-img')) lightbox.close(); });
    lightbox.addEventListener('close', () => {
      document.documentElement.classList.remove('lb-open');
      if (lightbox.opener && lightbox.opener.isConnected) lightbox.opener.focus({ preventScroll: true });
      lightbox.opener = null;
    });
  }
  const big = lightbox.querySelector('.lb-img');
  big.src = img.currentSrc || img.src;
  big.alt = img.alt;
  lightbox.querySelector('.lb-cap').textContent = img.alt;
  lightbox.opener = btn;
  document.documentElement.classList.add('lb-open');
  lightbox.showModal();
  lightbox.querySelector('.lb-close').focus();
}

document.addEventListener('click', (e) => {
  const zoom = e.target.closest('.img-zoom');
  if (zoom) { openLightbox(zoom); return; }
  const copy = e.target.closest('.code-copy');
  if (copy) copyCode(copy);
});

// 목록·관련 글 대표 사진을 불러오지 못하면: 목록은 사진 칸을 숨기고, 관련 글은 종류 아이콘으로
document.addEventListener('error', (e) => {
  const img = e.target;
  if (!(img instanceof HTMLImageElement)) return;
  if (img.classList.contains('post-thumb')) { img.closest('.post-row')?.classList.remove('has-thumb'); img.remove(); }
  else if (img.classList.contains('pop-thumb')) img.remove();
  else if (img.parentElement && img.parentElement.classList.contains('rel-thumb')) {
    const icon = document.createElement('span');
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = img.parentElement.dataset.icon || '📝';
    img.replaceWith(icon);
  }
}, true);

// 댓글 입력 폼 (댓글·답글 공통)
const commentFormHtml = (id, placeholder, replyTo) => `
  <form class="c-form" id="${id}" ${replyTo ? `data-parent="${replyTo}"` : ''}>
    ${blog.user
      ? `<div class="c-as"><b>${esc(blog.user.nickname)}</b> 님으로 ${replyTo ? '답글' : '댓글'}을 남깁니다</div>`
      : `<div class="row">
      <input name="name" placeholder="이름" maxlength="30" required>
      <input name="password" type="password" placeholder="비밀번호 (삭제할 때 필요)" required>
    </div>`}
    <textarea name="content" placeholder="${placeholder}" maxlength="2000" required></textarea>
    <div class="actions">${replyTo ? '<button type="button" class="btn small" data-cancel>취소</button>' : ''}<button class="btn primary">등록</button></div>
  </form>`;

const commentHtml = (c, isReply) => c.deleted
  ? `<div class="comment ${isReply ? 'reply' : ''} gone"><p>삭제된 댓글입니다.</p></div>`
  : `<div class="comment ${isReply ? 'reply' : ''}" id="c-${c.id}">
      <div class="c-head">${isReply ? '<span class="reply-mark" aria-hidden="true">↳</span>' : ''}<span class="c-name">${esc(c.name)}</span>${c.is_member ? '<span class="member-badge">회원</span>' : ''}
        <span class="c-date">${fmtDate(c.created_at, true)}</span>
        ${c.can_delete || c.guest ? `<button class="c-del" data-id="${c.id}" data-own="${c.can_delete ? 1 : ''}">삭제</button>` : ''}</div>
      <p>${esc(c.content)}</p>
      ${isReply ? '' : `<button type="button" class="c-reply" data-reply="${c.id}">답글</button>`}
    </div>`;

async function renderComments(postId) {
  const box = $('#comments');
  const list = await api('comments?post=' + postId);
  // 댓글 아래에 그 댓글의 답글을 모아 붙임 (답글은 1단계)
  const tops = list.filter((c) => !c.parent_id);
  const repliesOf = (id) => list.filter((c) => c.parent_id === id);
  const count = list.filter((c) => !c.deleted).length;
  box.innerHTML = `
    <h3>댓글 ${count}</h3>
    ${tops.map((c) => `
      <div class="thread">
        ${commentHtml(c, false)}
        ${repliesOf(c.id).map((r) => commentHtml(r, true)).join('')}
        <div class="reply-slot" id="slot-${c.id}"></div>
      </div>`).join('')}
    ${commentFormHtml('cForm', '댓글을 남겨 주세요', null)}`;

  const submit = (form) => async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    if (form.dataset.parent) f.parent_id = Number(form.dataset.parent);
    try {
      await api('comments', { method: 'POST', body: { post_id: postId, ...f } });
      toast(form.dataset.parent ? '답글을 등록했습니다.' : '댓글을 등록했습니다.');
      renderComments(postId);
    } catch (err) { toast(err.message); }
  };
  $('#cForm').onsubmit = submit($('#cForm'));

  // '답글' 버튼: 그 댓글 아래에 답글 입력칸을 엶 (한 번에 하나)
  box.querySelectorAll('.c-reply').forEach((b) => (b.onclick = () => {
    box.querySelectorAll('.reply-slot').forEach((sl) => (sl.innerHTML = ''));
    const slot = $('#slot-' + b.dataset.reply);
    slot.innerHTML = commentFormHtml('rForm', '답글을 남겨 주세요', b.dataset.reply);
    const form = $('#rForm');
    form.onsubmit = submit(form);
    form.querySelector('[data-cancel]').onclick = () => (slot.innerHTML = '');
    form.content.focus();
  }));

  box.querySelectorAll('.c-del').forEach((b) => (b.onclick = async () => {
    let pw = '';
    if (!b.dataset.own) {
      pw = prompt('댓글 작성 시 입력한 비밀번호');
      if (pw === null) return;
    } else if (!confirm('댓글을 삭제할까요?')) return;
    try {
      // 비밀번호는 주소가 아니라 본문으로 (서버 기록·방문 기록에 남지 않게)
      await api('comments/' + b.dataset.id, { method: 'DELETE', body: pw ? { password: pw } : undefined });
      toast('댓글을 삭제했습니다.');
      renderComments(postId);
    } catch (err) { toast(err.message); }
  }));
}

// ---------- 글쓰기 / 수정 ----------
const EDITOR_HINTS = {
  insight: { title: '제목을 입력하세요', content: '마크다운으로 작성하세요. 사진과 파일은 붙여넣기·드래그하거나 위의 🖼 사진 / 📎 파일 버튼으로 올릴 수 있어요.' },
  faq: { title: '질문을 입력하세요 (예: 생성형 AI는 회사 데이터를 학습하나요?)', content: '답변을 작성하세요.' },
  glossary: { title: '용어를 입력하세요 (예: CTR (Click Through Rate))', content: '뜻과 설명, 예시를 작성하세요. 첫 문장은 굵게 쓰면 한 줄 정의로 보기 좋아요.' },
  daily: { title: '제목을 입력하세요', content: '오늘 있었던 일을 자유롭게 기록하세요.' },
};

// 005: 본문에 있는 이 블로그 업로드 사진 (서버의 upload_images와 같은 규칙: 코드·주석 속 예시는 빼고, 나온 순서·중복 없이)
function uploadImagesIn(md) {
  const text = String(md || '')
    .replace(/^[ \t]{0,3}(`{3,}|~{3,})[\s\S]*?(?:^[ \t]{0,3}\1|(?![\s\S]))/gm, ' ')
    .replace(/<!--[\s\S]*?(?:-->|$)/g, ' ')
    .replace(/``(?:[^`\n]|`(?!`))*?``|`[^`\n]*`/g, ' ');
  const re = /(?:!\[[^[\]\n]*\]\(\s*<?|<[iI][mM][gG]\b[^<>]*?\s[sS][rR][cC]\s*=\s*["']?)(\/uploads\/[0-9a-f]{32}\.(?:png|jpg|gif|webp))(?=[\s)>"'])/g;
  const found = [];
  for (const m of text.matchAll(re)) if (!found.includes(m[1])) found.push(m[1]);
  return found;
}

// 글 목록 요약 미리보기 (서버 요약과 비슷하게: 코드 블록 빼고 160자)
function excerptOf(previewEl) {
  const box = previewEl.cloneNode(true);
  box.querySelectorAll('.code-block, pre, .code-head').forEach((x) => x.remove());
  return box.textContent.replace(/\s+/g, ' ').trim().slice(0, 160);
}

// 작성 중인 화면을 떠날 때 확인 (005): 편집 화면이 정해 둠, () => true면 떠나도 됨
let leaveGuard = null;

async function renderEditor(id, defaultType) {
  const seq = routeSeq;
  if (!blog.user) { needLogin('글을 쓰려면 로그인하세요.'); return; }
  const p = id ? await api('posts/' + id)
    : { type: EDITOR_HINTS[defaultType] ? defaultType : 'insight', title: '', content: '', category: '', tags: [], is_public: true, cover: '' };
  if (id && !p.can_edit) { main.innerHTML = '<div class="empty">내가 쓴 글만 고칠 수 있어요.</div>'; return; }
  // 카테고리는 글쓴이 블로그의 카테고리 (관리자가 남의 글을 고칠 때는 그 사람 블로그 기준)
  const owner = id && p.author_username !== blog.user.username ? await api('blogs/' + enc(p.author_username)) : blog.user;
  // 불러오는 사이 다른 화면으로 갔으면 편집 화면·나가기 경고를 그 화면에 남기지 않음
  if (seq !== routeSeq) return;
  const cats = owner.categories;
  document.body.classList.add('editor-mode');
  // 발행 설정 창에서 정하는 값 (창에서 고르면 바로 기억해 취소·Esc 뒤 다시 열어도 남음, 서버로는 창의 발행/저장 버튼으로만)
  const pub = { category: p.category || '', tags: (p.tags || []).join(', '), is_public: p.is_public !== false, cover: p.cover || '' };
  main.innerHTML = `
    <form class="editor" id="editor" novalidate>
      <div class="editor-blog">📝 <b>${esc(owner.blog_title)}</b>에 ${id ? '쓴 글 고치기' : '새 글 쓰기'}</div>
      <div class="type-pick" role="radiogroup" aria-label="글 종류">
        ${blog.types.map((t) => `
          <label class="type-opt"><input type="radio" name="type" value="${t.key}" ${p.type === t.key ? 'checked' : ''}>
            <span>${TYPE_ICON[t.key]} ${esc(t.name)}</span></label>`).join('')}
      </div>
      <input class="title-input" name="title" placeholder="${esc(EDITOR_HINTS[p.type].title)}" value="${esc(p.title)}" aria-label="제목" maxlength="200">
      <div>
        <div class="toolbar" id="toolbar">
          <button type="button" data-md="## |" title="제목">H2</button>
          <button type="button" data-md="### |" title="소제목">H3</button>
          <span class="sep"></span>
          <button type="button" data-wrap="**" title="굵게"><b>B</b></button>
          <button type="button" data-wrap="*" title="기울임"><i>I</i></button>
          <button type="button" data-wrap="~~" title="취소선"><s>S</s></button>
          <button type="button" data-wrap="\`" title="코드">&lt;/&gt;</button>
          <span class="sep"></span>
          <button type="button" data-md="> |" title="인용">❝</button>
          <button type="button" data-md="- |" title="목록">•</button>
          <button type="button" data-md="[|](https://)" title="링크">링크</button>
          <button type="button" data-md="\n\`\`\`\n|\n\`\`\`\n" title="코드 블록">코드블록</button>
          <button type="button" data-md="\n---\n|" title="구분선">―</button>
          <button type="button" id="imgBtn" title="사진 넣기 (본문에 바로 보여요)">🖼 사진</button>
          <button type="button" id="fileBtn" title="파일 첨부 (PDF·한글·오피스·ZIP 등, 30MB까지)">📎 파일</button>
          <input type="file" id="imgFile" accept="image/png,image/jpeg,image/gif,image/webp" multiple hidden>
          <input type="file" id="fileFile" accept="${FILE_ACCEPT}" multiple hidden>
          <div class="tabs">
            <button type="button" data-mode="write">작성</button>
            <button type="button" data-mode="split" class="on">나란히</button>
            <button type="button" data-mode="preview">미리보기</button>
          </div>
        </div>
        <div class="edit-area" id="editArea">
          <textarea name="content" id="mdInput" aria-label="본문" placeholder="${esc(EDITOR_HINTS[p.type].content)}">${esc(p.content)}</textarea>
          <div class="preview content" id="preview"></div>
        </div>
      </div>
      <div class="editor-foot">
        <span class="char-count" id="charCount" aria-live="off"></span>
        <span class="hint" id="saveHint">${id ? '' : '작성 중인 글은 이 브라우저에 자동 저장됩니다.'}</span>
        <div class="editor-actions">
          <a class="btn" href="${id ? '#/post/' + id : '#/@' + esc(blog.user.username)}">취소</a>
          <button class="btn primary" id="publishBtn">${id ? '저장' : '발행'}</button>
        </div>
      </div>
    </form>
    <dialog class="publish-dlg" id="publishDlg" aria-labelledby="pubTitle">
      <form method="dialog" class="publish-form" id="publishForm" novalidate>
        <div class="pub-head"><h2 id="pubTitle">발행 설정</h2>
          <button type="button" class="pub-close" value="cancel" aria-label="닫기" data-close>✕</button></div>
        <div class="pub-body">
          <div class="pub-fields">
            <label class="field"><span>카테고리</span><select name="category" id="pubCategory">
              <option value="">카테고리 선택</option>
              ${cats.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join('')}
            </select>
            ${!cats.length ? '<small class="hint">카테고리가 없어요. <a class="link" href="#/manage/categories">만들기</a></small>' : ''}</label>
            <fieldset class="field pub-vis"><legend>공개 설정</legend>
              <div class="pub-row">
                <label class="pub-radio"><input type="radio" name="vis" value="public"> <b>공개</b> <small>누구나 볼 수 있어요</small></label>
                <label class="pub-radio"><input type="radio" name="vis" value="private"> <b>비공개</b> <small>나와 관리자만 봐요</small></label>
              </div>
            </fieldset>
            <label class="field"><span>태그</span><input name="tags" id="pubTags" placeholder="쉼표로 구분 (예: 마케팅, 리텐션)" autocomplete="off"></label>
            <fieldset class="field pub-cover"><legend>대표 사진 <small>목록·관련 글에 보여요</small></legend>
              <div class="cover-grid" id="coverGrid"></div>
            </fieldset>
          </div>
          <div class="pub-preview" aria-label="목록 미리보기">
            <span class="side-title">목록에서 이렇게 보여요</span>
            <div class="post-list" id="pubPreview"></div>
          </div>
        </div>
        <p class="pub-error error-text" id="pubError" role="alert" hidden></p>
        <div class="pub-actions">
          <button type="button" class="btn" data-close>취소</button>
          <button type="submit" class="btn primary" id="pubSubmit" value="ok">${id ? '저장' : '발행'}</button>
        </div>
      </form>
    </dialog>`;

  const form = $('#editor');
  const ta = $('#mdInput');
  const preview = $('#preview');
  const area = $('#editArea');
  const dlg = $('#publishDlg');
  const pform = $('#publishForm');
  const draftKey = 'draft-' + blog.user.username;

  if (!id) {
    try {
      const d = JSON.parse(localStorage.getItem(draftKey) || 'null');
      if (d && (d.title || d.content) && confirm('작성 중이던 글이 있어요. 불러올까요?')) {
        if (d.type && EDITOR_HINTS[d.type]) form.elements.type.value = d.type;
        form.title.value = d.title || ''; ta.value = d.content || '';
        if (typeof d.category === 'string') pub.category = d.category;
        if (typeof d.tags === 'string') pub.tags = d.tags;
        if (typeof d.is_public === 'boolean') pub.is_public = d.is_public;
        if (typeof d.cover === 'string') pub.cover = d.cover;
      }
    } catch { /* 저장소를 쓸 수 없으면 무시 */ }
  }

  // 지금 편집 상태 (바뀌었는지 비교용)
  const snapshot = () => JSON.stringify([form.elements.type.value, form.title.value, ta.value, pub.category, pub.tags, pub.is_public, pub.cover]);
  let initial = snapshot();
  let done = false;
  leaveGuard = (silent) => {
    if (done || snapshot() === initial) return true;
    if (silent) return false;
    return confirm(id ? '고친 내용이 아직 저장되지 않았어요. 이 화면을 나갈까요?'
      : '작성 중인 내용이 있어요. 이 화면을 나갈까요? (자동 저장된 내용은 다음에 불러올 수 있어요)');
  };

  const countChars = () => {
    const all = ta.value.length;
    const noSpace = ta.value.replace(/\s/g, '').length;
    $('#charCount').textContent = `글자 ${all.toLocaleString()} · 공백 제외 ${noSpace.toLocaleString()}`;
  };
  const update = () => { preview.innerHTML = renderMd(ta.value); countChars(); };
  let saveTimer;
  const saveDraft = () => {
    if (id) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (done) return; // 발행·저장을 마친 뒤에는 다시 쓰지 않음
      try {
        localStorage.setItem(draftKey, JSON.stringify({ type: form.elements.type.value, title: form.title.value, content: ta.value,
          category: pub.category, tags: pub.tags, is_public: pub.is_public, cover: pub.cover }));
        $('#saveHint').textContent = `임시 저장됨 ${fmtDate(new Date().toISOString(), true).slice(-5)}`;
      } catch { /* 무시 */ }
    }, 600);
  };
  // 글 종류에 맞춰 안내 문구 바꾸기 (일상은 카테고리 없이도 가능)
  const categoryOptional = () => form.elements.type.value === 'daily' || !cats.length;
  const syncType = () => {
    const t = form.elements.type.value;
    form.title.placeholder = EDITOR_HINTS[t].title;
    ta.placeholder = EDITOR_HINTS[t].content;
  };
  form.querySelectorAll('input[name="type"]').forEach((r) => r.addEventListener('change', () => { syncType(); saveDraft(); }));
  syncType();
  ta.addEventListener('input', () => { update(); saveDraft(); });
  form.title.addEventListener('input', saveDraft);
  update();

  function insert(before, after = '') {
    const { selectionStart: st, selectionEnd: e, value } = ta;
    const sel = value.slice(st, e);
    ta.setRangeText(before + sel + after, st, e, 'end');
    if (!sel) ta.selectionStart = ta.selectionEnd = st + before.length;
    ta.focus();
    update(); saveDraft();
  }

  $('#toolbar').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.wrap) insert(b.dataset.wrap, b.dataset.wrap);
    else if (b.dataset.md) {
      const [before, after] = b.dataset.md.split('|');
      const lineStart = ta.value.lastIndexOf('\n', ta.selectionStart - 1) + 1;
      if (/^[#>-]/.test(before) && ta.selectionStart !== lineStart) insert('\n' + before, after);
      else insert(before, after);
    } else if (b.dataset.mode) {
      area.className = 'edit-area' + (b.dataset.mode === 'split' ? '' : ' mode-' + b.dataset.mode);
      b.parentElement.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
    }
  });

  // 사진은 본문에 바로 보이게, 그 밖의 파일은 내려받는 첨부 링크로 넣음
  async function uploadFiles(files) {
    for (const file of files) {
      const isImage = IMAGE_MIME.includes(file.type);
      const limit = isImage ? 10 : 30;
      if (file.size > limit * 1024 * 1024) { toast(`${isImage ? '사진' : '파일'}은 ${limit}MB까지 올릴 수 있어요: ${file.name}`); continue; }
      const marker = `[업로드 중: ${mdSafe(file.name)}…]()`;
      insert(marker + '\n');
      try {
        const up = await uploadFile(file);
        ta.value = ta.value.replace(marker, up.is_image
          ? `![${mdSafe(file.name.replace(/\.\w+$/, ''))}](${up.url})`
          : `[📎 ${mdSafe(up.name)} (${fmtSize(up.size)})](${up.url})`);
      } catch (err) {
        ta.value = ta.value.replace(marker + '\n', '');
        toast(err.message);
      }
      update(); saveDraft();
    }
  }
  $('#imgBtn').onclick = () => $('#imgFile').click();
  $('#imgFile').onchange = (e) => { uploadFiles([...e.target.files]); e.target.value = ''; };
  $('#fileBtn').onclick = () => $('#fileFile').click();
  $('#fileFile').onchange = (e) => { uploadFiles([...e.target.files]); e.target.value = ''; };
  ta.addEventListener('paste', (e) => {
    const files = [...e.clipboardData.files];
    if (files.length) { e.preventDefault(); uploadFiles(files); }
  });
  area.addEventListener('dragover', (e) => { e.preventDefault(); area.classList.add('dragging'); });
  area.addEventListener('dragleave', () => area.classList.remove('dragging'));
  area.addEventListener('drop', (e) => { e.preventDefault(); area.classList.remove('dragging'); uploadFiles([...e.dataTransfer.files]); });
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') { e.preventDefault(); insert('  '); }
    if ((e.metaKey || e.ctrlKey) && e.key === 'b') { e.preventDefault(); insert('**', '**'); }
    if ((e.metaKey || e.ctrlKey) && e.key === 'i') { e.preventDefault(); insert('*', '*'); }
  });

  // ---------- 발행 설정 창 ----------
  const pubError = (msg) => { const el = $('#pubError'); el.textContent = msg || ''; el.hidden = !msg; };
  const coverChoices = () => uploadImagesIn(ta.value);
  const drawCovers = () => {
    const imgs = coverChoices();
    if (pub.cover && pub.cover !== 'none' && !imgs.includes(pub.cover)) pub.cover = ''; // 본문에서 지운 사진이면 자동으로
    const opt = (value, inner, label) => `
      <label class="cover-opt" title="${esc(label)}"><input type="radio" name="cover" value="${esc(value)}" ${pub.cover === value ? 'checked' : ''} aria-label="${esc(label)}">
        <span class="cover-face">${inner}</span></label>`;
    $('#coverGrid').innerHTML = opt('', '<b>자동</b><small>본문 첫 사진</small>', '자동: 본문 첫 사진')
      + opt('none', '<b>사진 없이</b><small>글자만</small>', '사진 없이')
      + imgs.map((src, i) => opt(src, `<img src="${esc(src)}" alt="" loading="lazy">`, `본문 ${i + 1}번째 사진`)).join('')
      + (imgs.length ? '' : '<p class="hint cover-none">본문에 올린 사진이 없어요. 사진을 넣으면 여기서 고를 수 있어요.</p>');
  };
  const drawPreview = () => {
    const imgs = coverChoices();
    const thumb = pub.cover === 'none' ? null : (pub.cover && imgs.includes(pub.cover) ? pub.cover : imgs[0] || null);
    const t = form.elements.type.value;
    $('#pubPreview').innerHTML = postRowHtml({
      id: id || 0, type: t, category: pub.category, title: form.title.value.trim() || '(제목)', excerpt: excerptOf(preview),
      is_public: pub.is_public, thumbnail: thumb, author_avatar: owner.avatar, author_nickname: owner.nickname,
      author_blog_title: owner.blog_title, created_at: p.created_at || new Date().toISOString(), comment_count: p.comment_count || 0,
      views: p.views || 0, like_count: p.like_count || 0,
    }, false);
    $('#pubPreview').querySelector('a.post-row')?.removeAttribute('href');
  };
  const readDialog = () => {
    pub.category = pform.category.value;
    pub.tags = pform.tags.value;
    pub.is_public = pform.elements.vis.value !== 'private';
    pub.cover = pform.elements.cover ? (pform.elements.cover.value || '') : '';
  };
  const openDialog = () => {
    if (!form.title.value.trim()) { toast('제목을 입력하세요.'); form.title.focus(); return; }
    pubError('');
    pform.category.value = cats.includes(pub.category) ? pub.category : '';
    pform.category.options[0].textContent = categoryOptional() ? '카테고리 없음' : '카테고리 선택';
    pform.tags.value = pub.tags;
    pform.elements.vis.value = pub.is_public ? 'public' : 'private';
    drawCovers();
    drawPreview();
    dlg.showModal();
    (pform.category.value || categoryOptional() ? pform.querySelector('#pubSubmit') : pform.category).focus();
  };
  pform.addEventListener('change', () => { readDialog(); if (dlg.open) { drawPreview(); saveDraft(); } });
  pform.addEventListener('input', (e) => { if (e.target === pform.tags) { readDialog(); saveDraft(); } });
  // 태그 칸의 Enter는 발행이 아니라 다음 태그로 (쉼표 넣기)
  pform.tags.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || e.isComposing) return;
    e.preventDefault();
    if (pform.tags.value.trim() && !/,\s*$/.test(pform.tags.value)) pform.tags.value += ', ';
  });
  dlg.addEventListener('click', (e) => { if (e.target === dlg || e.target.closest('[data-close]')) dlg.close(); });

  form.onsubmit = (e) => { e.preventDefault(); openDialog(); };
  pform.onsubmit = async (e) => {
    e.preventDefault();
    readDialog();
    if (!pub.category && !categoryOptional()) { pubError('카테고리를 선택하세요.'); pform.category.focus(); return; }
    const body = {
      type: form.elements.type.value, title: form.title.value, content: ta.value, category: pub.category,
      tags: pub.tags, is_public: pub.is_public, cover: pub.cover,
    };
    const btn = $('#pubSubmit');
    btn.disabled = true;
    try {
      const r = await api(id ? 'posts/' + id : 'posts', { method: id ? 'PUT' : 'POST', body });
      done = true;
      clearTimeout(saveTimer); // 창에서 고른 값의 임시 저장 예약이 발행한 글을 다시 남기지 않게
      if (!id) try { localStorage.removeItem(draftKey); } catch { /* 무시 */ }
      dlg.close();
      toast(id ? '저장했습니다.' : '발행했습니다! 🎉');
      cur = null;
      location.hash = '#/post/' + r.id;
    } catch (err) {
      pubError(err.message);
      if (!dlg.open) toast(err.message); // 기다리는 사이 창을 닫았으면 창 밖에서도 알림
      btn.disabled = false;
    }
  };
  initial = snapshot(); // 불러온 임시 저장까지 반영한 뒤를 기준으로
  form.title.focus();
}

async function uploadFile(file) {
  const data = await new Promise((ok, no) => {
    const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(file);
  });
  return api('upload', { method: 'POST', body: { data, name: file.name } });
}

// ---------- 블로그 관리 ----------
const MANAGE_TABS = [
  ['', '📊 홈'], ['posts', '📝 글'], ['comments', '💬 댓글'], ['categories', '🗂 카테고리'], ['room', '🏠 미니룸'], ['design', '🎨 꾸미기'],
  ['info', '🏷 블로그 정보'],
];

async function renderManage(tab, qs) {
  const seq = routeSeq;
  if (!blog.user) { needLogin('블로그를 관리하려면 로그인하세요.'); return; }
  cur = null;
  const u = blog.user;
  renderTypeNav(null);
  main.innerHTML = `
    <div class="manage-head">
      <div><h1>블로그 관리</h1><a class="link" href="#/@${esc(u.username)}">${esc(u.blog_title)} 보러 가기 →</a></div>
      <a class="btn primary" href="#/write">글쓰기</a>
    </div>
    <nav class="chips manage-tabs">${MANAGE_TABS.map(([k, label]) =>
      `<a class="chip ${tab === k ? 'on' : ''}" href="#/manage${k ? '/' + k : ''}">${label}</a>`).join('')}</nav>
    <div id="manageBody"><div class="empty">불러오는 중…</div></div>`;
  const body = $('#manageBody');
  const fn = {
    '': manageHome, posts: managePosts, comments: manageComments, categories: manageCategories, room: manageRoom, design: manageDesign,
    info: manageInfo,
  }[tab];
  if (!fn) { body.innerHTML = '<div class="empty">없는 메뉴예요.</div>'; return; }
  await fn(body, qs);
  if (seq !== routeSeq) return;
  // 사이드바: 내 블로그
  const mine = await api('blogs/' + enc(u.username));
  if (seq !== routeSeq) return;
  renderBlogSidebar(mine, null, null);
}

async function manageHome(body) {
  const s = await api('manage/stats');
  // 최근 7일 (방문이 없는 날도 0으로)
  const days = [...Array(7)].map((_, i) => {
    const d = new Date(); d.setDate(d.getDate() - 6 + i);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { key, label: i === 6 ? '오늘' : `${d.getMonth() + 1}/${d.getDate()}`, count: s.week.find((w) => w.day === key)?.count || 0 };
  });
  const max = Math.max(1, ...days.map((d) => d.count));
  body.innerHTML = `
    <div class="tiles">
      ${[['오늘 방문', s.today], ['어제 방문', s.yesterday], ['전체 방문', s.total], ['글', `${s.posts}<small> (공개 ${s.public_posts})</small>`],
        ['받은 댓글', s.comments], ['전체 조회수', s.views], ['받은 공감', s.likes], ['나를 이웃한 사람', s.neighbors]].map(([k, v]) =>
        `<div class="card tile"><span>${k}</span><b>${typeof v === 'number' ? v.toLocaleString() : v}</b></div>`).join('')}
    </div>
    <section class="card form-card">
      <h2 class="side-title">최근 7일 방문자</h2>
      <div class="bars" role="img" aria-label="최근 7일 방문자: ${days.map((d) => `${d.label} ${d.count}명`).join(', ')}">
        ${days.map((d) => `<div class="bar"><span class="bar-n">${d.count}</span><i style="height:${Math.round((d.count / max) * 100)}%"></i><small>${d.label}</small></div>`).join('')}
      </div>
    </section>
    <section class="card form-card">
      <h2 class="side-title">많이 본 글</h2>
      ${s.top_posts.length ? `<ol class="top-list">${s.top_posts.map((p) =>
        `<li><a href="#/post/${p.id}">${TYPE_ICON[p.type]} ${esc(p.title)}</a><span class="count">조회 ${p.views}</span></li>`).join('')}</ol>`
        : '<p class="w-msg">아직 글이 없어요. <a class="link" href="#/write">첫 글 쓰기 →</a></p>'}
    </section>`;
}

async function managePosts(body, qs) {
  const page = qs.get('page') || 1;
  const q = qs.get('q') || '';
  const params = new URLSearchParams({ blog: blog.user.username, page, size: 20 });
  if (q) params.set('q', q);
  const data = await api('posts?' + params);
  body.innerHTML = `
    <form class="manage-search" id="mSearch"><input name="q" type="search" value="${esc(q)}" placeholder="내 글 검색"><button class="btn small">검색</button></form>
    <div class="bulk">
      <label class="switch"><input type="checkbox" id="checkAll"> 전체 선택</label>
      <button class="btn small" data-bulk="public">공개로</button>
      <button class="btn small" data-bulk="private">비공개로</button>
      <button class="btn small danger" data-bulk="delete">삭제</button>
      <span class="hint" id="picked">0개 선택</span>
    </div>
    ${data.posts.length ? `<table class="post-table">
      <thead><tr><th></th><th>제목</th><th>종류 · 카테고리</th><th>상태</th><th>날짜</th><th>조회</th><th></th></tr></thead>
      <tbody>${data.posts.map((p) => `
        <tr>
          <td><input type="checkbox" class="pick" value="${p.id}" aria-label="${esc(p.title)} 선택"></td>
          <td class="t-title"><a href="#/post/${p.id}">${esc(p.title)}</a> <small class="count">💬${p.comment_count}</small></td>
          <td>${TYPE_ICON[p.type]} ${esc(catName(p.category))}</td>
          <td>${p.is_public ? '<span class="state on">공개</span>' : '<span class="state">비공개</span>'}</td>
          <td>${fmtDate(p.created_at)}</td>
          <td>${p.views}</td>
          <td><a class="btn small" href="#/edit/${p.id}">수정</a></td>
        </tr>`).join('')}</tbody></table>`
      : `<div class="empty">${q ? '찾는 글이 없어요.' : '아직 글이 없어요. <a class="link" href="#/write">첫 글 쓰기 →</a>'}</div>`}
    ${pagerHtml(data)}`;
  $('#mSearch').onsubmit = (e) => { e.preventDefault(); location.hash = '#/manage/posts?q=' + enc(e.target.q.value.trim()); };
  const picks = () => [...body.querySelectorAll('.pick:checked')].map((c) => Number(c.value));
  const count = () => ($('#picked').textContent = `${picks().length}개 선택`);
  body.querySelectorAll('.pick').forEach((c) => (c.onchange = count));
  $('#checkAll').onchange = (e) => { body.querySelectorAll('.pick').forEach((c) => (c.checked = e.target.checked)); count(); };
  body.querySelectorAll('[data-bulk]').forEach((btn) => (btn.onclick = async () => {
    const ids = picks();
    if (!ids.length) { toast('글을 먼저 골라 주세요.'); return; }
    const act = btn.dataset.bulk;
    if (act === 'delete' && !confirm(`글 ${ids.length}개를 삭제할까요? 댓글도 함께 지워지고 되돌릴 수 없어요.`)) return;
    try {
      const r = act === 'delete'
        ? await api('manage/delete', { method: 'POST', body: { ids } })
        : await api('manage/visibility', { method: 'POST', body: { ids, is_public: act === 'public' } });
      toast(`${r.changed}개 ${act === 'delete' ? '삭제' : act === 'public' ? '공개로 바꿈' : '비공개로 바꿈'}`);
      managePosts(body, qs);
    } catch (err) { toast(err.message); }
  }));
}

async function manageComments(body, qs) {
  const data = await api('manage/comments?page=' + (qs.get('page') || 1));
  body.innerHTML = `
    <p class="intro">내 블로그 글에 달린 댓글이에요. 광고나 불쾌한 댓글은 바로 지울 수 있어요.</p>
    ${data.comments.length ? `<div class="m-comments">${data.comments.map((c) => `
      <div class="card m-comment">
        <div class="c-head"><b>${esc(c.name)}</b>${c.user_id ? '<span class="member-badge">회원</span>' : ''}
          <span class="c-date">${fmtDate(c.created_at, true)}</span>
          <button class="c-del" data-del="${c.id}">삭제</button></div>
        <p>${esc(c.content)}</p>
        <a class="link small-link" href="#/post/${c.post_id}">↳ ${esc(c.post_title)}</a>
      </div>`).join('')}</div>` : '<div class="empty">아직 받은 댓글이 없어요.</div>'}
    ${pagerHtml(data)}`;
  body.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => {
    if (!confirm('이 댓글을 삭제할까요?')) return;
    try {
      await api('comments/' + b.dataset.del, { method: 'DELETE' });
      toast('댓글을 삭제했습니다.');
      manageComments(body, qs);
    } catch (err) { toast(err.message); }
  }));
}

async function manageCategories(body) {
  const b = await api('blogs/' + enc(blog.user.username));
  const counts = Object.fromEntries(b.category_counts.map((c) => [c.name, c.count]));
  // 원래 이름을 기억해 두었다가, 이름을 바꾸면 그 카테고리의 글도 함께 옮김
  let rows = b.categories.map((name) => ({ orig: name, name }));
  const draw = () => {
    body.innerHTML = `
      <p class="intro">카테고리 이름을 바꾸면 그 카테고리의 글도 함께 옮겨져요. 지운 카테고리의 글은 '미분류'가 돼요.</p>
      <div class="card form-card">
        <ul class="cat-edit">${rows.map((r, i) => `
          <li>
            <input value="${esc(r.name)}" data-i="${i}" maxlength="20" aria-label="카테고리 이름">
            <span class="count">${r.orig ? `글 ${counts[r.orig] || 0}` : '새 카테고리'}</span>
            <button type="button" class="btn small" data-up="${i}" ${i === 0 ? 'disabled' : ''} aria-label="위로">↑</button>
            <button type="button" class="btn small" data-down="${i}" ${i === rows.length - 1 ? 'disabled' : ''} aria-label="아래로">↓</button>
            <button type="button" class="btn small danger" data-rm="${i}">삭제</button>
          </li>`).join('')}</ul>
        ${counts[''] ? `<p class="hint">미분류 글 ${counts['']}개</p>` : ''}
        <div class="cat-add"><input id="newCat" maxlength="20" placeholder="새 카테고리 이름"><button type="button" class="btn small" id="addCat">추가</button></div>
        <button class="btn primary" id="saveCats" style="width:100%; margin-top:16px">저장</button>
      </div>`;
    body.querySelectorAll('[data-i]').forEach((inp) => (inp.oninput = () => { rows[inp.dataset.i].name = inp.value; }));
    body.querySelectorAll('[data-up]').forEach((x) => (x.onclick = () => { const i = +x.dataset.up; [rows[i - 1], rows[i]] = [rows[i], rows[i - 1]]; draw(); }));
    body.querySelectorAll('[data-down]').forEach((x) => (x.onclick = () => { const i = +x.dataset.down; [rows[i + 1], rows[i]] = [rows[i], rows[i + 1]]; draw(); }));
    body.querySelectorAll('[data-rm]').forEach((x) => (x.onclick = () => {
      const r = rows[+x.dataset.rm];
      if (r.orig && counts[r.orig] && !confirm(`'${r.orig}'의 글 ${counts[r.orig]}개는 미분류가 돼요. 지울까요?`)) return;
      rows.splice(+x.dataset.rm, 1); draw();
    }));
    const add = () => {
      const v = $('#newCat').value.trim();
      if (!v) return;
      if (rows.some((r) => r.name.trim() === v)) { toast('이미 있는 이름이에요.'); return; }
      rows.push({ orig: null, name: v }); draw(); $('#newCat').focus();
    };
    $('#addCat').onclick = add;
    $('#newCat').onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } };
    $('#saveCats').onclick = async () => {
      const names = rows.map((r) => r.name.trim()).filter(Boolean);
      if (new Set(names).size !== names.length) { toast('같은 이름의 카테고리가 있어요.'); return; }
      const renames = Object.fromEntries(rows.filter((r) => r.orig && r.name.trim() && r.orig !== r.name.trim()).map((r) => [r.orig, r.name.trim()]));
      try {
        await api('me/categories', { method: 'PUT', body: { categories: names, renames } });
        await loadBlog();
        toast('카테고리를 저장했어요.');
        renderManage('categories', new URLSearchParams());
      } catch (err) { toast(err.message); }
    };
  };
  draw();
}

// 미니룸: 기본 목록에서 배경·캐릭터를 골라 미리 보고 저장
async function manageRoom(body) {
  const u = blog.user;
  const pick = { bg: MINIROOM.bgs[u.room_bg] ? u.room_bg : 'room', ch: MINIROOM.chars[u.room_char] ? u.room_char : 'bear' };
  const draw = () => {
    const changed = pick.bg !== u.room_bg || pick.ch !== u.room_char;
    body.innerHTML = `
      <p class="intro">블로그 맨 위에 보이는 미니룸이에요. 배경과 캐릭터를 골라 미리 보고 저장하세요.</p>
      <div class="card room-preview">${miniroomSvg(pick.bg, pick.ch)}</div>
      <section class="card form-card">
        <h2 class="side-title">배경</h2>
        <div class="room-grid bgs" role="radiogroup" aria-label="배경">
          ${Object.entries(MINIROOM.bgs).map(([k, v]) => `
            <button type="button" class="room-opt ${pick.bg === k ? 'on' : ''}" role="radio" aria-checked="${pick.bg === k}" data-bg="${k}">
              ${miniroomBgThumb(k)}<span>${esc(v.name)}</span></button>`).join('')}
        </div>
        <h2 class="side-title" style="margin-top:22px">캐릭터</h2>
        <div class="room-grid chars" role="radiogroup" aria-label="캐릭터">
          ${Object.entries(MINIROOM.chars).map(([k, v]) => `
            <button type="button" class="room-opt ${pick.ch === k ? 'on' : ''}" role="radio" aria-checked="${pick.ch === k}" data-ch="${k}">
              ${miniroomCharThumb(k)}<span>${esc(v.name)}</span></button>`).join('')}
        </div>
        <button class="btn primary" id="saveRoom" style="width:100%; margin-top:20px" ${changed ? '' : 'disabled'}>${changed ? '저장' : '저장됨'}</button>
      </section>`;
    body.querySelectorAll('[data-bg]').forEach((b) => (b.onclick = () => { pick.bg = b.dataset.bg; draw(); body.querySelector(`[data-bg="${pick.bg}"]`).focus(); }));
    body.querySelectorAll('[data-ch]').forEach((b) => (b.onclick = () => { pick.ch = b.dataset.ch; draw(); body.querySelector(`[data-ch="${pick.ch}"]`).focus(); }));
    $('#saveRoom').onclick = async () => {
      try {
        await api('me', { method: 'PUT', body: { room_bg: pick.bg, room_char: pick.ch } });
        await loadBlog();
        cur = null;
        toast('미니룸을 바꿨어요.');
        renderManage('room', new URLSearchParams());
      } catch (err) { toast(err.message); }
    };
  };
  draw();
}

// 꾸미기: 대표 색(미리보기 카드 안에만 바로 적용) + 사이드바·배너 항목 켜고 끄기
async function manageDesign(body) {
  const u = blog.user;
  const saved = { skin: hasSkin(u.skin) ? u.skin : 'coral', hidden: (u.hidden_widgets || []).filter((k) => WIDGETS.some(([w]) => w === k)) };
  const pick = { skin: saved.skin, hidden: [...saved.hidden] };
  const changed = () => pick.skin !== saved.skin
    || pick.hidden.length !== saved.hidden.length || pick.hidden.some((k) => !saved.hidden.includes(k));
  body.innerHTML = `
    <p class="intro">내 블로그 화면과 내 글 화면에 쓰는 색, 사이드바·배너에 보일 항목을 골라요. 방문자에게도 이렇게 보여요.</p>
    <form id="designForm">
      <section class="card form-card">
        <h2 class="side-title" id="skinTitle">대표 색</h2>
        <div class="skin-grid" role="radiogroup" aria-labelledby="skinTitle">
          ${Object.entries(SKINS).map(([k, name]) => `
            <label class="skin-opt" data-skin="${k}"><input type="radio" name="skin" value="${k}" ${pick.skin === k ? 'checked' : ''}>
              <span class="skin-face"><i class="skin-dot" aria-hidden="true"></i>${esc(name)}${k === 'coral' ? ' <small>기본</small>' : ''}</span></label>`).join('')}
        </div>
        <div class="skin-preview" id="skinPreview" data-skin="${pick.skin}" aria-label="미리보기">
          <div class="sp-head"><b>${esc(u.blog_title)}</b><span class="btn small primary" aria-hidden="true">글쓰기</span></div>
          <div class="sp-chips" aria-hidden="true"><span class="chip on">전체</span><span class="chip">💡 인사이트</span><span class="chip">☕️ 일상</span></div>
          <p class="sp-text">본문 속 <span class="sp-link">링크</span>와 <span class="tag on">#태그</span>, 선택된 메뉴가 이 색으로 보여요.</p>
        </div>
      </section>
      <section class="card form-card">
        <h2 class="side-title">사이드바·배너 항목</h2>
        <p class="hint">끄면 방문자에게 보이지 않고, 인기 글·태그·최근 댓글·방문자 수는 자료도 보내지 않아요. 프로필과 카테고리는 항상 보여요.</p>
        <div class="widget-list">
          ${WIDGETS.map(([k, name, desc]) => `
            <label class="switch field"><input type="checkbox" name="w" value="${k}" ${pick.hidden.includes(k) ? '' : 'checked'}>
              <span>${esc(name)} <small>${esc(desc)}</small></span></label>`).join('')}
        </div>
      </section>
      <div class="design-actions">
        <a class="link" href="#/@${esc(u.username)}">내 블로그에서 보기 →</a>
        <button class="btn primary" id="saveDesign" disabled>저장됨</button>
      </div>
    </form>`;
  const form = $('#designForm');
  const btn = $('#saveDesign');
  const sync = () => {
    pick.skin = form.elements.skin.value || 'coral';
    pick.hidden = WIDGETS.map(([k]) => k).filter((k) => !form.querySelector(`input[name="w"][value="${k}"]`).checked);
    $('#skinPreview').dataset.skin = pick.skin;
    const c = changed();
    btn.disabled = !c;
    btn.textContent = c ? '저장' : '저장됨';
  };
  form.addEventListener('change', sync);
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!changed()) return;
    btn.disabled = true;
    try {
      await api('me', { method: 'PUT', body: { skin: pick.skin, hidden_widgets: pick.hidden } });
      await loadBlog();
      cur = null;
      toast('꾸미기를 저장했어요.');
      renderManage('design', new URLSearchParams());
    } catch (err) { toast(err.message); btn.disabled = false; }
  };
}

async function manageInfo(body) {
  const u = blog.user;
  body.innerHTML = `
    <form class="card form-card" id="infoForm">
      <label class="field"><span>블로그 이름</span><input name="blog_title" value="${esc(u.blog_title)}" required maxlength="40"></label>
      <label class="field"><span>블로그 소개</span><textarea name="blog_desc" rows="3" maxlength="200" placeholder="어떤 이야기를 쓰는 블로그인가요?">${esc(u.blog_desc)}</textarea></label>
      <label class="field"><span>닉네임</span><input name="nickname" value="${esc(u.nickname)}" required minlength="2" maxlength="20"></label>
      <div class="field"><span>프로필 사진</span>
        <div class="avatar-row">${avatarOf(u)}
          <input type="file" id="avatarFile" accept="image/png,image/jpeg,image/gif,image/webp" hidden>
          <button type="button" class="btn small" id="avatarBtn">사진 바꾸기</button>
          ${u.avatar ? '<button type="button" class="btn small" id="avatarDel">사진 지우기</button>' : ''}</div></div>
      <p class="hint">블로그 주소: ${esc(location.origin)}/#/@${esc(u.username)}</p>
      <button class="btn primary" style="width:100%">저장</button>
    </form>`;
  const save = async (extra = {}) => {
    try {
      await api('me', { method: 'PUT', body: { ...Object.fromEntries(new FormData($('#infoForm'))), ...extra } });
      await loadBlog();
      toast('저장했습니다.');
      renderManage('info', new URLSearchParams());
    } catch (err) { toast(err.message); }
  };
  $('#infoForm').onsubmit = (e) => { e.preventDefault(); save(); };
  $('#avatarBtn').onclick = () => $('#avatarFile').click();
  if ($('#avatarDel')) $('#avatarDel').onclick = () => save({ avatar: '' });
  $('#avatarFile').onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try { save({ avatar: (await uploadFile(file)).url }); } catch (err) { toast(err.message); }
  };
}

// ---------- 로그인 / 회원가입 / 내 정보 / 사이트 설정 ----------
// 로그인이 필요한 화면에서 넘어왔으면 끝나고 그 화면으로 돌려보냄
const afterLogin = (fallback = '#/') => {
  let back = null;
  try { back = sessionStorage.getItem('afterLogin'); sessionStorage.removeItem('afterLogin'); } catch { /* 무시 */ }
  location.hash = back || fallback;
};
const needLogin = (msg) => {
  try { sessionStorage.setItem('afterLogin', location.hash); } catch { /* 무시 */ }
  toast(msg);
  location.hash = '#/login';
};

function renderLogin() {
  if (blog.user) { location.hash = '#/'; return; }
  main.innerHTML = `
    <section class="panel card">
      <a class="btn small back-home" href="#/">← 블로그 홈으로</a>
      <h1>로그인</h1>
      <p class="hint">회원 계정은 회원 페이지에서 로그인한 뒤 블로그로 돌아와요.</p>
      <button class="btn primary" style="width:100%" id="memberLogin">회원 로그인</button>
      ${blog.allow_signup ? '<p class="panel-foot">아직 회원이 아니신가요? <button type="button" class="link link-btn" id="memberSignup">회원가입</button></p>' : ''}
      <details class="legacy-login">
        <summary>관리자 · 예전 블로그 계정으로 로그인</summary>
        <form id="loginForm">
          <label class="field"><span>아이디</span><input name="username" autocomplete="username" required></label>
          <label class="field"><span>비밀번호</span><input type="password" name="password" autocomplete="current-password" required></label>
          <button class="btn" style="width:100%">로그인</button>
        </form>
      </details>
    </section>`;
  $('#memberLogin').onclick = () => goAuth('login');
  if ($('#memberSignup')) $('#memberSignup').onclick = () => goAuth('register');
  $('#loginForm').onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api('login', { method: 'POST', body: Object.fromEntries(new FormData(e.target)) });
      await loadBlog();
      toast(`${blog.user.nickname}님, 반가워요!`);
      afterLogin();
    } catch (err) { toast(err.message); }
  };
}

// 회원가입은 PHP 회원 페이지로
function renderSignup() {
  if (blog.user) { location.hash = '#/'; return; }
  goAuth('register');
}

// PHP에서 로그인하고 돌아온 곳: 입장권(t)으로 블로그 로그인
async function renderSso(ticket) {
  // 주소창·방문 기록에서 입장권을 바로 지움
  history.replaceState(null, '', location.pathname + '#/sso');
  if (!ticket) { location.hash = '#/'; return; }
  main.innerHTML = '<div class="empty">로그인하는 중…</div>';
  const redeem = async (password) => {
    const res = await fetch('/api/sso', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticket, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      await loadBlog();
      toast(data.new ? `${blog.user.nickname}님의 블로그가 생겼어요! 🎉` : `${blog.user.nickname}님, 반가워요!`);
      if (data.new) { try { sessionStorage.removeItem('afterLogin'); } catch { /* 무시 */ } location.hash = '#/manage/info'; } else afterLogin();
      return;
    }
    if (data.need_link) {
      // 같은 아이디의 예전 블로그 계정: 그 비밀번호를 알아야 연결
      main.innerHTML = `
        <form class="panel card" id="linkForm">
          <h1>블로그 계정 연결</h1>
          <p>블로그에 <b>@${esc(data.username)}</b> 계정이 이미 있어요. 그 계정의 <b>예전 블로그 비밀번호</b>를 입력하면 회원 계정과 연결돼요. 한 번만 하면 돼요.</p>
          ${password ? `<p class="error-text" role="alert">${esc(data.error)}</p>` : ''}
          <label class="field"><span>예전 블로그 비밀번호</span><input type="password" name="password" autocomplete="current-password" required autofocus></label>
          <button class="btn primary" style="width:100%">연결하고 로그인</button>
          <p class="panel-foot"><a class="link" href="#/">취소</a></p>
        </form>`;
      $('#linkForm').onsubmit = (e) => { e.preventDefault(); redeem(e.target.password.value); };
      return;
    }
    main.innerHTML = `<div class="empty">${esc(data.error || '로그인하지 못했어요.')}<br><button class="btn" id="retry" style="margin-top:12px">다시 로그인</button></div>`;
    $('#retry').onclick = () => goAuth('login');
  };
  await redeem('');
}

async function renderMe() {
  if (!blog.user) { location.hash = '#/login'; return; }
  const u = blog.user;
  const isOwner = u.role === 'admin';
  main.innerHTML = `
    <div class="panel">
      <h1>내 정보</h1>
      <div class="me-links">
        <a class="btn" href="#/@${esc(u.username)}">내 블로그</a>
        <a class="btn" href="#/manage">블로그 관리</a>
        ${isOwner ? '<a class="btn" href="#/settings">사이트 설정</a>' : ''}
        <button class="btn danger" id="logoutBtn2">로그아웃</button>
      </div>
      <form class="card form-card" id="meForm">
        <label class="field"><span>아이디</span><input value="${esc(u.username)}" disabled></label>
        <label class="field"><span>닉네임</span><input name="nickname" value="${esc(u.nickname)}" required minlength="2" maxlength="20"></label>
        ${isOwner ? '<p class="hint">관리자 비밀번호는 서버를 켤 때 BLOG_PASSWORD로 정해요.</p>'
          : u.auth_uid ? `<p class="hint">비밀번호·자기소개·회원 탈퇴는 <a class="link" href="${esc(blog.auth_url)}/profile.php" target="_blank" rel="noopener">회원 페이지 내 정보 수정</a>에서 해요. 회원 페이지에서 바꾼 닉네임은 다음에 블로그로 들어올 때 반영돼요.</p>` : `
        <label class="field"><span>현재 비밀번호</span><input type="password" name="current_password" autocomplete="current-password"></label>
        <label class="field"><span>새 비밀번호</span><input type="password" name="new_password" autocomplete="new-password" minlength="8">
          <small class="hint">바꿀 때만 입력하세요</small></label>`}
        <button class="btn primary" style="width:100%">저장</button>
      </form>
    </div>`;
  $('#logoutBtn2').onclick = logout;
  $('#meForm').onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api('me', { method: 'PUT', body: Object.fromEntries(new FormData(e.target)) });
      await loadBlog();
      toast('저장했습니다.');
      renderMe();
    } catch (err) { toast(err.message); }
  };
  renderPortalSidebar();
}

// 003: 사이트 설정의 '공개 주소'·'가입 현황' 상자. 회원 서버 상태는 서명된 브리지로 받아 옴(IP는 없음)
const SNS_LABEL = { kakao: '카카오', naver: '네이버', google: '구글' };

function deployBox(st) {
  if (!st) return '<p class="hint">상태를 불러오지 못했어요. 화면을 새로 고쳐 주세요.</p>';
  const d = st.deploy;
  const a = st.auth;
  const rows = [
    ['실행 모드', d.public_mode ? '공개 모드 (https)' : '개발 모드'],
    ['블로그 주소', `<code>${esc(d.blog_url)}</code>`],
    ['회원 서버 주소', `<code>${esc(d.auth_url)}</code>`],
  ];
  if (a) {
    rows.push(['SNS 콜백 주소', `<code class="pick">${esc(a.sns.callback_url)}</code>`]);
    rows.push(['키가 등록된 SNS', a.sns.providers.length ? a.sns.providers.map((p) => esc(SNS_LABEL[p] || p)).join(' · ') : '없음']);
  }
  let warn = '';
  if (!a) warn = '<p class="hint warn" role="status">회원 서버에 연결할 수 없어 SNS 정보를 불러오지 못했어요.</p>';
  else if (a.public_mode !== d.public_mode) {
    warn = '<p class="hint warn" role="status">두 서버의 공개 모드 설정이 달라요. 설정 파일을 확인하고 블로그 서버를 다시 켜 주세요.</p>';
  }
  return `<dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>${warn}
    <p class="hint">SNS 개발자 콘솔에는 위 콜백 주소를 그대로 등록하세요. 키 값은 화면에 보이지 않아요.</p>`;
}

function signupBox(st) {
  const s = st && st.auth && st.auth.signups;
  if (!s) return '<p class="hint warn" role="status">회원 서버에 연결할 수 없어 가입 현황을 불러오지 못했어요.</p>';
  const b = s.blocked;
  return `<p class="signup-stats">새 가입 <strong>${Number(s.created)}</strong>
      · 막힘: 한 곳에서 너무 많이 ${Number(b.limit_ip)} · 전체 한도 ${Number(b.limit_site)} · 자동 가입 의심 ${Number(b.bot)}</p>
    ${s.site_limited_now ? `<p class="hint warn" role="status">지금 사이트 전체 가입 제한이 걸려 있어요(1시간 ${Number(s.limits.site_per_hour)}개).</p>` : ''}
    <p class="hint">한도: 같은 곳에서 1시간 ${Number(s.limits.per_ip_per_hour)}개, 사이트 전체 1시간 ${Number(s.limits.site_per_hour)}개 (deploy.config.json). 방문자 IP는 보이지 않아요.</p>`;
}

async function renderSettings() {
  const seq = routeSeq;
  if (!blog.is_admin) { location.hash = blog.user ? '#/' : '#/login'; return; }
  const users = await api('users');
  // 회원 서버가 꺼져 있어도 나머지 설정 화면은 그대로 보이게
  const status = await api('admin/status').catch(() => null);
  if (seq !== routeSeq) return;
  main.innerHTML = `
    <div class="panel wide">
    <form id="setForm" class="card form-card">
      <h1>사이트 설정</h1>
      <label class="field"><span>사이트 이름 (맨 위 로고)</span><input name="blog_title" value="${esc(blog.blog_title)}" required></label>
      <label class="field"><span>사이트 소개 (블로그 홈 맨 위)</span><textarea name="blog_desc" rows="2">${esc(blog.blog_desc)}</textarea></label>
      <label class="field"><span>기본 관심 종목 (처음 온 방문자에게 보이는 목록)</span>
        <input name="stock_codes" value="${esc(blog.stock_codes || '')}" placeholder="005930, 000660">
        <small class="hint">6자리 종목코드를 쉼표로 구분해 최대 12개. 방문자는 사이드바에서 자기 목록으로 바꿀 수 있어요 (예: 삼성전자 005930, SK하이닉스 000660, NAVER 035420)</small></label>
      <fieldset class="field key-box">
        <legend>🍽 맛집 검색 API 키</legend>
        <p class="hint">키는 서버에만 저장되고 화면에는 다시 보이지 않아요. 바꿀 때만 새로 입력하고, 지우려면 - 를 입력하세요.</p>
        <label class="field"><span>네이버 Client ID ${blog.food_ready?.naver ? '<em class="ok">등록됨</em>' : ''}</span>
          <input name="naver_client_id" autocomplete="off" placeholder="${blog.food_ready?.naver ? '등록됨 (바꿀 때만 입력)' : '장소 검색·블로그 후기용'}"></label>
        <label class="field"><span>네이버 Client Secret</span>
          <input name="naver_client_secret" type="password" autocomplete="new-password" placeholder="${blog.food_ready?.naver ? '등록됨 (바꿀 때만 입력)' : ''}"></label>
        <label class="field"><span>구글 Places API 키 ${blog.food_ready?.google ? '<em class="ok">등록됨</em>' : ''}</span>
          <input name="google_places_key" type="password" autocomplete="new-password" placeholder="${blog.food_ready?.google ? '등록됨 (바꿀 때만 입력)' : '평점·방문자 리뷰용'}"></label>
      </fieldset>
      <label class="switch field"><input type="checkbox" name="allow_signup" ${blog.allow_signup ? 'checked' : ''}> 누구나 회원가입해서 블로그를 만들 수 있게 하기</label>
      <button class="btn primary" style="width:100%">저장</button>
    </form>
    <section class="card form-card" aria-labelledby="deployTitle">
      <h2 class="side-title" id="deployTitle">공개 주소</h2>
      ${deployBox(status)}
    </section>
    <section class="card form-card" aria-labelledby="signupTitle">
      <h2 class="side-title" id="signupTitle">가입 현황 (최근 24시간)</h2>
      ${signupBox(status)}
    </section>
    <section class="card form-card">
      <h2 class="side-title">회원 ${users.length}명</h2>
      <table class="user-table">
        <thead><tr><th>닉네임</th><th>아이디</th><th>글</th><th>가입일</th><th></th></tr></thead>
        <tbody>${users.map((u) => `
          <tr><td><a class="link" href="#/@${esc(u.username)}">${esc(u.nickname)}</a>${u.role === 'admin' ? ' <span class="member-badge">관리자</span>' : ''}</td>
            <td>${esc(u.username)}</td><td>${u.post_count}</td><td>${fmtDate(u.created_at)}</td>
            <td>${u.role === 'admin' ? '' : `<button class="btn small danger" data-del-user="${u.id}" data-name="${esc(u.nickname)}">탈퇴</button>`}</td></tr>`).join('')}
        </tbody>
      </table>
    </section>
    </div>`;
  const form = $('#setForm');
  form.onsubmit = async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(form));
    body.allow_signup = form.allow_signup.checked;
    try {
      await api('blog', { method: 'PUT', body });
      await loadBlog();
      toast('저장했습니다.');
      renderSettings();
    } catch (err) { toast(err.message); }
  };
  main.querySelectorAll('[data-del-user]').forEach((b) => (b.onclick = async () => {
    if (!confirm(`'${b.dataset.name}' 회원을 탈퇴시킬까요?\n이 회원의 블로그 글과 댓글도 모두 지워지고, 되돌릴 수 없어요.`)) return;
    try {
      await api('users/' + b.dataset.delUser, { method: 'DELETE' });
      toast('탈퇴 처리했습니다.');
      await loadBlog();
      renderSettings();
    } catch (err) { toast(err.message); }
  }));
  renderPortalSidebar();
}

// ---------- 라우터 ----------
let routeSeq = 0; // 화면을 바꿀 때마다 1씩 (늦게 도착한 응답이 새 화면을 덮지 않게)
async function render() {
  routeSeq += 1;
  const seq = routeSeq;
  leaveGuard = null;
  document.body.classList.remove('editor-mode');
  const [path, query] = (location.hash.slice(1) || '/').split('?');
  const qs = new URLSearchParams(query);
  const page = qs.get('page') || 1;
  const parts = path.split('/').filter(Boolean).map(decodeURIComponent);
  document.title = blog.blog_title;
  stopReadingTools();
  if (lightbox && lightbox.open) lightbox.close();
  renderTypeNav(null);
  // 블로그 안에서는 그 블로그만 검색
  const inBlog = parts[0] && parts[0].startsWith('@');
  // 블로그 화면·글 화면이 아니면 그리기 전에 기본색으로 (블로그·글 화면은 응답을 받은 뒤 그 블로그 색으로)
  if (!inBlog && parts[0] !== 'post') setSkin('');
  $('#searchInput').placeholder = inBlog ? '이 블로그 검색' : '검색';
  try {
    if (inBlog) {
      await renderBlog(parts[0].slice(1), {
        type: qs.get('type') || undefined, category: qs.get('category') || undefined,
        tag: qs.get('tag') || undefined, q: qs.get('q') || undefined, page,
      });
    } else {
      switch (parts[0]) {
        case undefined: await renderPortal({ page }); break;
        case 'insight': case 'faq': case 'glossary': case 'daily':
          await renderPortal({ type: parts[0], page }); break;
        case 'tag': await renderPortal({ tag: parts[1], page }); break;
        case 'search': await renderPortal({ q: parts[1], page }); break;
        case 'post': await renderPost(parts[1]); break;
        case 'write': await renderEditor(null, qs.get('type')); break;
        case 'edit': await renderEditor(parts[1]); break;
        case 'manage': await renderManage(parts[1] || '', qs); break;
        case 'login': renderLogin(); renderPortalSidebar(); break;
        case 'food': cur = null; await renderFood(qs.get('q')); if (seq === routeSeq) renderPortalSidebar(); break;
        case 'neighbors': await renderNeighbors(page); break;
        case 'signup': renderSignup(); break;
        case 'sso': await renderSso(qs.get('t')); if (seq === routeSeq) renderPortalSidebar(); break;
        case 'me': await renderMe(); break;
        case 'settings': await renderSettings(); break;
        default: main.innerHTML = '<div class="empty">페이지를 찾을 수 없습니다.</div>';
      }
    }
  } catch (err) {
    if (seq !== routeSeq) return; // 늦게 실패한 이전 화면이 새 화면을 덮지 않게
    setSkin(''); // 없는 블로그·글이면 기본색
    main.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
  if (seq === routeSeq) window.scrollTo(0, 0);
}

$('#searchForm').onsubmit = (e) => {
  e.preventDefault();
  const q = $('#searchInput').value.trim();
  if (!q) return;
  const path = location.hash.slice(1).split('?')[0].split('/').filter(Boolean)[0] || '';
  location.hash = path.startsWith('@') ? blogHref(path.slice(1), { q }) : '#/search/' + enc(q);
};

// ---------- 화면 모드: 시스템 → 라이트 → 다크 순서로 바뀜 ----------
const THEMES = {
  system: { icon: '🖥', label: '시스템 설정 따라가기' },
  light: { icon: '☀️', label: '라이트 모드' },
  dark: { icon: '🌙', label: '다크 모드' },
};
const THEME_ORDER = ['system', 'light', 'dark'];
let theme = 'system';
try { theme = localStorage.getItem('theme') || 'system'; } catch { /* 무시 */ }
function drawThemeBtn() {
  const b = $('#themeBtn');
  b.textContent = THEMES[theme].icon;
  b.title = `화면 모드: ${THEMES[theme].label} (누르면 바뀜)`;
}
$('#themeBtn').onclick = () => {
  theme = THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length];
  try { localStorage.setItem('theme', theme); } catch { /* 무시 */ }
  window.applyTheme(theme);
  drawThemeBtn();
  toast(`${THEMES[theme].icon} ${THEMES[theme].label}`);
};
drawThemeBtn();

// 화면 이동: 작성 중인 화면이면 먼저 묻고, 취소하면 주소만 되돌림 (다시 그리지 않음)
let lastHash = location.hash;
let revertingHash = false;
window.addEventListener('hashchange', () => {
  if (revertingHash) { revertingHash = false; return; }
  if (leaveGuard && !leaveGuard()) { revertingHash = true; location.hash = lastHash; return; }
  lastHash = location.hash;
  render();
});
window.addEventListener('beforeunload', (e) => {
  if (leaveGuard && !leaveGuard(true)) { e.preventDefault(); e.returnValue = ''; }
});
loadBlog().then(() => {
  render();
  // 회원 페이지까지 함께 로그아웃하고 돌아왔으면 안내
  try {
    if (sessionStorage.getItem('justLoggedOut')) { sessionStorage.removeItem('justLoggedOut'); toast('로그아웃했습니다. (회원 페이지도 함께)'); }
  } catch { /* 무시 */ }
});

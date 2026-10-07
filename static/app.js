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

function renderMd(md) {
  const html = DOMPurify.sanitize(marked.parse(md || ''));
  const box = document.createElement('div');
  box.innerHTML = html;
  box.querySelectorAll('pre code').forEach((el) => window.hljs && hljs.highlightElement(el));
  box.querySelectorAll('img').forEach((img) => (img.loading = 'lazy'));
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
    <section class="side-box">
      <h2 class="side-title">글 종류</h2>
      <ul class="cat-list">
        ${b.type_counts.map((t) => `
          <li><a href="${blogHref(b.username, { type: t.key, category: activeCat })}" class="${activeType === t.key ? 'on' : ''}">
            ${TYPE_ICON[t.key]} ${esc(t.name)} <span class="count">(${t.count})</span></a></li>`).join('')}
      </ul>
    </section>
    ${b.tags.length ? `
    <section class="side-box">
      <h2 class="side-title">태그</h2>
      <div class="tag-cloud">${b.tags.map((t) => `<a class="tag" href="${blogHref(b.username, { tag: t.name })}">#${esc(t.name)}</a>`).join('')}</div>
    </section>` : ''}
    ${b.recent_comments.length ? `
    <section class="side-box recent-c">
      <h2 class="side-title">최근 댓글</h2>
      ${b.recent_comments.map((c) => `<a href="#/post/${c.post_id}">${esc(c.content)} <span class="count">· ${esc(c.name)}</span></a>`).join('')}
    </section>` : ''}
    <section class="side-box">
      <h2 class="side-title">방문자</h2>
      ${statsHtml(b.stats)}
    </section>`;
}

// 블로그 위쪽 배너 (블로그 이름·주인·소개)
const blogBanner = (b, small = false) => `
  <header class="blog-banner card ${small ? 'small' : 'has-room'}">
    ${small ? '' : `<div class="banner-room">${miniroomSvg(b.room_bg, b.room_char)}
      ${b.is_owner ? '<a class="room-edit" href="#/manage/room">미니룸 꾸미기</a>' : ''}</div>`}
    <div class="banner-row">
    <a class="banner-avatar" href="#/@${esc(b.username)}">${avatarOf(b)}</a>
    <div class="banner-text">
      <a class="banner-title" href="#/@${esc(b.username)}">${esc(b.blog_title)}</a>
      <div class="banner-meta">${esc(b.nickname)} · 글 ${b.total_posts}개 · 이웃 <span class="nb-count">${b.neighbor_count || 0}</span>명</div>
      ${!small && b.blog_desc ? `<p class="banner-desc">${esc(b.blog_desc)}</p>` : ''}
    </div>
    ${b.is_owner && !small ? `<div class="banner-actions">
      <a class="btn small primary" href="#/write">글쓰기</a><a class="btn small" href="#/manage">관리</a></div>` : ''}
    ${!b.is_owner ? `<div class="banner-actions"><button type="button" class="btn small nb-btn ${b.is_neighbor ? 'on' : ''}" data-nb="${esc(b.username)}" aria-pressed="${!!b.is_neighbor}">${b.is_neighbor ? '✓ 이웃' : '+ 이웃 추가'}</button></div>` : ''}
    </div>
  </header>`;

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

// 카드 컴포넌트: 썸네일(있으면) → 종류·카테고리 → 제목 → 요약 → 블로그·날짜·댓글·조회
const postCardHtml = (p, showBlog = true) => `
  <a class="card post-card" href="#/post/${p.id}">
    ${p.thumbnail ? `<img class="card-thumb" src="${esc(p.thumbnail)}" alt="" loading="lazy">` : ''}
    <div class="card-body">
      <div class="labels">${postLabels(p)}</div>
      <h2 class="card-title">${p.is_public ? '' : '<span class="badge">비공개</span>'}${esc(p.title)}</h2>
      <p class="card-excerpt">${esc(p.excerpt)}</p>
      <div class="meta card-meta">
        ${showBlog ? `<span class="card-blog">${avatarOf({ avatar: p.author_avatar, nickname: p.author_nickname }, 'mini')}${esc(p.author_blog_title || p.author_nickname || '')}</span>` : ''}
        <span>${fmtDate(p.created_at)}</span><span>댓글 ${p.comment_count}</span><span>조회 ${p.views}</span>${p.like_count ? `<span class="like-n">♥ ${p.like_count}</span>` : ''}</div>
    </div>
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
document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-jump]');
  if (!a) return;
  e.preventDefault();
  document.getElementById(a.dataset.jump)?.scrollIntoView({ behavior: 'smooth' });
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
  return `<div class="card-grid">${data.posts.map((p) => postCardHtml(p, showBlog)).join('')}</div>`;
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
  cur = null;
  const params = { page };
  if (tag) params.tag = tag;
  if (q) params.q = q;
  const showBlogs = !type && !tag && !q && Number(page) === 1;
  const [data, blogs] = await Promise.all([fetchPosts(params, type), showBlogs ? api('blogs?size=12') : null]);
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
  cur = null;
  if (!blog.user) { needLogin('이웃 새 글은 로그인하면 볼 수 있어요.'); return; }
  const [list, data] = await Promise.all([api('neighbors'), api(`posts?neighbors=1&page=${page}`)]);
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
  const b = await loadCur(username, Number(page) === 1 && !type && !category && !tag && !q);
  document.title = b.blog_title;
  const params = { page, blog: b.username };
  if (category) params.category = category; // '-'는 미분류
  if (tag) params.tag = tag;
  if (q) params.q = q;
  const data = await fetchPosts(params, type);
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
async function renderPost(id) {
  const p = await api('posts/' + id);
  const b = await loadCur(p.author_username);
  document.title = `${p.title} - ${b.blog_title}`;
  const isFaq = p.type === 'faq';
  main.innerHTML = `
    ${blogBanner(b, true)}
    <article class="article t-${p.type}">
      <header class="article-head">
        <div class="labels">
          <a href="${blogHref(b.username, { type: p.type })}">${postLabels(p)}</a>
        </div>
        <h1>${isFaq ? '<span class="q">Q</span>' : ''}${p.is_public ? '' : '<span class="badge">비공개</span>'}${esc(p.title)}</h1>
        <div class="row">
          <div class="meta"><a class="author-link" href="#/@${esc(b.username)}">${esc(p.author_nickname || '알 수 없음')}</a><span>${fmtDate(p.created_at, true)}</span><span>조회 ${p.views}</span></div>
          ${p.can_edit ? `<div class="admin-tools">
            <a class="btn small" href="#/edit/${p.id}">수정</a>
            <button class="btn small danger" id="delPost">삭제</button></div>` : ''}
        </div>
      </header>
      ${isFaq ? '<div class="answer-label"><span class="a">A</span> 답변</div>' : ''}
      <div class="content ${p.type === 'glossary' ? 'definition' : ''}">${renderMd(p.content)}</div>
      ${p.tags.length ? `<div class="article-tags">${p.tags.map((t) => `<a class="tag" href="${blogHref(b.username, { tag: t })}">#${esc(t)}</a>`).join('')}</div>` : ''}
      <div class="like-row">
        <button type="button" class="like-btn ${p.liked ? 'on' : ''}" id="likeBtn" aria-pressed="${p.liked}">
          <span class="heart" aria-hidden="true">${p.liked ? '♥' : '♡'}</span> 공감 <b id="likeN">${p.like_count}</b></button>
      </div>
      <a class="author-card" href="#/@${esc(b.username)}">
        ${avatarOf(b)}
        <div><b>${esc(b.blog_title)}</b><div class="desc">${esc(b.nickname)}${b.blog_desc ? ' · ' + esc(b.blog_desc) : ''} · 블로그 가기 →</div></div>
      </a>
      ${p.related.length ? `<section class="related"><h3><em>${esc(catName(p.category))}</em> 카테고리의 다른 ${esc(typeName(p.type))} 글</h3><ul>
        ${p.related.map((r) => `<li><a href="#/post/${r.id}">${esc(r.title)}</a> <span class="count">${fmtDate(r.created_at)}</span></li>`).join('')}
      </ul></section>` : ''}
      <nav class="prevnext">
        ${p.prev ? `<a href="#/post/${p.prev.id}"><small>← 이전 글</small><span>${esc(p.prev.title)}</span></a>` : ''}
        ${p.next ? `<a class="next" href="#/post/${p.next.id}"><small>다음 글 →</small><span>${esc(p.next.title)}</span></a>` : ''}
      </nav>
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
  renderTypeNav(null);
  renderBlogSidebar(b, p.category || '-', p.type);
  renderComments(id);
}

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

async function renderEditor(id, defaultType) {
  if (!blog.user) { needLogin('글을 쓰려면 로그인하세요.'); return; }
  const p = id ? await api('posts/' + id)
    : { type: EDITOR_HINTS[defaultType] ? defaultType : 'insight', title: '', content: '', category: '', tags: [], is_public: true };
  if (id && !p.can_edit) { main.innerHTML = '<div class="empty">내가 쓴 글만 고칠 수 있어요.</div>'; return; }
  // 카테고리는 글쓴이 블로그의 카테고리 (관리자가 남의 글을 고칠 때는 그 사람 블로그 기준)
  const owner = id && p.author_username !== blog.user.username ? await api('blogs/' + enc(p.author_username)) : blog.user;
  const cats = owner.categories;
  main.innerHTML = `
    <form class="editor" id="editor">
      <div class="editor-blog">📝 <b>${esc(owner.blog_title)}</b>에 ${id ? '쓴 글 고치기' : '새 글 쓰기'}</div>
      <div class="type-pick" role="radiogroup" aria-label="글 종류">
        ${blog.types.map((t) => `
          <label class="type-opt"><input type="radio" name="type" value="${t.key}" ${p.type === t.key ? 'checked' : ''}>
            <span>${TYPE_ICON[t.key]} ${esc(t.name)}</span></label>`).join('')}
      </div>
      <input class="title-input" name="title" placeholder="${esc(EDITOR_HINTS[p.type].title)}" value="${esc(p.title)}" required>
      <div class="opts">
        <div class="field" style="margin:0"><select name="category" aria-label="카테고리">
          <option value="">카테고리 선택</option>
          ${cats.map((c) => `<option value="${esc(c)}" ${p.category === c ? 'selected' : ''}>${esc(c)}</option>`).join('')}
        </select>
        ${!cats.length ? '<small class="hint">카테고리가 없어요. <a class="link" href="#/manage/categories">만들기</a></small>' : ''}</div>
        <div class="field" style="margin:0"><input name="tags" placeholder="태그 (쉼표로 구분)" value="${esc(p.tags.join(', '))}"></div>
        <label class="switch"><input type="checkbox" name="is_public" ${p.is_public ? 'checked' : ''}> 공개</label>
      </div>
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
          <textarea name="content" id="mdInput" placeholder="${esc(EDITOR_HINTS[p.type].content)}">${esc(p.content)}</textarea>
          <div class="preview content" id="preview"></div>
        </div>
      </div>
      <div class="editor-foot">
        <span class="hint" id="saveHint">${id ? '' : '작성 중인 글은 이 브라우저에 자동 저장됩니다.'}</span>
        <div style="display:flex; gap:8px">
          <a class="btn" href="${id ? '#/post/' + id : '#/@' + esc(blog.user.username)}">취소</a>
          <button class="btn primary" id="publishBtn">${id ? '수정 완료' : '발행'}</button>
        </div>
      </div>
    </form>`;

  const form = $('#editor');
  const ta = $('#mdInput');
  const preview = $('#preview');
  const area = $('#editArea');
  const draftKey = 'draft-' + blog.user.username;

  if (!id) {
    try {
      const d = JSON.parse(localStorage.getItem(draftKey) || 'null');
      if (d && (d.title || d.content) && confirm('작성 중이던 글이 있어요. 불러올까요?')) {
        if (d.type) form.elements.type.value = d.type;
        form.title.value = d.title; ta.value = d.content; form.category.value = d.category; form.tags.value = d.tags;
      }
    } catch { /* 저장소를 쓸 수 없으면 무시 */ }
  }

  const update = () => (preview.innerHTML = renderMd(ta.value));
  let saveTimer;
  const saveDraft = () => {
    if (id) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try {
        localStorage.setItem(draftKey, JSON.stringify({ type: form.elements.type.value, title: form.title.value, content: ta.value, category: form.category.value, tags: form.tags.value }));
        $('#saveHint').textContent = `임시 저장됨 ${fmtDate(new Date().toISOString(), true).slice(-5)}`;
      } catch { /* 무시 */ }
    }, 600);
  };
  // 글 종류에 맞춰 안내 문구와 카테고리 선택지 바꾸기 (일상은 카테고리 없이도 가능)
  const syncType = () => {
    const t = form.elements.type.value;
    form.title.placeholder = EDITOR_HINTS[t].title;
    ta.placeholder = EDITOR_HINTS[t].content;
    const optional = t === 'daily' || !cats.length;
    form.category.options[0].textContent = optional ? '카테고리 없음' : '카테고리 선택';
    form.category.required = !optional;
  };
  form.querySelectorAll('input[name="type"]').forEach((r) => r.addEventListener('change', () => { syncType(); saveDraft(); }));
  form.category.addEventListener('change', saveDraft);
  syncType();
  ta.addEventListener('input', () => { update(); saveDraft(); });
  form.title.addEventListener('input', saveDraft);
  update();

  function insert(before, after = '') {
    const { selectionStart: s, selectionEnd: e, value } = ta;
    const sel = value.slice(s, e);
    ta.setRangeText(before + sel + after, s, e, 'end');
    if (!sel) ta.selectionStart = ta.selectionEnd = s + before.length;
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

  form.onsubmit = async (e) => {
    e.preventDefault();
    const body = {
      type: form.elements.type.value, title: form.title.value, content: ta.value, category: form.category.value,
      tags: form.tags.value, is_public: form.is_public.checked,
    };
    $('#publishBtn').disabled = true;
    try {
      const r = await api(id ? 'posts/' + id : 'posts', { method: id ? 'PUT' : 'POST', body });
      if (!id) try { localStorage.removeItem(draftKey); } catch { /* 무시 */ }
      toast(id ? '수정했습니다.' : '발행했습니다! 🎉');
      cur = null;
      location.hash = '#/post/' + r.id;
    } catch (err) {
      toast(err.message);
      $('#publishBtn').disabled = false;
    }
  };
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
  ['', '📊 홈'], ['posts', '📝 글'], ['comments', '💬 댓글'], ['categories', '🗂 카테고리'], ['room', '🏠 미니룸'], ['info', '🏷 블로그 정보'],
];

async function renderManage(tab, qs) {
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
  const fn = { '': manageHome, posts: managePosts, comments: manageComments, categories: manageCategories, room: manageRoom, info: manageInfo }[tab];
  if (!fn) { body.innerHTML = '<div class="empty">없는 메뉴예요.</div>'; return; }
  await fn(body, qs);
  // 사이드바: 내 블로그
  renderBlogSidebar(await api('blogs/' + enc(u.username)), null, null);
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
          : u.auth_uid ? `<p class="hint">비밀번호와 자기소개는 <a class="link" href="${esc(blog.auth_url)}/index.php" target="_blank" rel="noopener">회원 페이지</a>에서 관리해요.</p>` : `
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

async function renderSettings() {
  if (!blog.is_admin) { location.hash = blog.user ? '#/' : '#/login'; return; }
  const users = await api('users');
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
async function render() {
  const [path, query] = (location.hash.slice(1) || '/').split('?');
  const qs = new URLSearchParams(query);
  const page = qs.get('page') || 1;
  const parts = path.split('/').filter(Boolean).map(decodeURIComponent);
  document.title = blog.blog_title;
  renderTypeNav(null);
  // 블로그 안에서는 그 블로그만 검색
  const inBlog = parts[0] && parts[0].startsWith('@');
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
        case 'food': cur = null; await renderFood(qs.get('q')); renderPortalSidebar(); break;
        case 'neighbors': await renderNeighbors(page); break;
        case 'signup': renderSignup(); break;
        case 'sso': await renderSso(qs.get('t')); renderPortalSidebar(); break;
        case 'me': await renderMe(); break;
        case 'settings': await renderSettings(); break;
        default: main.innerHTML = '<div class="empty">페이지를 찾을 수 없습니다.</div>';
      }
    }
  } catch (err) {
    main.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
  window.scrollTo(0, 0);
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

window.addEventListener('hashchange', render);
loadBlog().then(() => {
  render();
  // 회원 페이지까지 함께 로그아웃하고 돌아왔으면 안내
  try {
    if (sessionStorage.getItem('justLoggedOut')) { sessionStorage.removeItem('justLoggedOut'); toast('로그아웃했습니다. (회원 페이지도 함께)'); }
  } catch { /* 무시 */ }
});

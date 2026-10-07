'use strict';
// 맛집 찾기 화면 (#/food). app.js의 api·esc·enc·main·blog·renderTypeNav를 함께 씀
// 평점·방문자 리뷰: 구글 Places API / 블로그 후기·장소 검색: 네이버 검색 API (키는 블로그 설정에서 등록)

const stars = (r) => {
  if (r == null) return '';
  const full = Math.round(r * 2) / 2;
  return `<span class="stars" aria-label="5점 만점에 ${r}점">${'★'.repeat(Math.floor(full))}${full % 1 ? '⯪' : ''}${'☆'.repeat(5 - Math.ceil(full))}</span>`;
};
const naverDate = (d) => (d && d.length === 8 ? `${d.slice(0, 4)}. ${d.slice(4, 6)}. ${d.slice(6)}.` : '');
const mapButtons = (links) => `
  <div class="food-maps">
    <a class="btn small" href="${esc(links.naver)}" target="_blank" rel="noopener">네이버 지도</a>
    <a class="btn small" href="${esc(links.kakao)}" target="_blank" rel="noopener">카카오맵</a>
    <a class="btn small" href="${esc(links.google)}" target="_blank" rel="noopener">구글 지도</a>
  </div>`;

async function renderFood(query) {
  renderTypeNav('food');
  const ready = blog.food_ready || {};
  main.innerHTML = `
    <div class="list-head"><h1>🍽 맛집 찾기</h1></div>
    <p class="intro">가고 싶은 식당을 검색하면 평점, 방문자 리뷰, 블로그 후기를 한 번에 볼 수 있어요.</p>
    <form class="food-search" id="foodForm">
      <input name="q" type="search" placeholder="예: 강남역 파스타, 을지로 노가리" value="${esc(query || '')}" required aria-label="식당 검색">
      <button class="btn primary">검색</button>
    </form>
    ${!ready.naver && !ready.google ? `<div class="card food-setup">
      <b>아직 맛집 검색이 연결되지 않았어요.</b>
      <p>${blog.is_admin
        ? '<a class="link" href="#/settings">블로그 설정</a>에서 네이버 검색 API 키(장소·블로그 후기)와 구글 Places API 키(평점·리뷰)를 등록하면 바로 쓸 수 있어요.'
        : '블로그 주인이 API 키를 등록하면 쓸 수 있어요. 그동안은 아래 지도 링크로 찾아보세요.'}</p></div>` : ''}
    <div id="foodResults"></div>`;
  $('#foodForm').onsubmit = (e) => {
    e.preventDefault();
    const q = e.target.q.value.trim();
    if (q) location.hash = '#/food?q=' + enc(q);
  };
  if (!query) return;
  const box = $('#foodResults');
  if (!blog.user) {
    box.innerHTML = '<div class="empty">맛집 검색은 회원만 쓸 수 있어요. <a class="link" href="#/login">로그인</a></div>';
    return;
  }
  box.innerHTML = '<div class="empty">찾는 중…</div>';
  try {
    const d = await api('food?q=' + enc(query));
    box.innerHTML = `
      ${d.errors.map((m) => `<p class="food-error">⚠️ ${esc(m)}</p>`).join('')}
      ${d.places.length ? `<div class="food-list">${d.places.map((p, i) => `
        <article class="card food-place" data-i="${i}">
          <button type="button" class="food-head" aria-expanded="false">
            <span class="food-title"><b>${esc(p.name)}</b><small>${esc(p.category || '')}</small></span>
            ${p.rating != null ? `<span class="food-rating">${stars(p.rating)} <b>${p.rating}</b> <small>(${(p.count || 0).toLocaleString()})</small></span>` : ''}
            <span class="food-addr">📍 ${esc(p.address || '')}${p.phone ? ' · ☎ ' + esc(p.phone) : ''}</span>
            <span class="food-more">평점·후기 보기 ▾</span>
          </button>
          <div class="food-detail" hidden></div>
        </article>`).join('')}</div>`
        : (d.naver || d.google) && !d.errors.length ? '<div class="empty">검색 결과가 없어요. 지역 이름을 함께 넣어 보세요.</div>' : ''}
      <p class="hint food-maps-label">지도 앱에서 더 찾아보기</p>${mapButtons(d.links)}`;
    box.querySelectorAll('.food-place').forEach((card) => {
      const p = d.places[card.dataset.i];
      card.querySelector('.food-head').onclick = () => toggleFood(card, p);
    });
    if (d.places.length === 1) toggleFood(box.querySelector('.food-place'), d.places[0]);
  } catch (err) {
    box.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
}

async function toggleFood(card, p) {
  const detail = card.querySelector('.food-detail');
  const opening = detail.hidden;
  detail.hidden = !opening;
  card.querySelector('.food-head').setAttribute('aria-expanded', opening);
  card.querySelector('.food-more').textContent = opening ? '접기 ▴' : '평점·후기 보기 ▾';
  if (!opening || detail.dataset.loaded) return;
  detail.innerHTML = '<p class="w-msg">평점과 후기를 불러오는 중…</p>';
  const ready = blog.food_ready || {};
  try {
    const d = await api(`food/detail?q=${enc(p.name)}&address=${enc(p.address || '')}`);
    detail.dataset.loaded = '1';
    const g = d.google;
    detail.innerHTML = `
      ${d.errors.map((m) => `<p class="food-error">⚠️ ${esc(m)}</p>`).join('')}
      <section class="food-sec">
        <h3>⭐ 평점 · 방문자 리뷰 <small>구글 지도</small></h3>
        ${g ? `
          <div class="food-score"><b>${g.rating ?? '-'}</b>${stars(g.rating)}<small>리뷰 ${(g.count || 0).toLocaleString()}개</small>
            ${g.url ? `<a class="link" href="${esc(g.url)}" target="_blank" rel="noopener">구글 지도에서 전체 보기 →</a>` : ''}</div>
          ${g.reviews.length ? `<ul class="food-reviews">${g.reviews.map((r) => `
            <li><div class="r-head">${stars(r.rating)} <b>${esc(r.author)}</b> <small>${esc(r.when)}</small></div>
              <p>${esc(r.text)}</p></li>`).join('')}</ul>` : '<p class="w-msg">아직 리뷰가 없어요.</p>'}`
          : `<p class="w-msg">${ready.google ? '구글 지도에서 이 식당을 찾지 못했어요.' : '구글 Places API 키를 등록하면 평점과 리뷰가 보여요.'}</p>`}
      </section>
      <section class="food-sec">
        <h3>📝 블로그 후기 <small>네이버 블로그 · "${esc(d.blog_query)}"</small></h3>
        ${d.blogs.length ? `<ul class="food-blogs">${d.blogs.map((b) => `
          <li><a href="${esc(b.link)}" target="_blank" rel="noopener">
            <b>${esc(b.title)}</b><p>${esc(b.summary)}</p><small>${esc(b.blogger)} · ${naverDate(b.date)}</small></a></li>`).join('')}</ul>`
          : `<p class="w-msg">${ready.naver ? '블로그 후기를 찾지 못했어요.' : '네이버 검색 API 키를 등록하면 블로그 후기가 보여요.'}</p>`}
      </section>
      ${mapButtons(d.links)}`;
  } catch (err) {
    detail.innerHTML = `<p class="food-error">⚠️ ${esc(err.message)}</p>`;
  }
}

'use strict';
// 사이드바 맨 위: 오늘 날짜·시간 + 내 위치의 7일 날씨
// 날씨: Open-Meteo (무료, 키 없음) / 지역 이름: BigDataCloud (무료, 키 없음)
// 위치를 못 받으면 서울 날씨를 보여줌
(() => {
  const box = document.getElementById('widget');
  if (!box) return;

  const SEOUL = { lat: 37.57, lon: 126.98, name: '서울', fallback: true };
  const CACHE_KEY = 'weather-v1';
  const CACHE_MS = 30 * 60 * 1000;
  const DAYS = ['일', '월', '화', '수', '목', '금', '토'];

  // WMO 날씨 코드 → [아이콘, 설명]
  const WEATHER = {
    0: ['☀️', '맑음'], 1: ['🌤', '대체로 맑음'], 2: ['⛅️', '구름 조금'], 3: ['☁️', '흐림'],
    45: ['🌫', '안개'], 48: ['🌫', '안개'],
    51: ['🌦', '이슬비'], 53: ['🌦', '이슬비'], 55: ['🌦', '이슬비'], 56: ['🌧', '어는 이슬비'], 57: ['🌧', '어는 이슬비'],
    61: ['🌧', '비'], 63: ['🌧', '비'], 65: ['🌧', '강한 비'], 66: ['🌧', '어는 비'], 67: ['🌧', '어는 비'],
    71: ['🌨', '눈'], 73: ['🌨', '눈'], 75: ['❄️', '많은 눈'], 77: ['🌨', '싸락눈'],
    80: ['🌦', '소나기'], 81: ['🌦', '소나기'], 82: ['⛈', '강한 소나기'], 85: ['🌨', '눈 소나기'], 86: ['🌨', '눈 소나기'],
    95: ['⛈', '뇌우'], 96: ['⛈', '우박 뇌우'], 99: ['⛈', '우박 뇌우'],
  };
  const wx = (code) => WEATHER[code] || ['🌡', '-'];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  box.innerHTML = `
    <div class="w-clock">
      <div class="w-date" id="wDate"></div>
      <div class="w-time" id="wTime"></div>
    </div>
    <div class="w-weather" id="wWeather"><p class="w-msg">날씨를 불러오는 중…</p></div>
    <div class="w-stocks" id="wStocks"><p class="w-msg">주가를 불러오는 중…</p></div>`;

  // ---------- 시계 ----------
  const dateFmt = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' });
  const timeFmt = new Intl.DateTimeFormat('ko-KR', { hour: 'numeric', minute: '2-digit', second: '2-digit' });
  const tick = () => {
    const now = new Date();
    document.getElementById('wDate').textContent = dateFmt.format(now);
    document.getElementById('wTime').textContent = timeFmt.format(now);
  };
  tick();
  setInterval(tick, 1000);

  // ---------- 날씨 ----------
  const readCache = () => {
    try {
      const c = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
      return c && Date.now() - c.at < CACHE_MS ? c : null;
    } catch { return null; }
  };
  const writeCache = (c) => { try { localStorage.setItem(CACHE_KEY, JSON.stringify(c)); } catch { /* 무시 */ } };

  function getPosition() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(SEOUL);
      navigator.geolocation.getCurrentPosition(
        // 정확한 좌표가 필요 없으니 소수 둘째 자리(약 1km)까지만 사용
        (p) => resolve({ lat: +p.coords.latitude.toFixed(2), lon: +p.coords.longitude.toFixed(2) }),
        () => resolve(SEOUL),
        { timeout: 10000, maximumAge: CACHE_MS },
      );
    });
  }

  async function placeName(pos) {
    if (pos.name) return pos.name;
    try {
      const r = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${pos.lat}&longitude=${pos.lon}&localityLanguage=ko`);
      const d = await r.json();
      return [d.city || d.principalSubdivision, d.locality].filter((v, i, a) => v && a.indexOf(v) === i).join(' ') || '내 위치';
    } catch { return '내 위치'; }
  }

  async function fetchWeather(pos) {
    const url = 'https://api.open-meteo.com/v1/forecast'
      + `?latitude=${pos.lat}&longitude=${pos.lon}`
      + '&current=temperature_2m,weather_code,apparent_temperature'
      + '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max'
      + '&timezone=auto&forecast_days=7';
    const r = await fetch(url);
    if (!r.ok) throw new Error('날씨 정보를 가져오지 못했어요.');
    return r.json();
  }

  function draw(c) {
    const { data, place, fallback } = c;
    const [icon, label] = wx(data.current.weather_code);
    const d = data.daily;
    document.getElementById('wWeather').innerHTML = `
      <div class="w-now">
        <span class="w-icon" aria-hidden="true">${icon}</span>
        <div>
          <div class="w-temp">${Math.round(data.current.temperature_2m)}°</div>
          <div class="w-desc">${label} · 체감 ${Math.round(data.current.apparent_temperature)}°</div>
        </div>
      </div>
      <div class="w-place">📍 ${esc(place)}${fallback ? ' <button type="button" class="w-locate" id="wLocate">내 위치로</button>' : ''}</div>
      <ol class="w-week">
        ${d.time.map((t, i) => {
          const day = new Date(t + 'T00:00');
          const [ic, lb] = wx(d.weather_code[i]);
          const rain = d.precipitation_probability_max?.[i];
          return `<li>
            <span class="w-day">${i === 0 ? '오늘' : DAYS[day.getDay()]}</span>
            <span class="w-ic" title="${lb}">${ic}</span>
            <span class="w-rain">${rain != null && rain >= 30 ? `💧${rain}%` : ''}</span>
            <span class="w-range"><span class="w-min">${Math.round(d.temperature_2m_min[i])}°</span> / <span class="w-max">${Math.round(d.temperature_2m_max[i])}°</span></span>
          </li>`;
        }).join('')}
      </ol>
      <p class="w-src">Weather data by Open-Meteo.com</p>`;
    const btn = document.getElementById('wLocate');
    if (btn) btn.onclick = () => load(true);
  }

  async function load(force = false) {
    const cached = !force && readCache();
    if (cached) return draw(cached);
    try {
      const pos = await getPosition();
      const [data, place] = await Promise.all([fetchWeather(pos), placeName(pos)]);
      const c = { at: Date.now(), data, place, fallback: !!pos.fallback };
      if (!pos.fallback) writeCache(c);
      draw(c);
      if (force && pos.fallback) {
        document.querySelector('.w-place').insertAdjacentHTML('beforeend',
          '<p class="w-msg">위치 권한이 꺼져 있어요. 브라우저 주소창의 자물쇠 아이콘에서 위치를 허용해 주세요.</p>');
      }
    } catch (err) {
      document.getElementById('wWeather').innerHTML = `<p class="w-msg">${esc(err.message || '날씨를 불러오지 못했어요.')}</p>`;
    }
  }

  load();
  // 열어 둔 채로 두어도 30분마다 새로 가져오기
  setInterval(() => load(), CACHE_MS);

  // ---------- 주가: 코스피·코스닥 + 내 관심 종목 ----------
  // 장중에는 5초마다, 장 마감 후에는 1분마다 새로고침. 탭을 안 보고 있으면 멈춤.
  // 관심 종목: 로그인하면 계정에, 아니면 이 브라우저에 저장
  const ARROW = { up: '▲', down: '▼', flat: '-' };
  const LOCAL_KEY = 'watchlist-v1';
  const stocksEl = document.getElementById('wStocks');
  const st = { codes: [], loggedIn: false, editing: false, quotes: [], prev: {}, timer: null, names: {} };

  const readLocal = () => { try { return JSON.parse(localStorage.getItem(LOCAL_KEY) || 'null'); } catch { return null; } };
  const writeLocal = (codes) => { try { localStorage.setItem(LOCAL_KEY, JSON.stringify(codes)); } catch { /* 무시 */ } };

  async function loadWatchlist() {
    try {
      const w = await fetch('/api/watchlist').then((r) => r.json());
      st.loggedIn = w.logged_in;
      const local = readLocal();
      st.codes = !w.logged_in && Array.isArray(local) ? local : w.codes;
    } catch { st.codes = readLocal() || []; }
  }

  async function saveWatchlist() {
    if (st.loggedIn) {
      const r = await fetch('/api/watchlist', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ codes: st.codes }),
      });
      if (r.ok) st.codes = (await r.json()).codes;
    } else writeLocal(st.codes);
  }

  // 편집 중에는 화면을 다시 그리지 않음 (검색창·추천 목록이 사라지지 않게). force면 그래도 그림
  async function poll(force = false) {
    clearTimeout(st.timer);
    let next = 60;
    try {
      const r = await fetch('/api/stocks?codes=' + st.codes.join(','));
      if (!r.ok) throw new Error();
      const d = await r.json();
      st.quotes = d.quotes;
      st.quotes.forEach((q) => { if (q.name) st.names[q.code] = q.name; });
      if (st.quotes.some((q) => q.is_open)) next = d.refresh || 5;
      if (!st.editing || force) drawStocks();
    } catch {
      if (!st.quotes.length) stocksEl.innerHTML = '<p class="w-msg">주가를 불러오지 못했어요.</p>';
      next = 15;
    }
    if (!document.hidden) st.timer = setTimeout(poll, next * 1000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); else clearTimeout(st.timer); });
  // 편집을 마치면 최신 시세로 바로 다시 그림

  const rowHtml = (q) => {
    if (q.error) {
      return `<li data-code="${esc(q.code)}"><span class="s-name">${esc(st.names[q.code] || q.code)}</span>
        <span class="s-err">불러오지 못함</span>${removeBtn(q)}</li>`;
    }
    const before = st.prev[q.code];
    const flash = before && before !== q.price && !st.editing ? (q.direction === 'down' ? 'flash-down' : 'flash-up') : '';
    const sign = q.direction === 'down' ? '-' : q.direction === 'up' ? '+' : '';
    return `<li class="${q.is_index ? 's-index' : ''}" data-code="${esc(q.code)}">
        <span class="s-name">${esc(q.name)}</span>
        <span class="s-price ${flash}">${esc(q.price)}${q.is_index ? '' : '<small>원</small>'}</span>
        <span class="s-chg ${q.direction}">${ARROW[q.direction]} ${esc(q.change)} (${sign}${esc(q.ratio)}%)</span>
        ${removeBtn(q)}
      </li>`;
  };
  const removeBtn = (q) => (st.editing && !q.is_index
    ? `<button type="button" class="s-del" data-del="${esc(q.code)}" aria-label="${esc(st.names[q.code] || q.code)} 빼기">✕</button>` : '');

  function drawStocks() {
    const open = st.quotes.some((q) => q.is_open);
    const t = st.quotes.find((q) => q.traded_at)?.traded_at;
    // 사용자가 정한 순서대로 (지수는 맨 위)
    const byCode = Object.fromEntries(st.quotes.map((q) => [q.code, q]));
    const rows = [...st.quotes.filter((q) => q.is_index), ...st.codes.map((c) => byCode[c]).filter(Boolean)];
    const searchOpen = st.editing && document.getElementById('sSearch');
    const keep = searchOpen ? { value: searchOpen.value, focus: document.activeElement === searchOpen } : null;

    stocksEl.innerHTML = `
      <div class="s-head"><span>📈 주식</span>
        <span class="s-status ${open ? 'on' : ''}">${open ? '실시간' : '장 마감'}${t ? ' · ' + t.slice(11, 19) : ''}</span>
        <button type="button" class="s-edit" id="sEdit">${st.editing ? '완료' : '편집'}</button></div>
      <ul class="s-list ${st.editing ? 'editing' : ''}">${rows.map(rowHtml).join('')}</ul>
      ${st.editing ? `
        <div class="s-add">
          <input id="sSearch" type="search" placeholder="종목 이름이나 코드로 추가" autocomplete="off" aria-label="종목 검색">
          <ul class="s-suggest" id="sSuggest" role="listbox"></ul>
          <p class="w-msg">${st.codes.length}/12개 · ${st.loggedIn ? '내 계정에 저장돼요' : '이 브라우저에 저장돼요 (로그인하면 어디서나 유지)'}</p>
        </div>` : `${!st.codes.length ? '<p class="w-msg">편집을 눌러 관심 종목을 추가해 보세요.</p>' : ''}`}
      <p class="w-src">네이버 증권 실시간 시세 · 투자 판단의 근거로 쓰지 마세요</p>`;
    st.quotes.forEach((q) => { st.prev[q.code] = q.price; });

    document.getElementById('sEdit').onclick = () => {
      st.editing = !st.editing;
      if (st.editing) { drawStocks(); document.getElementById('sSearch').focus(); } else poll(true);
    };
    stocksEl.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => {
      st.codes = st.codes.filter((c) => c !== b.dataset.del);
      st.quotes = st.quotes.filter((q) => q.code !== b.dataset.del);
      drawStocks();
      await saveWatchlist();
    }));
    if (st.editing) {
      const input = document.getElementById('sSearch');
      if (keep) { input.value = keep.value; if (keep.focus) input.focus(); }
      input.oninput = () => { clearTimeout(st.searchTimer); st.searchTimer = setTimeout(() => search(input.value), 250); };
      input.onkeydown = (e) => {
        if (e.key === 'Enter') { e.preventDefault(); document.querySelector('#sSuggest [data-add]')?.click(); }
        if (e.key === 'Escape') { st.editing = false; drawStocks(); }
      };
    }
  }

  async function search(q) {
    const box = document.getElementById('sSuggest');
    if (!box) return;
    if (!q.trim()) { box.innerHTML = ''; return; }
    try {
      const items = await fetch('/api/stocks/search?q=' + encodeURIComponent(q)).then((r) => r.json());
      if (!Array.isArray(items)) throw new Error();
      box.innerHTML = items.length ? items.map((i) => `
        <li><button type="button" data-add="${esc(i.code)}" data-name="${esc(i.name)}" ${st.codes.includes(i.code) ? 'disabled' : ''}>
          <b>${esc(i.name)}</b><small>${esc(i.code)} · ${esc(i.market)}</small>${st.codes.includes(i.code) ? '<em>추가됨</em>' : ''}
        </button></li>`).join('') : '<li class="w-msg">찾는 종목이 없어요.</li>';
      box.querySelectorAll('[data-add]').forEach((b) => (b.onclick = async () => {
        if (st.codes.length >= 12) { box.innerHTML = '<li class="w-msg">최대 12개까지 담을 수 있어요.</li>'; return; }
        st.codes.push(b.dataset.add);
        st.names[b.dataset.add] = b.dataset.name;
        document.getElementById('sSearch').value = '';
        await saveWatchlist();
        poll(true);
      }));
    } catch { box.innerHTML = '<li class="w-msg">검색이 잠시 안 돼요.</li>'; }
  }

  async function startStocks() {
    await loadWatchlist();
    poll();
  }
  // 로그인·로그아웃하면 그 사람의 목록으로 다시 불러오기
  let lastUser;
  window.addEventListener('blog:user', (e) => {
    const id = e.detail ? e.detail.id : null;
    if (lastUser !== undefined && lastUser !== id) { st.editing = false; startStocks(); }
    lastUser = id;
  });
  startStocks();
})();

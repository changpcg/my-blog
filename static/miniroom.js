'use strict';
// 미니룸: 기본 목록에서 고르는 배경 6개 + 캐릭터 6개 (모두 직접 그린 SVG, 외부 이미지 없음)
// 장면 크기 400 × 160, 캐릭터는 100 × 110 칸에 그려서 장면 가운데 바닥에 세움.
// 서버의 허용 목록(server.py ROOM_BGS / ROOM_CHARS)과 키가 같아야 함.

const MINIROOM = {
  bgs: {
    room: {
      name: '내 방',
      svg: `
        <rect width="400" height="160" fill="#fbe9d7"/>
        <rect y="118" width="400" height="42" fill="#d9a77a"/>
        <path d="M0 118H400" stroke="#b9845a" stroke-width="3"/>
        <g opacity=".35" stroke="#b9845a" stroke-width="1.5"><path d="M40 160L70 118M120 160L130 118M200 160V118M280 160L270 118M360 160L330 118"/></g>
        <rect x="36" y="22" width="84" height="64" rx="4" fill="#bfe3f7" stroke="#fff" stroke-width="5"/>
        <path d="M78 22V86M36 54H120" stroke="#fff" stroke-width="4"/>
        <circle cx="104" cy="40" r="8" fill="#ffe28a"/>
        <rect x="292" y="84" width="76" height="40" rx="6" fill="#9cc5a1"/>
        <rect x="292" y="74" width="26" height="16" rx="5" fill="#fff"/>
        <rect x="250" y="96" width="22" height="26" rx="3" fill="#c97b4a"/>
        <path d="M261 96c-14-6-12-24 0-28 12 4 14 22 0 28z" fill="#6cae75"/>`,
    },
    forest: {
      name: '숲',
      svg: `
        <defs><linearGradient id="mr-sky-f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bfe8ff"/><stop offset="1" stop-color="#e9f8ff"/></linearGradient></defs>
        <rect width="400" height="160" fill="url(#mr-sky-f)"/>
        <ellipse cx="80" cy="130" rx="160" ry="50" fill="#a8d99a"/>
        <ellipse cx="330" cy="135" rx="170" ry="48" fill="#94cf86"/>
        <rect y="128" width="400" height="32" fill="#7fbf6e"/>
        <g fill="#4f9a57"><path d="M40 118l22-60 22 60z"/><path d="M340 120l24-70 24 70z"/><path d="M300 124l16-42 16 42z"/></g>
        <g fill="#8a5a3b"><rect x="58" y="116" width="8" height="12"/><rect x="360" y="118" width="8" height="12"/><rect x="312" y="122" width="7" height="8"/></g>
        <circle cx="330" cy="30" r="14" fill="#fff3a6"/>
        <g fill="#fff"><ellipse cx="120" cy="34" rx="24" ry="9"/><ellipse cx="140" cy="28" rx="16" ry="9"/></g>`,
    },
    beach: {
      name: '바다',
      svg: `
        <rect width="400" height="160" fill="#9fdcf7"/>
        <circle cx="70" cy="36" r="18" fill="#ffd36b"/>
        <rect y="78" width="400" height="44" fill="#3fa9d6"/>
        <path d="M0 92q20-6 40 0t40 0 40 0 40 0 40 0 40 0 40 0 40 0 40 0 40 0" fill="none" stroke="#bfeaff" stroke-width="2.5"/>
        <path d="M0 122q100-14 200-4t200-4V160H0z" fill="#f4d9a4"/>
        <g transform="translate(330 70)"><path d="M0 60V8" stroke="#a9744f" stroke-width="6"/><path d="M0 8c-20-8-36 2-40 10 14-4 26-4 40-10zm0 0c18-10 34-4 40 6-14-4-26-2-40-6zm0 0c-6-18 4-30 14-32-4 12-6 22-14 32z" fill="#3e9b5a"/></g>
        <circle cx="70" cy="140" r="6" fill="#f08d7c"/>`,
    },
    night: {
      name: '밤하늘',
      svg: `
        <defs><linearGradient id="mr-sky-n" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c2452"/><stop offset="1" stop-color="#3b3f7a"/></linearGradient></defs>
        <rect width="400" height="160" fill="url(#mr-sky-n)"/>
        <circle cx="320" cy="38" r="20" fill="#fff6c9"/>
        <circle cx="330" cy="32" r="18" fill="#2a3166"/>
        <g fill="#fff"><circle cx="40" cy="30" r="1.8"/><circle cx="90" cy="60" r="1.4"/><circle cx="150" cy="24" r="2"/><circle cx="210" cy="48" r="1.4"/><circle cx="250" cy="20" r="1.8"/><circle cx="370" cy="80" r="1.4"/><circle cx="20" cy="86" r="1.4"/><circle cx="120" cy="96" r="1.2"/></g>
        <path d="M0 128q100-26 200-8t200-12V160H0z" fill="#26304f"/>
        <rect y="138" width="400" height="22" fill="#1f2741"/>`,
    },
    cafe: {
      name: '카페',
      svg: `
        <rect width="400" height="160" fill="#efe1cf"/>
        <rect width="400" height="16" fill="#6b4a36"/>
        <g stroke="#6b4a36" stroke-width="2"><path d="M80 16V40M200 16V34M320 16V40"/></g>
        <g fill="#ffcf73"><path d="M70 40h20l-4 10h-12z"/><path d="M190 34h20l-4 10h-12z"/><path d="M310 40h20l-4 10h-12z"/></g>
        <rect x="24" y="58" width="96" height="40" rx="4" fill="#3f3a36"/>
        <g fill="#f7f1e8" font-family="sans-serif" font-size="9"><text x="34" y="74">COFFEE</text><text x="34" y="88">LATTE · TEA</text></g>
        <rect y="122" width="400" height="38" fill="#b78a62"/>
        <rect x="270" y="96" width="110" height="28" rx="3" fill="#8c5f40"/>
        <g fill="#fff"><rect x="286" y="84" width="14" height="12" rx="2"/><rect x="314" y="86" width="12" height="10" rx="2"/></g>
        <path d="M293 80c-3-4 3-6 0-10" stroke="#c9b8a6" stroke-width="1.5" fill="none"/>`,
    },
    library: {
      name: '도서관',
      svg: `
        <rect width="400" height="160" fill="#e8dcc8"/>
        <rect y="124" width="400" height="36" fill="#9b6b48"/>
        <g fill="#7a4f33"><rect x="16" y="14" width="110" height="112"/><rect x="274" y="14" width="110" height="112"/></g>
        <g fill="#5c3a25"><rect x="16" y="48" width="110" height="5"/><rect x="16" y="86" width="110" height="5"/><rect x="274" y="48" width="110" height="5"/><rect x="274" y="86" width="110" height="5"/></g>
        <g><rect x="22" y="22" width="10" height="26" fill="#d9534f"/><rect x="34" y="26" width="8" height="22" fill="#5b8def"/><rect x="44" y="20" width="12" height="28" fill="#f0ad4e"/><rect x="58" y="24" width="9" height="24" fill="#5cb85c"/><rect x="70" y="22" width="11" height="26" fill="#9b59b6"/>
           <rect x="22" y="60" width="12" height="26" fill="#5cb85c"/><rect x="36" y="64" width="9" height="22" fill="#d9534f"/><rect x="48" y="58" width="10" height="28" fill="#5b8def"/>
           <rect x="282" y="22" width="11" height="26" fill="#5b8def"/><rect x="295" y="26" width="9" height="22" fill="#f0ad4e"/><rect x="306" y="20" width="12" height="28" fill="#d9534f"/>
           <rect x="282" y="60" width="9" height="26" fill="#9b59b6"/><rect x="293" y="62" width="12" height="24" fill="#5cb85c"/><rect x="308" y="58" width="10" height="28" fill="#f0ad4e"/><rect x="320" y="64" width="9" height="22" fill="#5b8def"/></g>
        <rect x="150" y="30" width="100" height="56" rx="50" fill="#cfe9f7" stroke="#fff" stroke-width="5"/>`,
    },
  },

  chars: {
    bear: {
      name: '곰',
      svg: `
        <ellipse cx="50" cy="104" rx="30" ry="5" fill="#000" opacity=".15"/>
        <ellipse cx="50" cy="80" rx="26" ry="24" fill="#a0693f"/>
        <ellipse cx="50" cy="84" rx="15" ry="14" fill="#d9a57a"/>
        <circle cx="28" cy="22" r="11" fill="#a0693f"/><circle cx="72" cy="22" r="11" fill="#a0693f"/>
        <circle cx="28" cy="22" r="6" fill="#d9a57a"/><circle cx="72" cy="22" r="6" fill="#d9a57a"/>
        <circle cx="50" cy="40" r="27" fill="#a0693f"/>
        <ellipse cx="50" cy="49" rx="12" ry="9" fill="#d9a57a"/>
        <circle cx="40" cy="36" r="3.2" fill="#222"/><circle cx="60" cy="36" r="3.2" fill="#222"/>
        <ellipse cx="50" cy="45" rx="4" ry="3" fill="#222"/>
        <path d="M46 51q4 4 8 0" stroke="#222" stroke-width="1.6" fill="none"/>
        <circle cx="33" cy="45" r="4" fill="#ff9a9a" opacity=".6"/><circle cx="67" cy="45" r="4" fill="#ff9a9a" opacity=".6"/>`,
    },
    cat: {
      name: '고양이',
      svg: `
        <ellipse cx="50" cy="104" rx="28" ry="5" fill="#000" opacity=".15"/>
        <path d="M76 92q18-6 12-30" stroke="#8d929b" stroke-width="6" fill="none" stroke-linecap="round"/>
        <ellipse cx="50" cy="82" rx="24" ry="22" fill="#a7adb6"/>
        <ellipse cx="50" cy="86" rx="13" ry="12" fill="#eef0f2"/>
        <path d="M26 30L28 6 44 20zM74 30L72 6 56 20z" fill="#a7adb6"/>
        <path d="M30 24L31 12 39 19zM70 24L69 12 61 19z" fill="#f4b6c2"/>
        <circle cx="50" cy="40" r="26" fill="#a7adb6"/>
        <ellipse cx="40" cy="38" rx="3.2" ry="4.2" fill="#222"/><ellipse cx="60" cy="38" rx="3.2" ry="4.2" fill="#222"/>
        <path d="M47 47h6l-3 3z" fill="#f08aa0"/>
        <path d="M50 50q-3 4-7 2M50 50q3 4 7 2" stroke="#222" stroke-width="1.4" fill="none"/>
        <g stroke="#555" stroke-width="1.1"><path d="M24 46h13M24 51l13-2M76 46H63M76 51l-13-2"/></g>`,
    },
    rabbit: {
      name: '토끼',
      svg: `
        <ellipse cx="50" cy="104" rx="26" ry="5" fill="#000" opacity=".15"/>
        <ellipse cx="50" cy="84" rx="22" ry="20" fill="#fbfbfb" stroke="#e3e3e3"/>
        <ellipse cx="38" cy="14" rx="7" ry="22" fill="#fbfbfb" stroke="#e3e3e3"/><ellipse cx="62" cy="14" rx="7" ry="22" fill="#fbfbfb" stroke="#e3e3e3"/>
        <ellipse cx="38" cy="15" rx="3.5" ry="16" fill="#f7c1cc"/><ellipse cx="62" cy="15" rx="3.5" ry="16" fill="#f7c1cc"/>
        <circle cx="50" cy="46" r="23" fill="#fbfbfb" stroke="#e3e3e3"/>
        <circle cx="41" cy="44" r="3" fill="#222"/><circle cx="59" cy="44" r="3" fill="#222"/>
        <path d="M47 51h6l-3 3z" fill="#f08aa0"/>
        <path d="M50 54v3M46 59q4 2 8 0" stroke="#222" stroke-width="1.3" fill="none"/>
        <circle cx="35" cy="52" r="4" fill="#ffb3c1" opacity=".6"/><circle cx="65" cy="52" r="4" fill="#ffb3c1" opacity=".6"/>`,
    },
    penguin: {
      name: '펭귄',
      svg: `
        <ellipse cx="50" cy="104" rx="26" ry="5" fill="#000" opacity=".15"/>
        <ellipse cx="38" cy="102" rx="9" ry="4" fill="#f2a33a"/><ellipse cx="62" cy="102" rx="9" ry="4" fill="#f2a33a"/>
        <path d="M24 66q-10 14-4 24M76 66q10 14 4 24" stroke="#273043" stroke-width="8" fill="none" stroke-linecap="round"/>
        <ellipse cx="50" cy="62" rx="28" ry="40" fill="#273043"/>
        <ellipse cx="50" cy="72" rx="19" ry="28" fill="#fff"/>
        <ellipse cx="50" cy="40" rx="18" ry="14" fill="#fff"/>
        <circle cx="43" cy="38" r="3" fill="#222"/><circle cx="57" cy="38" r="3" fill="#222"/>
        <path d="M44 45h12l-6 6z" fill="#f2a33a"/>
        <circle cx="36" cy="47" r="3.5" fill="#ff9a9a" opacity=".55"/><circle cx="64" cy="47" r="3.5" fill="#ff9a9a" opacity=".55"/>`,
    },
    dog: {
      name: '강아지',
      svg: `
        <ellipse cx="50" cy="104" rx="28" ry="5" fill="#000" opacity=".15"/>
        <path d="M74 86q14-4 14-18" stroke="#d6a86b" stroke-width="6" fill="none" stroke-linecap="round"/>
        <ellipse cx="50" cy="82" rx="24" ry="22" fill="#e8c08a"/>
        <ellipse cx="50" cy="86" rx="13" ry="12" fill="#fbe7c8"/>
        <circle cx="50" cy="42" r="26" fill="#e8c08a"/>
        <path d="M26 30q-12 6-6 30 10-2 12-20z" fill="#a8743f"/><path d="M74 30q12 6 6 30-10-2-12-20z" fill="#a8743f"/>
        <ellipse cx="50" cy="52" rx="13" ry="10" fill="#fbe7c8"/>
        <circle cx="40" cy="39" r="3.2" fill="#222"/><circle cx="60" cy="39" r="3.2" fill="#222"/>
        <ellipse cx="50" cy="48" rx="4.5" ry="3.2" fill="#222"/>
        <path d="M46 55q4 5 8 0" stroke="#222" stroke-width="1.5" fill="#f08aa0"/>`,
    },
    robot: {
      name: '로봇',
      svg: `
        <ellipse cx="50" cy="104" rx="28" ry="5" fill="#000" opacity=".15"/>
        <rect x="32" y="92" width="10" height="10" rx="2" fill="#7d8796"/><rect x="58" y="92" width="10" height="10" rx="2" fill="#7d8796"/>
        <rect x="18" y="66" width="8" height="20" rx="4" fill="#9aa4b2"/><rect x="74" y="66" width="8" height="20" rx="4" fill="#9aa4b2"/>
        <rect x="26" y="60" width="48" height="34" rx="8" fill="#b8c2cf"/>
        <circle cx="50" cy="76" r="7" fill="#5ad1c5"/>
        <path d="M50 6V16" stroke="#7d8796" stroke-width="3"/><circle cx="50" cy="6" r="4" fill="#ff6b6b"/>
        <rect x="22" y="16" width="56" height="42" rx="12" fill="#cfd7e2"/>
        <rect x="30" y="26" width="40" height="20" rx="8" fill="#273043"/>
        <circle cx="41" cy="36" r="4" fill="#5ad1c5"/><circle cx="59" cy="36" r="4" fill="#5ad1c5"/>
        <rect x="16" y="30" width="6" height="14" rx="3" fill="#9aa4b2"/><rect x="78" y="30" width="6" height="14" rx="3" fill="#9aa4b2"/>`,
    },
  },
};

/** 미니룸 장면 (배경 + 가운데 캐릭터). 없는 키면 기본값 */
function miniroomSvg(bgKey, charKey, extraClass = '') {
  const bg = MINIROOM.bgs[bgKey] || MINIROOM.bgs.room;
  const ch = MINIROOM.chars[charKey] || MINIROOM.chars.bear;
  return `<svg class="miniroom ${extraClass}" viewBox="0 0 400 160" role="img" aria-label="미니룸: ${bg.name}의 ${ch.name}"
    preserveAspectRatio="xMidYMid slice">${bg.svg}<g transform="translate(150 50) scale(1)"><g class="mr-char">${ch.svg}</g></g></svg>`;
}

/** 고르는 칸의 작은 그림 */
const miniroomBgThumb = (k) => `<svg viewBox="0 0 400 160" aria-hidden="true" preserveAspectRatio="xMidYMid slice">${MINIROOM.bgs[k].svg}</svg>`;
const miniroomCharThumb = (k) => `<svg viewBox="0 0 100 110" aria-hidden="true">${MINIROOM.chars[k].svg}</svg>`;

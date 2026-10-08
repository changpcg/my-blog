# 인터넷에 공개하기 (VPS 배포 안내)

리눅스 VPS 한 대에 블로그(Python)와 회원 서버(PHP)를 **공개 모드**로 올리는 순서입니다. 처음이라도 1시간 안에 끝내는 것을
목표로 했습니다. 기준 환경은 **Ubuntu 24.04 LTS + Nginx + PHP-FPM + Let's Encrypt**입니다.

```text
방문자 ──https──▶ Nginx(443, 인증서)
                   ├─ blog.내도메인 ─▶ 블로그 서버 python3 server.py (127.0.0.1:8000)
                   └─ auth.내도메인 ─▶ PHP-FPM (php-auth/public 만 열림)
두 서버가 함께 읽는 설정: /srv/my-blog/deploy.config.json (공개 모드·공개 주소·믿는 프록시·가입 한도)
```

- 내 컴퓨터에서 쓰던 방식(`python3 server.py`, `php -S`)은 **개발 모드**로 그대로 남습니다. 공개 모드는 이 안내대로 만든
  `deploy.config.json`에서만 켜집니다.
- 공개 모드에서는 관리자 비밀번호가 약하거나, 주소가 https가 아니거나, 회원 서버를 `php -S`로 켜면 **서버가 일부러 멈춥니다.**
  멈추면서 무엇을 고칠지 한국어로 알려 줍니다(아래 '문제 해결').

## 0. 준비물

- VPS 1대: Ubuntu 24.04, 메모리 1GB 이상, SSH로 접속 가능(22.04도 됨: 아래 `8.3`을 `8.1`로 바꿔 읽기)
- 도메인 1개와 DNS **A 레코드 2개**: `blog.내도메인`, `auth.내도메인` → VPS의 IP
  - 두 주소는 **반드시 같은 도메인의 하위 도메인**이어야 합니다. 브라우저 쿠키 규칙(SameSite) 때문에 다른 도메인이면
    '블로그 들어가기'와 '함께 로그아웃'이 동작하지 않습니다.
- 아래 명령의 `blog.example.com`·`auth.example.com`은 모두 내 주소로 바꿔서 실행하세요.

## 1. 패키지 설치

```bash
sudo apt update
sudo apt install -y nginx php8.3-fpm php8.3-sqlite3 php8.3-mbstring php8.3-curl \
                    python3 git certbot python3-certbot-nginx
```

앱 자체는 Python 표준 라이브러리와 PHP 기본 기능만 씁니다. 위 패키지는 서버를 돌리는 운영 환경입니다.

## 2. 실행 사용자와 코드

블로그와 회원 서버를 같은 사용자(`myblog`)로 돌려서 DB·키·설정 파일을 그 사용자만 읽게 합니다.

```bash
sudo useradd --system --home /srv/my-blog --shell /usr/sbin/nologin myblog
sudo git clone https://github.com/changpcg/my-blog.git /srv/my-blog     # 또는 내 컴퓨터에서 rsync로 복사
sudo chown -R myblog:myblog /srv/my-blog
sudo chmod 711 /srv/my-blog /srv/my-blog/php-auth                      # 남은 목록을 못 보고 지나가기만
sudo chmod -R o+rX /srv/my-blog/php-auth/public                         # Nginx는 회원 화면의 css·js만 읽음
```

이미 쓰던 데이터를 옮길 때는 `blog.db`, `uploads/`, `php-auth/db/`(회원 DB와 `sso.key`)를 **함께** 같은 자리에 복사하고
`sudo chown -R myblog:myblog /srv/my-blog`를 한 번 더 실행합니다. 회원 DB와 blog.db는 짝이 맞아야 합니다.

## 3. 배포 설정 파일 (공개 모드 켜기)

```bash
sudo -u myblog cp /srv/my-blog/deploy.config.example.json /srv/my-blog/deploy.config.json
sudo -u myblog nano /srv/my-blog/deploy.config.json
sudo chmod 600 /srv/my-blog/deploy.config.json
```

```json
{
  "public_mode": true,
  "blog_url": "https://blog.example.com",
  "auth_url": "https://auth.example.com",
  "trusted_proxies": ["127.0.0.1", "::1"],
  "signup": { "per_ip_per_hour": 3, "site_per_hour": 30, "bot_check": true }
}
```

| 키 | 뜻 |
| --- | --- |
| `public_mode` | `true`면 공개 모드(https 전용, Secure 쿠키, 관리자 비밀번호 검사) |
| `blog_url`·`auth_url` | 공개 주소. `https://호스트`까지만(뒤에 경로·`/` 없이), 서로 달라야 함 |
| `trusted_proxies` | 실제 방문자 IP를 알려 주는 앞단(같은 서버의 Nginx = 127.0.0.1). 여기 적은 곳의 `X-Forwarded-*`만 믿음 |
| `signup` | 같은 곳(IP)에서 1시간에 가입 몇 개, 사이트 전체 1시간에 몇 개. `bot_check`(자동 가입 방지)는 공개 모드에서 끌 수 없음 |

관리자 비밀번호는 이 파일에 넣지 않습니다(다음 단계).

## 4. 관리자 비밀번호

12자 이상, 영문과 숫자를 함께 넣습니다. `admin1234`는 쓸 수 없습니다.

```bash
sudo mkdir -p /etc/my-blog
sudo sh -c 'umask 077; echo "BLOG_PASSWORD=여기에-12자이상-영문숫자" > /etc/my-blog/blog.env'
```

바꿀 때는 이 파일을 고치고 `sudo systemctl restart my-blog` — 예전 관리자 로그인은 모두 끊깁니다.

## 5. SNS 로그인 키 (선택)

```bash
sudo -u myblog cp /srv/my-blog/php-auth/oauth.config.example.php /srv/my-blog/php-auth/oauth.config.php
sudo -u myblog nano /srv/my-blog/php-auth/oauth.config.php     # 키만 넣기 (redirect_uri는 공개 모드에서 안 씀)
sudo chmod 600 /srv/my-blog/php-auth/oauth.config.php
```

콜백 주소는 공개 모드에서 자동으로 `https://auth.example.com/oauth_callback.php`가 됩니다(11단계에서 등록).

## 6. 서비스 등록 (블로그 = systemd, 회원 서버 = PHP-FPM 풀)

```bash
cd /srv/my-blog
sudo cp deploy/my-blog.service.example /etc/systemd/system/my-blog.service
sudo cp deploy/php-fpm-my-blog.conf.example /etc/php/8.3/fpm/pool.d/my-blog.conf
sudo php-fpm8.3 -t && sudo systemctl restart php8.3-fpm
sudo systemctl daemon-reload && sudo systemctl enable --now my-blog
journalctl -u my-blog -n 20
```

`journalctl`에 아래처럼 보이면 성공입니다.

```text
블로그 실행 중 (공개 모드) → https://blog.example.com  (내부 127.0.0.1:8000)
회원 서버: https://auth.example.com
SNS 개발자 콘솔에 등록할 콜백 주소: https://auth.example.com/oauth_callback.php
```

"서버를 켜지 않았어요"가 보이면 그 아래 줄의 안내대로 고치고 `sudo systemctl restart my-blog`.

## 7. Nginx

```bash
sudo cp /srv/my-blog/deploy/nginx-my-blog.conf.example /etc/nginx/sites-available/my-blog
sudo sed -i 's/blog\.example\.com/blog.내도메인/g; s/auth\.example\.com/auth.내도메인/g' /etc/nginx/sites-available/my-blog
sudo ln -s /etc/nginx/sites-available/my-blog /etc/nginx/sites-enabled/my-blog
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t`가 `[::]:80 ... Address family not supported`로 실패하면 그 VPS에는 IPv6가 없는 것이니 예시의
`listen [::]:80;` 줄을 지우고 다시 실행합니다.

## 8. HTTPS 인증서 (Let's Encrypt)

```bash
sudo certbot --nginx -d blog.example.com -d auth.example.com --redirect -m 내이메일 --agree-tos
```

certbot이 443 설정과 `http → https` 이동을 Nginx 설정에 더하고, 인증서를 자동으로 갱신합니다.

## 9. 방화벽

```bash
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
```

블로그 서버(8000)는 127.0.0.1에만 열려 있어 따로 막을 필요가 없습니다.

## 10. (필요할 때만) 서버끼리 부르기

두 서버는 서로를 **공개 주소(https)**로 부릅니다(가입 허용 확인, 탈퇴, 관리자 가입 현황). 어떤 VPS는 자기 공개 IP로 되돌아오는
연결을 막는데, 그러면 회원가입 화면이 계속 "지금은 새 가입을 받지 않아요"이거나 관리자 사이트 설정에 "회원 서버에 연결할 수
없어요"가 나옵니다. 이때는 두 주소를 이 서버 자신으로 적어 둡니다.

```bash
echo "127.0.0.1 blog.example.com auth.example.com" | sudo tee -a /etc/hosts
```

## 11. SNS 개발자 콘솔에 주소 등록

관리자로 로그인 → 사이트 설정 → **공개 주소** 상자의 콜백 주소를 그대로 등록합니다.

| SNS | 등록할 곳 |
| --- | --- |
| 네이버 | 서비스 URL `https://blog.example.com`, Callback URL `https://auth.example.com/oauth_callback.php` |
| 카카오 | 플랫폼 → Web 사이트 도메인 `https://auth.example.com`, 카카오 로그인 → Redirect URI(콜백 주소) |
| 구글 | 사용자 인증 정보 → 승인된 리디렉션 URI(콜백 주소) |

## 12. 점검

```bash
B=https://blog.example.com; A=https://auth.example.com
curl -sI http://blog.example.com/ | head -1                       # 301 (https로 이동)
curl -sI $B/ | grep -i strict-transport                           # Strict-Transport-Security: max-age=31536000
curl -s -D - -o /dev/null $B/api/blog | grep -i set-cookie        # vid=...; Secure
curl -s -D - -o /dev/null $A/login.php | grep -i set-cookie       # AUTHSESS=...; secure; HttpOnly; SameSite=Lax
for p in db/sqlite.db db/sso.key oauth.config.php; do curl -s -o /dev/null -w "%{http_code} $p\n" "$A/$p"; done        # 모두 404
for p in blog.db deploy.config.json php-auth/db/sso.key; do curl -s -o /dev/null -w "%{http_code} $p\n" "$B/$p"; done  # 모두 404
```

그다음 브라우저로 **회원가입 → 블로그 들어가기 → 글쓰기 → 로그아웃**(회원 페이지도 함께 로그아웃)까지 해 봅니다.
휴대폰(LTE)으로 회원 로그인을 5번 틀리면 휴대폰만 잠기고 PC는 그대로 로그인되면 실제 방문자 IP도 잘 잡힌 것입니다.

## 운영

**백업** — 두 DB(블로그·회원)·서명 키·설정·업로드를 **함께**, 서버를 멈추지 않고 매일 자동으로(008):

```bash
sudo install -d -o myblog -g myblog -m 700 /var/backups/my-blog
sudo cp deploy/my-blog-backup.service.example /etc/systemd/system/my-blog-backup.service
sudo cp deploy/my-blog-backup.timer.example   /etc/systemd/system/my-blog-backup.timer
sudo systemctl daemon-reload && sudo systemctl enable --now my-blog-backup.timer
sudo systemctl start my-blog-backup && journalctl -u my-blog-backup -n 5     # "백업했어요: …"
```

- 매일 04:10에 `/var/backups/my-blog/날짜_시각/`이 생기고 최근 14개만 남습니다. 큰 작업 전에는 `sudo systemctl start my-blog-backup`으로 바로 백업.
- 디스크 고장에 대비해 이 폴더를 다른 곳(내 컴퓨터 등)으로도 복사해 두세요. 폴더는 `myblog`만 읽을 수 있고 백업끼리 하드 링크로 이어져 있으니
  `-H`와 sudo를 함께 씁니다: `rsync -aH --rsync-path="sudo rsync" 내계정@서버:/var/backups/my-blog/ ./my-blog-backups/`
  (백업에는 비밀번호 해시와 서명 키가 들어 있으니 안전한 곳에만).

**복원** — 두 서비스를 멈추고 블로그 사용자로(root로 하면 파일 주인이 바뀌어 거절됨):

```bash
sudo -u myblog python3 /srv/my-blog/tools/restore.py --dest /var/backups/my-blog          # 목록
sudo systemctl stop my-blog php8.3-fpm
cd /srv/my-blog && sudo -u myblog python3 tools/restore.py --dest /var/backups/my-blog /var/backups/my-blog/<폴더>
sudo systemctl start php8.3-fpm my-blog
```

복원 직전 상태는 `…_before-restore` 폴더로 남고, 중간에 실패하면 그 상태로 자동으로 돌려놓습니다. 서버의 `deploy.config.json`·
`oauth.config.php`는 그대로 둡니다(백업 것으로 바꾸려면 `--with-config`). 한쪽 DB만 되돌리면 회원 번호가 어긋나므로 항상 이 도구로 함께 되돌리세요.
복원하는 동안에는 백업 타이머가 끼어들지 못하게 잠급니다.

**코드 업데이트**

```bash
cd /srv/my-blog && sudo -u myblog git pull && sudo systemctl restart my-blog     # PHP는 다음 요청부터 새 코드
```

**가입 막기** — 스팸이 몰리면 관리자 사이트 설정에서 '회원가입 허용'을 끄면 블로그·회원 서버 가입이 함께 닫힙니다.
가입 한도는 `deploy.config.json`의 `signup`에서 바꿉니다(회원 서버는 다음 요청부터, 블로그 화면 표시는 블로그를 다시 켜면).

## 문제 해결

| 보이는 것 | 이유 | 고치는 법 |
| --- | --- | --- |
| `journalctl`에 "서버를 켜지 않았어요" (종료 코드 78) | 설정 파일·관리자 비밀번호·HOST가 공개 모드 규칙에 안 맞음 | 그 아래 안내대로 고치고 `sudo systemctl restart my-blog` |
| 블로그 화면이 "서버 설정 오류: … X-Forwarded-Proto" | Nginx 설정에서 `proxy_set_header X-Forwarded-Proto $scheme;`이 빠짐 | 예시대로 넣고 `sudo systemctl reload nginx` |
| 회원 화면이 "회원 서버 설정을 확인하고 있어요" | `deploy.config.json`이 틀렸거나 읽을 수 없음 | `sudo tail /var/log/php8.3-fpm.log`에서 이유 확인 |
| 회원 화면이 "php -S로 회원 서버를 켤 수 없어요" | 공개 모드에서 `php -S`로 실행함 | 6단계의 PHP-FPM으로 실행 |
| 502 Bad Gateway | 블로그 또는 PHP-FPM이 꺼짐 | `systemctl status my-blog php8.3-fpm` |
| 회원가입이 계속 닫힘 / 관리자 화면 "회원 서버에 연결할 수 없어요" | 서버끼리 공개 주소로 못 부름 | 10단계 |
| 관리자 화면 "두 서버의 공개 모드 설정이 달라요" | 설정을 바꾼 뒤 블로그를 다시 켜지 않음 | `sudo systemctl restart my-blog` |
| SNS 로그인 중 SNS 쪽 오류 화면 | 콜백 주소가 SNS 콘솔 등록 값과 다름 | 11단계 |
| 큰 첨부 파일이 413 오류 | Nginx 업로드 크기 | 예시의 `client_max_body_size 45m` 확인 |

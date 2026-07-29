# Deploy runbook — Odysseus / TripSmart

Two separate deploys:

| Phần | Đi đâu | Cách |
|---|---|---|
| **Backend** (FastAPI) | Server `zah-40.123c.vn` (118.102.2.140) | SSH + uvicorn sau nginx (HTTPS) — hướng dẫn dưới |
| **Frontend** (Mini App) | **Nền tảng Zalo Mini App** (KHÔNG phải server trên) | `zmp deploy` → duyệt trên Zalo — xem `../README_ZALO_DEPLOY.md` |

> ⚠️ Mini App **không** chạy trên server của bạn. Server chỉ chứa **backend API** mà Mini App gọi tới. Đó là lý do backend cần domain HTTPS công khai (`https://zah-40.123c.vn`).

---

## ⚡ Quickstart cho ĐÚNG server này (RHEL + sudo + nginx sẵn, git-based)

Recon đã xác nhận: passwordless sudo, nginx 1.20.1, Python 3.9.18, **SELinux bật**,
**SSH ở cổng 2222** (không phải 22 → dùng `ssh -p 2222` và `scp -P 2222`).
Deploy vào `/opt/tripsmart` (KHÔNG để trong `/home` — SELinux chặn systemd exec từ home).

```bash
ssh -p 2222 zah19-team40@118.102.2.140     # đăng nhập server (cổng 2222)
```

```bash
# ── trên MÁY MAC: đẩy code lên GitHub (repo đã init sẵn, secret đã loại) ──
gh repo create odysseus-tripsmart --private --source=. --push     # hoặc tạo repo private + git push -u origin main

# ── trên SERVER ──
sudo mkdir -p /opt/tripsmart && sudo chown "$USER":"$USER" /opt/tripsmart
git clone https://github.com/<user>/odysseus-tripsmart.git /opt/tripsmart   # user=github, pass=PAT
cp .env.example .env && nano .env            # điền ANTHROPIC_API_KEY + SERPAPI_KEY (cách khuyên dùng)
#   (hoặc từ MAC:  scp -P 2222 .env zah19-team40@118.102.2.140:/opt/tripsmart/.env)
bash deploy/server_setup.sh                  # venv + deps + smoke test

# chạy nền (systemd)
sudo cp deploy/tripsmart.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tripsmart
systemctl status tripsmart --no-pager        # phải "active (running)"

# nginx (đã cài) + SELinux + HTTPS
sudo cp deploy/nginx-zah-40.conf /etc/nginx/conf.d/zah-40.conf
sudo setsebool -P httpd_can_network_connect 1                     # ⭐ SELinux: cho nginx gọi uvicorn
sudo nginx -t && sudo systemctl reload nginx
sudo firewall-cmd --permanent --add-service=http --add-service=https 2>/dev/null && sudo firewall-cmd --reload || true
sudo dnf install -y epel-release && sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d zah-40.123c.vn        # cần DNS zah-40.123c.vn -> 118.102.2.140

# verify (từ Mac):  curl -s https://zah-40.123c.vn/health   → {"ok":true,...}
```

Cập nhật về sau: `git push` (Mac) → trên server `cd /opt/tripsmart && git pull && ./.venv/bin/pip install -q -r requirements.txt && sudo systemctl restart tripsmart`.

> Phần tổng quát bên dưới (Ubuntu/apt, không-sudo, tmux…) giữ để tham khảo; server này dùng Quickstart trên.

---

---

## 0. Bảo mật (làm ngay)

Mật khẩu SSH và các API key đã bị dán plaintext trong chat → **đổi mật khẩu SSH** sau khi setup xong, và cân nhắc rotate `ANTHROPIC_API_KEY` / `SERPAPI_KEY`. `.env` đã nằm trong `.gitignore` — đừng commit.

## 1. (Khuyên dùng) Tạo SSH key để khỏi gõ mật khẩu mỗi lần

Trên máy Mac:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/zah40 -N ""      # nếu chưa có
ssh-copy-id -i ~/.ssh/zah40.pub zah19-team40@118.102.2.140   # gõ mật khẩu 1 lần
# từ giờ: ssh -i ~/.ssh/zah40 zah19-team40@118.102.2.140  (không cần mật khẩu)
```
Rồi thêm vào `~/.ssh/config` cho gọn:
```
Host zah40
    HostName 118.102.2.140
    User zah19-team40
    IdentityFile ~/.ssh/zah40
```

## 2. Đẩy code lên server (từ máy Mac, ở repo root)

```bash
bash deploy/push.sh
```
(Hoặc dùng host alias: `SSH_HOST=zah40 bash deploy/push.sh`.) Script rsync toàn bộ repo vào `~/app` trên server, **kèm `.env`** (đã có key thật). Nếu muốn tự tạo `.env` trên server thì bỏ dòng exclude tương ứng trong `push.sh`.

## 3. Cài đặt phía server (SSH vào server)

```bash
ssh zah19-team40@118.102.2.140     # hoặc: ssh zah40
cd ~/app
bash deploy/server_setup.sh        # tạo .venv + cài deps + smoke test
```
Nếu báo thiếu `.env`: `cp .env.example .env && nano .env` rồi điền `ANTHROPIC_API_KEY` và `SERPAPI_KEY`, chạy lại.

## 4. Chạy thử nhanh (foreground, để chắc chắn nó sống)

```bash
./.venv/bin/uvicorn tripsmart.server:app --host 127.0.0.1 --port 3100 --env-file .env
# mở tab SSH khác:  curl -s localhost:3100/health   ->  {"ok":true,...}
# OK thì Ctrl-C, chuyển sang chạy nền ở bước 5.
```

## 5. Chạy nền lâu dài

### 5a. Có quyền sudo → systemd (khuyên dùng, tự restart khi crash/reboot)
```bash
sudo cp ~/app/deploy/tripsmart.service /etc/systemd/system/tripsmart.service
# sửa path/User trong file nếu bạn để code ở chỗ khác:  sudo nano /etc/systemd/system/tripsmart.service
sudo systemctl daemon-reload
sudo systemctl enable --now tripsmart
systemctl status tripsmart --no-pager      # phải thấy "active (running)"
journalctl -u tripsmart -f                  # xem log realtime
```

### 5b. KHÔNG có sudo → tmux (hoặc nohup)
```bash
tmux new -s tripsmart
cd ~/app && ./.venv/bin/uvicorn tripsmart.server:app --host 0.0.0.0 --port 3100 --env-file .env
# thoát mà vẫn chạy: nhấn  Ctrl-b  rồi  d
```
Không sudo thì bạn cũng không cài được nginx — nhờ ban tổ chức trỏ `zah-40.123c.vn` (443) về port `3100`, hoặc chạy `--host 0.0.0.0` và gọi qua `http://118.102.2.140:3100` (Zalo Mini App **bắt buộc HTTPS**, nên vẫn cần org cấp TLS).

## 6. nginx + HTTPS (cần sudo)

```bash
sudo apt update && sudo apt install -y nginx        # nếu chưa có
sudo cp ~/app/deploy/nginx-zah-40.conf /etc/nginx/sites-available/zah-40
sudo ln -sf /etc/nginx/sites-available/zah-40 /etc/nginx/sites-enabled/zah-40
sudo nginx -t && sudo systemctl reload nginx

# HTTPS miễn phí (Let's Encrypt) — cần DNS zah-40.123c.vn đã trỏ về 118.102.2.140:
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d zah-40.123c.vn
```
Kiểm tra DNS trước: `dig +short zah-40.123c.vn` phải ra `118.102.2.140`. Nếu chưa, báo ban tổ chức trỏ DNS.

## 7. Xác minh từ ngoài (trên máy Mac)

```bash
curl -s https://zah-40.123c.vn/health                 # {"ok":true,"model":...}
curl -s https://zah-40.123c.vn/suggestions            # {"suggestions":[...],"cache":...}
curl -s -X POST https://zah-40.123c.vn/chat \
  -H 'Content-Type: application/json' \
  -d '{"userId":"deploy-test","message":"Chào bạn"}'  # có "reply"
```
Cả 3 chạy được = backend production sẵn sàng cho Mini App.

## Cập nhật code về sau

```bash
bash deploy/push.sh                       # trên Mac
ssh zah40 'cd ~/app && ./.venv/bin/pip install -q -r requirements.txt && sudo systemctl restart tripsmart'
```

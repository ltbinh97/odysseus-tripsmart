# Đưa Odysseus lên Zalo Mini App

Mini App **không** deploy lên server `zah-40.123c.vn` — nó chạy trên **nền tảng Zalo**.
Server chỉ là **backend API** mà Mini App gọi. Vì vậy làm **backend trước** (xem
`deploy/README.md`), verify `https://zah-40.123c.vn/health` chạy, rồi mới làm bước dưới.

## Bức tranh tổng thể

```
 Người dùng Zalo ──► Mini App "Odysseus" (chạy trong Zalo)
                          │  fetch https://zah-40.123c.vn/chat, /chat/stream, /places, /suggestions
                          ▼
                     Backend FastAPI trên server (đã deploy) ──► Claude + SerpApi
```

## Điều kiện cần

1. **Tài khoản Zalo Developer**: https://developers.zalo.me → đăng nhập bằng Zalo.
2. **Zalo Official Account (OA)**: Mini App gắn với một OA. Tạo/dùng OA của team tại https://oa.zalo.me.
3. **Mini App** được tạo trong Zalo Mini App console: https://mini.zalo.me → *Tạo Mini App* → lấy **App ID**.
4. Backend đã chạy HTTPS công khai: `https://zah-40.123c.vn` (bắt buộc HTTPS, không nhận http/IP).

## Bước 1 — Khai báo domain backend (whitelist)

Zalo chặn request tới domain chưa khai báo. Trong console Mini App
(https://mini.zalo.me → app của bạn → **Thông tin ứng dụng / Cấu hình**), thêm
`zah-40.123c.vn` vào danh sách **domain được phép gọi** (request domain / trusted domain).
Thiếu bước này thì app gọi `/chat` sẽ bị chặn.

## Bước 2 — Gắn App ID + base URL vào project

- **App ID**: chạy `zmp` lần đầu nó sẽ hỏi, hoặc sửa trong file cấu hình zmp (`zmp-cli` tạo ra khi `zmp login`). App ID lấy ở console bước điều kiện #3.
- **Base URL backend**: đã set sẵn trong `miniapp/.env.production`:
  ```
  VITE_API_BASE=https://zah-40.123c.vn
  ```
  (Bản build production tự dùng file này; dev vẫn dùng proxy `/api` như cũ.)

## Bước 3 — Đăng nhập & build/deploy bằng zmp CLI

```bash
cd miniapp
npm install                 # nếu máy mới
npx zmp login               # mở trình duyệt, đăng nhập Zalo Developer
npx zmp deploy              # build (vite) rồi upload 1 version lên Zalo
```
- `zmp deploy` tự chạy build production → dùng `.env.production` → gọi đúng `https://zah-40.123c.vn`.
- Nếu `zmp` hỏi chọn app: chọn Mini App đã tạo ở console (đúng App ID).
- Muốn chạy thử local trong khung Zalo trước khi deploy: `npx zmp start`.

## Bước 4 — Test trên điện thoại

Sau `zmp deploy`, console Mini App sẽ có 1 **version Testing** + mã QR / link.
- Mở app **Zalo** trên điện thoại → quét QR (hoặc mở link testing).
- Thêm tài khoản Zalo của bạn vào danh sách **tester** trong console nếu bị chặn.
- Bấm thử tab **Trợ lý AI**, gửi "Đi Bangkok cuối tháng 8, 2 người, 8 triệu" → phải thấy reply (chứng tỏ Mini App → backend production thông).

## Bước 5 — Submit duyệt để công khai

Trong console: điền thông tin app (icon, mô tả, phân loại, chính sách), rồi
**Gửi duyệt** (Submit for review). Zalo review vài ngày; duyệt xong app mới public
cho mọi người. Cho demo hackathon, thường chỉ cần **bản Testing + tester list** là đủ.

## Trục trặc thường gặp

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| App gọi `/chat` fail, không có reply | Domain chưa whitelist | Thêm `zah-40.123c.vn` (Bước 1) |
| `Mixed content` / bị chặn | Backend chạy http/IP | Bắt buộc HTTPS (`deploy/README.md` bước 6) |
| CORS error | (đã fix) | Backend đã bật CORS middleware; restart service nếu vừa cập nhật |
| `zmp deploy` báo chưa chọn app | Chưa login / sai App ID | `npx zmp login` lại, chọn đúng app |
| Streaming (SSE) khựng | nginx buffer | Đã set `proxy_buffering off` cho `/chat/stream` trong nginx conf |

> Lưu ý quota: mỗi lịch trình tốn ~2 lượt SerpApi, mỗi tra vé/khách sạn 1 lượt.
> Cache dùng chung (mới thêm) giúp giảm mạnh, nhưng free tier ~250/tháng — canh khi demo đông.

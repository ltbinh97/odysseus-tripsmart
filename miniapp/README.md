# Odysseus — Zalo Mini App

Front-end cho agent du lịch AI **TripSmart** (thư mục `../tripsmart`).
Ý tưởng: **"Chọn vibe, AI dựng chuyến đi"** (theo concept Lababah) **+** một **trợ lý AI chat**
chạy trực tiếp trên backend hiện có.

> **Backend không bị thay đổi.** App chỉ gọi đúng endpoint có sẵn
> `POST /chat` (`{userId, message}` → `{reply, card, blocked}`) trong
> [`tripsmart/server.py`](../tripsmart/server.py). Không thêm CORS, không thêm route.

---

## Màn hình

| Tab | Chức năng |
|---|---|
| 🧭 **Khám phá** | Lưới "vibe" (biển, ẩm thực, gia đình…) + điểm đến gợi ý + hỏi nhanh. Chạm một vibe → bảng nhập nhanh (điểm đến, ngày, số người, ngân sách) → app tự soạn một câu hỏi tiếng Việt và gửi cho AI. |
| 💬 **Trợ lý AI** | Chat đầy đủ với agent. Hiển thị câu trả lời, **thẻ tóm tắt chuyến đi** (`generate_summary_card`), trạng thái `blocked`, nút **Đặt ngay** + **🗺️ Xem lịch trình gợi ý**. |
| 🗺️ **Lịch trình** | Bản đồ + lịch trình theo ngày (giống "maps your whole day"). Các điểm đánh số trên bản đồ nối bằng **tuyến đường thật từ OpenRouteService**, kèm thời gian di chuyển từng chặng (🚶 đi bộ / 🚗 đi xe). **AI tự sinh lịch trình từ hội thoại** hoặc chọn điểm đến mẫu (Tokyo / Bangkok / Đà Nẵng). Nút **💾 Lưu** để theo dõi. |
| 🎫 **Chuyến đi** | Lịch trình đã lưu (mở lại / xoá) + các thẻ phương án AI đã tạo. |

### AI tự sinh lịch trình từ hội thoại

Backend `/chat` chỉ trả text + `trip_summary` (không có toạ độ) và **không được sửa**. Nên luồng
sinh lịch trình chạy hoàn toàn ở frontend, dùng chính agent + OpenRouteService:

1. **Kích hoạt:** chip "🗺️ Lên lịch trình chi tiết" trong chat, hoặc "✨ Tạo lịch trình bằng AI" trên thẻ chuyến đi.
2. **Xác định điểm đến:** ưu tiên điểm đến từ thẻ `trip_summary`; nếu không có, gửi *transcript hội thoại hiện tại* (cắt ngắn dưới giới hạn `MAX_INPUT_CHARS`=2000 của backend) cho agent để hỏi điểm đến — dùng session id tạm để không lẫn bộ nhớ.
3. **Sinh lịch trình (song ngữ):** prompt định dạng 5 cột `NGÀY|GIỜ|TÊN TIẾNG VIỆT|TÊN QUỐC TẾ|LOẠI` ([`src/utils/itinerary.ts`](src/utils/itinerary.ts)). AI ưu tiên **địa danh nổi tiếng** và cho cả **tên quốc tế** (để geocode chính xác) lẫn **tên tiếng Việt** (để hiển thị). Geocode bằng tên quốc tế theo nhiều biến thể (ưu tiên danh từ riêng, bỏ từ loại như "Monastery/Lake" vì geocoder khớp tên gốc tốt hơn); hiển thị tên tiếng Việt.
4. **Định vị (2 tầng):** geocode từng địa điểm qua **ORS `/geocode/search`** (giới hạn 60km quanh tâm thành phố, chuẩn hoá tên nước VN→EN + `boundary.country`, loại kết quả `layer` thô kiểu thành phố). Địa điểm nào ORS không có (vùng hẻo lánh như Shangri-La) sẽ **fallback sang Nominatim (OSM)** — dữ liệu POI phong phú hơn nhiều ([`src/api/nominatim.ts`](src/api/nominatim.ts), gọi tuần tự ~1 req/giây). Nếu vẫn <2 điểm định vị được → hiển thị **danh sách + banner "chưa đủ dữ liệu bản đồ"** thay vì chồng điểm sai chỗ. Vẽ lên bản đồ + tính tuyến bằng ORS.
5. **Lưu:** nút 💾 lưu lịch trình vào `localStorage`; tab **Chuyến đi** liệt kê, mở lại, xoá.

Yêu cầu có `VITE_ORS_API_KEY` (để geocode). Không có key thì chỉ dùng được lịch trình mẫu.

### Bản đồ & lịch trình (OpenRouteService)

Backend là chat-agent, không có endpoint lịch trình và **không được sửa** — nên tính năng này
là **frontend-driven**:

- Dữ liệu điểm đến (POI + toạ độ) ở [`src/data/itineraries.ts`](src/data/itineraries.ts).
- Bản đồ: **Leaflet** + tile CARTO/OpenStreetMap.
- Tuyến đường & thời gian: **OpenRouteService** ([`src/api/ors.ts`](src/api/ors.ts)) — mỗi chặng
  tự chọn `foot-walking` (gần) hay `driving-car` (xa) rồi vẽ polyline + tính phút di chuyển.
- **Chạy được ngay cả khi chưa có key:** nếu `VITE_ORS_API_KEY` trống hoặc gọi lỗi, app vẽ
  đường thẳng + ước lượng thời gian (haversine). Thêm key → tự động dùng tuyến đường thật.

Lấy key miễn phí tại https://openrouteservice.org/dev/#/signup rồi thêm vào `miniapp/.env`:

```
VITE_ORS_API_KEY=your_ors_key_here
```

(Rồi khởi động lại `npm run dev` để nạp biến môi trường.)

Cốt lõi: người dùng không phải "điền form tìm kiếm". Vibe + vài input → một câu
hội thoại → **agent backend** tự quyết định gọi `search_flights`, `search_hotels`,
`check_travel_requirements`, `family_travel_checklist`… và trả về thẻ.

---

## Chạy thử (trình duyệt)

Cần backend chạy trước (ở thư mục gốc repo):

```bash
# terminal 1 — backend (cần ANTHROPIC_API_KEY)
cd ..
uvicorn tripsmart.server:app --host 0.0.0.0 --port 3000
```

```bash
# terminal 2 — mini app
cd miniapp
cp .env.example .env        # chỉnh BACKEND_ORIGIN nếu backend không ở :3000
npm install
npm run dev                 # http://localhost:5173
```

**CORS:** backend không set CORS header và ta không được sửa nó, nên khi dev trên
trình duyệt, Vite **proxy** `/api/chat` → `BACKEND_ORIGIN/chat`
(xem [`vite.config.mts`](vite.config.mts)). Trình duyệt không gọi cross-origin nên
không vướng CORS — và backend giữ nguyên.

---

## Build & deploy lên Zalo

```bash
npm run build        # xuất tĩnh ra ./www (tsc + vite build)
npm run deploy       # zmp deploy  (cần zmp-cli đã đăng nhập)
```

Cấu hình Mini App ở [`app-config.json`](app-config.json). Khi chạy trong Zalo:

- App lấy `userId` thật qua `zmp-sdk` (`getUserID`); ngoài Zalo thì tự sinh id cục bộ.
- Đặt `VITE_API_BASE=https://your-domain` (origin công khai của backend) và
  **whitelist domain đó** trong Zalo Mini App console. App sẽ gọi thẳng
  `https://your-domain/chat`.

---

## Bản đồ tích hợp backend

| Backend (không sửa) | Front-end dùng ở |
|---|---|
| `POST /chat` → `{reply, card, blocked}` | [`src/api/client.ts`](src/api/client.ts) |
| `card` = `trip_summary` (từ `generate_summary_card`) | [`src/components/TripCard.tsx`](src/components/TripCard.tsx) |
| `blocked` (`rate_limited`, `truncated`, `api_error`…) | thông báo nhỏ trong [`src/pages/ChatPage.tsx`](src/pages/ChatPage.tsx) |
| `checkout_url` (từ `initiate_booking`) | phát hiện trong text reply → nút "Mở thanh toán" |
| `GET /health` | `checkHealth()` trong `client.ts` |

### Nút "Đặt ngay" / mở checkout thật

Backend `initiate_booking` trả `checkout_url`, **nhưng `/chat` chỉ surface
`{reply, card, blocked}`** — url nằm trong tool_result, không phải một field riêng,
và ta **không được sửa backend** để expose nó. Vì vậy luồng đặt chỗ đi qua chính agent:

1. Người dùng bấm **Đặt ngay** trên thẻ → app gửi *"Đặt lựa chọn này giúp mình nhé."* tới agent.
2. Agent gọi `initiate_booking` (bắn commission event phía server) rồi trả lời, **kèm
   link checkout** trong text (system prompt yêu cầu agent chuyển người dùng tới thanh toán).
3. Front-end **dò URL trong reply** ([`src/utils/links.ts`](src/utils/links.ts)) → hiện nút
   vàng **🔒 Mở trang thanh toán** + link inline có thể chạm.
4. Mở link: trong Zalo dùng `zmp-sdk` `openWebview`; trên trình duyệt dùng `window.open`
   (tự nhận biết môi trường qua `inZalo()` trong [`src/utils/zalo.ts`](src/utils/zalo.ts)).

> Cách này giữ đúng nguyên tắc: commission vẫn được track ở backend (qua `initiate_booking`),
> và không cần thay đổi một dòng backend nào.

Kiểu dữ liệu suy ra trực tiếp từ backend nằm ở [`src/types.ts`](src/types.ts).

---

## Cấu trúc

```
miniapp/
├─ app-config.json         # cấu hình Zalo Mini App
├─ vite.config.mts         # dev proxy /api -> backend (né CORS, không sửa backend)
├─ index.html
└─ src/
   ├─ app.tsx              # entry, mount React vào #app
   ├─ api/client.ts        # gọi POST /chat
   ├─ store/AppContext.tsx # state: userId, messages, gửi tin, điều hướng tab
   ├─ pages/               # DiscoverPage · ChatPage · TripsPage
   ├─ components/          # Layout · ComposerSheet · TripCard
   ├─ data/content.ts      # vibes + điểm đến + prompt gợi ý
   ├─ utils/               # format (VND), zalo (zmp-sdk có bảo vệ)
   └─ css/app.css
```

## Ghi chú kỹ thuật

- **Không framework agent, không state phức tạp** — một React context nhỏ, `fetch` thuần.
- **zmp-sdk được gọi có phòng vệ** (try/catch + dynamic import) nên app vẫn chạy tốt
  trong trình duyệt thường khi phát triển.
- Lịch sử chat + thẻ được lưu `localStorage` để không mất khi tải lại.
- Toàn bộ hình ảnh dùng emoji + gradient CSS → nhẹ, không phụ thuộc URL ảnh ngoài.

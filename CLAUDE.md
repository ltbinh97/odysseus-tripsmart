# CLAUDE.md — Zalo TripSmart / Odysseus (handoff)

Bàn giao trạng thái code cho người tiếp tục dev. Repo gồm **2 phần**:

1. **Backend** (`tripsmart/`, Python/FastAPI) — AI travel agent "TripSmart" cho za.hackathon 2026.
2. **Frontend** (`miniapp/`, React + Vite + TypeScript) — Zalo Mini App **"Odysseus"**: "chọn vibe → AI dựng chuyến đi" + trợ lý AI chat + bản đồ/lịch trình theo ngày.

> ⚠️ **Ràng buộc "không sửa backend" ban đầu ĐÃ ĐƯỢC GỠ.** Backend giờ được sửa tự do và đã thay đổi nhiều (giá thật, web_search, tool mới, verification, streaming…). Đừng làm theo ghi chú cũ ở đâu đó nói "backend không được sửa".

---

## Đã thay đổi trong version hiện tại (so với bản gốc mock)

| Mảng | Trước | Giờ |
|---|---|---|
| Giá vé | Mock cứng (VietJet/VNA) | **Google Flights** thật qua SerpApi (`search_flights`) |
| Giá khách sạn | Mock cứng | **Google Hotels** thật qua SerpApi (`search_hotels`) |
| Địa điểm lịch trình | AI bịa tên + geocode ORS/Nominatim (ở frontend) | **Google Maps** thật (POI + rating + toạ độ) qua tool backend `generate_itinerary` |
| web_search | Stub (chưa cài) | **Anthropic web_search server tool** (`web_search_20250305`) |
| Dữ liệu giả khi thiếu | Trả mock | **Không bịa nữa** — trả thông báo trung thực ("tạm thời chưa tra được", "cần ngày check-in/out", "không hỗ trợ sân bay này") |
| Thẻ tóm tắt | Echo nguyên số của model | **Có verification**: `total_vnd` phải khớp giá API thật; `visa_status` phải có gọi tool visa trước |
| Vòng lặp tool | `MAX_TOOL_TURNS=6`, không chống lặp | **8** + **thrash-guard** (`no_progress`) + xử lý `pause_turn` |
| Reply | `MAX_TOKENS=500` (hay bị cắt) | **1000** |
| UX chờ | Im lặng (chấm chấm) | **Streaming trạng thái** qua SSE `/chat/stream` |
| Gọi API lặp | Mỗi lần search = 1 SerpApi call | **Cache dùng chung** (SQLite `api_cache`): vé/khách sạn/POI cache theo query, tái dùng cho mọi user trong `CACHE_TTL_HOURS` (24h giá, 7 ngày POI); user đầu tiên sau khi hết hạn mới refresh. Tiết kiệm quota. |
| Gợi ý điểm đến | Không có | **Crowd-sourced** (SQLite `place_searches`): mọi địa điểm user search được đếm + lưu sample POI → tool `suggest_destinations` + endpoint `GET /suggestions` gợi ý cho user sau. |

---

## Chạy dự án

### Backend (cần API keys, nạp qua `--env-file`)
```bash
# venv tạo lại cho máy này bằng Python 3.9.6 (system /usr/bin/python3 — framework
# 3.13 cũ đã bị gỡ). Mất thì tạo lại (code chạy được cả 3.9 lẫn 3.13+):
#   /usr/bin/python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
source .venv/bin/activate
uvicorn tripsmart.server:app --host 0.0.0.0 --port 3100 --env-file .env
```
- ⚠️ **`python -m tripsmart.server` KHÔNG nạp `.env`** (backend chỉ đọc `os.environ`). Luôn dùng `uvicorn --env-file`.
- ⚠️ **Cổng 3000 bị app khác chiếm trên máy này** → backend chạy ở **3100** (frontend proxy trỏ tới đây).
- `.env` (gốc repo, **gitignore**) chứa các key thật — xem mục Env bên dưới.

### Frontend (Zalo Mini App)
```bash
cd miniapp
npm install
npm run dev      # http://localhost:5173 (Vite), proxy /api/* -> backend :3100
npm run build    # tsc --noEmit && vite build -> www/
```
- **CORS:** Vite dev **proxy** `/api/*` → `BACKEND_ORIGIN` (`miniapp/vite.config.mts`). SSE (`/api/chat/stream`) chạy qua proxy này bình thường.

### Biến môi trường (`.env` gốc repo)
| Key | Ý nghĩa |
|---|---|
| `ANTHROPIC_API_KEY` | Bắt buộc — gọi Claude. |
| `MODEL` | `claude-sonnet-5` (đang dùng — đổi từ Haiku 30/07 để demo chất lượng hơn; đắt hơn ~3-5x, chậm hơn chút). Đổi qua env. ⚠️ `.env` KHÔNG sync qua git — đổi model phải sửa cả `.env` local lẫn server. |
| `SERPAPI_KEY` | **Bắt buộc để có giá/địa điểm thật** (Google Flights/Hotels/Maps). Free tier ~250 search/tháng: https://serpapi.com. Trống → vé/khách sạn/lịch trình trả thông báo "chưa tra được", **không mock**. |
| `MAX_TOKENS` | `1000`. |
| `MAX_TOOL_TURNS` | `8` (⚠️ `.env` ghi đè default trong `config.py`). |
| `ENABLE_REFLECTION` | `false`. Bật `true` → thêm 1 lượt gọi model tự-kiểm câu trả lời (chậm hơn, chính xác hơn). |
| `MAX_INPUT_CHARS` | `2000` (guard chặn input dài hơn → `too_long`). |
| `CACHE_TTL_HOURS` | `24` — TTL cache giá vé/khách sạn. Hết hạn → user tiếp theo trigger refresh. |
| `PLACES_TTL_HOURS` | `168` (7 ngày) — TTL cache POI (đổi chậm hơn giá). |
| `SUGGESTIONS_LIMIT` | `6` — số điểm đến mặc định trả về ở `/suggestions` & tool. |
| `VITE_API_BASE`, `BACKEND_ORIGIN`, `VITE_ORS_API_KEY` | Trong `miniapp/.env` — proxy + geocode ORS (chỉ còn dùng cho lịch trình curated / route polyline). |

---

## Backend — hợp đồng API

`tripsmart/server.py`:
| Endpoint | Vào | Ra |
|---|---|---|
| `POST /chat` | `{userId, message}` | `{reply, card, itinerary, blocked}` (đồng bộ) |
| `POST /chat/stream` | `{userId, message}` | **SSE**: nhiều `event: status {text}` khi tool chạy → `event: done {reply, card, itinerary, blocked}` |
| `POST /places` | `{destination, days}` | `{destination, days, center, places[], data_source}` (Google Maps thật; frontend dùng cho lịch trình) |
| `POST /webhook/zalo` | payload Zalo | ack nhanh, xử lý nền |
| `GET /suggestions?limit=` | — | `{suggestions[], cache}` — điểm đến user trước hay tìm (crowd-sourced), kèm sample POI + `cache_stats` (số API call đã tiết kiệm) |
| `GET /health` | — | `{ok, model}` |

- **`card`** chỉ có khi model gọi `generate_summary_card` (đã qua verification). Kiểu ở `miniapp/src/types.ts` (`TripCard`).
- **`itinerary`** chỉ có khi model gọi `generate_itinerary` → `{destination, days, center, places[]}` (POI thật + rating). Kiểu `ItineraryPayload`.
- **`blocked`** = lý do guard/agent chặn: `rate_limited`, `cooldown`, `too_long`, `truncated`, `empty_reply`, `api_error`, `max_tool_turns`, **`no_progress`** (thrash-guard), `prices_unavailable`… (frontend map ở `ChatPage.noticeText`).
- **`initiate_booking`** trả `checkout_url` (⚠️ **link demo giả**) nhưng `/chat` KHÔNG surface nó — frontend dò URL trong `reply` (`utils/links.ts`).

---

## Nguồn dữ liệu — cái gì THẬT, cái gì TĨNH, cái gì GIẢ

| Tool / nguồn | Loại |
|---|---|
| `search_flights` | ✅ Google Flights (SerpApi), VND. Sân bay ngoài `CITY_IATA` → "không hỗ trợ". Lỗi/không key → "tạm thời chưa tra được" (không mock). |
| `search_hotels` | ✅ Google Hotels (SerpApi), VND. **Chỉ lấy `type=="hotel"`** (bỏ vacation rental). Cần ngày check-in/out; thiếu ngày → hỏi lại. |
| `generate_itinerary` / `POST /places` | ✅ Google Maps (SerpApi): POI + `rating` + toạ độ thật. |
| `web_search` | ✅ Anthropic server tool (`web_search_20250305`, `max_uses:3`). API tự chạy, không qua vòng lặp local. |
| `check_travel_requirements` | 🟡 Dữ liệu **tĩnh** `data/visa_requirements.json` (vetted, KHÔNG phải API chính phủ live). |
| `family_travel_checklist` | 🟡 Tĩnh `data/family_travel_checklist.json`. |
| `save/forget_user_preference` | ✅ SQLite thật (`memory.py`). |
| `suggest_destinations` | ✅ SQLite `place_searches` — điểm đến user trước đã search (đếm + sample POI). Rỗng lúc đầu → tool báo "early user", model tự gợi ý. |
| Cache vé/khách sạn/POI | ✅ SQLite `api_cache` — `Memory.cached_or_fetch()`. Fresh → 0 API call; stale → refresh 1 lần; refresh lỗi → phục vụ bản cũ. Số cache đã lưu độc lập pax/budget/star (tính lại lúc serve). |
| `generate_summary_card` | ✅ Số đã **verify** khớp dữ liệu API thật (xem dưới). |
| `initiate_booking` | ❌ `checkout_url` **giả** (link demo), commission chỉ `print`. |

### `tools.json` — 11 tool (thứ tự quan trọng vì `cache_control` gắn ở tool cuối)
`search_flights`, `search_hotels`, `check_travel_requirements`, `web_search` (server tool, chỉ `{type,name,max_uses}`), `generate_itinerary`, `family_travel_checklist`, `save_user_preference`, `forget_user_preference`, `generate_summary_card`, `suggest_destinations`, `initiate_booking`.

---

## Chống bịa số (anti-hallucination) — QUAN TRỌNG

Hai kiểu bịa từng gặp: (P) model viết prose thêm thắt; (S) model tự điền số vào thẻ. Cơ chế hiện tại:

1. **Sổ cái quan sát** (`agent.py` → `_observe`): mỗi khi tool search chạy, ghi lại số **thật** API trả về vào `ctx["observed"]` (`amounts`, `flight_totals`, `hotel_totals`, `visa_checked`).
2. **Verify thẻ** (`tools.py` → `generate_summary_card` + `_amount_reconciles`): trước khi tạo thẻ, `total_vnd` model đưa ra phải khớp giá đã search (1 giá, hoặc vé+khách sạn, sai số ≤2%). Không khớp → trả `error: total_mismatch`/`unverified_total` + hint → model phải sửa. `visa_status` phải có `visa_checked=True`.
3. **Prompt guard** (`system_prompt.md`): `search_hotels` chỉ dùng `stars`/`rating`/giá tool trả; `stars=null` thì không được gọi "N sao"; không suy tiện nghi từ tên.
4. **Còn hở (chưa fix):** prose trong chat (giá vé, advice từ kiến thức Haiku) vẫn do model viết → có thể sai. Fix triệt để = hiển thị vé/khách sạn bằng **thẻ có cấu trúc** (deterministic) thay vì prose. Xem TODO.

---

## Agent loop (`tripsmart/agent.py`)

Vòng lặp tool-calling: guard → nạp memory + `ctx["observed"]` → gọi Claude (system prompt cached + 11 tool + lịch sử) → model gọi tool → code chạy → lặp **tối đa `MAX_TOOL_TURNS=8`**.

**Chống "mất trí nhớ" do cửa sổ trượt** (lịch sử chỉ giữ `KEEP_RECENT_MESSAGES=8` *message* ≈ 1-2 lượt tool-heavy):
- **Trip state bền** (`sessions.trip_state`): điểm đến/ngày/số người/ngân sách trích **từ args của tool call thành công** (`_update_trip_state` — 0 API call, không bịa được; lỗi validation như `date_in_past` thì không ghi). Sống theo session (TTL 48h).
- **Summary cuốn chiếu** (`sessions.summary`): message bị trim được digest deterministic (`merge_summary`, cap 1500 ký tự, giữ dòng mới nhất) thay vì vứt bỏ.
- Cả hai nạp vào **block system THỨ HAI không cache** (`_build_system`) — block 1 (prompt tĩnh) giữ nguyên prompt cache, block 2 đổi mỗi lượt không làm vỡ cache.
- **Retry API** (429/5xx/timeout, backoff) — `_create_with_retry`.
- **`pause_turn`**: server tool (web_search) chạy dài → tự `continue` để resume.
- **Thrash-guard**: model lặp **đúng cùng tool call** (`_tool_signature`) → dừng sớm, trả `blocked="no_progress"` (tránh đốt hết lượt).
- **`emit` callback** (tuỳ chọn): dùng cho streaming — phát `status` trước khi chạy tool (nhãn VN ở `_TOOL_LABELS`). `emit=None` (mọi test) → hành vi như cũ.
- **Reflection** (`_reflect`): tự-kiểm câu trả lời, **tắt mặc định** (`ENABLE_REFLECTION`).
- `AgentResult` giờ có thêm field `itinerary`.

---

## Frontend — kiến trúc (`miniapp/src/`)

React 18 + Vite 5 + TS. Một React Context (`store/AppContext.tsx`), không router (điều hướng bằng `tab`). `zmp-sdk` gọi có phòng vệ (`utils/zalo.ts`). Bản đồ Leaflet + tile CARTO/OSM.

4 tab (`components/Layout.tsx`): 🧭 Khám phá, 💬 Trợ lý AI, 🗺️ Lịch trình, 🎫 Chuyến đi.

### Điểm mới của frontend version này
- **Streaming**: `api/client.ts` → `sendChatStream` (đọc SSE `/api/chat/stream`); `AppContext.send()` ưu tiên stream, **tự fallback về `sendChat` (`/chat`)** nếu lỗi. Trạng thái sống hiện trong bong bóng chờ (`ChatMessage.statusText`, render ở `ChatPage`).
- **Lịch trình do AGENT dựng**: `/chat` trả `itinerary` → frontend build `DestinationItinerary` bằng `buildItineraryFromPlaces` + `showItinerary()` (mở tab Lịch trình). Chip "🗺️ Xem lịch trình trên bản đồ" trong bubble.
- **Pipeline lịch trình CŨ (frontend tự orchestrate) ĐÃ GỠ**: không còn `generateItinerary`/`generateItineraryFromChat`, không còn session tạm `extract-`/`itin-`, không parse chuỗi 5-cột. Nút "Tạo lịch trình" ở `TripCard` giờ chỉ `planWith("Lên lịch trình chi tiết …")` → agent làm.
- ⚠️ **Module frontend giờ là code chết** (không ai gọi nữa, không gây lỗi build): `api/nominatim.ts`, `data/landmarks.ts`, phần lớn `utils/itinerary.ts` (`buildItineraryPrompt`, `parseItineraryRows`, `EXTRACT_DEST_PROMPT`, `cleanDestination`, `geoCandidates`, `geocodeQuery`, `normalizeDestination`), vài export trong `api/ors.ts` (`geocode`, `COARSE_LAYERS`, `haversineKm`). Có thể xoá cho sạch.

### File map chính
- `api/client.ts` — `sendChat` (POST /chat) + `sendChatStream` (SSE).
- `api/places.ts` — client cho `POST /places` (POI thật). `PlaceResult` dùng lại bởi `buildItineraryFromPlaces`.
- `store/AppContext.tsx` — trái tim: userId, messages, send (streaming+fallback), tab, `showItinerary`, saved itineraries (localStorage).
- `data/itineraries.ts` — lịch trình **curated** (Tokyo/Bangkok/Đà Nẵng, rating hardcode) + `buildItineraryFromPlaces()` (dựng từ POI thật, gán ngày + giờ gợi ý + tối ưu thứ tự) + `buildGeneratedItinerary()` (dùng nội bộ).
- `components/TripCard.tsx` — render `trip_summary`; nút Chia sẻ / Đặt ngay / Tạo lịch trình (→ `planWith`).
- `components/ItineraryMap.tsx` — Leaflet map (nhớ `setView()` trước khi nạp tile).
- `pages/ChatPage.tsx` — chat; render reply/card/itinerary chip/status streaming/checkout link.

---

## Kiểm thử

```bash
.venv/bin/python tests/selftest.py     # 181 passed, 0 failed
cd miniapp && npx tsc --noEmit && npm run build   # đều sạch
```
- Selftest chạy **không cần key** (mock Anthropic client; verification test dùng canned SerpApi + observed ledger giả).

---

## Hạn chế đã biết / TODO (ưu tiên giảm dần)

1. **Giá trong prose vẫn do model viết** (vé máy bay, advice) → còn nguy cơ sai/thêm thắt. Fix triệt để: hiển thị vé/khách sạn bằng **thẻ có cấu trúc** như `TripCard`, không qua prose. (Thẻ tóm tắt đã có verify; đây là bước tiếp theo.)
2. **Google `hotel_class` không đáng tin**: đôi khi gắn "4 sao" cho khách sạn bình dân giá thấp. Tool trả trung thực (`stars`+`rating`+`type`), prompt cấm bịa, nhưng dữ liệu gốc của Google vẫn lệch. Có thể thêm bộ lọc "giá bất thường-thấp so với hạng sao".
3. **`initiate_booking` = link giả**. Muốn thật → cắm ZaloPay (Create Order → order_url; đã khảo sát, xem lịch sử chat).
4. **web_search không stream tiến trình riêng** (chạy trong 1 lần gọi model → chỉ hiện "🧭 Đang xử lý…"). Token-streaming từng chữ chưa làm.
5. **SerpApi free 250 search/tháng** — mỗi lịch trình tốn 2 search, mỗi vé/khách sạn 1. Cẩn thận quota khi demo. Production nên nâng gói.
6. **Reflection tắt mặc định** (độ trễ). Bật khi cần chính xác.
7. **Bảo mật:** `ANTHROPIC_API_KEY`, `SERPAPI_KEY`, `VITE_ORS_API_KEY` nằm trong `.env` (gitignore). Từng dán plaintext trong chat → **nên rotate**.
8. **Dọn code chết frontend** (mục trên).
9. **`userId` do client tự khai** (`POST /chat {userId}`) — chưa xác thực với Zalo, nên về lý thuyết ai biết URL + đoán được userId có thể đọc preference/session của người đó qua chat. Đã giảm thiểu bằng rate-limit theo IP (nginx) + prompt cấm lộ dữ liệu user khác, nhưng fix triệt để = verify Zalo access token (`zmp-sdk getAccessToken` → backend gọi Zalo API đổi ra userId thật). Nên làm trước khi production thật.

---

## Bài học / cạm bẫy (đừng lặp lại)

- **`.env` ghi đè default trong `config.py`.** Đổi hằng số phải sửa `.env` (vd `MAX_TOOL_TURNS`), không chỉ sửa `config.py`.
- **Backend không tự nạp `.env`** → phải `uvicorn --env-file`.
- **SerpApi Google Flights cần mã sân bay CỤ THỂ** (NRT, KIX, ICN…) — mã metro (TYO, OSA, SEL) trả rỗng. Xem `CITY_IATA` trong `tools.py`.
- **Google Hotels trộn vacation rental** giá rẻ bất thường + `stars=null` → lọc `type=="hotel"`.
- **LLM không phải bộ định dạng trung thực**: cho `{stars:null, name:"...Hotel & Spa"}` là Haiku dễ bịa "4 sao, spa đầy đủ". Với số nhạy cảm phải verify hoặc render deterministic, đừng để model tự viết.
- **Agent hay hỏi lại / hụt lượt**: prompt ép trả lời NGAY; `MAX_TOOL_TURNS=8` cho yêu cầu đa bước; thrash-guard chặn lặp.
- **venv trong repo từng trỏ Python 3.13 (framework đã bị gỡ khỏi máy)** → tạo lại bằng `/usr/bin/python3` (3.9.6). Mất thì tạo lại bằng lệnh ở trên.

---

## Trạng thái hiện tại

- ✅ Backend chạy (:3100, Haiku), `/chat` + `/chat/stream` (SSE) + `/places` hoạt động.
- ✅ Frontend build sạch, 4 tab OK, streaming trạng thái sống.
- ✅ Giá vé/khách sạn/địa điểm THẬT (SerpApi); web_search THẬT (Anthropic); không còn mock.
- ✅ Thẻ tóm tắt có verify số; thrash-guard; `MAX_TOKENS=1000`, `MAX_TOOL_TURNS=8`.
- ✅ 181/181 test pass; `tsc`/`build` sạch.

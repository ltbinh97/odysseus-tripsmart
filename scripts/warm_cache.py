"""Warm the shared price/POI cache for demo day.

Chạy TRÊN SERVER (nơi giữ tripsmart.db production):

    cd /opt/tripsmart && .venv/bin/python scripts/warm_cache.py            # warm thật
    cd /opt/tripsmart && .venv/bin/python scripts/warm_cache.py --dry-run  # chỉ in kế hoạch

Vì sao: demo mượt và miễn nhiễm SerpApi chập chờn — mọi kịch bản demo được
tra sẵn và nằm trong cache dùng chung (giá 24h, POI 7 ngày). Chạy lại lần 2
toàn bộ là cache HIT → 0 quota, nên cứ chạy sáng ngày demo cho chắc.

Lưu ý: cache key của giá gắn với NGÀY CỤ THỂ — sửa DEMO_DEPART/DEMO_RETURN
bên dưới cho khớp ngày bạn sẽ gõ khi demo (mặc định 28/08 → 31/08).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Nạp .env thủ công (script chạy ngoài uvicorn nên không có --env-file).
import os

for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from tripsmart import tools as T  # noqa: E402
from tripsmart.memory import Memory  # noqa: E402

# ---- Kịch bản demo (sửa tự do) --------------------------------------------
DEMO_DEPART = "2026-08-28"
DEMO_RETURN = "2026-08-31"
GUESTS = 2  # cache khách sạn key theo số khách — khớp câu demo "2 người"

# Demo thuần Việt Nam — các điểm nội địa nổi bật (khớp luôn các fix VN coverage:
# sân bay UIH/CXR/DLI, domestic không hỏi visa).
PLACES: list[tuple[str, int]] = [  # (điểm đến, số ngày) — key theo days!
    ("Phú Quốc", 3), ("Phú Quốc", 5),
    ("Đà Nẵng", 2), ("Đà Nẵng", 3),
    ("Nha Trang", 3),
    ("Đà Lạt", 3),
    ("Ninh Bình", 2),
    ("Tây Ninh", 2),
]
FLIGHTS: list[tuple[str, str]] = [
    ("TP.HCM", "Phú Quốc"),
    ("TP.HCM", "Đà Nẵng"),
    ("Hà Nội", "Đà Nẵng"),
    ("TP.HCM", "Nha Trang"),
    ("Hà Nội", "Phú Quốc"),
    ("TP.HCM", "Đà Lạt"),
]
HOTELS: list[str] = ["Phú Quốc", "Đà Nẵng", "Nha Trang", "Đà Lạt"]
# ---------------------------------------------------------------------------

DRY = "--dry-run" in sys.argv


def main() -> None:
    if not os.environ.get("SERPAPI_KEY") and not DRY:
        sys.exit("SERPAPI_KEY không có trong .env — dừng.")

    mem = Memory()  # dùng đúng DB_PATH production (./tripsmart.db)
    ctx = {"user_id": "warm-cache", "memory": mem}
    hits = fetched = failed = 0

    def report(kind: str, label: str, result: dict) -> None:
        nonlocal hits, fetched, failed
        meta = result.get("cache") or {}
        if result.get("error"):
            failed += 1
            print(f"  ✗ {kind:8} {label:34} FAIL: {result['error']}")
        elif meta.get("from_cache"):
            hits += 1
            print(f"  = {kind:8} {label:34} HIT (0 quota)")
        else:
            fetched += 1
            print(f"  + {kind:8} {label:34} FETCHED (đã vào cache)")

    print(f"Warm cache — ngày demo {DEMO_DEPART} -> {DEMO_RETURN}, {GUESTS} khách")
    print(f"DB: {mem and 'tripsmart.db'} | dry-run: {DRY}\n")

    for dest, days in PLACES:
        label = f"{dest} ({days} ngày)"
        if DRY:
            print(f"  · places   {label}")
            continue
        try:
            r = T.fetch_places(dest, days, memory=mem)
            report("places", label, r)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗ places   {label:34} FAIL: {exc!r}")

    for org, dst in FLIGHTS:
        label = f"{org} -> {dst}"
        if DRY:
            print(f"  · flights  {label}")
            continue
        r = T.search_flights(
            {"origin_city": org, "destination": dst, "depart_date": DEMO_DEPART,
             "return_date": DEMO_RETURN, "traveler_count": 2}, ctx)
        report("flights", label, r)

    for dest in HOTELS:
        if DRY:
            print(f"  · hotels   {dest}")
            continue
        r = T.search_hotels(
            {"destination": dest, "checkin_date": DEMO_DEPART,
             "checkout_date": DEMO_RETURN, "guests": GUESTS}, ctx)
        report("hotels", dest, r)

    if not DRY:
        print(f"\nKết quả: {hits} hit, {fetched} fetched, {failed} fail")
        print("Chạy lại lần nữa: tất cả phải là HIT (0 quota).")


if __name__ == "__main__":
    main()

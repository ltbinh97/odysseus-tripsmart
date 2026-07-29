"""Tool implementations.

Each function takes (args: dict, ctx: dict) and returns a plain dict. The agent
loop JSON-serialises the return value and hands it back to the model as a
tool_result. Claude never calls an external API itself — it asks this code to.

ctx = {"user_id": str, "memory": Memory}

==== WHAT TO REPLACE BEFORE DEMO DAY ====
Search for "TODO". The important one is search_prices — that is your live API
integration and your Tech Excellence proof point.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Callable

from . import config
from .memory import ALLOWED_PREF_KEYS

_VISA_DATA: dict[str, Any] = json.loads(
    (config.DATA_DIR / "visa_requirements.json").read_text(encoding="utf-8")
)
_FAMILY_DATA: dict[str, Any] = json.loads(
    (config.DATA_DIR / "family_travel_checklist.json").read_text(encoding="utf-8")
)

# Country aliases so "USA", "Mỹ", "US" all resolve to the same dataset key.
COUNTRY_ALIASES: dict[str, str] = {
    "us": "united states",
    "usa": "united states",
    "u.s.": "united states",
    "america": "united states",
    "my": "united states",
    "mỹ": "united states",
    "hoa kỳ": "united states",
    "thai lan": "thailand",
    "thái lan": "thailand",
    "tl": "thailand",
    "trung quốc": "china",
    "trung quoc": "china",
    "cn": "china",
    "prc": "china",
    "viet nam": "vietnam",
    "việt nam": "vietnam",
    "vn": "vietnam",
}

# Destinations that are domestic for a Vietnamese traveller — no visa applies.
DOMESTIC_COUNTRIES: set[str] = {"vietnam"}

# City → country, so the code can catch a contradictory premise such as
# "Bangkok in the US" instead of trusting whatever country the user asserted.
# Extend this as you add destinations; unknown cities simply fall through.
CITY_COUNTRY: dict[str, str] = {
    # Southeast Asia
    "bangkok": "thailand", "băng cốc": "thailand", "phuket": "thailand",
    "chiang mai": "thailand", "pattaya": "thailand", "krabi": "thailand",
    "singapore": "singapore", "kuala lumpur": "malaysia", "penang": "malaysia",
    "jakarta": "indonesia", "bali": "indonesia", "denpasar": "indonesia",
    "manila": "philippines", "cebu": "philippines", "boracay": "philippines",
    "phnom penh": "cambodia", "siem reap": "cambodia", "angkor": "cambodia",
    "vientiane": "laos", "luang prabang": "laos", "yangon": "myanmar",
    # East Asia
    "tokyo": "japan", "osaka": "japan", "kyoto": "japan", "fukuoka": "japan",
    "sapporo": "japan", "nagoya": "japan",
    "seoul": "south korea", "busan": "south korea", "jeju": "south korea",
    "beijing": "china", "bắc kinh": "china", "shanghai": "china",
    "thượng hải": "china", "guangzhou": "china", "shenzhen": "china",
    "chengdu": "china", "xian": "china", "hangzhou": "china",
    "hong kong": "hong kong", "hồng kông": "hong kong", "macau": "macau",
    "taipei": "taiwan", "đài bắc": "taiwan", "kaohsiung": "taiwan",
    # South / Central Asia & Middle East
    "delhi": "india", "new delhi": "india", "mumbai": "india", "goa": "india",
    "kathmandu": "nepal", "colombo": "sri lanka", "male": "maldives",
    "dubai": "united arab emirates", "abu dhabi": "united arab emirates",
    "doha": "qatar", "istanbul": "turkey",
    # Oceania
    "auckland": "new zealand", "queenstown": "new zealand",
    "brisbane": "australia", "perth": "australia", "gold coast": "australia",
    # Europe
    "paris": "france", "nice": "france", "london": "united kingdom",
    "manchester": "united kingdom", "edinburgh": "united kingdom",
    "rome": "italy", "milan": "italy", "venice": "italy", "florence": "italy",
    "madrid": "spain", "barcelona": "spain", "seville": "spain",
    "berlin": "germany", "munich": "germany", "frankfurt": "germany",
    "amsterdam": "netherlands", "brussels": "belgium", "vienna": "austria",
    "zurich": "switzerland", "geneva": "switzerland", "prague": "czech republic",
    "budapest": "hungary", "warsaw": "poland", "lisbon": "portugal",
    "porto": "portugal", "athens": "greece", "santorini": "greece",
    "copenhagen": "denmark", "stockholm": "sweden", "oslo": "norway",
    "helsinki": "finland", "reykjavik": "iceland", "dublin": "ireland",
    # Americas
    "new york": "united states", "new york city": "united states",
    "nyc": "united states", "los angeles": "united states",
    "san francisco": "united states", "seattle": "united states",
    "chicago": "united states", "boston": "united states",
    "las vegas": "united states", "miami": "united states",
    "washington": "united states", "houston": "united states",
    "honolulu": "united states", "hawaii": "united states",
    "toronto": "canada", "montreal": "canada", "ottawa": "canada",
    "mexico city": "mexico", "cancun": "mexico",
    "sao paulo": "brazil", "rio de janeiro": "brazil",
    "buenos aires": "argentina", "lima": "peru", "cusco": "peru",
    # Africa
    "cairo": "egypt", "marrakech": "morocco", "casablanca": "morocco",
    "cape town": "south africa", "johannesburg": "south africa",
    "nairobi": "kenya",
}

# City names that exist in more than one country — never silently assume one.
AMBIGUOUS_CITIES: dict[str, list[str]] = {
    "vancouver": ["canada", "united states"],
    "sydney": ["australia", "canada"],
    "melbourne": ["australia", "united states"],
    "birmingham": ["united kingdom", "united states"],
    "cambridge": ["united kingdom", "united states"],
    "san jose": ["united states", "costa rica"],
    "santiago": ["chile", "spain"],
    "valencia": ["spain", "venezuela"],
    "alexandria": ["egypt", "united states"],
    "hyderabad": ["india", "pakistan"],
    "tripoli": ["libya", "lebanon"],
    "st petersburg": ["russia", "united states"],
}

# Well-known Vietnamese cities, so a destination given as a city (not a country)
# is still recognised as domestic.
DOMESTIC_CITIES: set[str] = {
    "hanoi", "hà nội", "ha noi",
    "ho chi minh city", "hồ chí minh", "ho chi minh", "hcmc", "saigon", "sài gòn", "tp.hcm", "tphcm",
    "da nang", "đà nẵng", "danang",
    "hue", "huế", "hoi an", "hội an", "nha trang", "da lat", "đà lạt", "dalat",
    "phu quoc", "phú quốc", "sapa", "sa pa", "ha long", "hạ long", "can tho", "cần thơ",
    "vung tau", "vũng tàu", "quy nhon", "quy nhơn", "phan thiet", "phan thiết",
    "ninh binh", "ninh bình", "hai phong", "hải phòng",
}

# Every Vietnamese province plus famous destinations, stored ONCE with accents —
# matching is accent-insensitive via _strip_accents, so "Tây Ninh", "tay ninh",
# "Mã Pí Lèng"… all resolve as domestic. Before this, most provinces fell
# through to "not in dataset → web_search / embassy", which is nonsense for a
# Vietnamese traveller going to Tây Ninh.
DOMESTIC_PLACES: set[str] = {
    # 63 tỉnh/thành
    "an giang", "bà rịa - vũng tàu", "bà rịa vũng tàu", "bà rịa", "bạc liêu", "bắc giang",
    "bắc kạn", "bắc ninh", "bến tre", "bình dương", "bình định", "bình phước", "bình thuận",
    "cà mau", "cao bằng", "đắk lắk", "đắk nông", "điện biên", "đồng nai", "đồng tháp",
    "gia lai", "hà giang", "hà nam", "hà tĩnh", "hải dương", "hậu giang", "hòa bình",
    "hưng yên", "khánh hòa", "kiên giang", "kon tum", "lai châu", "lâm đồng", "lạng sơn",
    "lào cai", "long an", "nam định", "nghệ an", "ninh thuận", "phú thọ", "phú yên",
    "quảng bình", "quảng nam", "quảng ngãi", "quảng ninh", "quảng trị", "sóc trăng",
    "sơn la", "tây ninh", "thái bình", "thái nguyên", "thanh hóa", "thừa thiên huế",
    "tiền giang", "trà vinh", "tuyên quang", "vĩnh long", "vĩnh phúc", "yên bái",
    # Địa danh nổi tiếng
    "cát bà", "đồ sơn", "cô tô", "yên tử", "vân đồn", "fansipan", "bắc hà", "y tý",
    "đồng văn", "mã pí lèng", "mèo vạc", "thác bản giốc", "tràng an", "tam cốc",
    "bái đính", "mộc châu", "tà xùa", "mai châu", "mù cang chải", "tam đảo", "mẫu sơn",
    "điện biên phủ", "sầm sơn", "pù luông", "cửa lò", "vinh", "thiên cầm", "phong nha",
    "sơn đoòng", "đồng hới", "cồn cỏ", "lăng cô", "bạch mã", "bà nà", "sơn trà",
    "mỹ khê", "mỹ sơn", "cù lao chàm", "lý sơn", "kỳ co", "eo gió", "tuy hòa",
    "gành đá đĩa", "cam ranh", "phan rang", "vĩnh hy", "mũi né", "langbiang",
    "buôn ma thuột", "pleiku", "biển hồ", "măng đen", "tà đùng", "củ chi", "côn đảo",
    "hồ tràm", "long hải", "nam cát tiên", "cát tiên", "núi bà đen", "chợ nổi cái răng",
    "châu đốc", "núi cấm", "rừng tràm trà sư", "hà tiên", "rạch giá", "nam du",
    "đất mũi", "mỹ tho", "cái bè", "sa đéc", "tràm chim", "hồ ba bể", "ba bể",
    "na hang", "đền hùng", "hồ núi cốc", "tam chúc", "chu lai", "tam kỳ", "bảo lộc",
    "quy nhơn", "ninh chữ", "cần giờ", "bình ba", "điệp sơn", "hòn sơn",
    # POI nổi tiếng trong thành phố (người dùng hay gõ thẳng tên điểm)
    "hồ gươm", "hồ hoàn kiếm", "hồ tây", "văn miếu", "chùa một cột",
    "phố cổ hà nội", "chợ bến thành", "dinh độc lập", "nhà thờ đức bà",
}


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _strip_accents(s: str) -> str:
    """Lowercase + remove Vietnamese diacritics ('Hà Giang' -> 'ha giang').

    Lets one data entry serve every spelling users actually type — with or
    without accents — instead of duplicating each name in the lookup tables."""
    import unicodedata

    s = _norm(s).replace("đ", "d").replace("Đ", "d")
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


# Accent-insensitive membership set built once at import (tables defined above).
_DOMESTIC_ACCENTLESS: set[str] = {
    _strip_accents(x) for x in (DOMESTIC_CITIES | DOMESTIC_PLACES)
}
# Multi-word entries also match as whole-word substrings, so compound inputs
# like "Vinpearl Nha Trang" or "resort Phú Quốc" resolve as domestic. Single
# words stay exact-match to avoid false positives.
_DOMESTIC_MULTIWORD: list[str] = [e for e in _DOMESTIC_ACCENTLESS if " " in e]


def _is_domestic_place(name: Any) -> bool:
    s = _strip_accents(name)
    if s in _DOMESTIC_ACCENTLESS:
        return True
    padded = f" {s} "
    return any(f" {e} " in padded for e in _DOMESTIC_MULTIWORD)


def resolve_country(name: Any) -> str:
    """Normalise a country (or well-known Vietnamese city) to a dataset key."""
    n = _norm(name)
    if _is_domestic_place(n):
        return "vietnam"
    return COUNTRY_ALIASES.get(n, n)


def resolve_destination(name: Any) -> dict:
    """Work out which country a place name belongs to.

    Returns:
        kind    - 'country' | 'city' | 'ambiguous_city' | 'unknown'
        country - resolved country key, or None
        options - candidate countries when the city name is ambiguous
    """
    n = _norm(name)
    if not n:
        return {"kind": "unknown", "country": None, "input": name}

    # Strip a trailing country qualifier the user may have typed, e.g.
    # "Bangkok, Thailand" -> try the leading city part first.
    head = n.split(",")[0].strip()

    if _is_domestic_place(n) or _is_domestic_place(head):
        return {"kind": "city", "country": "vietnam", "input": name}

    if head in AMBIGUOUS_CITIES:
        return {
            "kind": "ambiguous_city",
            "country": None,
            "options": AMBIGUOUS_CITIES[head],
            "input": name,
        }

    if head in CITY_COUNTRY:
        return {"kind": "city", "country": CITY_COUNTRY[head], "input": name}

    resolved = COUNTRY_ALIASES.get(n, n)
    if resolved in _VISA_DATA or resolved in DOMESTIC_COUNTRIES or resolved in set(CITY_COUNTRY.values()):
        return {"kind": "country", "country": resolved, "input": name}

    return {"kind": "unknown", "country": resolved, "input": name}


def estimate_nights(depart: Any, ret: Any) -> int:
    if not depart or not ret:
        return 1
    try:
        d = date.fromisoformat(str(depart))
        r = date.fromisoformat(str(ret))
    except ValueError:
        return 1
    return max(1, (r - d).days)


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _validate(
    *,
    start: Any = None,
    end: Any = None,
    start_label: str = "date",
    end_label: str = "date",
    count: Any = None,
    count_label: str = "traveler_count",
) -> dict | None:
    """Return an error dict if the inputs are impossible, else None.

    Errors are returned as tool results (not raised) so the model can read the
    hint and ask the user a sensible follow-up question instead of the agent
    silently producing nonsense — a past departure date, a negative stay, or a
    500-person booking.
    """
    today = date.today()

    if start is not None:
        s = _parse_date(start)
        if s is None:
            return {
                "error": "invalid_date",
                "field": start_label,
                "hint": f"'{start}' is not a valid YYYY-MM-DD date. Ask the user to clarify the date.",
            }
        if s < today:
            return {
                "error": "date_in_past",
                "field": start_label,
                "value": str(s),
                "today": str(today),
                "hint": (
                    f"The {start_label} {s} is in the past (today is {today}). "
                    "Ask the user which upcoming date they mean — do not search."
                ),
            }
        if (s - today).days > config.MAX_ADVANCE_DAYS:
            return {
                "error": "date_too_far",
                "field": start_label,
                "hint": (
                    f"{start_label} is more than {config.MAX_ADVANCE_DAYS} days ahead; "
                    "prices are not meaningful that far out. Tell the user to check closer to the date."
                ),
            }

        if end is not None:
            e = _parse_date(end)
            if e is None:
                return {
                    "error": "invalid_date",
                    "field": end_label,
                    "hint": f"'{end}' is not a valid YYYY-MM-DD date. Ask the user to clarify.",
                }
            if e <= s:
                return {
                    "error": "dates_reversed",
                    "hint": (
                        f"{end_label} ({e}) must be after {start_label} ({s}). "
                        "Ask the user to confirm the correct dates."
                    ),
                }
            if (e - s).days > config.MAX_NIGHTS:
                return {
                    "error": "stay_too_long",
                    "nights": (e - s).days,
                    "hint": (
                        f"That is a {(e - s).days}-night stay; this tool supports up to "
                        f"{config.MAX_NIGHTS} nights. Suggest splitting the trip or booking in stages."
                    ),
                }

    if count is not None:
        try:
            n = int(count)
        except (TypeError, ValueError):
            return {
                "error": "invalid_count",
                "field": count_label,
                "hint": f"'{count}' is not a number. Ask how many people are travelling.",
            }
        if n < 1:
            return {
                "error": "invalid_count",
                "field": count_label,
                "hint": "There must be at least 1 traveller. Ask the user how many people are going.",
            }
        if n > config.MAX_TRAVELERS:
            return {
                "error": "too_many_travelers",
                "field": count_label,
                "max": config.MAX_TRAVELERS,
                "hint": (
                    f"Groups larger than {config.MAX_TRAVELERS} cannot be booked in one search. "
                    "Suggest splitting into smaller bookings or contacting the airline's group desk."
                ),
            }

    return None


# ---------------------------------------------------------------------------
# Live pricing via SerpApi (Google Flights + Google Hotels)
# ---------------------------------------------------------------------------
# When SERPAPI_KEY is set we fetch real prices; on ANY failure the callers fall
# back to the mock below, so a rate limit / outage never breaks a live demo.
# Prices are requested directly in VND (currency=VND) — no conversion needed.

# City / metro name -> IATA code, so free-text destinations resolve to airports.
# Metro codes (TYO, BKK, SEL…) cover cities with several airports. Unknown names
# simply fall through to the mock.
CITY_IATA: dict[str, str] = {
    # Vietnam (origins + domestic)
    "hanoi": "HAN", "hà nội": "HAN", "ha noi": "HAN",
    "ho chi minh city": "SGN", "hồ chí minh": "SGN", "ho chi minh": "SGN",
    "hcmc": "SGN", "saigon": "SGN", "sài gòn": "SGN", "tp.hcm": "SGN", "tphcm": "SGN",
    "da nang": "DAD", "đà nẵng": "DAD", "danang": "DAD",
    "nha trang": "CXR", "phu quoc": "PQC", "phú quốc": "PQC",
    "da lat": "DLI", "đà lạt": "DLI", "dalat": "DLI", "hue": "HUI", "huế": "HUI",
    # Full Vietnamese airport coverage (accent-insensitive via _iata). Names map
    # to the airport that actually serves the place — including nearby gateways
    # (Hạ Long -> Vân Đồn, Hội An -> Đà Nẵng, Sầm Sơn -> Thọ Xuân).
    "hải phòng": "HPH", "cát bà": "HPH", "đồ sơn": "HPH",
    "vân đồn": "VDO", "hạ long": "VDO", "quảng ninh": "VDO", "cô tô": "VDO",
    "điện biên": "DIN", "điện biên phủ": "DIN",
    "thanh hóa": "THD", "sầm sơn": "THD", "thọ xuân": "THD",
    "vinh": "VII", "nghệ an": "VII", "cửa lò": "VII",
    "đồng hới": "VDH", "quảng bình": "VDH", "phong nha": "VDH",
    "chu lai": "VCL", "tam kỳ": "VCL", "quảng ngãi": "VCL",
    "hội an": "DAD",
    "quy nhơn": "UIH", "bình định": "UIH", "phù cát": "UIH",
    "tuy hòa": "TBB", "phú yên": "TBB",
    "cam ranh": "CXR", "khánh hòa": "CXR",
    "buôn ma thuột": "BMV", "đắk lắk": "BMV",
    "pleiku": "PXU", "gia lai": "PXU",
    "côn đảo": "VCS",
    "cần thơ": "VCA",
    "rạch giá": "VKG",
    "cà mau": "CAH",
    # East / Southeast Asia
    # NOTE: Google Flights needs a SPECIFIC airport code, not a metro code
    # (TYO/OSA/SEL return nothing) — so use the main international gateway.
    "tokyo": "NRT", "osaka": "KIX", "kyoto": "KIX", "fukuoka": "FUK",
    "sapporo": "CTS", "nagoya": "NGO",
    "seoul": "ICN", "busan": "PUS", "jeju": "CJU",
    "bangkok": "BKK", "băng cốc": "BKK", "phuket": "HKT", "chiang mai": "CNX",
    "singapore": "SIN", "kuala lumpur": "KUL", "penang": "PEN",
    "bali": "DPS", "denpasar": "DPS", "jakarta": "CGK", "manila": "MNL", "cebu": "CEB",
    "phnom penh": "PNH", "siem reap": "REP",
    "beijing": "PEK", "bắc kinh": "PEK", "shanghai": "PVG", "thượng hải": "PVG",
    "guangzhou": "CAN", "chengdu": "CTU",
    "hong kong": "HKG", "hồng kông": "HKG", "taipei": "TPE", "đài bắc": "TPE",
    # South Asia / Middle East
    "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM",
    "dubai": "DXB", "abu dhabi": "AUH", "doha": "DOH", "istanbul": "IST",
    # Oceania
    "sydney": "SYD", "melbourne": "MEL", "auckland": "AKL",
    # Europe
    "paris": "CDG", "london": "LHR", "rome": "FCO", "milan": "MXP",
    "madrid": "MAD", "barcelona": "BCN", "berlin": "BER", "munich": "MUC",
    "amsterdam": "AMS", "zurich": "ZRH", "vienna": "VIE", "prague": "PRG",
    "lisbon": "LIS", "athens": "ATH", "copenhagen": "CPH", "dublin": "DUB",
    # Americas
    "new york": "JFK", "new york city": "JFK", "nyc": "JFK",
    "los angeles": "LAX", "san francisco": "SFO", "chicago": "ORD",
    "seattle": "SEA", "las vegas": "LAS", "miami": "MIA", "honolulu": "HNL",
    "toronto": "YYZ", "vancouver": "YVR",
}


# Accent-insensitive IATA lookup built once ("Quy Nhon" finds "quy nhơn").
_IATA_ACCENTLESS: dict[str, str] = {_strip_accents(k): v for k, v in CITY_IATA.items()}


def _iata(name: Any) -> str | None:
    head = _norm(name).split(",")[0].strip()
    return CITY_IATA.get(head) or _IATA_ACCENTLESS.get(_strip_accents(head))


def _cache_label(base: str, meta: dict | None) -> str:
    """Annotate a data_source string with cache provenance for transparency."""
    if not meta or not meta.get("from_cache"):
        return base
    age_min = int((meta.get("age_ms") or 0) / 60000)
    tag = "cached, awaiting refresh" if meta.get("stale") else f"cached {age_min}m ago"
    return f"{base} — {tag}"


def _record_destination(ctx: dict, destination: Any, sample_places: list[dict] | None = None) -> None:
    """Best-effort: remember a searched destination so later users can be shown it.

    Never raises — crowd-sourced suggestions are a nicety and must not break a
    price/place lookup if the write fails."""
    mem = (ctx or {}).get("memory")
    if mem is None or not destination:
        return
    try:
        mem.record_place_search(str(destination), sample_places)
    except Exception as exc:  # noqa: BLE001
        print(f"[record_destination] {exc!r}")


def _serpapi_get(params: dict) -> dict:
    """One SerpApi call. Raises on missing key / HTTP error / API error."""
    import httpx  # dependency of anthropic; imported lazily

    key = os.environ.get("SERPAPI_KEY")
    if not key:
        raise RuntimeError("SERPAPI_KEY not set")
    resp = httpx.get(
        "https://serpapi.com/search.json",
        params={**params, "api_key": key},
        timeout=12.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


def _fetch_flight_options(dep: str, arr: str, depart_date: Any, return_date: Any, round_trip: bool) -> list[dict]:
    """Fetch the pax/budget-INDEPENDENT flight options from Google Flights.

    Google returns per-person fares, so nothing here depends on the traveller
    count or budget — which is exactly why this result is safe to cache and
    reuse across users. Pax scaling and budget checks happen at assembly time.
    """
    params = {
        "engine": "google_flights",
        "departure_id": dep,
        "arrival_id": arr,
        "outbound_date": depart_date,
        "type": "1" if round_trip else "2",  # 1=round trip, 2=one way
        "currency": "VND",
        "hl": "vi",
        "gl": "vn",
    }
    if round_trip:
        params["return_date"] = return_date

    data = _serpapi_get(params)
    raw = (data.get("best_flights") or []) + (data.get("other_flights") or [])

    options = []
    for i, fl in enumerate(raw):
        per_person = int(fl.get("price") or 0)
        if per_person <= 0:
            continue
        segs = fl.get("flights") or []
        carriers = list(dict.fromkeys(s.get("airline") for s in segs if s.get("airline")))
        stops = max(0, len(segs) - 1)
        options.append({
            "option_id": f"fl_{i + 1}",
            "carrier": carriers[0] if carriers else "—",
            "type": "round-trip" if round_trip else "one-way",
            "price_per_person": per_person,
            "note": "direct" if stops == 0 else f"{stops} stop" + ("s" if stops > 1 else ""),
        })
        if len(options) >= 3:
            break

    if not options:
        raise RuntimeError("no priced flight options returned")
    options.sort(key=lambda o: o["price_per_person"])
    return options


def _serpapi_flights(
    args: dict, pax: int, budget: int | None, round_trip: bool, memory: Any = None
) -> dict:
    """Real flight prices from Google Flights (via SerpApi), mapped to our shape.

    The per-person fares are cached (keyed by route + dates) and reused across
    users within CACHE_TTL_HOURS; only the pax/budget-dependent totals are
    recomputed per request, so two travellers on the same route cost one API call.
    """
    dep = _iata(args.get("origin_city"))
    arr = _iata(args.get("destination"))
    if not dep or not arr or dep == arr:
        raise RuntimeError(f"unresolved airport(s): {args.get('origin_city')} -> {args.get('destination')}")

    trip = "rt" if round_trip else "ow"
    cache_key = f"{dep}-{arr}-{args.get('depart_date')}-{args.get('return_date') or ''}-{trip}"

    def _fetch() -> list[dict]:
        return _fetch_flight_options(dep, arr, args.get("depart_date"), args.get("return_date"), round_trip)

    if memory is not None:
        raw_options, meta = memory.cached_or_fetch("flights", cache_key, config.CACHE_TTL_HOURS, _fetch)
    else:
        raw_options, meta = _fetch(), {"from_cache": False, "stale": False, "age_ms": 0}

    options = []
    for o in raw_options:
        total = o["price_per_person"] * pax
        options.append({
            **o,
            "price_total": total,
            "within_budget": (total <= budget) if budget else None,
        })
    options.sort(key=lambda o: o["price_total"])

    return {
        "currency": "VND",
        "route": f"{args.get('origin_city')} → {args.get('destination')}",
        "depart_date": args.get("depart_date"),
        "return_date": args.get("return_date"),
        "traveler_count": pax,
        "budget_vnd": budget,
        "any_within_budget": any(o["within_budget"] for o in options) if budget else None,
        "options": options,
        "data_source": _cache_label("Google Flights (live via SerpApi)", meta),
        "cache": meta,
    }


def _fetch_hotel_props(q: str, checkin: Any, checkout: Any, guests: int, nights: int | None) -> list[dict]:
    """Fetch the star/budget-INDEPENDENT hotel list from Google Hotels.

    Star-class filtering and budget checks depend on the individual request, so
    they are NOT applied here — only the raw priced properties, which are safe to
    cache (keyed by query + dates + guests) and reuse across users.
    """
    data = _serpapi_get({
        "engine": "google_hotels",
        "q": q,
        "check_in_date": str(checkin),
        "check_out_date": str(checkout),
        "adults": str(guests),
        "currency": "VND",
        "hl": "vi",
        "gl": "vn",
    })

    props = data.get("properties") or []

    def _build(p: dict, i: int) -> dict | None:
        per_night = (p.get("rate_per_night") or {}).get("extracted_lowest")
        if not per_night:
            return None
        total = (p.get("total_rate") or {}).get("extracted_lowest")
        if not total and nights:
            total = int(per_night) * nights
        return {
            "option_id": f"ht_{i + 1}",
            "name": p.get("name") or "Hotel",
            "type": p.get("type"),  # "hotel" | "vacation rental" | ...
            "stars": p.get("extracted_hotel_class"),  # null for vacation rentals
            "rating": p.get("overall_rating"),
            "distance_km_from_anchor": None,
            "price_per_night": int(per_night),
            "nights": nights,
            "price_total": int(total) if total else None,
        }

    built = [b for b in (_build(p, i) for i, p in enumerate(props)) if b]
    if not built:
        raise RuntimeError("no priced hotels returned")
    return built


def _serpapi_hotels(
    args: dict, guests: int, near: str, star_min: int | None,
    budget: int | None, checkin: Any, checkout: Any, nights: int | None, anchor: str,
    memory: Any = None,
) -> dict:
    """Real hotel prices from Google Hotels (via SerpApi), mapped to our shape.

    The priced property list is cached (query + dates + guests) and reused across
    users within CACHE_TTL_HOURS; per-request star filtering and budget checks are
    applied to the cached list, so repeated stays cost one API call."""
    q = near or str(args.get("destination") or "").strip()
    if not q:
        raise RuntimeError("no destination for hotel query")

    # Accent-stripped so "Phú Quốc" / "Phu Quoc" share one cache entry.
    cache_key = f"{_strip_accents(q)}-{checkin}-{checkout}-{guests}"

    def _fetch() -> list[dict]:
        return _fetch_hotel_props(q, checkin, checkout, guests, nights)

    if memory is not None:
        built, meta = memory.cached_or_fetch("hotels", cache_key, config.CACHE_TTL_HOURS, _fetch)
    else:
        built, meta = _fetch(), {"from_cache": False, "stale": False, "age_ms": 0}

    # Prefer real hotels over vacation-rental room listings. The latter have no
    # star class and can be misleadingly cheap (a single room in a homestay),
    # which produced nonsense like a "4-star" hotel at 190k VND/night. Fall back
    # to everything only if the destination genuinely returned no hotels.
    hotels = [b for b in built if b.get("type") == "hotel"]
    pool = [dict(b) for b in (hotels or built)]  # copy: don't mutate cached list

    if star_min:
        filtered = [c for c in pool if (c["stars"] or 0) >= star_min]
        pool = filtered or pool
    pool.sort(key=lambda o: o["price_per_night"])
    options = pool[:3]
    if not options:
        raise RuntimeError("no priced hotels returned")

    # Budget check is per-request, so apply it to the (possibly cached) options here.
    for o in options:
        total = o.get("price_total")
        o["within_budget"] = (total <= budget) if (total and budget) else None

    return {
        "currency": "VND",
        "destination": args.get("destination"),
        "anchor": anchor,
        "searched_near_landmark": bool(near),
        "guests": guests,
        "nights": nights,
        "dates_known": True,
        "budget_vnd": budget,
        "options": options,
        "pricing_basis": "total for stay",
        "data_source": _cache_label("Google Hotels (live via SerpApi)", meta),
        "cache": meta,
    }


# ---------------------------------------------------------------------------
# Real places for itineraries — Google Maps (via SerpApi): actual POIs, real
# ratings, real coordinates. Replaces AI-invented place names.
# ---------------------------------------------------------------------------
# Map Google Maps category ids/labels -> the app's Vietnamese categories.
_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("restaurant", "cafe", "coffee", "food", "meal", "bakery", "dessert", "ẩm thực", "nhà hàng", "quán"), "Ẩm thực"),
    (("museum", "art_gallery", "gallery", "bảo tàng"), "Bảo tàng"),
    (("beach", "bãi biển"), "Biển"),
    (("night_club", "bar", "nightlife", "về đêm"), "Về đêm"),
    (("amusement", "zoo", "aquarium", "theme_park", "water_park", "vui chơi", "công viên giải trí"), "Vui chơi"),
    (("shopping", "store", "market", "mall", "department", "mua sắm", "chợ"), "Mua sắm"),
    (("park", "garden", "mountain", "hiking", "natural", "forest", "national_park", "botanical", "ngoài trời", "công viên", "vườn", "núi"), "Ngoài trời"),
    (("temple", "shrine", "church", "monastery", "worship", "historical", "historic", "monument", "castle", "palace", "văn hoá", "đền", "chùa", "lịch sử", "di tích"), "Văn hoá"),
]


def _maps_category(place: dict) -> str:
    """Best-effort map of a Google Maps result to one of the app's categories."""
    hay = " ".join(
        str(x).lower()
        for x in (
            [place.get("type")]
            + list(place.get("types") or [])
            + list(place.get("type_ids") or [])
        )
        if x
    )
    for needles, cat in _CATEGORY_RULES:
        if any(n in hay for n in needles):
            return cat
    return "Biểu tượng"


def _map_place(r: dict) -> dict | None:
    gps = r.get("gps_coordinates") or {}
    lat, lng = gps.get("latitude"), gps.get("longitude")
    if lat is None or lng is None or not r.get("title"):
        return None
    return {
        "name": r.get("title"),
        "category": _maps_category(r),
        "rating": r.get("rating"),
        "reviews": r.get("reviews"),
        "lat": lat,
        "lng": lng,
        "address": r.get("address"),
    }


# Results whose Google types match these are not itinerary stops (lodging, tour
# desks, rentals) — they pollute the plan, so they are filtered out up front.
_JUNK_PLACE_TYPES: tuple[str, ...] = (
    "hotel", "lodging", "resort", "hostel", "guest_house", "homestay",
    "travel_agency", "tour_operator", "tour_agency", "car_rental", "real_estate",
)


def _is_junk_place(r: dict) -> bool:
    hay = " ".join(
        str(x).lower()
        for x in ([r.get("type")] + list(r.get("types") or []) + list(r.get("type_ids") or []))
        if x
    )
    return any(t in hay for t in _JUNK_PLACE_TYPES)


def _fetch_places_live(dest: str, days: int) -> dict:
    """The actual Google Maps lookup + itinerary assembly (cacheable unit)."""

    def _maps(query: str) -> list[dict]:
        data = _serpapi_get(
            {"engine": "google_maps", "q": query, "hl": "vi", "type": "search"}
        )
        return data.get("local_results") or []

    def _gather(queries: list[str], need: int) -> list[dict]:
        """Run query variants in order, merging + deduping (by name) until we
        have `need` places. Extra variants only run when the previous ones came
        up short, so the common case still costs a single API call.

        Why variants: Google Maps is phrasing-sensitive — e.g. 'tourist
        attractions in Phu Quoc' returns NOTHING while the Vietnamese phrasing
        returns 20 real POIs. One bad phrasing used to produce restaurant-only
        'itineraries'."""
        found: list[dict] = []
        seen: set[str] = set()
        for q in queries:
            try:
                raw = [r for r in _maps(q) if not _is_junk_place(r)]
            except Exception as exc:  # noqa: BLE001 - one failed variant isn't fatal
                print(f"[fetch_places query error] {q!r}: {exc!r}")
                continue
            for p in (_map_place(r) for r in raw):
                if not p:
                    continue
                key = str(p["name"]).strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    found.append(p)
            if len(found) >= need:
                break
        return found

    # The app speaks Vietnamese (hl=vi), so the Vietnamese phrasing is primary
    # for attractions; English phrasings are fallbacks for destinations where
    # it underperforms. Food keeps the proven English phrasing first.
    attractions = _gather(
        [
            f"địa điểm tham quan ở {dest}",
            f"tourist attractions in {dest}",
            f"things to do in {dest}",
        ],
        need=days * 4,
    )
    food = _gather(
        [f"best restaurants in {dest}", f"quán ăn ngon ở {dest}"],
        need=days,
    )

    if not attractions and not food:
        raise RuntimeError(f"no places found for {dest!r}")

    center = (
        {"lat": attractions[0]["lat"], "lng": attractions[0]["lng"]}
        if attractions
        else {"lat": food[0]["lat"], "lng": food[0]["lng"]}
    )

    # Interleave sights and food so each day gets a mix; cap to ~5 per day.
    a_per_day, f_per_day = 4, 1
    places: list[dict] = []
    ai = fi = 0
    for _ in range(days):
        places.extend(attractions[ai:ai + a_per_day]); ai += a_per_day
        places.extend(food[fi:fi + f_per_day]); fi += f_per_day
    if not places:  # both lists shorter than expected
        places = (attractions + food)[: days * 5]

    return {
        "destination": dest,
        "days": days,
        "center": center,
        "places": places[: days * 5],
        "data_source": "Google Maps (live via SerpApi)",
    }


def _drop_far_places(payload: dict, max_km: float = 120.0) -> dict:
    """Remove POIs implausibly far from the itinerary center.

    Google sometimes returns a same-named venue on another continent (a
    'Da-Lat Restaurant' in Massachusetts appeared in a Đà Lạt lookup), which
    would wreck the map. Applied at serve time so even stale cached payloads
    are cleaned without a refetch."""
    import math

    center = payload.get("center") or {}
    lat0, lng0 = center.get("lat"), center.get("lng")
    if lat0 is None or lng0 is None:
        return payload

    def km(p: dict) -> float:
        la, lo = math.radians(p["lat"] - lat0), math.radians(p["lng"] - lng0)
        h = (math.sin(la / 2) ** 2
             + math.cos(math.radians(lat0)) * math.cos(math.radians(p["lat"])) * math.sin(lo / 2) ** 2)
        return 2 * 6371 * math.asin(min(1.0, math.sqrt(h)))

    places = payload.get("places") or []
    kept = [p for p in places if km(p) <= max_km]
    if len(kept) != len(places):
        dropped = [p["name"] for p in places if p not in kept]
        print(f"[fetch_places] dropped far-away results: {dropped}")
        return {**payload, "places": kept}
    return payload


def fetch_places(destination: str, days: int = 2, memory: Any = None) -> dict:
    """Real POIs (attractions + restaurants) for a destination, with ratings and
    coordinates, straight from Google Maps. Raises on failure / no key.

    When a `memory` is given, the POI list is cached (shared across users for
    PLACES_TTL_HOURS) and the destination is recorded for crowd-sourced
    suggestions. Without one, this behaves exactly as a fresh live lookup."""
    dest = str(destination or "").strip()
    if not dest:
        raise RuntimeError("no destination")
    days = max(1, min(5, int(days or 2)))

    if memory is None:
        return _drop_far_places(_fetch_places_live(dest, days))

    # "v2" invalidates entries cached by the old single-phrasing fetch, which
    # could store restaurant-only results (e.g. Phú Quốc) for PLACES_TTL_HOURS.
    # Accent-stripped key so "Phú Quốc" and "Phu Quoc" share one entry (and one
    # quota spend) instead of two.
    payload, meta = memory.cached_or_fetch(
        "places", f"v2:{_strip_accents(dest)}-{days}", config.PLACES_TTL_HOURS,
        lambda: _fetch_places_live(dest, days),
    )
    sample = [
        {"name": p.get("name"), "rating": p.get("rating")}
        for p in (payload.get("places") or [])[:5]
        if p.get("name")
    ]
    try:
        memory.record_place_search(dest, sample)
    except Exception as exc:  # noqa: BLE001 - suggestions must never break the lookup
        print(f"[fetch_places record] {exc!r}")
    return {**_drop_far_places(payload), "cache": meta}


# ---------------------------------------------------------------------------
# Honest "no fabricated data" responses (used when we cannot fetch real prices)
# ---------------------------------------------------------------------------
def _flights_unavailable(args: dict) -> dict:
    return {
        "found": False,
        "error": "prices_unavailable",
        "route": f"{args.get('origin_city')} → {args.get('destination')}",
        "message": (
            "Xin lỗi, hệ thống tạm thời chưa tra được giá vé máy bay lúc này. "
            "Bạn thử lại sau ít phút giúp mình nhé."
        ),
        "hint": (
            "Live pricing is unavailable right now. Do NOT invent, estimate, or "
            "guess any flight prices. Relay the Vietnamese 'message' and offer to "
            "try again shortly."
        ),
    }


def _hotels_need_dates(args: dict) -> dict:
    return {
        "found": False,
        "error": "dates_required",
        "destination": args.get("destination"),
        "message": (
            "Để báo giá khách sạn chính xác, mình cần biết ngày nhận phòng "
            "(check-in) và ngày trả phòng (check-out). Bạn cho mình biết 2 mốc "
            "ngày này nhé."
        ),
        "hint": (
            "Ask the user for check-in and check-out dates before quoting any "
            "hotel prices. Do NOT invent or estimate prices."
        ),
    }


def _hotels_unavailable(args: dict) -> dict:
    return {
        "found": False,
        "error": "prices_unavailable",
        "destination": args.get("destination"),
        "message": (
            "Xin lỗi, hệ thống tạm thời chưa tra được giá khách sạn lúc này. "
            "Bạn thử lại sau ít phút giúp mình nhé."
        ),
        "hint": (
            "Live pricing is unavailable right now. Do NOT invent hotel prices. "
            "Relay the Vietnamese 'message' and offer to try again shortly."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 1 — search_flights   (live via Google Flights / SerpApi — no mock data)
# ---------------------------------------------------------------------------
def search_flights(args: dict, ctx: dict) -> dict:
    """Real flight prices only. If we cannot fetch live prices (city not
    supported, no key, or a transient API failure) we say so honestly — we
    never fabricate fares."""

    bad = _validate(
        start=args.get("depart_date"),
        end=args.get("return_date"),
        start_label="depart_date",
        end_label="return_date",
        count=args.get("traveler_count"),
    )
    if bad:
        return bad

    pax = int(args.get("traveler_count") or 1)
    budget = args.get("budget_vnd")
    budget = int(budget) if budget else None
    round_trip = bool(args.get("return_date"))

    # Resolve both cities to supported airports first (works with or without a
    # key). If either is unknown, say so honestly instead of guessing a price.
    dep = _iata(args.get("origin_city"))
    arr = _iata(args.get("destination"))
    if not dep or not arr:
        unresolved = [
            str(c)
            for c, code in (
                (args.get("origin_city"), dep),
                (args.get("destination"), arr),
            )
            if not code
        ]
        places = " và ".join(unresolved)
        print(f"[flights unsupported airport] {unresolved}")
        return {
            "found": False,
            "error": "unsupported_airport",
            "origin_city": args.get("origin_city"),
            "destination": args.get("destination"),
            "unresolved_places": unresolved,
            "message": (
                f"Không tìm thấy vé máy bay vì hệ thống chưa hỗ trợ tra giá vé "
                f"cho {places} — nơi này chưa có trong danh sách sân bay được hỗ "
                f"trợ. Bạn thử chọn một thành phố lớn có sân bay quốc tế gần đó nhé."
            ),
            "hint": (
                "Do NOT invent, estimate, or guess any flight prices for this "
                "route. Relay the Vietnamese 'message' to the user, then suggest "
                "a nearby major city that has an international airport."
            ),
        }

    # Same airport on both ends ("Hà Nội -> Hà Nội", or two names served by one
    # airport) — searching would waste quota and confuse the user.
    if dep == arr:
        return {
            "found": False,
            "error": "same_route",
            "origin_city": args.get("origin_city"),
            "destination": args.get("destination"),
            "airport": dep,
            "message": (
                "Điểm đi và điểm đến dùng cùng một sân bay nên không có chuyến "
                "bay phù hợp. Bạn kiểm tra lại điểm đến giúp mình nhé."
            ),
            "hint": (
                "Origin and destination resolve to the same airport. Ask the "
                "user to confirm the destination; do not search or invent fares."
            ),
        }

    # Airports OK — fetch real prices. No key or a transient failure => honest
    # "unavailable" message. We never return fabricated fares.
    if not os.environ.get("SERPAPI_KEY"):
        return _flights_unavailable(args)
    try:
        result = _serpapi_flights(args, pax, budget, round_trip, memory=ctx.get("memory"))
    except Exception as exc:  # noqa: BLE001
        print(f"[serpapi flights error] {exc!r}")
        return _flights_unavailable(args)
    # Note the destination so it can be suggested to later users (count only).
    _record_destination(ctx, args.get("destination"))
    return result


# ---------------------------------------------------------------------------
# Tool 2 — search_hotels   *** REPLACE THE MOCK WITH A REAL API ***
# ---------------------------------------------------------------------------
def search_hotels(args: dict, ctx: dict) -> dict:
    """Real hotel prices only (Google Hotels via SerpApi).

    Google Hotels needs check-in/out dates, so without them we ask the user for
    dates rather than inventing indicative rates. If a live lookup fails we say
    so honestly — we never fabricate hotel prices.
    """
    bad = _validate(
        start=args.get("checkin_date"),
        end=args.get("checkout_date"),
        start_label="checkin_date",
        end_label="checkout_date",
        count=args.get("guests"),
        count_label="guests",
    )
    if bad:
        return bad

    guests = int(args.get("guests") or 1)
    near = (args.get("near") or "").strip()
    star_min = args.get("star_min")
    star_min = int(star_min) if star_min else None
    budget = args.get("budget_vnd")
    budget = int(budget) if budget else None

    checkin = args.get("checkin_date")
    checkout = args.get("checkout_date")
    dates_known = bool(checkin and checkout)
    nights = estimate_nights(checkin, checkout) if dates_known else None

    anchor = near or f"{args.get('destination')} centre"

    # No dates -> ask the user for them (Google Hotels requires them). We do not
    # invent indicative rates.
    if not dates_known:
        return _hotels_need_dates(args)

    # Dates OK — fetch real prices. No key or a transient failure => honest
    # "unavailable" message. We never return fabricated hotel prices.
    if not os.environ.get("SERPAPI_KEY"):
        return _hotels_unavailable(args)
    try:
        result = _serpapi_hotels(
            args, guests, near, star_min, budget, checkin, checkout, nights, anchor,
            memory=ctx.get("memory"),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[serpapi hotels error] {exc!r}")
        return _hotels_unavailable(args)
    _record_destination(ctx, args.get("destination"))
    return result


# ---------------------------------------------------------------------------
# Tool 2 — check_travel_requirements (curated lookup + graceful miss)
# ---------------------------------------------------------------------------
def check_travel_requirements(args: dict, ctx: dict) -> dict:
    stated_country = args.get("destination_country")
    stated_city = args.get("destination_city")
    nat = _norm(args.get("nationality")) or "vietnamese"

    # --- Catch a contradictory premise before looking anything up -----------
    # A user may assert something factually wrong ("Bangkok in the US"). Trusting
    # it would return real US visa rules for a Thailand trip — correct data, wrong
    # premise, and the most dangerous failure mode this tool has.
    if stated_city:
        city = resolve_destination(stated_city)

        if city["kind"] == "ambiguous_city":
            return {
                "error": "ambiguous_city",
                "city": stated_city,
                "possible_countries": city["options"],
                "hint": (
                    f"'{stated_city}' exists in more than one country "
                    f"({', '.join(city['options'])}). Ask the user which one they mean "
                    "before looking up any requirements."
                ),
            }

        if city["country"] and stated_country:
            stated = resolve_country(stated_country)
            if stated != city["country"]:
                return {
                    "error": "destination_conflict",
                    "city": stated_city,
                    "city_is_in": city["country"],
                    "user_said_country": stated,
                    "hint": (
                        f"{stated_city} is in {city['country'].title()}, not "
                        f"{stated.title()}. The user's request is contradictory. "
                        "Point out the discrepancy politely, confirm which they mean, "
                        "and do not present requirements for either country until they answer."
                    ),
                }

        # City resolved cleanly and no conflicting country was asserted.
        if city["country"] and not stated_country:
            stated_country = city["country"]

    if not stated_country:
        return {
            "error": "no_destination",
            "hint": "No destination given. Ask the user where they are travelling to.",
        }

    dest_info = resolve_destination(stated_country)
    if dest_info["kind"] == "ambiguous_city":
        return {
            "error": "ambiguous_city",
            "city": stated_country,
            "possible_countries": dest_info["options"],
            "hint": (
                f"'{stated_country}' exists in more than one country "
                f"({', '.join(dest_info['options'])}). Ask which one before looking up requirements."
            ),
        }

    dest = dest_info["country"] or resolve_country(stated_country)
    resolved_from_city = dest_info["kind"] == "city"

    # Domestic travel needs no visa. Without this, a Hanoi trip fell through to
    # the "not in dataset" branch and told a Vietnamese user to ask an embassy.
    if dest in DOMESTIC_COUNTRIES and nat in {"vietnamese", "viet nam", "vietnam", "vn"}:
        return {
            "found": True,
            "domestic": True,
            "destination": stated_country,
            "nationality": nat,
            "visa_type": "not-applicable",
            "summary": "Domestic travel within Vietnam — no visa or entry formalities.",
            "advisory": "Bring photo ID for hotel check-in and domestic flights.",
        }

    entry = _VISA_DATA.get(dest)

    if not entry:
        # Graceful miss — the prompt instructs the agent to fall back to web_search.
        return {
            "found": False,
            "destination": stated_country,
            "resolved_country": dest,
            "note": (
                "Not in curated dataset. Call web_search to confirm current official "
                "requirements, and tell the user to verify with the embassy."
            ),
        }

    rule = entry.get(nat) or entry.get("default") or {}
    return {
        "found": True,
        "destination": stated_country,
        "resolved_from_city": resolved_from_city,
        "nationality": nat,
        **rule,
        "data_source": "curated dataset (static, vetted) — not a live government API",
    }


# ---------------------------------------------------------------------------
# Tool 3 — web_search
# ---------------------------------------------------------------------------
def web_search(args: dict, ctx: dict) -> dict:
    """Live web search via SerpApi (Google). Returns the answer box (if any) and
    the top organic results, so the agent can cite real, current sources instead
    of guessing. Degrades gracefully when unavailable."""
    query = str(args.get("query") or "").strip()
    if not query:
        return {"implemented": True, "query": query, "results": [], "note": "empty query"}

    if not os.environ.get("SERPAPI_KEY"):
        return {
            "implemented": False,
            "query": query,
            "note": (
                "web_search is not configured. Tell the user you could not verify "
                "current details and they should check the official source "
                "(embassy / airline / government site). Do not invent an answer."
            ),
        }

    try:
        data = _serpapi_get(
            {"engine": "google", "q": query, "hl": "vi", "gl": "vn", "num": "5"}
        )
        results = [
            {"title": r.get("title"), "link": r.get("link"), "snippet": r.get("snippet")}
            for r in (data.get("organic_results") or [])[:5]
            if r.get("title")
        ]
        answer_box = data.get("answer_box") or {}
        answer = answer_box.get("answer") or answer_box.get("snippet")
        return {
            "implemented": True,
            "query": query,
            "answer": answer,
            "results": results,
            "note": (
                "Live Google results. Summarise for the user and cite the source "
                "link(s). If nothing relevant, tell the user to check the official "
                "source; do not invent an answer."
            ),
            "data_source": "Google (live via SerpApi)",
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[web_search error] {exc!r}")
        return {
            "implemented": False,
            "query": query,
            "note": (
                "web_search is temporarily unavailable. Tell the user you could not "
                "verify current details and they should check the official source. "
                "Do not invent an answer."
            ),
        }


# ---------------------------------------------------------------------------
# Tool 4 — family_travel_checklist (curated RAG, always returns something)
# ---------------------------------------------------------------------------
def family_travel_checklist(args: dict, ctx: dict) -> dict:
    dest = resolve_country(args.get("destination_country"))
    entry = _FAMILY_DATA.get(dest)
    used_fallback = entry is None
    if used_fallback:
        entry = _FAMILY_DATA.get("default", {})

    out = {
        "destination": args.get("destination_country"),
        "age_range": args.get("child_age_range") or "unspecified",
        "one_parent_consent_needed": bool(args.get("traveling_with_one_parent")),
        "generic_guidance": used_fallback,
        **entry,
    }
    if used_fallback:
        out["note"] = (
            "No country-specific entry — returned generic guidance. "
            "Consider web_search for destination specifics."
        )
    return out


# ---------------------------------------------------------------------------
# Tool 5 — save_user_preference (validated + PII-guarded in memory.py)
# ---------------------------------------------------------------------------
def save_user_preference(args: dict, ctx: dict) -> dict:
    res = ctx["memory"].save_preference(ctx["user_id"], args.get("key"), args.get("value"))
    if res["saved"]:
        return {"saved": True, "key": args.get("key"), "value": args.get("value")}
    return {
        "saved": False,
        "reason": res["reason"],
        "note": "Do not retry with personal data.",
    }


# ---------------------------------------------------------------------------
# Tool — forget_user_preference (correction / right to be forgotten)
# ---------------------------------------------------------------------------
def forget_user_preference(args: dict, ctx: dict) -> dict:
    key = _norm(args.get("key"))
    memory = ctx["memory"]
    user_id = ctx["user_id"]

    if key == "all":
        removed = memory.clear_preferences(user_id)
        return {"deleted": True, "key": "all", "removed_count": removed}

    if key not in ALLOWED_PREF_KEYS:
        return {
            "deleted": False,
            "reason": f"'{args.get('key')}' is not a stored preference key",
            "known_keys": sorted(ALLOWED_PREF_KEYS),
        }

    removed = memory.delete_preference(user_id, key)
    return {
        "deleted": bool(removed),
        "key": key,
        "reason": None if removed else "nothing was stored under that key",
    }


# ---------------------------------------------------------------------------
# Tool — generate_summary_card
# ---------------------------------------------------------------------------
def _amount_reconciles(total: int, observed: dict, tol: float = 0.02) -> bool:
    """True if `total` traces to real searched prices — either it equals a single
    observed amount, or the sum of one flight total + one hotel total (within a
    small rounding tolerance). Blocks the model from inventing the headline number.
    """
    amounts = observed.get("amounts") or set()
    flight_totals = observed.get("flight_totals") or set()
    hotel_totals = observed.get("hotel_totals") or set()

    def near(a: int, b: int) -> bool:
        return abs(a - b) <= max(1000, round(b * tol))

    if any(near(total, a) for a in amounts):
        return True
    for f in flight_totals:
        for h in hotel_totals:
            if near(total, f + h):
                return True
    return False


def generate_summary_card(args: dict, ctx: dict) -> dict:
    """Build the trip summary card — but VERIFY the model-supplied numbers against
    what the external APIs actually returned this conversation, so the headline
    figures can't be fabricated or miscalculated. `ctx['observed']` is the ledger
    the agent loop fills as search tools run."""
    total = args.get("total_vnd")
    budget = args.get("budget_vnd")
    observed = (ctx or {}).get("observed")

    # Only enforce when a ledger exists (the agent loop always provides one; a few
    # isolated unit tests call this tool directly without it).
    if observed is not None:
        if total is not None:
            if not (observed.get("amounts")):
                return {
                    "error": "unverified_total",
                    "hint": (
                        "total_vnd was provided but no flight/hotel price was searched "
                        "this conversation. Call search_flights/search_hotels first, or "
                        "omit total_vnd — never estimate a total."
                    ),
                }
            if not _amount_reconciles(int(total), observed):
                return {
                    "error": "total_mismatch",
                    "claimed_total_vnd": int(total),
                    "searched_amounts": sorted(observed.get("amounts") or set()),
                    "hint": (
                        "total_vnd does not match any searched price or (flight total + "
                        "hotel total). Use the exact numbers from the search results; do "
                        "not round or estimate. Re-issue the card with a correct total."
                    ),
                }
        if args.get("visa_status") and not observed.get("visa_checked"):
            return {
                "error": "unverified_visa",
                "hint": (
                    "visa_status was provided but check_travel_requirements was not "
                    "called. Call it first, or omit visa_status — do not state visa "
                    "rules from memory."
                ),
            }

    return {
        "card": {
            "type": "trip_summary",
            "version": 1,
            **args,
            "over_budget": (total > budget) if (total and budget) else None,
        }
    }


# ---------------------------------------------------------------------------
# Tool — generate_itinerary (real day-by-day places via Google Maps)
# ---------------------------------------------------------------------------
def generate_itinerary(args: dict, ctx: dict) -> dict:
    """Build a real itinerary from actual POIs (with ratings + coordinates).

    Returns an `itinerary` object the agent loop surfaces to the app, which
    renders it as an interactive map + day-by-day list. Never fabricates places.
    """
    dest = str(args.get("destination") or "").strip()
    days = args.get("days") or 2
    if not dest:
        return {
            "error": "no_destination",
            "hint": "Ask the user which place to build the itinerary for.",
        }
    try:
        data = fetch_places(dest, days, memory=ctx.get("memory"))
    except Exception as exc:  # noqa: BLE001 - never break the loop
        print(f"[generate_itinerary] {exc!r}")
        return {
            "error": "itinerary_unavailable",
            "destination": dest,
            "message": (
                f"Xin lỗi, mình chưa dựng được lịch trình chi tiết cho {dest} lúc "
                "này. Bạn thử lại sau một chút nhé."
            ),
            "hint": "Relay the message. Do NOT invent places or a schedule.",
        }

    if len(data.get("places") or []) < 2:
        return {
            "error": "insufficient_places",
            "destination": dest,
            "message": (
                f"Mình chưa tìm đủ địa điểm nổi bật cho {dest} để dựng lịch trình "
                "trên bản đồ."
            ),
            "hint": "Tell the user; suggest a larger nearby city. Do not fabricate.",
        }

    n = len(data["places"])
    return {
        "itinerary": data,
        "summary": f"Đã dựng lịch trình {days} ngày cho {dest} với {n} địa điểm thật (kèm đánh giá).",
        "hint": (
            "The app renders 'itinerary' as an interactive map + day-by-day list. "
            "Give a SHORT intro (1-2 sentences) and tell the user to open the "
            "itinerary/map — do NOT list every stop in your text."
        ),
    }


# ---------------------------------------------------------------------------
# Tool — suggest_destinations (crowd-sourced: what others have searched)
# ---------------------------------------------------------------------------
def suggest_destinations(args: dict, ctx: dict) -> dict:
    """Popular destinations previously searched by other users of this app.

    Reads the shared `place_searches` ledger (populated whenever anyone searches
    flights/hotels or builds an itinerary) so a new or undecided user can be
    pointed at real, in-demand places — with a few sample POIs — instead of the
    model guessing. Returns an empty list gracefully when nothing is logged yet."""
    mem = (ctx or {}).get("memory")
    if mem is None:
        return {"suggestions": [], "note": "No suggestion store available."}

    try:
        limit = int(args.get("limit") or config.SUGGESTIONS_LIMIT)
    except (TypeError, ValueError):
        limit = config.SUGGESTIONS_LIMIT
    limit = max(1, min(20, limit))

    suggestions = mem.top_place_suggestions(limit)
    if not suggestions:
        return {
            "suggestions": [],
            "note": (
                "No destinations have been searched yet — this is an early user. "
                "Suggest popular destinations from your own knowledge instead, and "
                "do NOT claim these come from other users."
            ),
        }
    return {
        "suggestions": suggestions,
        "note": (
            "These are the destinations other users searched most, newest-popular "
            "first, with a few real sample places each. You may say they are trending "
            "among users. Do not invent ratings — use only the sample_places given."
        ),
        "data_source": "TripSmart crowd-sourced search history (SQLite)",
    }


# ---------------------------------------------------------------------------
# Tool 7 — initiate_booking (affiliate handoff + commission event)
# ---------------------------------------------------------------------------
def initiate_booking(args: dict, ctx: dict) -> dict:
    # TODO: build the real affiliate checkout URL and persist the commission
    # event to your DB. The print below is the demo stand-in.
    from urllib.parse import quote

    tag = os.environ.get("AFFILIATE_TAG", config.AFFILIATE_TAG)
    option_id = str(args.get("option_id", ""))
    checkout_url = (
        "https://zalo.me/s/zahackathon/checkout"
        f"?opt={quote(option_id)}&ref={quote(tag)}"
    )

    from datetime import datetime, timezone

    event = {
        "event": "booking_initiated",
        "user_id": ctx["user_id"],
        "option_id": option_id,
        "destination": args.get("destination"),
        "total_vnd": args.get("total_vnd"),
        "affiliate_tag": tag,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    print("[COMMISSION EVENT]", json.dumps(event, ensure_ascii=False))

    return {"checkout_url": checkout_url, "commission_tracked": True, "event": event}


# ---------------------------------------------------------------------------
# Registry — maps tool name (as declared in tools.json) to implementation
# ---------------------------------------------------------------------------
TOOL_IMPLS: dict[str, Callable[[dict, dict], dict]] = {
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "check_travel_requirements": check_travel_requirements,
    "web_search": web_search,
    "family_travel_checklist": family_travel_checklist,
    "save_user_preference": save_user_preference,
    "forget_user_preference": forget_user_preference,
    "generate_summary_card": generate_summary_card,
    "generate_itinerary": generate_itinerary,
    "suggest_destinations": suggest_destinations,
    "initiate_booking": initiate_booking,
}

#!/usr/bin/env python3
"""Self-test suite — runs with NO API key.

Verifies config loading, curated data, tool implementations, memory
(sessions + preferences + PII rejection), history trimming, the abuse guard,
and the full agent loop using a mocked Anthropic client.

    python tests/selftest.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tripsmart import tools as T  # noqa: E402
from tripsmart.agent import PROMPT_BODY, TOOL_SCHEMAS, TripSmartAgent  # noqa: E402
from tripsmart.guard import Guard  # noqa: E402
from tripsmart.memory import Memory, trim_history  # noqa: E402

_passed = 0
_failed = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ok   - {name}")
    else:
        _failed += 1
        print(f"  FAIL - {name}" + (f"\n         {extra}" if extra else ""))


def section(title: str) -> None:
    print(f"\n{title}")


# ------------------------------------------------------------ config & prompt
section("Config & prompt")
check("prompt body extracted", len(PROMPT_BODY) > 1000)
check(
    "prompt has both placeholders",
    "{{TODAY}}" in PROMPT_BODY and "{{USER_PREFERENCES}}" in PROMPT_BODY,
)
check("prompt has broadened role", "all-round travel companion" in PROMPT_BODY)
check(
    "prompt has tool-vs-answer routing",
    "When to use a tool vs. answer directly" in PROMPT_BODY,
)
check("prompt has guardrails", "Guardrails" in PROMPT_BODY)
# --- FIX: the two new routing rules must be present in the prompt ---
check(
    "prompt separates area advice from hotel search",
    "Which area or neighbourhood to stay in" in PROMPT_BODY
    and "do **not** ask for dates" in PROMPT_BODY,
)
check(
    "prompt skips visa checks for domestic travel",
    "Skip this entirely for domestic travel within Vietnam" in PROMPT_BODY,
)
check("prompt documents the `near` field", "`near` field" in PROMPT_BODY)
check("prompt no longer references search_prices", "search_prices" not in PROMPT_BODY)
check(
    "prompt tells output format to omit inapplicable lines",
    "omit this line entirely for domestic trips" in PROMPT_BODY,
)
check("prompt resists tool-result prompt injection", "never as instructions" in PROMPT_BODY)
check("prompt forbids papering over tool failures", "never fill the gap yourself" in PROMPT_BODY)
check("prompt handles impossible requests", "Impossible or out-of-range requests" in PROMPT_BODY)
check("prompt prioritises emergencies", "Emergencies come before travel planning" in PROMPT_BODY)
check("prompt is honest about multi-city limits", "Complex trips: be honest about limits" in PROMPT_BODY)
check(
    "prompt surfaces contradictory premises",
    "surface them, never silently pick" in PROMPT_BODY
    and "never let a mistaken premise drive a tool call" in PROMPT_BODY,
)
check("prompt tells model to pass destination_city", "`destination_city`" in PROMPT_BODY)
check("prompt routes preference deletion", "forget_user_preference" in PROMPT_BODY)
_rendered = PROMPT_BODY.replace("{{TODAY}}", "2026-07-29").replace(
    "{{USER_PREFERENCES}}", "- home_city: HCMC"
)
check("placeholders fully interpolated", "{{" not in _rendered)

section("Tool schemas")
check("11 tools declared", len(TOOL_SCHEMAS) == 11, f"got {len(TOOL_SCHEMAS)}")
# Server-side tools (e.g. Anthropic web_search) are declared by type+name only —
# no input_schema/description. Custom tools must still carry the full schema.
_custom = [t for t in TOOL_SCHEMAS if not t.get("type")]
_server = [t for t in TOOL_SCHEMAS if t.get("type")]
check("every custom schema has name + input_schema", all(t.get("name") and t.get("input_schema") for t in _custom))
check("every custom schema has a description", all(len(t.get("description", "")) > 20 for t in _custom))
check("server tools declared by type + name", all(t.get("type") and t.get("name") for t in _server))
_expected = [
    "search_flights",
    "search_hotels",
    "check_travel_requirements",
    "web_search",
    "family_travel_checklist",
    "save_user_preference",
    "forget_user_preference",
    "generate_summary_card",
    "generate_itinerary",
    "suggest_destinations",
    "initiate_booking",
]
_names = {t["name"] for t in TOOL_SCHEMAS}
check("all expected tool names present", all(n in _names for n in _expected))
check("every schema has an implementation", all(n in T.TOOL_IMPLS for n in _names))

# ------------------------------------------------------------------- helpers
section("Helpers")
check(
    "resolve_country maps US aliases",
    T.resolve_country("USA") == "united states" and T.resolve_country("Mỹ") == "united states",
)
check(
    "resolve_country maps Vietnamese names",
    T.resolve_country("Thái Lan") == "thailand" and T.resolve_country("Trung Quốc") == "china",
)
check("estimate_nights computes span", T.estimate_nights("2026-08-28", "2026-08-31") == 3)
check("estimate_nights defaults safely", T.estimate_nights(None, None) == 1)
check("estimate_nights survives bad input", T.estimate_nights("not-a-date", "also-bad") == 1)

# --------------------------------------------------------------------- tools
section("Tool implementations")
mem = Memory(":memory:")
ctx = {"user_id": "t1", "memory": mem}

# --- Flights: real prices only; honest (never fabricated) when unavailable ---
_f_unsupported = T.search_flights(
    {"origin_city": "Cần Thơ", "destination": "Vientiane", "depart_date": "2026-08-28", "traveler_count": 1},
    ctx,
)
check(
    "search_flights: unsupported airport -> honest, no fabricated prices",
    _f_unsupported.get("error") == "unsupported_airport" and "options" not in _f_unsupported,
)

os.environ.pop("SERPAPI_KEY", None)
_f_nokey = T.search_flights(
    {"origin_city": "Ho Chi Minh City", "destination": "Bangkok", "depart_date": "2026-08-28", "traveler_count": 1},
    ctx,
)
check(
    "search_flights: no live source -> prices_unavailable (never mock)",
    _f_nokey.get("error") == "prices_unavailable" and "options" not in _f_nokey,
)

# Live mapping is exercised against a canned SerpApi response (no network).
_orig_serpapi_get = T._serpapi_get


def _canned_flights(_params):
    return {
        "best_flights": [{"price": 3_000_000, "flights": [{"airline": "Vietjet"}]}],
        "other_flights": [{"price": 2_000_000, "flights": [{"airline": "AirAsia"}, {"airline": "AirAsia"}]}],
    }


os.environ["SERPAPI_KEY"] = "test"
T._serpapi_get = _canned_flights
_f_live = T.search_flights(
    {
        "origin_city": "Ho Chi Minh City",
        "destination": "Bangkok",
        "depart_date": "2026-08-28",
        "return_date": "2026-08-31",
        "traveler_count": 2,
        "budget_vnd": 8_000_000,
    },
    ctx,
)
T._serpapi_get = _orig_serpapi_get
os.environ.pop("SERPAPI_KEY", None)
check("search_flights (live map): returns options", isinstance(_f_live.get("options"), list) and len(_f_live["options"]) >= 2)
check("search_flights (live map): sorted cheapest first", _f_live["options"][0]["price_total"] <= _f_live["options"][1]["price_total"])
check("search_flights (live map): scales by pax", _f_live["options"][0]["price_total"] == _f_live["options"][0]["price_per_person"] * 2)
check("search_flights (live map): marks round-trip", _f_live["options"][0]["type"] == "round-trip")
check("search_flights (live map): flags budget fit", _f_live["any_within_budget"] is True)
check("search_flights (live map): live data source", "live" in _f_live["data_source"])

# --- Hotels: real prices only; ask for dates instead of inventing them ---
_h_nodates = T.search_hotels({"destination": "Hanoi", "near": "Mỹ Đình Stadium"}, ctx)
check(
    "search_hotels: no dates -> ask for dates (no fabricated rates)",
    _h_nodates.get("error") == "dates_required" and "options" not in _h_nodates,
)

os.environ.pop("SERPAPI_KEY", None)
_h_nokey = T.search_hotels(
    {"destination": "Bangkok", "checkin_date": "2026-08-28", "checkout_date": "2026-08-31", "guests": 2},
    ctx,
)
check(
    "search_hotels: dated but no live source -> prices_unavailable (never mock)",
    _h_nokey.get("error") == "prices_unavailable" and "options" not in _h_nokey,
)


def _canned_hotels(_params):
    return {
        "properties": [
            {"name": "Hotel A", "extracted_hotel_class": 4, "rate_per_night": {"extracted_lowest": 1_000_000}, "total_rate": {"extracted_lowest": 3_000_000}},
            {"name": "Hotel B", "extracted_hotel_class": 3, "rate_per_night": {"extracted_lowest": 800_000}, "total_rate": {"extracted_lowest": 2_400_000}},
        ]
    }


os.environ["SERPAPI_KEY"] = "test"
T._serpapi_get = _canned_hotels
_h_live = T.search_hotels(
    {
        "destination": "Bangkok",
        "near": "Sukhumvit",
        "checkin_date": "2026-08-28",
        "checkout_date": "2026-08-31",
        "guests": 2,
        "budget_vnd": 3_000_000,
    },
    ctx,
)
_h_star = T.search_hotels(
    {"destination": "Bangkok", "checkin_date": "2026-08-28", "checkout_date": "2026-08-31", "star_min": 4},
    ctx,
)
T._serpapi_get = _orig_serpapi_get
os.environ.pop("SERPAPI_KEY", None)
check("search_hotels (live map): honours `near` anchor", _h_live["anchor"] == "Sukhumvit" and _h_live["searched_near_landmark"] is True)
check("search_hotels (live map): computes 3 nights", _h_live["nights"] == 3)
check("search_hotels (live map): sorted cheapest first", _h_live["options"][0]["price_per_night"] <= _h_live["options"][1]["price_per_night"])
check("search_hotels (live map): totals the stay", _h_live["options"][0]["price_total"] is not None)
check("search_hotels (live map): evaluates budget", _h_live["options"][0]["within_budget"] is True)
check("search_hotels (live map): filters by star_min", all((o["stars"] or 0) >= 4 for o in _h_star["options"]))

# --- Real places for itineraries (Google Maps mapping, canned) ---
def _canned_maps(_params):
    return {
        "local_results": [
            {"title": "Wat Arun", "type_ids": ["buddhist_temple"], "rating": 4.6, "reviews": 100, "gps_coordinates": {"latitude": 13.7437, "longitude": 100.4889}},
            {"title": "Chatuchak Market", "type_ids": ["market"], "rating": 4.4, "reviews": 50, "gps_coordinates": {"latitude": 13.7999, "longitude": 100.5503}},
        ]
    }


os.environ["SERPAPI_KEY"] = "test"
T._serpapi_get = _canned_maps
_places = T.fetch_places("Bangkok", 1)
T._serpapi_get = _orig_serpapi_get
os.environ.pop("SERPAPI_KEY", None)
check("fetch_places: returns real POIs with coords + rating", bool(_places["places"]) and all("lat" in p and "rating" in p for p in _places["places"]))
_cats = {p["name"]: p["category"] for p in _places["places"]}
check("fetch_places: maps categories", _cats.get("Wat Arun") == "Văn hoá" and _cats.get("Chatuchak Market") == "Mua sắm")

# generate_itinerary tool: surfaces a real itinerary object (no fabrication).
os.environ["SERPAPI_KEY"] = "test"
T._serpapi_get = _canned_maps
_itin = T.generate_itinerary({"destination": "Bangkok", "days": 1}, ctx)
_itin_nodest = T.generate_itinerary({}, ctx)
T._serpapi_get = _orig_serpapi_get
os.environ.pop("SERPAPI_KEY", None)
check("generate_itinerary: returns itinerary with real places", "itinerary" in _itin and len(_itin["itinerary"]["places"]) >= 2)
check("generate_itinerary: itinerary carries days", _itin["itinerary"].get("days") == 1)
check("generate_itinerary: missing destination -> error, no places", _itin_nodest.get("error") == "no_destination")

# --- Shared result cache (save external API calls) + crowd-sourced suggestions ---
section("Shared cache + suggestions")
mem2 = Memory(":memory:")
ctx2 = {"user_id": "t2", "memory": mem2}

_calls = {"n": 0}


def _counting_flights(_params):
    _calls["n"] += 1
    return {
        "best_flights": [{"price": 3_000_000, "flights": [{"airline": "Vietjet"}]}],
        "other_flights": [{"price": 2_000_000, "flights": [{"airline": "AirAsia"}]}],
    }


os.environ["SERPAPI_KEY"] = "test"
T._serpapi_get = _counting_flights
_c1 = T.search_flights(
    {"origin_city": "Ho Chi Minh City", "destination": "Bangkok", "depart_date": "2026-09-01", "return_date": "2026-09-05", "traveler_count": 2},
    ctx2,
)
_c2 = T.search_flights(
    {"origin_city": "Ho Chi Minh City", "destination": "Bangkok", "depart_date": "2026-09-01", "return_date": "2026-09-05", "traveler_count": 3},
    ctx2,
)
T._serpapi_get = _orig_serpapi_get
os.environ.pop("SERPAPI_KEY", None)
check("cache: first flight search hits the API", _c1["cache"]["from_cache"] is False and _calls["n"] == 1)
check("cache: same route reused from cache (0 extra API calls)", _c2["cache"]["from_cache"] is True and _calls["n"] == 1)
check("cache: pax re-scaled from cached per-person fare", _c2["options"][0]["price_total"] == _c2["options"][0]["price_per_person"] * 3)

# Places are cached AND recorded as crowd-sourced suggestions.
os.environ["SERPAPI_KEY"] = "test"
T._serpapi_get = _canned_maps
_pl1 = T.fetch_places("Bangkok", 1, mem2)   # miss -> fetch + record
_pl2 = T.fetch_places("Bangkok", 1, mem2)   # hit  -> cached + count bump
T._serpapi_get = _orig_serpapi_get
os.environ.pop("SERPAPI_KEY", None)
check("cache: first places lookup is a miss", _pl1["cache"]["from_cache"] is False)
check("cache: repeat places lookup served from cache", _pl2["cache"]["from_cache"] is True)

_sugg = T.suggest_destinations({}, ctx2)
check("suggestions: surfaces a previously searched destination", any(s["destination"].lower() == "bangkok" for s in _sugg["suggestions"]))
check("suggestions: carries real sample places (names only)", all("name" in sp for s in _sugg["suggestions"] for sp in s["sample_places"]))

_empty = T.suggest_destinations({}, {"user_id": "z", "memory": Memory(":memory:")})
check("suggestions: empty store degrades gracefully", _empty["suggestions"] == [] and "early user" in _empty["note"])

visa_th = T.check_travel_requirements(
    {"nationality": "Vietnamese", "destination_country": "Thailand"}, ctx
)
check("visa: Thailand visa-free for VN", visa_th["found"] and visa_th["visa_type"] == "visa-free")

visa_us = T.check_travel_requirements({"destination_country": "USA"}, ctx)
check("visa: alias 'USA' resolves", visa_us["found"] and visa_us["visa_type"] == "visa-required")

visa_miss = T.check_travel_requirements({"destination_country": "Iceland"}, ctx)
check(
    "visa: undefined country degrades gracefully",
    visa_miss["found"] is False and "web_search" in visa_miss["note"],
)

# --- VN coverage: provinces & famous places are domestic, accent-insensitive ---
section("VN coverage (63 provinces)")
for _dest in [
    "Hà Giang", "Ha Giang", "Tây Ninh", "tay ninh", "Côn Đảo", "Mộc Châu",
    "Tràng An", "Phong Nha", "Lý Sơn", "Măng Đen", "Đất Mũi", "Hồ Ba Bể",
    "Buôn Ma Thuột", "Buon Ma Thuot", "Hồ Gươm", "Vinpearl Nha Trang",
]:
    _r = T.check_travel_requirements({"nationality": "Vietnamese", "destination_country": _dest}, ctx)
    check(f"domestic (expanded): {_dest}", _r.get("domestic") is True)
for _foreign in ["Bangkok", "Sapporo", "Vientiane", "Chiang Mai", "Luang Prabang"]:
    check(f"not domestic: {_foreign}", not T._is_domestic_place(_foreign))
# VN airports resolve accent-insensitively to the right IATA code
for _city, _code in [
    ("Cần Thơ", "VCA"), ("Can Tho", "VCA"), ("Quy Nhơn", "UIH"), ("Quy Nhon", "UIH"),
    ("Côn Đảo", "VCS"), ("Vinh", "VII"), ("Buôn Ma Thuột", "BMV"), ("Pleiku", "PXU"),
    ("Hải Phòng", "HPH"), ("Đồng Hới", "VDH"), ("Tuy Hòa", "TBB"), ("Hạ Long", "VDO"),
    ("Thanh Hóa", "THD"), ("Cam Ranh", "CXR"), ("Rạch Giá", "VKG"), ("Cà Mau", "CAH"),
]:
    check(f"iata: {_city} -> {_code}", T._iata(_city) == _code)
# origin == destination must be rejected without searching
_same = T.search_flights(
    {"origin_city": "Hà Nội", "destination": "Ha Noi", "depart_date": "2026-09-01", "traveler_count": 2}, ctx
)
check("flights: same origin/destination -> same_route error", _same.get("error") == "same_route")
# traveler-count edges
_pax10 = T.search_flights(
    {"origin_city": "Hà Nội", "destination": "Phú Quốc", "depart_date": "2026-09-01", "traveler_count": 10}, ctx
)
check("flights: 10 pax rejected with friendly cap", _pax10.get("error") == "too_many_travelers")

# --- FIX: domestic travel must never mention embassies/visas ---
for _dest in ["Vietnam", "Hanoi", "Hà Nội", "Da Nang", "TP.HCM", "Phú Quốc"]:
    _dom = T.check_travel_requirements({"nationality": "Vietnamese", "destination_country": _dest}, ctx)
    check(
        f"domestic: {_dest} -> not-applicable, no embassy text",
        _dom.get("domestic") is True
        and _dom["visa_type"] == "not-applicable"
        and "embassy" not in str(_dom).lower(),
    )
check("resolve_country maps VN cities to vietnam", T.resolve_country("Hà Nội") == "vietnam")
check("overseas unaffected by domestic rule", T.check_travel_requirements({"destination_country": "China"}, ctx)["visa_type"] == "visa-required")

fam_cn = T.family_travel_checklist(
    {"destination_country": "China", "child_age_range": "3-6"}, ctx
)
check("family: China returns specific docs", isinstance(fam_cn["documents"], list) and fam_cn["documents"])
check("family: China not marked generic", fam_cn["generic_guidance"] is False)

fam_miss = T.family_travel_checklist({"destination_country": "Iceland"}, ctx)
check(
    "family: undefined country falls back to generic",
    fam_miss["generic_guidance"] is True and isinstance(fam_miss["health"], list),
)

ok_pref = T.save_user_preference({"key": "home_city", "value": "Ho Chi Minh City"}, ctx)
check("preference: valid key saved", ok_pref["saved"] is True)

bad_key = T.save_user_preference({"key": "passport_number", "value": "C1234567"}, ctx)
check("preference: disallowed key rejected", bad_key["saved"] is False)

pii_phone = T.save_user_preference({"key": "companions", "value": "call me 0912345678"}, ctx)
check(
    "preference: PII (phone) rejected",
    pii_phone["saved"] is False and "personal data" in pii_phone["reason"],
)

pii_dob = T.save_user_preference({"key": "companions", "value": "child born 2021-05-14"}, ctx)
check("preference: PII (DOB) rejected", pii_dob["saved"] is False)

pii_email = T.save_user_preference({"key": "dietary", "value": "email me at a@b.com"}, ctx)
check("preference: PII (email) rejected", pii_email["saved"] is False)

booking = T.initiate_booking(
    {"option_id": "opt_1", "destination": "Bangkok", "total_vnd": 6_500_000}, ctx
)
check("booking: returns checkout url", "checkout?opt=opt_1" in booking["checkout_url"])
check(
    "booking: fires commission event",
    booking["commission_tracked"] is True and booking["event"]["event"] == "booking_initiated",
)

card_res = T.generate_summary_card(
    {
        "destination": "Bangkok",
        "dates": "28/08 - 31/08",
        "traveler_count": 2,
        "flight_summary": "VietJet 3.6M",
        "hotel_summary": "3-star 2.9M",
        "total_vnd": 6_500_000,
        "budget_vnd": 8_000_000,
        "visa_status": "visa-free 30 days",
    },
    ctx,
)
check(
    "card: built with over_budget flag",
    card_res["card"]["type"] == "trip_summary" and card_res["card"]["over_budget"] is False,
)

# --- Card number verification: model-supplied figures must trace to real API data ---
_obs_ctx = {
    "user_id": "v",
    "memory": mem,
    "observed": {
        "amounts": {3_600_000, 2_900_000},
        "flight_totals": {3_600_000},
        "hotel_totals": {2_900_000},
        "visa_checked": True,
    },
}
_c_ok = T.generate_summary_card(
    {"destination": "Bangkok", "traveler_count": 2, "total_vnd": 6_500_000, "visa_status": "visa-free"},
    _obs_ctx,
)
check("card verify: reconciling total accepted", "card" in _c_ok and _c_ok["card"]["total_vnd"] == 6_500_000)

_c_bad = T.generate_summary_card(
    {"destination": "Bangkok", "traveler_count": 2, "total_vnd": 9_999_999}, _obs_ctx
)
check("card verify: fabricated total rejected", _c_bad.get("error") == "total_mismatch" and "card" not in _c_bad)

_c_novisa = T.generate_summary_card(
    {"destination": "Tokyo", "traveler_count": 1, "visa_status": "visa-required"},
    {"user_id": "v", "memory": mem, "observed": {"amounts": {5_000_000}, "flight_totals": {5_000_000}, "hotel_totals": set(), "visa_checked": False}},
)
check("card verify: visa_status without a visa check rejected", _c_novisa.get("error") == "unverified_visa")

_c_nototal = T.generate_summary_card(
    {"destination": "Tokyo", "traveler_count": 1, "total_vnd": 5_000_000},
    {"user_id": "v", "memory": mem, "observed": {"amounts": set(), "flight_totals": set(), "hotel_totals": set(), "visa_checked": False}},
)
check("card verify: total with no search rejected", _c_nototal.get("error") == "unverified_total")

# -------------------------------------------------------------------- memory
section("Memory")
check("preferences round-trip", mem.get_preferences("t1")["home_city"] == "Ho Chi Minh City")
check("render_preferences formats", "home_city" in mem.render_preferences("t1"))
check("render_preferences handles new user", "No stored preferences" in mem.render_preferences("nobody"))

mem.save_session("t1", [{"role": "user", "content": "hi"}])
check("session round-trip", len(mem.load_session("t1")["messages"]) == 1)
check("session preserves unicode", True)
mem.save_session("t1", [{"role": "user", "content": "đi Bangkok với con nhỏ"}])
check("session keeps Vietnamese text", "Bangkok" in mem.load_session("t1")["messages"][0]["content"])
mem.clear_session("t1")
check("session cleared", mem.load_session("t1")["messages"] == [])

mem.log_usage("t1", 1200, 300)
mem.log_usage("t1", 800, 200)
usage = mem.usage_today("t1")
check("usage accumulates", usage["in_tokens"] == 2000 and usage["out_tokens"] == 500)

# ----------------------------------------------------------------- trimming
section("History trimming")
big = "x" * 5000
msgs: list[dict] = []
for i in range(14):
    msgs.append({"role": "user", "content": f"msg {i}"})
    msgs.append(
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"id{i}", "content": big}]}
    )
trimmed = trim_history(msgs, keep_recent=6)
check("trimming caps length", len(trimmed) <= 7, f"got {len(trimmed)}")


def _starts_with_tool_result(m: dict) -> bool:
    c = m.get("content")
    return isinstance(c, list) and any(b.get("type") == "tool_result" for b in c)


check("trimming does not start on tool_result", not _starts_with_tool_result(trimmed[0]))

short_hist = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
check("short history untouched", len(trim_history(short_hist, keep_recent=8)) == 2)

mixed: list[dict] = []
for i in range(10):
    mixed.append({"role": "assistant", "content": [{"type": "text", "text": f"t{i}"}]})
    mixed.append(
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"x{i}", "content": big}]}
    )
dig = trim_history(mixed, keep_recent=4)
any_digested = any(
    isinstance(m.get("content"), list)
    and any(
        b.get("type") == "tool_result" and "trimmed tool result" in str(b.get("content"))
        for b in m["content"]
    )
    for m in dig
)
check("older tool results digested or dropped", any_digested or len(dig) <= 4)
last = dig[-1]
last_full = isinstance(last.get("content"), list) and any(
    b.get("type") == "tool_result" and len(str(b.get("content"))) > 1000 for b in last["content"]
)
check("recent tool result kept verbatim", last_full or len(dig) <= 4)

# -------------------------------------------------------------------- guard
section("Abuse guard")
g = Guard(per_minute=3, per_day=5, max_chars=50, debounce_ms=500)
t0 = 1_000_000
check("normal message allowed", g.check("u1", "đi Bangkok", t0).allowed)
check("oversized message blocked", g.check("u1", "y" * 51, t0).reason == "too_long")
check("empty message blocked", g.check("u1", "   ", t0).reason == "empty")
_dup = g.check("u1", "đi Bangkok", t0 + 100)
check("duplicate within debounce dropped silently", _dup.reason == "duplicate" and _dup.reply is None)

g2 = Guard(per_minute=3, per_day=100, max_chars=500, debounce_ms=0)
_last = None
for i in range(5):
    _last = g2.check("u2", f"m{i}", 2_000_000 + i * 10)
check("per-minute limit enforced", _last.reason == "rate_minute" and bool(_last.reply))

g3 = Guard(per_minute=1000, per_day=4, max_chars=500, debounce_ms=0)
for i in range(6):
    _last = g3.check("u3", f"d{i}", 3_000_000 + i * 1000)
check("per-day limit enforced", _last.reason == "rate_day")

check("missing user_id blocked", g.check(None, "hi", t0).reason == "missing_user")
check("stats report counts", g.stats("u1", t0)["last_minute"] >= 1)

g5 = Guard(per_minute=5, per_day=10, max_chars=500, debounce_ms=0)
g5.check("sweepme", "hello", 1_000)
g5.sweep(now=1_000 + 86_400_001)
check("sweep drops stale users", "sweepme" not in g5.hits)

# --- Gibberish filter: junk answered with 0 model tokens; real text passes ---
g6 = Guard(per_minute=100, per_day=100, max_chars=2000, debounce_ms=0)
for _junk in ["!!!!", "😂😂😂😂", "??????", "aaaaaaa", "sdfghjklqwrtp", "kkkkkkkk"]:
    _v = g6.check("junk", _junk, 5_000_000)
    check(f"gibberish blocked: {_junk!r}", _v.reason == "nonsense" and bool(_v.reply))
for _real in [
    "ok", "có", "ừ", "2 người", "28/8 - 31/8", "đi Bangkok", "Hà Nội",
    "cho mình xem lựa chọn rẻ hơn", "5 ngày", "1/9", "ib", "Quy Nhơn nhé",
]:
    check(f"real text passes: {_real!r}", g6.check("real", _real, 5_100_000).allowed)
# prompt hardening markers present
check("prompt: confidentiality rule", "Confidentiality" in PROMPT_BODY)
check("prompt: other-users-data rule", "Other users' data is off-limits" in PROMPT_BODY)
check("prompt: short refusals for off-topic", "at most 2 sentences" in PROMPT_BODY)

# --------------------------------------------------------------- agent loop
section("Agent loop (mocked Claude client)")


class _Usage:
    def __init__(self, i: int, o: int) -> None:
        self.input_tokens = i
        self.output_tokens = o


class _Response:
    def __init__(self, stop_reason: str, content: list[dict], usage: _Usage) -> None:
        self.stop_reason = stop_reason
        self.content = content
        self.usage = usage


class _Messages:
    def __init__(self, parent: "_MockClient") -> None:
        self._parent = parent

    def create(self, **req):
        self._parent.calls += 1
        self._parent.last_request = req
        return self._parent.script(self._parent.calls)


class _MockClient:
    def __init__(self, script) -> None:
        self.calls = 0
        self.last_request: dict = {}
        self.script = script
        self.messages = _Messages(self)


def two_turn_script(call: int):
    if call == 1:
        return _Response(
            "tool_use",
            [
                {"type": "text", "text": "Để mình kiểm tra nhé."},
                {
                    "type": "tool_use",
                    "id": "tu1",
                    "name": "search_flights",
                    "input": {
                        "origin_city": "HCMC",
                        "destination": "Bangkok",
                        "depart_date": "2026-08-28",
                        "return_date": "2026-08-31",
                        "traveler_count": 2,
                        "budget_vnd": 8_000_000,
                    },
                },
                {
                    "type": "tool_use",
                    "id": "tu2",
                    "name": "check_travel_requirements",
                    "input": {"nationality": "Vietnamese", "destination_country": "Thailand"},
                },
            ],
            _Usage(1500, 80),
        )
    return _Response(
        "end_turn",
        [{"type": "text", "text": "✈️ VietJet 3.6tr · 🏨 2.9tr · Tổng 6.5tr/8tr · ✅ Miễn visa 30 ngày"}],
        _Usage(2100, 160),
    )


mock = _MockClient(two_turn_script)
mem2 = Memory(":memory:")
agent = TripSmartAgent(client=mock, memory=mem2, guard=Guard())
out = agent.handle_message("u-agent", "Đi Bangkok 28/08-31/08, 2 người, 8 triệu, từ HCMC")

check("agent returns final text", "Tổng 6.5tr" in (out.reply or ""))
check("agent looped twice (tool turn + final)", mock.calls == 2, f"calls={mock.calls}")
_sys = mock.last_request.get("system")
check(
    "system sent as cacheable block",
    isinstance(_sys, list)
    and _sys[0]["type"] == "text"
    and _sys[0].get("cache_control", {}).get("type") == "ephemeral",
)
_tools = mock.last_request.get("tools")
check(
    "tools sent with cache_control on last",
    len(_tools) == 11 and _tools[-1].get("cache_control", {}).get("type") == "ephemeral",
)
check("max_tokens capped from config", mock.last_request.get("max_tokens") <= 1000)
check("history persisted after turn", len(mem2.load_session("u-agent")["messages"]) >= 3)
check("usage logged", mem2.usage_today("u-agent")["in_tokens"] == 3600)
check("tool results are JSON-serialisable", True)

# --- Durable trip state + rolling summary (anti sliding-window amnesia) ---
section("Trip state + session summary")
_state = mem2.load_session("u-agent")["trip_state"]
check("trip state extracted from successful tool args", _state.get("destination") == "Bangkok")
check("trip state captures dates + pax + budget",
      _state.get("depart_date") == "2026-08-28" and _state.get("pax") == 2
      and _state.get("budget_vnd") == 8_000_000 and _state.get("origin") == "HCMC")

# Next turn: the dynamic (uncached) system block must carry that state back in.
out2 = agent.handle_message("u-agent", "Chốt phương án rẻ nhất nhé")
_sys2 = mock.last_request.get("system")
check("dynamic context sent as SECOND system block", isinstance(_sys2, list) and len(_sys2) == 2)
check("static block still cached", _sys2[0].get("cache_control", {}).get("type") == "ephemeral")
check("dynamic block NOT cached (would bust prompt cache)", "cache_control" not in _sys2[1])
check("dynamic block carries established trip context",
      "Established trip context" in _sys2[1]["text"] and "Bangkok" in _sys2[1]["text"])

# Failed tool calls must NOT pollute the state.
from tripsmart.agent import _update_trip_state  # noqa: E402
_s = {"destination": "Bangkok"}
_update_trip_state("search_flights", {"destination": "Mars"}, {"error": "unsupported_airport"}, _s)
check("rejected tool call settles nothing", _s["destination"] == "Bangkok")

# split_history hands back what was cut; merge_summary folds it into a digest.
from tripsmart.memory import merge_summary, split_history  # noqa: E402
_long = []
for i in range(10):
    _long.append({"role": "user", "content": f"câu hỏi số {i}"})
    _long.append({"role": "assistant", "content": [{"type": "text", "text": f"trả lời số {i}"}]})
_kept, _dropped = split_history(_long, keep_recent=6)
check("split_history keeps the window", len(_kept) == 6)
check("split_history returns the trimmed prefix", len(_dropped) == 14)
_sum = merge_summary(None, _dropped)
check("summary digests trimmed messages", "câu hỏi số 0" in _sum and "trả lời số 6" in _sum)
_sum2 = merge_summary(_sum, [{"role": "user", "content": "mới nhất"}])
check("summary is incremental", _sum2.endswith("User: mới nhất"))
_huge = merge_summary(None, [{"role": "user", "content": f"dòng {i} " + "x" * 100} for i in range(40)])
check("summary capped, keeps newest lines", len(_huge) <= 1500 and "dòng 39" in _huge and "dòng 0" not in _huge)
# tool_result plumbing (no text blocks) is skipped, not dumped into the summary
_sum3 = merge_summary(None, [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "{...}"}]}])
check("tool plumbing skipped in summary", _sum3 is None)

# Guard integration: flood until blocked.
g4 = Guard(per_minute=2, per_day=100, max_chars=500, debounce_ms=0)
agent2 = TripSmartAgent(client=_MockClient(two_turn_script), memory=Memory(":memory:"), guard=g4)
agent2.handle_message("u-flood", "one")
agent2.handle_message("u-flood", "two")
blocked = agent2.handle_message("u-flood", "three")
check("agent honours rate limit", blocked.blocked == "rate_minute")


# Unknown tool must not crash the loop.
def unknown_tool_script(call: int):
    if call == 1:
        return _Response(
            "tool_use",
            [{"type": "tool_use", "id": "e1", "name": "does_not_exist", "input": {}}],
            _Usage(10, 10),
        )
    return _Response("end_turn", [{"type": "text", "text": "handled"}], _Usage(10, 10))


agent3 = TripSmartAgent(
    client=_MockClient(unknown_tool_script), memory=Memory(":memory:"), guard=Guard()
)
check("unknown tool handled without crashing", agent3.handle_message("u-err", "x").reply == "handled")


# A tool that raises must not crash the loop either.
def _boom(args, ctx):
    raise RuntimeError("simulated tool failure")


T.TOOL_IMPLS["web_search"], _orig_ws = _boom, T.TOOL_IMPLS["web_search"]


def raising_tool_script(call: int):
    if call == 1:
        return _Response(
            "tool_use",
            [{"type": "tool_use", "id": "r1", "name": "web_search", "input": {"query": "x"}}],
            _Usage(10, 10),
        )
    return _Response("end_turn", [{"type": "text", "text": "recovered"}], _Usage(10, 10))


agent5 = TripSmartAgent(
    client=_MockClient(raising_tool_script), memory=Memory(":memory:"), guard=Guard()
)
check("raising tool handled without crashing", agent5.handle_message("u-raise", "x").reply == "recovered")
T.TOOL_IMPLS["web_search"] = _orig_ws


# Progress guard: a model repeating the EXACT same tool call is caught early.
def repeat_tool_script(call: int):
    return _Response(
        "tool_use",
        [{"type": "tool_use", "id": "l1", "name": "web_search", "input": {"query": "x"}}],
        _Usage(5, 5),
    )


agent4 = TripSmartAgent(
    client=_MockClient(repeat_tool_script), memory=Memory(":memory:"), guard=Guard()
)
check(
    "repeated identical tool call caught (no_progress)",
    agent4.handle_message("u-loop", "loop forever").blocked == "no_progress",
)


# Loop cap: a model that keeps requesting tools (varying args) still terminates.
def varying_tool_script(call: int):
    return _Response(
        "tool_use",
        [{"type": "tool_use", "id": f"l{call}", "name": "web_search", "input": {"query": str(call)}}],
        _Usage(5, 5),
    )


agent5 = TripSmartAgent(
    client=_MockClient(varying_tool_script), memory=Memory(":memory:"), guard=Guard()
)
check(
    "MAX_TOOL_TURNS terminates the loop",
    agent5.handle_message("u-loop2", "loop forever").blocked == "max_tool_turns",
)

# Card capture through the loop.
def card_script(call: int):
    if call == 1:
        return _Response(
            "tool_use",
            [
                {
                    "type": "tool_use",
                    "id": "c1",
                    "name": "generate_summary_card",
                    "input": {
                        "destination": "Bangkok",
                        "dates": "28/08 - 31/08",
                        "traveler_count": 2,
                        "flight_summary": "VietJet",
                        "hotel_summary": "3-star",
                    },
                }
            ],
            _Usage(10, 10),
        )
    return _Response("end_turn", [{"type": "text", "text": "đây là thẻ"}], _Usage(10, 10))


agent6 = TripSmartAgent(client=_MockClient(card_script), memory=Memory(":memory:"), guard=Guard())
_card_out = agent6.handle_message("u-card", "tóm tắt giúp mình")
check("card captured from tool result", _card_out.card is not None and _card_out.card["type"] == "trip_summary")

# ----------------------------------------------------------------- packaging
section("Input validation edge cases")
_v_past = T.search_flights(
    {"origin_city": "A", "destination": "B", "depart_date": "2020-01-01", "traveler_count": 1}, ctx
)
check("rejects departure date in the past", _v_past.get("error") == "date_in_past" and "hint" in _v_past)

_v_rev = T.search_hotels(
    {"destination": "Hanoi", "checkin_date": "2026-08-31", "checkout_date": "2026-08-28"}, ctx
)
check("rejects checkout before checkin", _v_rev.get("error") == "dates_reversed")

_v_pax = T.search_flights(
    {"origin_city": "A", "destination": "B", "depart_date": "2026-09-01", "traveler_count": 500}, ctx
)
check("rejects oversized group", _v_pax.get("error") == "too_many_travelers")

_v_zero = T.search_flights(
    {"origin_city": "A", "destination": "B", "depart_date": "2026-09-01", "traveler_count": 0}, ctx
)
check("rejects zero travellers", _v_zero.get("error") == "invalid_count")

_v_long = T.search_hotels(
    {"destination": "Hanoi", "checkin_date": "2026-09-01", "checkout_date": "2027-08-31"}, ctx
)
check("rejects over-long stay", _v_long.get("error") == "stay_too_long")

_v_bad = T.search_flights(
    {"origin_city": "A", "destination": "B", "depart_date": "tomorrow", "traveler_count": 1}, ctx
)
check("rejects unparseable date", _v_bad.get("error") == "invalid_date")

_v_ok = T.search_flights(
    {"origin_city": "Ho Chi Minh City", "destination": "Bangkok", "depart_date": "2026-09-01", "traveler_count": 2}, ctx
)
check("valid input passes validation to pricing", _v_ok.get("error") == "prices_unavailable")
check("every validation error carries an actionable hint", all(
    "hint" in r for r in (_v_past, _v_rev, _v_pax, _v_zero, _v_long, _v_bad)
))

section("Preference deletion")
_m3 = Memory(":memory:")
_c3 = {"user_id": "del", "memory": _m3}
T.save_user_preference({"key": "home_city", "value": "HCMC"}, _c3)
T.save_user_preference({"key": "companions", "value": "1 child age 3-6"}, _c3)
check("forget removes one key", T.forget_user_preference({"key": "companions"}, _c3)["deleted"] is True)
check("other keys survive", _m3.get_preferences("del") == {"home_city": "HCMC"})
check(
    "forgetting an absent key reports honestly",
    T.forget_user_preference({"key": "companions"}, _c3)["deleted"] is False,
)
check("forget all clears everything", T.forget_user_preference({"key": "all"}, _c3)["deleted"] is True)
check("preferences empty after clear", _m3.get_preferences("del") == {})
check(
    "forget rejects unknown key",
    T.forget_user_preference({"key": "passport_number"}, _c3)["deleted"] is False,
)

section("Summary card flexibility")
_hotel_only = T.generate_summary_card(
    {"destination": "Hanoi", "traveler_count": 1, "hotel_summary": "3-star gần Mỹ Đình"}, ctx
)
check("hotel-only card builds without flight/visa", _hotel_only["card"]["destination"] == "Hanoi")
check("no fabricated flight field", "flight_summary" not in _hotel_only["card"])
check("no fabricated visa field", "visa_status" not in _hotel_only["card"])
_card_schema = next(t for t in TOOL_SCHEMAS if t["name"] == "generate_summary_card")
check(
    "schema no longer forces flight/visa",
    "flight_summary" not in _card_schema["input_schema"]["required"]
    and "visa_status" not in _card_schema["input_schema"]["required"],
)

section("API resilience")
import tripsmart.config as _cfg  # noqa: E402

_cfg.API_RETRY_BASE_MS = 1


class _Flaky:
    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self.fail_times = fail_times
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("529 overloaded_error")
        return _Response("end_turn", [{"type": "text", "text": "ok"}], _Usage(10, 10))


_flaky = _Flaky(fail_times=2)
_a_retry = TripSmartAgent(client=_flaky, memory=Memory(":memory:"), guard=Guard())
_r_retry = _a_retry.handle_message("u-retry", "hello")
check("retries transient API errors then succeeds", _r_retry.reply == "ok" and _flaky.calls == 3)

_always = _Flaky(fail_times=99)
_a_fail = TripSmartAgent(client=_always, memory=Memory(":memory:"), guard=Guard())
_r_fail = _a_fail.handle_message("u-fail", "hello")
check("permanent API failure degrades gracefully", _r_fail.blocked == "api_error" and bool(_r_fail.reply))
check("failure does not exceed retry budget", _always.calls == _cfg.API_MAX_RETRIES)


class _BadRequest:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        exc = Exception("invalid_request_error")
        exc.status_code = 400
        raise exc


_br = _BadRequest()
_r_br = TripSmartAgent(client=_br, memory=Memory(":memory:"), guard=Guard()).handle_message("u-br", "x")
check("non-retryable 4xx is not retried", _br.calls == 1 and _r_br.blocked == "api_error")

from tripsmart.agent import _is_retryable  # noqa: E402

check("classifier: 429 retryable", _is_retryable(type("E", (Exception,), {"status_code": 429})()))
check("classifier: 503 retryable", _is_retryable(type("E", (Exception,), {"status_code": 503})()))
check("classifier: 400 not retryable", not _is_retryable(type("E", (Exception,), {"status_code": 400})()))

section("Truncated / empty responses")


class _Truncated:
    def __init__(self) -> None:
        self.messages = self

    def create(self, **kwargs):
        return _Response(
            "max_tokens",
            [{"type": "tool_use", "id": "t", "name": "search_hotels", "input": {"destination": "Hanoi"}}],
            _Usage(10, 500),
        )


_r_trunc = TripSmartAgent(
    client=_Truncated(), memory=Memory(":memory:"), guard=Guard()
).handle_message("u-trunc", "x")
check("truncated response never returns empty text", bool(_r_trunc.reply))
check("truncated response is flagged", _r_trunc.blocked == "truncated")


class _NoText:
    def __init__(self) -> None:
        self.messages = self

    def create(self, **kwargs):
        return _Response("end_turn", [], _Usage(10, 0))


_r_empty = TripSmartAgent(
    client=_NoText(), memory=Memory(":memory:"), guard=Guard()
).handle_message("u-empty", "x")
check("empty content never returns empty text", bool(_r_empty.reply) and _r_empty.blocked == "empty_reply")

section("Wrong-premise / contradictory input")
_conf = T.check_travel_requirements(
    {"nationality": "Vietnamese", "destination_city": "Bangkok", "destination_country": "United States"}, ctx
)
check("detects city/country contradiction", _conf.get("error") == "destination_conflict")
check("names the real country", _conf.get("city_is_in") == "thailand")
check("refuses to return visa data on conflict", "visa_type" not in _conf)
check("conflict hint tells agent not to answer yet", "do not present requirements" in _conf["hint"])

_amb = T.check_travel_requirements({"destination_city": "Vancouver"}, ctx)
check("flags ambiguous city names", _amb.get("error") == "ambiguous_city")
check("lists the candidate countries", set(_amb["possible_countries"]) == {"canada", "united states"})
check("refuses to guess on ambiguity", "visa_type" not in _amb)

_city_only = T.check_travel_requirements({"destination_city": "Bangkok"}, ctx)
check("city alone resolves to the right country", _city_only["found"] and _city_only["visa_type"] == "visa-free")

_as_country = T.check_travel_requirements({"destination_country": "Tokyo"}, ctx)
check("a city passed as a country still resolves", _as_country.get("resolved_country") == "japan")

_consistent = T.check_travel_requirements(
    {"destination_city": "Bangkok", "destination_country": "Thailand"}, ctx
)
check("consistent input is unaffected", _consistent["visa_type"] == "visa-free")

_no_dest = T.check_travel_requirements({}, ctx)
check("missing destination asks rather than guessing", _no_dest.get("error") == "no_destination")

check("resolve_destination: country", T.resolve_destination("Thailand")["kind"] == "country")
check("resolve_destination: city", T.resolve_destination("Osaka")["country"] == "japan")
check("resolve_destination: ambiguous", T.resolve_destination("Sydney")["kind"] == "ambiguous_city")
check("resolve_destination: domestic city", T.resolve_destination("Đà Nẵng")["country"] == "vietnam")
check(
    "resolve_destination: strips country qualifier",
    T.resolve_destination("Bangkok, Thailand")["country"] == "thailand",
)
check("resolve_destination: unknown place", T.resolve_destination("Zzyzx")["kind"] == "unknown")
check("domestic rule survives the rewrite", T.check_travel_requirements({"destination_country": "Hanoi"}, ctx)["visa_type"] == "not-applicable")

section("Project files")
for rel in [
    "requirements.txt",
    "README.md",
    "system_prompt.md",
    "tools.json",
    "demo.py",
    "tripsmart/__init__.py",
    "tripsmart/agent.py",
    "tripsmart/memory.py",
    "tripsmart/guard.py",
    "tripsmart/tools.py",
    "tripsmart/config.py",
    "tripsmart/server.py",
    "data/visa_requirements.json",
    "data/family_travel_checklist.json",
]:
    check(f"exists: {rel}", (ROOT / rel).exists())

print(f"\n{_passed} passed, {_failed} failed\n")
sys.exit(1 if _failed else 0)

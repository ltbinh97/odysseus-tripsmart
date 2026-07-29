# Zalo TripSmart (Python)

AI travel companion agent for Zalo — **za.hackathon 2026, Business Growth Agent track**.

An agentic AI that plans, prices, and de-risks trips through natural conversation
inside Zalo, then converts the conversation into a booking that earns affiliate
commission.

> **This README describes the design. For the up-to-date handoff (what changed,
> live data sources, verification, streaming, run commands), read
> [`CLAUDE.md`](./CLAUDE.md) — it is the authoritative source and supersedes any
> stale note here.** Since the original build, prices/hotels/places are now
> **live** (SerpApi: Google Flights / Hotels / Maps), `web_search` is the real
> **Anthropic server tool**, mock data is gone, the summary card **verifies its
> numbers**, and replies **stream** over SSE.

---

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY and SERPAPI_KEY (live prices)

python tests/selftest.py        # 173 checks, runs WITHOUT an API key
python demo.py                  # plays the Demo Day script (needs API key)
```

Server command (⚠️ always via uvicorn `--env-file`; `python -m tripsmart.server`
does NOT load `.env`. Port 3100 because 3000 is taken on this machine):

```bash
uvicorn tripsmart.server:app --host 0.0.0.0 --port 3100 --env-file .env
```

Local chat without Zalo:

```bash
curl -X POST localhost:3100/chat \
  -H 'Content-Type: application/json' \
  -d '{"userId":"me","message":"Đi Bangkok cuối tháng 8, 2 người, 8 triệu"}'

# streaming (Server-Sent Events): live "đang tìm khách sạn…" progress
curl -N -X POST localhost:3100/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"userId":"me","message":"Tìm khách sạn 4 sao Đà Nẵng 1/9-4/9/2026, 2 người"}'
```

---

## Architecture

```
Zalo Mini App / OA / Bot Platform            (chat UI)
                 |
                 v
tripsmart/server.py   webhook -> agent -> reply     (FastAPI)
                 |
                 v
tripsmart/agent.py    the tool-calling loop         (Claude API, cached prompt)
                 |
       +---------+---------+---------+---------+---------+
       v         v         v         v         v         v
  search_   search_   check_    generate_  family_   save/forget_
  flights   hotels    travel_   itinerary  travel_   user_preference
  (Google   (Google   require-  (Google    checklist
  Flights)  Hotels)   ments               generate_summary_card
                                          (verified numbers)
       + web_search  = Anthropic SERVER tool (API runs it, not the loop)
       |
       v
   initiate_booking -> Mini App checkout -> commission event

tripsmart/memory.py   sessions + preferences        (SQLite, stdlib)
tripsmart/guard.py    rate limits + input caps      (abuse prevention)
```

Endpoints: `POST /chat` (sync), `POST /chat/stream` (SSE progress + result),
`POST /places` (real POIs for the itinerary map), `GET /health`, `POST /webhook/zalo`.

Claude never calls a *custom* API itself. It emits a `tool_use` block telling
`tripsmart/agent.py` which tool to run; the loop executes it (real prices via
SerpApi) and feeds the result back until Claude produces a final answer.
`web_search` is the exception — an Anthropic **server tool** the API runs itself.
Numbers the model puts on the summary card are **verified against the real API
results** before the card is emitted (see Cost control / CLAUDE.md).

---

## Files

| Path | What it is |
|---|---|
| `system_prompt.md` | The agent's behaviour spec. Text after `<<<PROMPT-BODY>>>` is sent as the API `system` field. |
| `tools.json` | The 10 tool schemas (`web_search` is an Anthropic server tool; the rest are custom). |
| `tripsmart/agent.py` | **Core.** The tool-calling loop, prompt caching, memory + guard wiring, observation ledger, thrash-guard, streaming `emit`, optional reflection. |
| `tripsmart/tools.py` | Tool implementations — **live SerpApi** integrations (Google Flights/Hotels/Maps), summary-card number verification, honest "unavailable" fallbacks (no mock). |
| `tripsmart/memory.py` | SQLite sessions, preferences, PII guard, history trimming. |
| `tripsmart/guard.py` | Per-user rate limits, input size cap, debounce. |
| `tripsmart/config.py` | All tunables, overridable by env var. |
| `tripsmart/server.py` | FastAPI webhook + `/chat` + `/chat/stream` (SSE) + `/places` + `/health` + hourly housekeeping. |
| `demo.py` | Plays the rehearsed Demo Day conversation. `--interactive` to chat freely. |
| `tests/selftest.py` | 173 checks, no API key needed. |
| `data/*.json` | Curated visa + family-travel datasets. |

---

## Key design decisions

**No fine-tuning.** Travel facts (prices, visa rules, entry requirements) change
constantly. A fine-tuned model freezes them at training time and risks
confidently stating wrong information — dangerous for a travel agent. Facts live
in tools and data, never in frozen weights. The agent is grounded by
construction: it never states a price or visa rule it did not just retrieve.

**No agent framework.** The loop is ~70 lines in `tripsmart/agent.py`. LangChain
and similar add abstraction and debugging risk without adding capability at this
scale. Native tool-calling *is* the current standard.

**Broad coverage without a tool for everything.** Tools handle live data and real
actions. Everything else — packing, culture, food, budgeting, itinerary ideas —
the model answers from its own knowledge, with `web_search` as the fallback for
anything time-sensitive. See the routing rules in `system_prompt.md`.

**Flights and hotels are separate tools.** A hotel-only question ("where should
I stay near the stadium?") should not have to supply an origin city and departure
date. `search_hotels` needs only a `destination` plus an optional `near`
landmark/venue/district. It **requires check-in/out dates** (Google Hotels does)
— without them it asks the user rather than inventing indicative rates, and it
filters to `type == "hotel"` (drops vacation-rental room listings that were
producing misleadingly cheap "4-star" results).

**Advice is not a search.** Asking *which area* is convenient is answered
directly from model knowledge — naming districts and explaining transport
trade-offs — with no tool call and no interrogation about dates. Only when the
user wants actual options does `search_hotels` run. See the routing rules in
`system_prompt.md`.

**Domestic travel skips entry checks.** A trip within Vietnam returns
`visa_type: not-applicable` and the prompt forbids mentioning visas or embassies,
so a Hanoi trip can never produce "check with the embassy". Vietnamese city names
(Hà Nội, TP.HCM, Đà Nẵng, Phú Quốc…) resolve as domestic, not just "Vietnam".

**Three kinds of memory.** Session history (expiring, SQLite), durable
preferences (SQLite, PII-guarded), and static knowledge (JSON files). No vector
database — the curated data has exact keys, so a dict lookup is faster and more
debuggable than semantic search.

**Why FastAPI.** The webhook must acknowledge fast so Zalo does not retry, and
the Claude call is blocking. FastAPI + `asyncio.to_thread` acks immediately and
runs the agent off the event loop, so concurrent users do not queue behind each
other.

---

## Edge cases handled

Input validation (`_validate` in `tripsmart/tools.py`) returns a structured error
with an actionable `hint` rather than silently producing nonsense:

| Input | Result |
|---|---|
| Departure date in the past | `date_in_past` — agent asks which upcoming date |
| Checkout before checkin | `dates_reversed` |
| Unparseable date ("tomorrow") | `invalid_date` |
| 0 or negative travellers | `invalid_count` |
| Group above `MAX_TRAVELERS` (9) | `too_many_travelers` — suggests the group desk |
| Stay above `MAX_NIGHTS` (30) | `stay_too_long` |
| Date more than a year out | `date_too_far` |
| City contradicts stated country ("Bangkok in the US") | `destination_conflict` — names the real country, returns **no** visa data |
| City name exists in several countries ("Vancouver") | `ambiguous_city` — lists candidates and asks |
| No destination given | `no_destination` |

Operational resilience in `tripsmart/agent.py`:

- **Transient API failures retry** with exponential backoff (`API_MAX_RETRIES`).
  A single 529 `overloaded_error` no longer kills a turn mid-demo. Non-retryable
  4xx errors fail fast instead of burning the budget.
- **Truncated or empty responses never reach the user as blank text** — a reply
  cut off at `max_tokens` returns a fallback message flagged `truncated`.
- **Tool exceptions are contained** — a raising tool becomes a tool result the
  model can react to, not a crashed turn.
- **Permanent API failure degrades gracefully** with a plain Vietnamese apology.

Prompt guardrails (9 rules in `system_prompt.md`) cover: grounding on
consequential facts, staying in scope, honest unknowns, **treating tool and web
output as data rather than instructions** (prompt-injection resistance), never
papering over failed tool calls, impossible requests, **emergencies abroad taking
priority over trip planning**, **surfacing contradictory or ambiguous requests instead of silently picking an
interpretation**, and honesty about multi-city limits.

**Wrong premises are treated as a distinct risk.** A malformed input is obvious;
a *well-formed but false* one is not. If a user asserts "Bangkok in the US", the
naive path returns genuine US visa rules for a Thailand trip — accurate data
attached to the wrong country, which is worse than no answer. `check_travel_requirements`
therefore takes an optional `destination_city`, resolves it against a city→country
map, and returns `destination_conflict` **without any visa data** when the two
disagree, so the model cannot repeat the mistake. Ambiguous names (Vancouver,
Sydney, Cambridge) return `ambiguous_city` with the candidate countries.

## Live integrations — status

| Integration | Status |
|---|---|
| `search_flights` | ✅ **Live** — Google Flights via SerpApi (VND). Needs `SERPAPI_KEY`. |
| `search_hotels` | ✅ **Live** — Google Hotels via SerpApi (VND), hotels only. |
| `generate_itinerary` / `POST /places` | ✅ **Live** — Google Maps POIs + ratings via SerpApi. |
| `web_search` | ✅ **Live** — Anthropic `web_search_20250305` server tool. |
| Streaming UX | ✅ **Live** — `POST /chat/stream` (SSE progress). |
| Summary-card numbers | ✅ **Verified** against real API results (no fabricated totals). |
| `initiate_booking` | ❌ **Still a demo stub** — `checkout_url` is a fake link, commission is a `print`. Wire ZaloPay Create Order for real. |
| `send_zalo_reply` + `extract_message` (`server.py`) | ⚠️ **Adapters** — adjust to the real Zalo Bot/OA payload + send-message API. |

**No mock data anywhere.** When a live source can't answer (no key, quota, city
unsupported, missing dates) the tools return an honest "unavailable / need info"
message; the agent never fabricates a price. See CLAUDE.md for the full data-source
table and anti-hallucination design.

---

## Cost control

Already implemented:

- **Prompt caching** on the system prompt + tool schemas (identical every turn,
  so cached reads bill at ~0.1x input). Toggle with `ENABLE_PROMPT_CACHE`.
- **`MAX_TOKENS=1000`** — output bills higher than input, so replies stay short.
- **`MAX_TOOL_TURNS=8`** — caps how expensive a single message can become; a
  **thrash-guard** stops a model repeating the same tool call (`no_progress`).
- **History trimming** — keeps recent turns verbatim, digests older tool results.
- **Usage logging** — per-user token totals in the `usage_log` table.
- **`web_search max_uses:3`** — bounds Anthropic per-search charges per message.

Model in use is **Claude Haiku 4.5** (`MODEL` env). External cost also includes
the **SerpApi** quota (free tier ~250 searches/month — a flight or hotel search is
1, an itinerary is 2) and Anthropic's per-search fee for `web_search`. Verify
current pricing before submission.

---

## Abuse prevention (Tier 1)

In `tripsmart/guard.py`, enforced before any paid API call:

- Per-user rate limits — `RATE_PER_MINUTE` (10) and `RATE_PER_DAY` (100)
- Input size cap — `MAX_INPUT_CHARS` (2000)
- Debounce of identical rapid-fire messages
- Escalating friction (slow down, then cooldown) rather than hard bans
- In-prompt scope guardrail redirects non-travel requests

Counters are in-process (fine for one worker). For multiple workers, back them
with Redis — only `tripsmart/guard.py` changes.

---

## Privacy / contest compliance

The contest rules prohibit production systems, internal tools, customer data, and
PII. This project complies:

- Stores **only self-declared travel preferences** — an allow-list of 6 keys in
  `tripsmart/memory.py`.
- **Rejects PII in code**, independent of what the model decides: phone/passport-
  like digit runs, full dates of birth, card-like numbers, and emails are refused
  even if the model tries to save them (verified by tests).
- Companion ages stored as **ranges**, never birthdates.
- Sessions expire after `SESSION_TTL_HOURS` (48) so stale conversation data is
  not retained indefinitely.
- Uses anonymised Zalo user IDs, never names.
- **Users can correct or erase what is stored** — `forget_user_preference`
  removes a single key or clears everything ("forget what you know about me").

---

## Deployment on the provided VPS

Runs comfortably on 4 cores / 6GB RAM / 40GB SSD — no GPU, no self-hosted model.
`sqlite3` is in the Python standard library, so there is no database server to
install.

```bash
git clone <your-repo> && cd zalo-tripsmart
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add ANTHROPIC_API_KEY
python tests/selftest.py  # confirm the install
uvicorn tripsmart.server:app --host 0.0.0.0 --port 3000
```

Point your domain at the VPS and register `https://your-domain/webhook/zalo` as
the webhook URL in the Zalo Bot/OA console.

---

## Timeline (za.hackathon 2026)

| Date | Milestone |
|---|---|
| 22–29/07 | Infrastructure provided — deploy to VPS, wire the price API |
| 30/07 | Submission |
| 31/07 | Top 5 announced |
| 03/08 | **Demo day** — run `python demo.py` |
| 03–07/08 | Internal voting |
| 10/08 | Awards |

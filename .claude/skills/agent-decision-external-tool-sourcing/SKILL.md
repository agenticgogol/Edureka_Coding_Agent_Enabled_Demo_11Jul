---
name: agent-decision-external-tool-sourcing
description: Use whenever a tool identified during agent-system-design's stage 4 (or any tool inventory step) requires a third-party external service rather than custom in-house logic. Researches current free options first, falls back to presenting real paid pricing for user approval, and if declined, searches for and presents concrete lower-fidelity alternatives (e.g. a public site an agent can check instead of a paid data API) before asking the user to accept a stated capability loss. Never used for LLM/infra cost (that's stage 8's budget decision) — only for sourcing a specific external capability.
---

# Agent Decision: External Tool Sourcing (Free → Paid → Degrade)

Decides, for one external-service-backed tool at a time, whether a free
option covers the actual requirement, whether the user will pay for a
paid option if not, and — if neither — whether a concrete alternative
approach (a different, usually lower-fidelity way to approximate the
same capability) can substitute before falling back to a stated
capability loss. This is a sourcing/cost decision, distinct from stage
4's auth-tier decision (read/write, human-approval, idempotency), which
still applies afterward to whatever tool this skill leaves in place.

## When to use

- Called once per tool, by `agent-decision-tools-and-authorization`
  (stage 4 of `/agent-system-design`), for every tool classified as
  **external** (calls a third-party API/SaaS) rather than **custom**
  (in-house logic, no third-party dependency — skip this skill entirely
  for those).
- Callable standalone any time a project needs to pick a specific
  external service for a capability and reason about its cost.
- **Not** for LLM provider cost, vector DB hosting, or general
  infrastructure spend — those are stage 8's (`agent-decision-eval-security-guardrails`)
  cost/latency budget, decided at the whole-system level. This skill is
  scoped to "which specific external tool do we call for this one
  capability, and can/will we pay for it."

## Input

- The specific capability the tool needs to provide, in plain language
  (e.g. "real-time web search," "geocode an address," "send SMS,"
  "look up company firmographic data").
- The usecase's actual volume/quality/latency requirement for that
  capability, if known — needed to judge whether a free tier's limits
  are actually a problem or just a number that doesn't matter here.

## Procedure

### 1. Confirm this tool is genuinely external, not custom

If the capability can be built with in-house logic and no third-party
dependency (e.g. a deterministic calculation, a lookup against the
project's own database), it isn't in scope for this skill — return
immediately and let stage 4 treat it as a custom tool.

### 2. Research current options — free first, always web-searched

Use `WebSearch`/`WebFetch` every time this runs. Pricing and free-tier
terms change often enough that answering from training data risks
recommending a free tier that's since been capped, paywalled, or
discontinued. Look for, in this priority order:

1. **Fully free / open-source, self-hostable** — no usage cap by
   construction (e.g. a self-hosted search index, an open-data API with
   no key required).
2. **Free tier of a paid service** — note the *specific* limit (requests/
   month, rate cap, feature restriction, e.g. "1,000 requests/month,
   resets monthly, no commercial-use restriction" vs. "free tier requires
   attribution and caps at 100/day").
3. **Paid-only, no free tier** — note the actual current price found
   (per-request, per-month, tiered), not a remembered number.

Cite what was actually found (service name, tier, limit, source) — don't
assert "there's a free tier" without having just confirmed it's still true.

### 3. Judge whether a free option actually covers the requirement

A free tier's limit only matters relative to the usecase's real volume.
100 requests/day is irrelevant friction for a low-volume internal tool
and a hard blocker for a customer-facing agent expecting thousands of
daily calls. State this comparison explicitly: "free tier caps at
[X]; this usecase's expected volume is [Y]; that [does/doesn't] fit."

- **Free option covers it** → recommend it, state the tier/limit in the
  record, done — skip to step 7.
- **No free option covers it** → continue to step 4.

### 4. Present the cheapest adequate paid option and ask for a real yes/no

State the specific service, the specific current price found, and ask
directly: "This capability needs a paid service — [service] at
[price/unit] is the cheapest option that covers the requirement. Are you
willing to pay this?"

- **Yes** → record the decision (service, price, confirmed) — done, skip
  to step 7.
- **No** → continue to step 5.

### 5. Search for concrete alternative approaches before accepting a gap

Don't jump straight to "the agent loses this capability." Actively search
for other ways to approximate the same outcome — these will usually be
lower-fidelity than the paid service, but "lower fidelity, free" is a
real, often-preferable middle option the user should get to see and
choose, not one this skill should skip past. Look for things like:

- **A public, human-facing site or page with the same underlying data**,
  reachable via a browsing/fetch tool instead of a dedicated paid API —
  e.g. a paid live flight-status API's natural free alternative is
  pointing the agent at a public flight-status page (Google Flights,
  the airline's own status page, FlightAware's free tier) and having it
  read the page, rather than calling a structured paid endpoint.
- **A community/open dataset** that's free but updates less often or has
  narrower coverage than the paid service (e.g. daily-batch pricing data
  instead of real-time).
- **A partial-coverage free API** that handles the common case and leaves
  edge cases uncovered (e.g. covers major carriers/routes, not charters).
- **A manual or semi-automated fallback** — the agent asks the user to
  supply or confirm the specific piece of information itself, rather than
  looking it up autonomously.

For each real alternative found, state its tradeoff honestly and
specifically, not just "this is free instead":

- **Fidelity/coverage gap** vs. the paid option (staleness, narrower
  scope, lower accuracy).
- **Engineering cost**, if relevant — a scraped/browsed public page needs
  its own parsing and is more brittle to page-layout changes than a
  stable API contract; this is a real, ongoing cost even though no money
  changes hands.
- **Terms-of-service / reliability risk**, if the alternative involves
  browsing or scraping a site that doesn't offer a public API for this
  purpose — say plainly that this may violate the site's terms of use or
  break without notice, don't present scraping as a clean free
  substitute if it isn't one.

If no genuine alternative exists (nothing found approximates the
capability at all), say so explicitly rather than inventing one, and
continue to step 6 with an empty alternatives list.

### 6. State the exact capability loss, present any alternatives found, then confirm the user's choice

Never silently drop the tool. Lay out every real option together and ask
the user to pick, rather than defaulting to "gap accepted":

- Which specific tasks/questions the agent can no longer handle at all if
  nothing substitutes.
- Any degraded free-tier option already covered in step 2/3 (rate-limited
  but still using the same paid-style service).
- Any alternative approach(es) found in step 5, each with its stated
  tradeoff (fidelity, engineering cost, ToS/reliability risk).
- Ask explicitly: "Given that gap, do you want to (a) proceed without
  this capability, (b) use [alternative], accepting [its stated
  tradeoff], (c) proceed with the degraded free-tier option and accept
  its limits, or (d) revisit — reduce scope, find budget, or change the
  usecase so this capability isn't required?" — list only the options
  that actually apply.

Whatever the user picks, record it verbatim — don't paraphrase a
capability loss or an alternative's tradeoff into something softer than
what was actually stated.

### 7. Return the sourcing record

Return this record to the caller (or, if run standalone, present it
directly):

```markdown
### External sourcing: <tool/capability name>
- **Researched options**: <what was found, with source/tier/price, and
  the date framing — "as of this search">
- **Alternative approaches considered** (only if paid was declined):
  <each alternative found in step 5, with its specific tradeoff, or "none
  found" if step 5 turned up nothing usable>
- **Decision**: <Free (service, tier/limit) | Paid-approved (service,
  price, user confirmed) | Alternative-approach (which one, its accepted
  tradeoff) | Declined — degraded (service+limits accepted) | Declined —
  omitted (no substitute, capability dropped)>
- **Capability impact**: <"None — free tier covers expected volume" |
  the alternative's stated tradeoff as accepted | exact statement of what
  the agent can't do, or does with degraded reliability, as confirmed
  with the user in step 6>
```

## Ground rules

- Always web-search current pricing/free-tier terms — never answer this
  from memory alone, even for well-known services.
- Never assume a free tier "probably still covers it" — state the actual
  limit found and the actual expected volume side by side, explicitly.
- Never drop or degrade a capability without the user's explicit,
  recorded confirmation — silence is not consent here.
- Never skip the alternative-approach search (step 5) once a paid option
  is declined — jumping straight to "capability lost" without checking
  for a lower-fidelity substitute is exactly the shortcut this skill
  exists to prevent.
- Never present a scraping/browsing-based alternative as cost-free
  without naming its real costs (ToS risk, brittleness, engineering
  maintenance) — "free" here means no invoice, not zero tradeoff.
- Never fold LLM/infrastructure cost into this skill's scope — redirect
  those to stage 8's budget decision if the user raises them here.
- If research turns up no clear pricing (opaque "contact sales" tiers),
  say so explicitly and treat it the same as "no confirmed paid option"
  — ask the user how they want to proceed rather than guessing a price.

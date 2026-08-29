# Teaching Brief: LangGraph Basics

## Description (as given by user)
Progressive LangGraph fundamentals demo, notebook format, toy data, free tools only.
Every step must include: (1) a markdown cell explaining the concept's theory —
what it is, why it exists, how LangGraph implements it, and related/adjacent
concepts that are easy to confuse with it; (2) a mermaid diagram of that
step's graph topology; (3) runnable code against the real Claude API; (4)
visible correct output demonstrating the concept.

## Steps (in order, each builds on the previous)
a) Basic StateGraph — one node, state schema, normal edges, START, END — added 2026-07-19
b) Conditional edges — added 2026-07-19
c) Loop / cycle (with termination condition) — added 2026-07-19
d) Checkpointing / memory (MemorySaver, multi-turn state persistence) — added 2026-07-19
e) Tool calling — added 2026-07-19
f) Multi-tool selection — how the LLM decides which tool to call — added 2026-07-19
g) Recursion limit — deliberately exceeded to show the resulting error — added 2026-07-19
h) Streaming (.stream() / token and event streaming) — added 2026-07-19
i) Human-in-the-loop (interrupt + resume) — added 2026-07-19
j) Subgraphs (nested graph inside a parent graph) — added 2026-07-19
k) Sequential vs parallel execution (fan-out/fan-in, timing comparison) — added 2026-07-19
l) Orchestrator-worker pattern — added 2026-07-19
m) LLM-as-node variants for steps a-d — added 2026-07-19: (a) node body is
   an LLM call instead of a string transform; (b) routing decision and
   both branches are LLM calls instead of a len() check; (c) loop is a
   real self-refinement pattern (write -> LLM judge -> loop until
   approved or max attempts) instead of a counter; (d) checkpointed node
   is a real chat node whose second turn recalls information from the
   first turn, instead of an incrementing counter

## Format
notebook

## Happy-path test case (user-approved)
User opens the notebook and runs it top to bottom. Each of the 12 steps has:
(1) a markdown cell explaining the concept's theory — what it is, why it
exists, how LangGraph implements it, and related concepts easy to confuse
with it (e.g. step b's markdown explains conditional edges and how they
differ from tool-calling-based routing introduced later in e/f); (2) a
mermaid diagram of that step's graph topology; (3) runnable code executing
against the real Claude API (model: claude-sonnet-5); (4) visible correct
output demonstrating the concept. No step throws an unhandled error, and no
tool requires a paid signup. Step g intentionally triggers and shows the
recursion-limit error as the expected outcome, not a bug.

## Observability
none

## Vector store
none

## Constraints
- Provider-swappable via an explicit flag: near the top of the notebook, a
  single visible variable (e.g. `PROVIDER = "anthropic"  # or "openai"`)
  controls which API the rest of the notebook uses — not silent
  auto-detection. A `get_llm()` helper reads that flag, pulls the matching
  key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) from `.env`, and fails
  loudly if that key is missing (no fallback to the other provider). Both
  paths verified working via real API calls on 2026-07-19: Anthropic
  (`claude-sonnet-5`) and OpenAI (`gpt-4o`).
- Tool roster (steps e/f), all free / no paid signup:
  - Toy calculator (local Python function)
  - Toy weather lookup (local hardcoded dict)
  - DuckDuckGo search (`duckduckgo-search` package, real, no API key)
  - Wikipedia lookup (`wikipedia` package, real, no API key)
  - Python REPL / sandboxed code execution tool (local, no key)
  - arXiv search (real, free API, no key)
- Toy/synthetic data only — no external datasets requiring download/license.
- No mock mode — every LLM call in the notebook is real.

## Audience level
Intermediate — assumes familiarity with LLMs/APIs/Python; explains
LangGraph-specific concepts in depth.

## Decisions
- User wants "some difficult/complicated" free tools in addition to
  trivial ones, hence Wikipedia/Python-REPL/arXiv added to the roster
  alongside calculator/weather/DuckDuckGo (6 tools total) — confirmed by
  user.
- Every step requires theory markdown + mermaid diagram, not just code —
  explicit user requirement, applies to all 12 steps uniformly.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified (Anthropic, claude-sonnet-5, real call succeeded 2026-07-19)
- Observability: approved (none)
- Vector store: approved (none)
- Ready to generate: approved
- Build: complete
- Verify: complete

## Advanced companion notebook

Added 2026-07-25 as a separate artifact: `langgraph_advanced.ipynb`.
It covers explicit bounded ReAct agents, complete streaming modes, tool
failure handling, structured output and validation, advanced checkpointing,
realistic human approval, subgraph state boundaries, robust async parallelism,
multi-agent patterns, and runtime context/configuration. The executed copy is
`executed_langgraph_advanced.ipynb`; it passed top-to-bottom execution against
the configured real provider with no cell errors.

The advanced companion was subsequently strengthened with an enforced
application-level agent budget, real custom and tool lifecycle streaming,
agent-integrated resilient tools, structured-output repair, file-backed SQLite
checkpoint restart and historical branching, and human-approved tool
execution; the corrected executed copy still passes with no cell errors.

## Agent memory deep-dive notebook

Added 2026-07-31 as a separate artifact: `agent_memory_deepdive.ipynb`.
Covers checkpointed (short-term, thread-scoped) memory vs. long-term
(cross-thread, user-scoped) memory in depth:
- `InMemorySaver` vs. `SqliteSaver` compared side by side, including a real
  `interrupt()`/resume cycle proven to survive an actual process restart
  (new SQLite connection/saver/graph object, same file) with `SqliteSaver`.
- The "amnesia problem" — a new `thread_id` has zero recall regardless of
  checkpointer durability.
- Long-term profile memory via Mem0 + ChromaDB, configured to run entirely
  on the Anthropic path: `llm.provider="anthropic"` (`claude-sonnet-5`),
  `embedder.provider="huggingface"` (local `sentence-transformers`, no
  OpenAI key needed), `vector_store.provider="chroma"` (local disk).
  Verified working via a standalone spike test before wiring into the
  notebook (Mem0/Chroma are outside the well-covered LangGraph/FastAPI/
  Next.js core, so `research-first` was used against current Mem0 docs).
- A markdown-only comparison of Mem0 alternatives (LangGraph's native
  `Store` interface, Zep, raw vector DB + custom extraction prompt) with a
  recommendation table.
- A combined finale proving checkpointer (in-thread recall) and Mem0
  (cross-thread recall) work together, not as substitutes for each other.

Executed top to bottom with 14 real Claude API calls total, all
individually user-approved before firing (per this repo's standing
API-cost-approval rule), each a short conversational exchange
(well under $0.15 total). Note: `claude-sonnet-5` rejects an explicit
`temperature` param with a 400 (deprecated for this model) — `get_llm()`
omits it for the Anthropic path; the OpenAI path still passes it.
`claude-sonnet-5` responses also include extended-thinking content blocks,
so a `get_text()` helper extracts the plain-text portion for display and
for writing back into Mem0.

## Agent context engineering notebook

Added 2026-07-31 as a separate artifact: `agent_context_engineering.ipynb`.
Two parts:

**Part 1 — Data Determinism**: without-vs-with-schema pairs on three real
scenarios — a support-ticket triage agent (naive keyword parsing vs.
`TicketTriage` + `.with_structured_output()`), a "create calendar event"
tool (unvalidated dict args crashing on bad types vs. a Pydantic
`args_schema` rejecting them cleanly at the boundary), and a supervisor
router (naive `"billing" in text` matching a churn-risk message to the
wrong team vs. a `Literal`-constrained `RouteDecision` schema feeding a
conditional edge directly). Closes with how `.with_structured_output()`
actually works (tool-calling-based extraction vs. native JSON mode) and
why it moves failures from silent-wrong-value to loud `ValidationError`.

**Part 2 — Token Economics**: theory on why unmanaged context grows
quadratically across a conversation; a real context-isolation demo (a
billing-lookup node given the full global state vs. one restricted via
LangGraph `input_schema` to only `account_id`, proven by showing the
unisolated version can read confidential `internal_notes`/full transcript
it has no business seeing); a real 10-turn support conversation pruned
two ways — sliding token window (via `tiktoken`) vs. semantic relevance
selection (local `sentence-transformers` embedder, same pattern as the
memory notebook). Ends with a full combined LangGraph agent (triage →
prune_history → router → isolated billing/technical/retention
specialists) tying every piece together across two real runs.

**Honest finding, not smoothed over**: semantic selection correctly
retrieved the relevant historical facts (verified by real relevance
scores) at a real token reduction, but the model's *generated answer* got
more cautious/self-doubting when given fragmented context instead of full
narrative continuity — a genuine caveat that retrieval correctness and
answer confidence are separate problems, documented directly in the
notebook's markdown rather than rewritten to match the originally-planned
narrative.

Executed top to bottom with 14 real Claude API calls total (5 in Part 1,
9 in Part 2), all individually approved per-group before firing. Adds
`tiktoken` to `requirements.txt` on top of the memory notebook's
dependencies (`mem0ai`, `chromadb`, `sentence-transformers`).

## Classifier/router workflow notebook (single_agent_architectures series, notebook 05)

Added 2026-08-01 as a new notebook in the existing `single_agent_architectures/`
series: `05_classifier_router_workflow.ipynb`. Extends the series' taxonomy
with a fifth topology term (`classifier/router workflow`) alongside true
agent, agentic workflow, self-evaluating workflow, and parallel/multi-agent
workflow, documented in the series `README.md`.

**Scenario**: a support-ticket triage router. A single structured-output LLM
call classifies a freeform ticket into exactly one of
`billing`/`technical_bug`/`account_access`/`feature_request`/`unclear`
(`Literal`-typed field, `.with_structured_output(..., method="json_schema")`).
A LangGraph conditional edge keyed directly on that field routes to one of
four specialist handler nodes, or to an `unclear` handler that asks a
clarifying question instead of guessing. No keyword matching anywhere — the
router is a plain dict lookup on the structured category.

**Fixtures** (all local Python dicts, no real infra): `INVOICES` (billing
handler), `INCIDENTS` (technical-bug handler, service status/ETA),
`ACCOUNTS` (account-access handler, lockout/permissions state), and
`BACKLOG` (feature-request handler appends an acknowledgment, no lookup).
Each handler extracts an `ACC-####` account id from the raw ticket text via
a deterministic regex, not a second LLM call, and reads only its own
fixture — never another handler's.

**Why this fills a real gap**: notebooks 01-04 cover a true ReAct agent, a
planner-controlled workflow, a self-evaluating generate→critique→revise
loop, and parallel/multi-agent boundary evidence — none of them is the
classifier/router pattern, arguably the single most common shape of
production LLM system (one bounded classification decision selecting a
fixed downstream path, with all subsequent control flow owned by
deterministic code, not the LLM). The notebook's central design point:
misrouting is a *more* insidious failure than an obvious agent error,
because a confidently wrong classification still produces a fluent,
plausible-sounding answer from the wrong specialist, with nothing in the
output signaling anything went wrong.

Includes a real scripted eval (`GROUND_TRUTH`, 8 labeled tickets covering
all 5 categories, including one deliberately ambiguous ticket that must
classify as `unclear`), a Mermaid diagram of the classify→5-branches→END
topology, and reuses `shared.invoke_with_budget` for the graph invoke per
the series' defensive-invoke convention (though this graph has no cycles,
so a recursion-limit hit is not a realistic failure mode here).

**Executed 2026-08-01** against a real provider (`gpt-4o`, `PROVIDER` default) with
explicit user cost approval — 8 real classification calls, one per `GROUND_TRUTH`
ticket. Result: **100% accuracy (8/8)**, including the deliberately ambiguous ticket
correctly landing on `unclear` instead of being force-classified. No cell errors.
Before this run, the saved `.ipynb` file was found to have two stray literal characters
(`\`+`n`) appended after the final closing brace, making it invalid JSON — fixed by
stripping them; the file parses clean now.

## Multi-agent human-in-the-loop notebook (multi_agent_architectures series, notebook 07)

Added 2026-08-01 as a new notebook in the existing `multi_agent_architectures/`
series: `07_multiagent_hitl.ipynb`. Fills the human-in-the-loop gap the series'
`README.md` had named as pending since notebook 01, by extending the
single-agent HITL mechanics already proven in `agent_hitl.ipynb` (this same
folder, parent level) into a supervisor/worker topology.

**Scenario**: an order-exception approval workflow. A supervisor classifies a
freeform ticket into `billing` (refund) or `logistics` (reship) — the same
supervisor/worker shape as notebook 01, narrowed to two domains since the
focus here is the approval gate, not routing breadth — and routes to the
matching specialist worker. The worker proposes a structured mutating action
(`RefundAction` or `ReshipAction`, both Pydantic models) but does not execute
it directly; execution is gated behind a real `interrupt()`/
`Command(resume=...)` approval node backed by a `MemorySaver` checkpointer.

**Fixtures** (all local Python dicts, no real infra): `_ORDERS` (order/refund/
reship source-of-truth records), `_REFUNDS_ISSUED` and `_RESHIPS_ISSUED`
(populated only by an actually-*executed* action, never by a mere proposal —
this distinction is what lets the eval tell "proposed" apart from
"executed"), and `_TICKET_LOG` (an audit trail recording both the proposed
and final action per ticket, important because the edit path lets them
legitimately differ).

**Naive version built first**: worker proposes and immediately executes, no
gate at all — same shape notebook 04's ungated `issue_refund` risk described,
but never actually demonstrated with a human check. A concrete failure is
constructed (not asserted as a live-run fact, since cells are unexecuted): a
refund ticket mentions a $20 promo credit already applied at checkout, so the
correct refund is $179.00 against a stated $199.00 — a worker that decides
and executes in the same node body has no seam for anyone to catch that
detail before the money moves.

**Three scripted resume cycles**, using non-interactive `Command(resume=...)`
values (same convention as `agent_hitl.ipynb`, not real `input()`):
approve-as-is (a clean $349.00 refund executes unchanged), edit-then-approve
(a human reviewer lowers the proposed amount to the correct $179.00 before
it executes, and the fixture reflects the edited value, not the worker's
original proposal), and deny (a proposed reship is rejected based on
information outside the ticket text; the reship fixture is never touched).
A scripted structural eval (not an LLM-judged accuracy score) verifies the
naive graph has no checkpointer, the gated graph pauses before any mutation
with an inspectable `get_state(config).next`, and all three resume paths
land in the correct final fixture/ticket state.

**Why this fills a real gap**: notebook 04 (planner-executor) structurally
separated a mutating `issue_refund` call into its own `finalize` node, but
nothing in that notebook actually paused for a human to look at the proposed
action before it fired — the gate was structural, never human. This
notebook makes that distinction explicit (plan visibility vs. action
reversibility are different problems) and proves HITL is orthogonal to
topology, not a replacement for it, by adding the gate on top of the
supervisor/worker routing from notebook 01 without touching the routing
logic at all. Closes with the honest limit of the pattern: gating 100% of
volume causes approval fatigue, and the realistic production shape is a
configurable risk/amount threshold (as in `agent_hitl.ipynb` Part 4).

**Not executed.** Per this repo's standing API-cost-approval rule, all 28
cells (17 markdown, 11 code) were written and left unexecuted — no notebook
run, no real API calls — pending the user's explicit go-ahead and cost
estimate for a verification pass.

## Peer-to-peer (network) handoff notebook (multi_agent_architectures series, notebook 08)

Added 2026-08-01 as a new notebook in the existing `multi_agent_architectures/`
series: `08_peer_to_peer_handoff.ipynb`. This was the last item the series'
`README.md` had named as pending since notebook 07 ("network / peer-to-peer
handoff"), so this closes out the series' originally announced roadmap.

**Scenario**: an infra alert ticket ("checkout service returning 500s") is
worked by three peer specialists that hand off directly to one another,
deliberately positioned against notebook 01's central supervisor rather than
extending it. The Infra/Triage agent checks a mock service-health fixture; if
infra is healthy but a recent deploy is on record, it hands off directly to
the Deploy agent. The Deploy/Release agent checks a mock recent-releases/
config fixture; if it confirms a bad config but the real fix requires
correcting data corrupted before rollback, it hands off directly to the Data
agent. The Data/DB agent checks a mock data-integrity fixture, applies the
fix, and closes the ticket — terminal, structurally unable to hand off
further (its own `Literal` type has no other option). Each specialist's
structured `next_action` output is narrowly scoped to only its role's valid
targets, not an open-ended peer list.

**Fixtures** (all local Python dicts, no real infra): `_SERVICE_HEALTH`,
`_RECENT_RELEASES`, and `_DATA_INTEGRITY`, each read directly by its owning
specialist's node code via a plain fixture-lookup function, not an LLM
tool-call loop.

**Naive version built first**: direct peer handoffs with narrowly-scoped
structured outputs but no hop counter and no cycle protection at all. A
deliberately ambiguous second ticket is constructed to make an Infra<->Deploy
ping-pong plausible — Deploy reads unclear evidence as "not actually a deploy
issue" and hands back to Infra, which hands it right back, with no central
dispatcher watching the whole flow to notice. `shared.invoke_with_budget`
wraps the risky invokes here — a good fit for this notebook specifically,
unlike notebook 07's linear HITL flow, since a handoff cycle is a real,
structural loop risk.

**Real-run bug found and fixed**: the first real execution surfaced a genuine
issue — `DEPLOY_PROMPT` gave the model no reason to know a config rollback
doesn't retroactively fix data already corrupted while the bad config was
live, so it defensibly resolved the happy-path ticket in 2 hops instead of
the intended 3, skipping the Data agent. Fixed with one added sentence of
*concept* (not the answer) in `DEPLOY_PROMPT`. After the fix, at
`temperature=0`, the model reasoned correctly through both the happy path and
the deliberately ambiguous ping-pong ticket on every hop — no cycle occurred
in either the naive or fixed graph on this real run. Kept as an honest,
reproducible finding rather than forced: the cycle risk remains real and
structural (the naive graph has zero protection against it if it ever
happens), but this specific ticket, with the corrected prompt, didn't
trigger it live.

**The fix**: keeps the narrowly-scoped structured outputs unchanged, and adds
an explicit `hop_count` plus an accumulated `history` of `{agent, action,
evidence}` entries threaded through shared state. Graph-level routing logic
checks `hop_count` against a hard `MAX_HOPS` budget on every transition,
before honoring any specialist's own proposed `next_action` — if exceeded,
the graph routes to an `escalate` node regardless of what the specialist
wanted, terminating with `escalated=True` instead of looping.
`recursion_limit` remains as an independent second safety net.

**Why this fills a real gap**: this is the only notebook in the series with
no central node ever deciding routing — every other pattern (supervisor,
planner-executor, hierarchical, HITL-gated supervisor) keeps a hub of some
kind. The notebook's honest central finding is the production cost of giving
that up: no single place to observe, rate-limit, or audit the whole flow,
which is why most real production "handoff" systems (e.g. OpenAI Agents
SDK-style customer-support handoff) keep a thin supervisor/session tracker
even when specialists still hand off directly to each other for the routing
decision. This notebook demonstrates the less common, fully unconstrained
form on purpose so that tradeoff is measured, not merely asserted. A scripted
structural eval (not an accuracy score) verifies, against real saved outputs:
the happy path resolves in exactly 3 hops ending at Data with Infra's
original evidence still present in state at Data's own turn, and the
ping-pong ticket's `hop_count` never exceeds `MAX_HOPS` regardless of how it
resolves.

**Executed 2026-08-01** against a real provider (`gpt-4o`, `PROVIDER`
default) with explicit user cost approval, across two runs (~24 short calls
total, well under $0.10): the first surfaced the prompt bug above; the
second, after the fix, passed all structural checks cleanly with real,
saved outputs. Recursion-limit safety margins (`happy_config`,
`ping_pong_config`) were tightened per the user's request to reduce
worst-case cost exposure, though actual call count was already capped by
`MAX_HOPS=4`.

## Multi-agent architectures review pass (2026-08-01)

A user review of `multi_agent_architectures/` notebooks 01, 03, 04, and 05
raised four issues, each checked against the actual code before deciding
whether to fix:

- **Notebook 01 (supervisor)**: the recorded 70% routing accuracy / 60%
  overall hit-rate (below the 90% single-agent baseline) was flagged as a
  possible problem. Decision: **not fixed, kept as the intended lesson** —
  the run already proves the right thing (tool isolation, `wrong_domain_call_rate=0%`)
  and does not prove overall accuracy improvement, and "fixing" it (tuning
  the router until it beats baseline) would teach the wrong lesson: that
  supervisors are automatically net-positive once tuned, rather than "the
  router must be evaluated independently." Assignment 4 already covers the
  tuning exercise. README's notebook 01 section tightened to state the
  proof/non-proof distinction explicitly.
- **Notebook 03 (sequential pipeline)**: confirmed by reading the code that
  only 2 of 4 stages (`extract_node`, `draft_node`) call the LLM;
  `dedup_node` and `review_gate_node` are pure deterministic Python. Fixed
  by adding an explicit "fixed pipeline ≠ automatically multi-agent" section
  (with a per-stage table) to both the notebook and README, with the rule
  of thumb: multi-agent requires multiple independent reasoning
  roles/contexts, not just sequential code organization.
- **Notebook 04 (planner-executor)**: confirmed the notebook had only a
  one-paragraph mention of `single_agent_architectures/02`'s single-agent
  plan-execute-replan, easy to miss. Fixed by adding an explicit side-by-side
  comparison table (in-notebook and README) distinguishing multi-agent
  notebook 04's separate `planner_llm`/`replanner_llm` roles + mutating-action
  boundary from single-agent notebook 02's one agent replanning inline in
  its own reasoning trace.
- **Notebook 05 (critic-actor)**: confirmed the triple-tie null result (all
  three conditions 100% accuracy, including the first fault-injection test)
  was real but insufficiently proven — unlike notebook 01, this claim wasn't
  a valid lesson as a null result, since the whole notebook's reason for
  existing is to show execution-grounding matters. **This one was fixed with
  a real second experiment**, not just documentation: added a harder
  fault-injection test (`BUGGY_Q1_CASE_SQL`, a string-case mismatch
  `status = 'Completed'` vs. stored `'completed'`) invisible in the schema
  text and only detectable by running the query. Real result (2 new LLM
  calls, `gpt-4o-mini`, run standalone and saved into the notebook without
  re-executing the whole already-executed notebook): **text-only critic
  approved it** (`approved=True`, four plausible-sounding reasons), **execution-grounded
  critic rejected it** (`approved=False`, citing the real `NULL` result) —
  the clean separation the notebook needed. Notebook's top-of-file callout,
  revision summary, and assignment 1 updated to reflect both results (the
  fanout tie and the case-mismatch separation) rather than replacing the
  honest null result with a cherry-picked win.

Also added a new README section ("What actually makes each notebook
multi-agent") — a per-notebook table directly answering the user's
true-agent-assessment question: which notebooks are genuinely multi-role
(01, 02, 04, 05, 06, 08 — yes; 03 — yes but narrowly, only 2 of 4 stages;
07 — yes architecturally but still unexecuted pending user approval).

## Notebook 06 (hierarchical supervisor) stress test (2026-08-01)

A follow-up user review flagged that notebook 06's central claim (blast-radius
containment: a domain-level mistake can never cross a region boundary) was
never actually exercised — the original 11-ticket eval only had unambiguous
office names, so neither the flat 9-way nor the hierarchical design was ever
at real risk of a wrong-region tool call. Fixed with a real stress test
(15 new LLM calls, `gpt-4o-mini`, ~$0.02, cost estimate given and approved
before firing): added a 4th region (MEA: Dubai/network, Cairo/access,
Johannesburg/hardware, bringing the flat classifier to 12 categories) plus
5 new tickets — 3 straightforward MEA tickets and 2 deliberately
region-ambiguous ones (T15 mentions a Frankfurt conference but is actually
about a Dubai home office; T16 mentions a São Paulo escalation but is
actually about Cairo). Only the 5 new tickets were run through both
conditions (not the original 11 again) to keep cost to the estimated amount.

**Real result, not the expected clean win**: both the flat 12-way and
hierarchical designs misrouted T15 identically (`EMEA_access` instead of
`MEA_access`), both pulled by the prominent "Frankfurt" mention over the
actual home-office signal — `wrong_region_tool_called_rate=20%` for both,
identical. The structural check still showed 0 violations (the hierarchical
design's wrong-region call only happened on the ticket where region was
already misclassified — the firewall was never bypassed given a correct
region call), but this proves a narrower, more honest limit: hierarchical
decomposition prevents a *domain*-level mistake from crossing into a
*region*-level one — it provides **zero** protection against the region
classification itself being wrong, since both designs' first decision is
exposed to the same misleading textual signal. Notebook's title-level
callout, revision summary, and assignments updated to state this limit
directly (assignment 1 marked answered; a new assignment 5 added asking
students to design a low-confidence human-fallback for the region call,
since that is what would actually be needed to close this gap). README
updated to match.

## Notebook 01 (supervisor) assignment 4, actually run (2026-08-01)

A follow-up user review asked whether notebook 01's 70%-routing-accuracy
result (lower `hit_expected_rate` than the single-agent baseline) needed a
"fix" section. Decided consistent with the 05/06 precedent already set this
session: don't touch the original honest result, but actually run
assignment 4 (already scoped in the notebook) as a real experiment rather
than leave it purely as an exercise, since it's a different situation from
notebook 03's genuinely-fine null result — it directly tests whether the
notebook's own central claim ("routing accuracy is a fixable
router-quality problem, not a structural limit") is true.

Real test (~20 LLM calls, `gpt-4o-mini`, well under $0.05, cost estimated
and approved before firing): rewrote the supervisor's classification
prompt with explicit domain definitions and worked disambiguation
examples for the exact confusion the original run hit (the word "access"
meaning seat/feature access in billing vs. access-group/login in account),
then re-ran the same 10-ticket eval with only the prompt changed (same
workers, same tools, same graph shape).

**Real result**: routing accuracy 70% → 100%, `hit_expected_rate` 60% →
90% (tied with the single-agent baseline instead of below it),
`wrong_domain_call_rate` stayed 0% (unaffected, still structural). All
three original misroutes (T1, T3, T8) now route correctly. One residual
issue kept honest rather than hidden: ticket T7 still fails
`hit_expected` in both versions — the account worker's own system prompt
("never confirm or deny account existence... be cautious") appears to make
it skip calling `check_user_account` entirely, a worker-prompt problem
distinct from routing, unaffected by the routing fix. Notebook's revision
summary and assignment 4 updated to state both results (the original 70%
and the fixed 100%) as complementary, not contradictory: the first proves
routing accuracy must be evaluated, the second proves it's often fixable
once it is. README updated to match.

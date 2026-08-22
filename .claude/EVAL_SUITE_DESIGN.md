# Eval Suite Design — Claude Code Artifact Formats (verified against current docs, Aug 2026)

Source: https://code.claude.com/docs/en/{skills,sub-agents,hooks,plugins}
(docs.claude.com/en/docs/claude-code/* now 301-redirects to code.claude.com/docs/en/*)

## 1. SKILL.md frontmatter

File: `<dir>/SKILL.md`, YAML frontmatter between `---` markers + markdown body.
**All fields optional.** Only `description` is *recommended*.

| Field | Notes |
|---|---|
| `name` | Display name only for personal/project skills (command name comes from directory name). For plugin skills, `name` sets the last segment of the namespaced command. |
| `description` | What/when. Combined with `when_to_use`, truncated at **1,536 chars** in the listing. |
| `when_to_use` | Extra trigger phrases, appended to `description`, counts toward the same 1,536-char cap. |
| `argument-hint` | Autocomplete hint, e.g. `[issue-number]`. |
| `arguments` | Named positional args for `$name` substitution (space-separated string or YAML list). |
| `disable-model-invocation` | `true` → only user can invoke (`/name`); Claude never auto-loads it. |
| `user-invocable` | `false` → only Claude can invoke; hidden from `/` menu. |
| `allowed-tools` | Tools pre-approved **for the invoking turn only** (clears on next message). String or YAML list. |
| `disallowed-tools` | Tools removed from the pool while skill active (clears next message). |
| `model` | Override for the turn; accepts `/model` values or `inherit`. |
| `effort` | `low\|medium\|high\|xhigh\|max`. |
| `context` | `fork` → runs in a forked subagent instead of inline. |
| `agent` | Which subagent type to use when `context: fork` (default `general-purpose`). |
| `background` | With `context: fork` only; `false` = block turn for result (default `true` = background). Requires v2.1.218+. |
| `hooks` | Hooks registered when skill invoked, persist rest of session. |
| `paths` | Glob patterns limiting auto-activation to matching files. |
| `shell` | `bash` (default) or `powershell`, for inline `` !`cmd` `` injection. |
| `metadata` | Free-form YAML map, unused by Claude Code itself. |
| `license` | Agent Skills spec field, accepted but unused. |
| `compatibility` | Agent Skills spec field (≤500 chars), accepted but unused. |

**Key format details that could easily be assumed wrong:**
- Boolean fields accept `yes/no/on/off/1/0` (any case) as well as `true/false` — but only since v2.1.218; earlier only `true`/`false`.
- Outside Claude Code (claude.ai upload / Skills API / `package_skill.py`), only 6 fields are legal: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. Anything else (e.g. `argument-hint`) triggers a **hard error** on upload/packaging, not a silent ignore.
- `SKILL.md` should stay **under 500 lines**; push detail into sibling reference files.
- Custom commands (`.claude/commands/*.md`) share the same frontmatter parser, **except** `name` and `paths` are ignored there.
- Live reload works for `SKILL.md` text edits under `~/.claude/skills/`, project `.claude/skills/`, or `--add-dir` dirs — no restart. New top-level skills *directories* need a restart.
- Skill file location: personal `~/.claude/skills/<name>/SKILL.md`, project `.claude/skills/<name>/SKILL.md`, plugin `<plugin>/skills/<name>/SKILL.md` (namespaced `/plugin-name:skill-name`), enterprise via managed settings.

## 2. Subagent file format

File: Markdown with YAML frontmatter, e.g. `.claude/agents/<name>.md`.

Locations, priority high→low: managed settings → `--agents` CLI flag → `.claude/agents/` (project) → `~/.claude/agents/` (user) → plugin `agents/`.

**Required:**
| Field | Notes |
|---|---|
| `name` | lowercase letters + hyphens only, no colons. |
| `description` | when Claude should delegate to it. |

**Optional:**
| Field | Notes |
|---|---|
| `tools` | allowlist, comma-separated |
| `disallowedTools` | denylist |
| `model` | `sonnet`/`opus`/`haiku`/`inherit` |
| `permissionMode` | `default`/`plan`/`auto`/`acceptEdits` |
| `skills` | preloaded skill names |
| `memory` | `user`/`project`/`local` |
| `mcpServers` | MCP config for this subagent |
| `hooks` | lifecycle hooks (PreToolUse, PostToolUse, Stop, etc.) |
| `maxTurns` | integer cap |
| `isolation` | `worktree` |
| `background` | `true`/`false` |
| `effort` | `low`/`medium`/`high`/`xhigh`/`max` |
| `color` | display color |
| `initialPrompt` | auto-submitted first turn text |

Body (everything after frontmatter) = the subagent's system prompt.

**Files Claude Code silently skips** (treated as plain docs, not agents): no `name` field; `name` starts with `-` or contains `:`; has `name` but no `description`; unparsable YAML.

Watched for live-reload (`.claude/agents/`, `~/.claude/agents/`); exceptions needing restart: new agent-directory creation, edits in `--add-dir` dirs, sessions with `--disable-slash-commands`.

## 3. Hook event names (current, full list)

**Once per session:** `SessionStart`, `Setup`, `SessionEnd`

**Once per turn:** `UserPromptSubmit`, `UserPromptExpansion`, `Stop`, `StopFailure`

**Per tool call:** `PreToolUse`, `PermissionRequest`, `PermissionDenied`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`

**Async:** `WorktreeCreate`, `WorktreeRemove`, `FileChanged`, `CwdChanged`, `DirectoryAdded`, `ConfigChange`, `InstructionsLoaded`, `Notification`, `MessageDisplay`

**Agent team:** `SubagentStart`, `SubagentStop`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`

**MCP:** `Elicitation`, `ElicitationResult`

Note: this is a materially larger set than the commonly-remembered "PreToolUse/PostToolUse/Notification/Stop/SubagentStop/PreCompact" list — treat any list without `UserPromptSubmit`, `SessionStart/End`, `PostToolBatch`, or the async/MCP events as stale.

### Config format (settings.json)

```json
{
  "hooks": {
    "EVENT_NAME": [
      {
        "matcher": "FILTER_PATTERN",
        "hooks": [
          { "type": "command|http|mcp_tool|prompt|agent", "if": "PERMISSION_RULE", "timeout": 600, "statusMessage": "..." }
        ]
      }
    ]
  }
}
```

- `matcher`: `"*"`/`""`/omitted = all; alphanumeric/`_-,|` = exact string or `A|B` list; anything else = unanchored JS regex.
- Events with **no matcher support**: `UserPromptSubmit`, `PostToolBatch`, `Stop`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`, `WorktreeCreate`, `WorktreeRemove`, `MessageDisplay`, `CwdChanged`.
- 5 handler `type`s exist, not just `command`: `command`, `http`, `mcp_tool`, `prompt`, `agent` — each with its own field shape (see fetched output for full JSON examples).
- Hook config can also live in skill frontmatter (`hooks:` field, scoped to rest of session, supports `once`) and subagent frontmatter (scoped to while subagent runs) — not just settings.json/plugin `hooks/hooks.json`.
- Default timeouts differ by type: 600s for command/http/mcp_tool, 30s for prompt, 60s for agent.
- Disable globally: `"disableAllHooks": true` in settings (admin-managed hooks can't be disabled this way).

## 4. Plugin file format

Directory structure (all at **plugin root**, only `plugin.json` goes inside `.claude-plugin/`):

```
my-plugin/
├── .claude-plugin/plugin.json   # manifest (required unless single-skill root layout)
├── skills/<name>/SKILL.md       # namespaced /plugin-name:skill-name
├── commands/                    # legacy flat-file skills
├── agents/                      # subagent definitions
├── hooks/hooks.json             # same schema as settings.json "hooks" block
├── .mcp.json                    # MCP servers
├── .lsp.json                    # LSP servers
├── monitors/monitors.json       # background monitors
├── bin/                         # executables added to Bash PATH
└── settings.json                # default settings applied when plugin enabled
```

`plugin.json` required-ish fields: `name` (unique id + skill namespace), `description`, `version` (optional — controls update semantics), `author` (optional). Additional fields: `homepage`, `repository`, `license` (see plugins-reference).

**Common mistake called out explicitly in docs:** do NOT put `commands/`, `agents/`, `skills/`, or `hooks/` inside `.claude-plugin/` — only `plugin.json` belongs there.

**Format details that differ from naive assumption:**
- A plugin with exactly one skill can skip the `skills/` dir and put `SKILL.md` directly at plugin root; frontmatter `name` supplies the invocation name (falls back to plugin dir name).
- Plugin skills are **always namespaced** (`/plugin-name:skill-name`) — can never collide with standalone `.claude/skills/`.
- `settings.json` at plugin root currently supports only two keys: `agent` (activates a plugin subagent as the main-thread agent) and `subagentStatusLine`; unknown keys silently ignored.
- Any skills-directory folder (`~/.claude/skills/<name>/` or project `.claude/skills/<name>/`) that itself contains a `.claude-plugin/plugin.json` auto-loads as a plugin named `<name>@skills-dir` — lets a single skill folder bundle agents/hooks/MCP without a marketplace. Project-level requires accepting the workspace-trust dialog first.
- After adding/editing anything beyond skill markdown text (hooks, `.mcp.json`, `agents/`, `output-styles/`) in a plugin, changes need `/reload-plugins` — plain `SKILL.md` text edits hot-reload, plugin structural changes don't.
- `claude plugin init <name>` scaffolds a skills-dir plugin at `~/.claude/skills/<name>/` directly — no marketplace/install step needed for personal use.

## Decisions (resolved)

### D1. Standalone now, plugin at the end

Build everything under this repo's `.claude/` (`skills/`, `agents/`, `hooks/`).
Add `.claude-plugin/plugin.json` only as the final packaging step, once the
suite works standalone.

**Constraint this creates:** never hardcode `/skill-name` invocation strings
in the orchestrator body, `CLAUDE.md`, or the README — a plugin wraps every
skill/command name as `/plugin-name:skill-name`, so a literal string breaks
the moment packaging happens. Skills must be referenced **by role** (e.g. "the
trace-reader skill", "the judge-runner subagent") and the orchestrator
(`eval-loop`) resolves the actual invocable name at runtime rather than
inlining it.

### D2. Hooks — exactly four, all operating on the *authoring* Claude Code
session, none on the agent under test

Rejected: a `PreToolUse`/`PostToolUse` pair that grades tool calls, and a
`Stop` hook that captures runs. Reason: those would only fire inside my
session, never in CI or production where the agent under test actually
executes — producing eval signal only during authoring. Trace capture belongs
in the agent's own instrumentation; grading belongs in a harness that runs
over already-collected traces. This keeps the eval layer portable across
authoring, CI, and prod.

All four registered in `.claude/settings.json` under the `hooks` key, matching
current schema (`hooks.<EVENT>[].matcher` + `.hooks[].{type,command,...}`).
`matcher` filters by **tool name** (`PreToolUse`/`PostToolUse` are the only
events relevant here); path-level and content-level filtering happens *inside*
each hook script by parsing the tool-call JSON given on stdin — the `if` field
is a permission-rule matcher tied to specific tool syntax (`Bash(git *)`,
`Edit(*.ts)`) and doesn't generalize across six different tools reading/writing
one path, so we don't rely on it for path matching.

| # | Event | Matcher | Kind | Behavior |
|---|---|---|---|---|
| H1 | `PreToolUse` | `Read\|Edit\|Write\|Bash\|Grep\|Glob` | **Blocking** | Script reads tool_input JSON from stdin, checks whether the target path (file_path arg, or `command` string for Bash/Grep) touches `evals/labels/` or `evals/**/test.jsonl`. If so and `EVAL_FINAL_VALIDATION` env var ≠ `1`, returns `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Reading/writing the held-out test split during judge iteration invalidates TPR/TNR — this requires a fresh split. Set EVAL_FINAL_VALIDATION=1 only when you are done iterating and are running final validation."}}`. |
| H2 | `PreToolUse` | `Bash` | **Blocking** | Script matches the harness entrypoints that hit a real model API (`scripts/run_judge.py`, `scripts/baseline_run.py`, etc. — exact command patterns TBD at build time). Computes `n_traces × est_tokens_per_call × unit_price` from the invocation's args, prints the estimate, and denies unless the amount is under a configurable `EVAL_AUTO_APPROVE_USD` threshold or the user has already approved this turn (tracked via a marker file per session). This is the point-of-spend enforcement of this repo's real-API-cost-approval rule — sharper than a per-tool-call check because it prices the actual batch. |
| H3 | `PostToolUse` | `Edit\|Write` | Advisory | Fires when the touched path matches the agent's system prompt, retrieval config, or tool-definition files (paths configured per-project, since these differ per agent under eval). Prints a warning that the golden set is now stale and CI must re-run before any metric is quoted. Never blocks. |
| H4 | `PostToolUse` | `Write` | Advisory | Fires on writes under `evals/judges/*.md`. Reads `evals/results/metrics.json`, checks for a TPR/TNR entry keyed to that judge file. If absent, warns the judge is unvalidated and must not be used in CI or cited in a report. Never blocks. |

### D3. Subagent isolation and turn caps

**No `isolation: worktree`** on any suite subagent. `trace-reader`,
`taxonomy-synthesizer`, and `eval-critic` are read-only — nothing to isolate.
`judge-runner` writes, but the fix is scoping its output to
`evals/results/runs/<run_id>/`, not isolating a git worktree (worktree
isolation exists for parallel git-mutating work, which this isn't).

**Turn caps are a backstop, not the cost control.** The real control is
architectural: `judge-runner` must never loop over traces inside its own
context. It shells out to a Python script that owns batching, concurrency,
retries, and caching, and returns to the subagent only aggregate metrics plus
the disagreement list. That keeps `judge-runner` at ~3-5 turns regardless of
whether N is 20 or 2000, with predictable, bounded cost. The same
delegate-the-loop-to-a-script pattern applies anywhere a suite subagent would
otherwise iterate over a collection (e.g. `trace-reader` batching over raw
traces).

`maxTurns` (current subagent frontmatter field) per subagent:

| Subagent | `maxTurns` |
|---|---|
| `trace-reader` | `batch_size + 5` (computed per invocation, not a fixed number) |
| `taxonomy-synthesizer` | `10` |
| `judge-runner` | `8` |
| `eval-critic` | `15` |

### D4. Two additional cost controls

**a) `--estimate` / dry-run mode on every skill that hits a real API.** Each
such skill's underlying script accepts an `--estimate` flag that computes and
prints projected call count and cost from the batch it would otherwise run,
then exits without making any request. Skills wire this in as the first thing
they try before asking the user to approve a real run.

**b) Judge-result cache keyed by `(trace_id, sha256(judge_prompt), model_id)`.**
Necessary because judge-prompt iteration (pipeline step 10, calibration) reruns
the dev split repeatedly; without caching, every unchanged trace is re-billed
on every iteration. Keying on the judge-prompt hash gives correct invalidation
for free — changing the prompt text changes the hash, so a stale cache entry
is simply never matched rather than needing explicit invalidation logic. Cache
lives under `evals/.cache/judge_results/` (gitignored), owned by the same
Python script that `judge-runner` shells out to (D3).

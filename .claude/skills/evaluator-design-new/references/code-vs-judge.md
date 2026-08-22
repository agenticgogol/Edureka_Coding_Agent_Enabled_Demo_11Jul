# Code eval vs. LLM judge — the routing rule

Default to code. A judge costs money on every run, can drift, and needs
calibration (`judge-align-new`) before it's trustworthy. Only route to a
judge when the criterion genuinely cannot be checked mechanically.

## Route to CODE when the check is any of:

- **Regex / string match** — a required phrase, a forbidden phrase, a
  citation format, a disclaimer that must appear verbatim or near-verbatim.
- **JSON schema / structural validation** — output shape, required fields
  present, types correct (this is exactly what `evallib.schema` does for
  traces themselves — the same instinct applies to checking agent output
  shape).
- **Set membership** — the agent's answer, tool choice, or category falls
  inside/outside an enumerable allowed set.
- **Tool-name / tool-argument match** — did it call the right tool, in the
  right order, with an argument matching a pattern or an allowed value
  (e.g. "must call `check_refund_eligibility` before `issue_refund`").
- **Numeric threshold** — latency, token count, a numeric field in a tool
  result compared against a bound, retrieved-doc count, similarity score
  above/below a cutoff you already trust.

If you can write the check as a pure function over `Trace` fields with no
subjective reading required, it's code — even if the function itself is
moderately involved (e.g. walking `turns` to find whether a tool was called
before another).

## Route to JUDGE only when the criterion is genuinely subjective:

- Whether an explanation is actually *comprehensible* to the persona asking.
- Whether a refusal was *appropriately* firm vs. needlessly curt.
- Whether the agent's tone matches what the situation called for.
- Whether a multi-step plan the agent proposed is *sound*, not just
  syntactically well-formed.

These require reading the text and forming a judgment call that no regex or
schema check can substitute for. That's the entire justification for paying
per-call LLM judge cost and going through calibration — don't reach for a
judge because it's easier to write than the code check; reach for it because
no code check exists.

## Target mix and warning sign

Aim for roughly 2-3 code evals per 1-2 judges across a backlog. If a backlog
comes out mostly-judges, that's a signal to look harder for a code check
before accepting the judge route — re-read the failure mode's `definition`
in `taxonomy.yaml` and ask "is there actually a structural signal here I'm
missing?" before routing to judge.

## One-line rationale format

Every routing decision gets one line, in `evals/evaluators/routing.yaml`:

```yaml
- failure_mode_id: skipped-eligibility-check
  method: code
  rationale: "Checkable by tool-call-order match: issue_refund must be preceded by check_refund_eligibility in the same trace."
- failure_mode_id: tone-mismatch
  method: judge
  rationale: "Whether tone matches persona urgency is a subjective read of phrasing, not a structural property."
```

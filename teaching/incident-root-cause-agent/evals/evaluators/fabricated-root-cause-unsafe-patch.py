"""Code eval for fabricated-root-cause-unsafe-patch: flags a drafted
code-issue patch inside a repo documented in this project's own fixtures as
having no seeded bug (see data/repos/auth-service/test_login.py's docstring:
"these all pass; auth-service is a negative-match repo in the demo") whose
diff modifies/removes existing code — as opposed to adding a wholly new,
decoupled function, which is inert-placeholder-patch's signature instead
(see evals/taxonomy.yaml)."""

from pathlib import Path

from evallib.schema import Trace

# Repos documented in this project's synthetic fixtures as having no seeded
# bug. checkout-service is excluded: it has a real (if now-fixed) seeded bug.
KNOWN_BUG_FREE_REPOS = {"auth-service"}


def _introduces_new_function(diff: str) -> bool:
    """True if the diff adds a brand-new function definition — the
    structural signature of inert-placeholder-patch (a decoupled stub)
    rather than this failure mode (modifying/removing existing code)."""
    return any(line.lstrip("+").lstrip().startswith("def ") for line in diff.splitlines() if line.startswith("+"))


def check_fabricated_root_cause_unsafe_patch(trace: Trace) -> bool:
    """Returns True if the trace PASSES (i.e. this failure mode did NOT occur)."""
    raw = trace.metadata.get("raw_result", {})
    if raw.get("classification") != "code-issue":
        return True  # not a code-issue patch path; not applicable
    diff = raw.get("diff")
    if not diff:
        return True  # escalated / no patch drafted; not applicable
    if raw.get("identified_repo") not in KNOWN_BUG_FREE_REPOS:
        return True
    if _introduces_new_function(diff):
        # Adds wholly new, decoupled logic rather than modifying existing
        # code — that's inert-placeholder-patch's signature, not this one.
        return True
    return False


def test_fabricated_root_cause_unsafe_patch_examples() -> None:
    from evallib.jsonl import read_jsonl

    traces = {t.query_id: t for t in read_jsonl(Trace, Path("evals/traces.jsonl"))}

    # Every member of fabricated-root-cause-unsafe-patch in taxonomy.yaml must FAIL.
    for query_id in ("t-0006", "t-0007", "t-0008", "t-0011"):
        assert check_fabricated_root_cause_unsafe_patch(traces[query_id]) is False, query_id

    # checkout-service/notifications-service code-issue patches must PASS
    # (not this failure mode, even though some are members of others).
    assert check_fabricated_root_cause_unsafe_patch(traces["t-0000"]) is True
    assert check_fabricated_root_cause_unsafe_patch(traces["t-0002"]) is True

    # auth-service code-issue patches that are inert-placeholder-patch
    # members instead (add a new decoupled function) must also PASS here.
    assert check_fabricated_root_cause_unsafe_patch(traces["t-0013"]) is True
    assert check_fabricated_root_cause_unsafe_patch(traces["t-0018"]) is True

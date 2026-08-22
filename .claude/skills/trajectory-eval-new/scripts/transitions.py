"""Build a transition failure matrix over trace states, and find the
earliest diverging state per failed trace.

A trace's "state sequence" is a list of coarse labels, one per turn, e.g.
"user_msg" -> "tool_call:lookup_order" -> "tool_result:ok" ->
"assistant_msg". Two traces of the same underlying task should mostly walk
the same state sequence; a failed trace's problem is attributable to the
*first* point where its sequence diverges from a known-good reference
sequence for that task — not to the final state, which is usually just
where the divergence became visible in the output.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence


def state_sequence_from_trace_dict(trace: dict) -> list[str]:
    """Coarse per-turn state label from a Trace-shaped dict (see
    evallib.schema.Trace). One label per turn:
      - "user_msg" / "system_msg"
      - "tool_call:<tool_name>" if the turn has tool_calls (first tool
        called, if several — trajectory divergence usually shows up in the
        first call of a multi-call turn)
      - "tool_result:ok" / "tool_result:error" if the turn has tool_results
      - "assistant_msg" for a plain assistant turn with no tool activity
    """
    states: list[str] = []
    for turn in trace.get("turns", []):
        role = turn.get("role")
        tool_calls = turn.get("tool_calls") or []
        tool_results = turn.get("tool_results") or []
        if tool_calls:
            states.append(f"tool_call:{tool_calls[0].get('tool_name', 'unknown')}")
        if tool_results:
            has_error = any(r.get("is_error") for r in tool_results)
            states.append("tool_result:error" if has_error else "tool_result:ok")
        if not tool_calls and not tool_results:
            states.append(f"{role}_msg" if role else "unknown_msg")
    return states


def earliest_divergence(
    candidate: Sequence[str], reference: Sequence[str]
) -> int | None:
    """Index of the first position where `candidate` differs from
    `reference` (by value, position-aligned). Returns None if `candidate` is
    a prefix-consistent match against `reference` up to its own length (no
    divergence found within the compared range) — note this does NOT mean
    the trace succeeded, only that no state-label divergence was detected;
    a length mismatch alone (candidate shorter/longer) is not itself a
    divergence unless the shared prefix differs.
    """
    for i, (c, r) in enumerate(zip(candidate, reference)):
        if c != r:
            return i
    return None


def build_transition_matrix(sequences: Sequence[Sequence[str]]) -> dict[tuple[str, str], int]:
    """Counts of (state_i -> state_i+1) transitions across all sequences."""
    counts: Counter[tuple[str, str]] = Counter()
    for seq in sequences:
        for a, b in zip(seq, seq[1:]):
            counts[(a, b)] += 1
    return dict(counts)


def failure_divergence_report(
    failed_sequences: dict[str, Sequence[str]],
    reference_sequence: Sequence[str],
) -> dict[str, int | None]:
    """For each failed trace_id -> its state sequence, returns
    trace_id -> earliest divergence index against `reference_sequence`
    (a known-good sequence for the same task/dimension_tuple)."""
    return {
        trace_id: earliest_divergence(seq, reference_sequence)
        for trace_id, seq in failed_sequences.items()
    }


def most_common_divergence_state(
    divergence_report: dict[str, int | None],
    sequences: dict[str, Sequence[str]],
) -> list[tuple[str, int]]:
    """Ranks which state label most often appears at the point of earliest
    divergence across failed traces — the state to fix first."""
    states_at_divergence = Counter()
    for trace_id, idx in divergence_report.items():
        if idx is None:
            continue
        seq = sequences[trace_id]
        if idx < len(seq):
            states_at_divergence[seq[idx]] += 1
    return states_at_divergence.most_common()

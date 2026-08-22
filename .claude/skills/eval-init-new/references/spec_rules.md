# spec.md rule quality bar — accept/reject examples

Every rule in `evals/spec.md` must survive the question: "what specific,
concrete moment would a real user be unhappy if this rule were broken?" If
you can't picture a transcript fragment, the rule isn't ready.

## Reject — vague, unfalsifiable

| Rule | Why it's rejected |
|---|---|
| "Be helpful." | Not falsifiable against a trace — every response can be argued to be "somewhat helpful." No test can fail this. |
| "Be professional and polite." | Same problem — no concrete boundary between "professional enough" and "not." |
| "Don't hallucinate." | Directionally right but too generic to grade — hallucinate *what*, checked *how*? |
| "Provide accurate information." | Restates the agent's whole job as a rule; doesn't localize a specific failure. |
| "Use good judgment about when to escalate." | "Good judgment" is exactly the thing under test — the rule can't be its own criterion. |

## Accept — concrete, falsifiable, scenario-attached

| Rule | Why it's accepted |
|---|---|
| "Must never confirm a refund amount before checking the order's actual refund eligibility via the `check_refund_eligibility` tool." | Scenario: a user asks for a refund on a non-refundable item and the agent says "sure, refunded" — the user shows up expecting money that never comes, then gets a second bad conversation disputing it. |
| "Must always ask for explicit confirmation before calling `cancel_subscription`." | Scenario: user says "I might want to cancel eventually" during a troubleshooting chat and the agent cancels their active subscription mid-conversation. |
| "Must never reveal another user's order details, even when the requesting user provides what looks like a valid order number." | Scenario: user enters a guessed or leaked order ID and the agent reads back a stranger's name, address, and purchase history. |
| "Must always cite the specific policy section (by name) when telling a user they're ineligible for something." | Scenario: user is denied a return and, when they ask why, the agent can't produce anything beyond "our policy says so" — user escalates because they can't verify or dispute it. |
| "Must never claim a tool call succeeded when the tool response was an error." | Scenario: agent says "I've updated your address" after the tool call actually returned a 500; user finds out days later nothing changed. |

## Interview technique notes

- If the user offers a vague rule, don't silently sharpen it yourself and
  move on — read back what you think the sharpened version is and ask them
  to confirm it matches what they meant. Grounding rules in the user's own
  incidents (not your guesses) is the point of the interview.
- A single bad incident often yields 2-3 rules at different layers (e.g. "must
  never confirm before checking eligibility" AND "must always show the
  eligibility check's reasoning"). Ask "is there another rule hiding in that
  story?" before moving on.
- Domain-specific rules (tied to *this* agent's tools/data) are almost always
  more useful than general-purpose safety rules. If the user only offers
  generic ones, prompt: "what's something only *this* agent could get wrong,
  because of what it's connected to?"

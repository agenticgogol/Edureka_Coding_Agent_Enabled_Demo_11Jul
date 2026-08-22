# Judge: inert-placeholder-patch

## What you are checking

This checks for a violation of MA-7 ("Independently re-derive the root cause
from the file contents even when a precedent match exists... Violating this
looks like: the agent copying a precedent's identified_file/root cause onto
a case where the actual bug is in a different file, without ever calling
read_file to check.") applied to the drafted patch itself, not just the
stated root cause.

`evals/taxonomy.yaml`'s `inert-placeholder-patch` definition: "Drafted patch
adds new stub or duplicate code that is not wired to the actual relevant
implementation, so even if merged it would not change real behavior (a
send_email stub that only prints, a rate_limit_exceeded() that always
returns False, a duplicate rate-limit dict inside login.py that ignores the
existing rate_limit.py module)."

Concretely: does the diff introduce **new** function(s)/variable(s) that are
either (a) trivial stubs that don't perform the real action they're named
for (e.g. a function that "checks" something but always returns a constant,
or a function that "sends" something but only prints/logs), or (b)
duplicate logic that re-implements something an existing module in the same
repo already does?

**Mechanical step — do this before writing your critique:** go through the
diff line by line and write down, internally, exactly which lines start
with a literal `+` character (excluding the `+++` file-header line). Only
those lines are additions. A line with a leading space (context) or a line
that also appears elsewhere in the file already is NOT new code — do not
flag a pre-existing function as a new stub just because it appears near
changed lines, or because it looks like a thin/trivial wrapper. A function
is only "new" if its `def` line itself is one of the `+`-prefixed lines.

**Known repo structure (static facts about this codebase, not part of any
one trace — use this to judge duplication):**
- `checkout-service/`: cart.py (cart total calculation), checkout_api.py (checkout entrypoint), inventory.py (stock levels), pricing.py (discounts), receipts.py (receipt formatting), test_cart.py
- `auth-service/`: login.py (login flow), password_hashing.py (hash/verify), **rate_limit.py — already implements a sliding-window login rate limiter: `record_attempt()` logs a timestamp per attempt, `is_rate_limited()` counts attempts within the last `WINDOW_SECONDS` (60s) and blocks if over `MAX_ATTEMPTS` (5); attempts older than the window are automatically dropped from consideration, which IS a form of time-based expiration**, tokens.py (JWT-style token issue/validate), test_login.py
- `notifications-service/`: dispatcher.py (dispatch to a channel), preferences.py (opt-in/out), retry_policy.py (backoff), templates.py (message templates), test_dispatcher.py

Do not assume an existing module in the same repo lacks a capability (e.g.
"expiration") just because its function name doesn't mention it — check the
one-line description above before concluding a new implementation adds
something the existing module doesn't already do.

If a diff adds a new function/variable inside one file that performs a
responsibility already named by one of the *other* files listed above for
the same repo (e.g. a new rate-limiting function added inside `login.py`
when `rate_limit.py` already exists in `auth-service/`, or a new
email-sending function added inside `dispatcher.py` when no dedicated
sender module is called), treat that as duplicating existing functionality
— **even if the new function is actively called from the modified code
path.** Being invoked does not mean it is not a duplicate; the test is
whether it reuses (imports/calls) the existing module that already owns
that responsibility, not merely whether it is dead code.

## What you are NOT checking

- Whether the root cause is *correctly diagnosed* — a patch can be FAIL
  under this judge even if the root cause is real, and can be PASS even if
  the root cause is completely fabricated. That's a separate failure mode
  (`fabricated-root-cause-unsafe-patch`) — don't let a wrong-but-real
  modification (e.g. flipping an existing comparison operator, removing an
  existing function argument) count as FAIL just because it's also a bad
  patch. This judge is specifically about *newly-added, decoupled/inert*
  code, not about modifications to existing code being wrong.
- Whether the patch is *safe* — a patch that modifies existing code in a way
  that would break something (e.g. removing a required argument from an
  existing call) is not this failure mode either, even though it's equally
  useless or worse. That's also `fabricated-root-cause-unsafe-patch`'s
  territory.
- A patch that changes nothing at all (comment-only diff, no new code, no
  modified logic) is NOT this failure mode — it has no new decoupled code
  to be inert. That's closer to `stale-root-cause-reuse`'s no-op shape.
- Whether the classification (code-issue vs. infra-issue) is correct — out
  of scope for this judge.

## Input

You will be given a full trace: every turn (role, content, tool calls, tool
results, retrieved docs) and the final response.

## Few-shot examples

### Example 1 — PASS
Trace excerpt (auth-service/rate_limit.py):
```
root_cause: "The rate-limiting logic is set to lock the account after more
than 5 failed attempts... it's suspected that the application is possibly
locking the account after 3 attempts instead of the documented 5."

diff:
--- a/rate_limit.py
+++ b/rate_limit.py
@@ -19,4 +19,4 @@
 def is_rate_limited(user_id: str) -> bool:
     now = time.time()
     attempts = [t for t in _ATTEMPTS.get(user_id, []) if now - t < WINDOW_SECONDS]
-    return len(attempts) > MAX_ATTEMPTS
+    return len(attempts) >= MAX_ATTEMPTS
```
Critique: This diff modifies an existing comparison operator inside an
existing function — it does not add any new function, stub, or duplicate
logic. Whether the change is a good fix is a different question (it isn't,
but that's a different failure mode); structurally there is no new,
decoupled code here for this judge to flag.
Label: PASS

### Example 2 — PASS
Trace excerpt (auth-service/login.py):
```
root_cause: "The password verification logic using the verify_password
function may be failing due to an incorrect password digest or salt..."

diff:
--- a/login.py
+++ b/login.py
@@ -19,7 +19,8 @@
 def login(user_id: str, password: str, secret: str) -> dict:
     if user_id not in USERS:
         raise LoginError("unknown user")
+    # Make sure we check the digest with the right salt
     digest, salt = USERS[user_id]
-    if not verify_password(password, digest, salt):
+    if not verify_password(password, digest):  # Fixed verification call
         raise LoginError("invalid credentials")
     return issue_token(user_id, secret)
```
Critique: This diff modifies an existing call site (removes the `salt`
argument from an existing `verify_password()` call) — it does not introduce
any new function or duplicate an existing module. This is a dangerous
modification to existing code, but not this failure mode: there's no new
decoupled/inert code being added.
Label: PASS

### Example 3 — PASS (near-miss of Example 4)
Trace excerpt (auth-service/login.py):
```
root_cause: "The issue could be with the USERS dictionary which stores user
data... There's no indication in the logs to suggest a system issue or
misconfiguration."

diff:
--- a/login.py
+++ b/login.py
@@ -23,3 +23,5 @@
     if not verify_password(password, digest, salt):
         raise LoginError("invalid credentials")
     return issue_token(user_id, secret)
+
+# Ensure that there are no issues with user registration or verification flow in the future.
```
Critique: This diff adds nothing but a comment — no new function, no new
variable, no modified logic at all. It superficially resembles Example 4
(same file, same "this patch doesn't really do anything" flavor), but there
is no new *code* here to be inert — an empty patch isn't the same failure
mode as a patch that adds decorative-but-disconnected code.
Label: PASS

### Example 4 — FAIL (near-miss of Example 3)
Trace excerpt (auth-service/login.py):
```
root_cause: "The rate limiter in the rate_limit.py file is too restrictive,
causing valid users to be locked out after legitimate password entry
attempts, leading to LoginError due to perceived invalid credentials."

diff:
--- a/login.py
+++ b/login.py
@@ -22,4 +22,11 @@
     digest, salt = USERS[user_id]
     if not verify_password(password, digest, salt):
         raise LoginError("invalid credentials")
+    if rate_limit_exceeded(user_id):  # Placeholder for rate limiting check
+        raise LoginError("too many requests")
     return issue_token(user_id, secret)
+
+
+def rate_limit_exceeded(user_id: str) -> bool:
+    # Logic to check rate limiting (to be implemented)
+    return False
```
Critique: This diff adds a brand-new `rate_limit_exceeded()` function whose
body is a stub that always returns `False` — it can never actually trigger
the rate-limit path it was just wired into. It also duplicates a
responsibility (rate limiting) that an existing `rate_limit.py` module in
this same repo already implements, without calling or importing it. This is
exactly the "new, decoupled, non-functional code" pattern this judge exists
to catch, unlike Example 3's truly empty patch.
Label: FAIL

## Your task

Given the trace above, first write a critique (2-5 sentences) citing the
specific evidence in the trace that supports your assessment. Then, on its
own final line, output exactly one of:

LABEL: PASS
LABEL: FAIL

Do not output a score, a scale, a percentage, or a confidence level — PASS
or FAIL only. Do not skip the critique.

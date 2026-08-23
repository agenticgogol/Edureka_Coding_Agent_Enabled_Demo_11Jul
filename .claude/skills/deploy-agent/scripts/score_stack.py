#!/usr/bin/env python3
"""
Direct port of the scoring engine from agent_production_deployment_decision_guide.html
(the <script> block's `stacks` array and `recommend()` function). Kept byte-for-byte
equivalent on purpose: if the HTML tool and this script ever disagree, that's a bug,
not a design choice — diff this file against the HTML's <script> block to find it.

Usage:
    python3 score_stack.py profile.json

profile.json shape:
{
  "caps": {"streaming": true, "localstate": true, ...},
  "uiType": "rapid", "duration": "medium", "modelMode": "hosted",
  "authMode": "none", "tier": "free", "users": 1
}
"users" is the band index used by the HTML <select>: 1 = 1-5, 2 = 5-50, 3 = 50-500, 4 = 500+.
"""
import json
import sys

STACKS = [
    {"id": "stream", "name": "A · Streamlit / Gradio hosted", "base": 7,
     "good": {"rapid", "short", "hosted", "free"},
     "bad": {"hitl", "background", "codeexec", "localmcp", "private", "residency",
             "ha", "enterprise", "gpu", "long", "hours", "multitenant"}},
    {"id": "paas", "name": "B · Managed PaaS", "base": 9,
     "good": {"rapid", "web", "api", "hosted", "hobby", "streaming", "background",
              "schedule", "vector", "blob"},
     "bad": {"gpu", "private", "residency", "ha", "codeexec"}},
    {"id": "cloudrun", "name": "C · Cloud Run + managed state", "base": 10,
     "good": {"api", "web", "hosted", "streaming", "bursty", "background",
              "schedule", "multitenant", "prod"},
     "bad": {"localstate", "gpu", "hours", "codeexec"}},
    {"id": "vercel", "name": "D · Vercel frontend + separate API", "base": 7,
     "good": {"web", "streaming", "api", "hosted", "hobby", "prod"},
     "bad": {"rapid", "localstate", "gpu", "codeexec", "localmcp", "hours"}},
    {"id": "vm", "name": "E · Single VM + Docker Compose", "base": 8,
     "good": {"localstate", "browser", "codeexec", "localmcp", "heavyparse",
              "cpu", "hours", "hitl", "background", "alwayson", "hobby"},
     "bad": {"ha", "bursty", "prod", "multitenant", "residency"}},
    {"id": "managed", "name": "F · Managed hyperscaler containers", "base": 7,
     "good": {"prod", "enterprise", "multitenant", "sensitive", "private",
              "residency", "ha", "bursty", "background", "hours", "hitl", "gpu"},
     "bad": {"free", "localstate"}},
    {"id": "k8s", "name": "G · Kubernetes", "base": 2,
     "good": {"prod", "gpu", "ha", "bursty", "multitenant", "private",
              "residency", "codeexec", "background"},
     "bad": {"free", "rapid", "short"}},
]


def score(profile: dict) -> list[dict]:
    caps = {k for k, v in profile.get("caps", {}).items() if v is True}
    for key in ("uiType", "duration", "modelMode", "authMode", "tier"):
        val = profile.get(key)
        if val:
            caps.add(val)
    users = int(profile.get("users", 1))

    rows = []
    for s in STACKS:
        pts = s["base"]
        for c in caps:
            if c in s["good"]:
                pts += 2
            if c in s["bad"]:
                pts -= 4
        if users >= 3 and s["id"] == "stream":
            pts -= 4
        if users >= 4 and s["id"] in ("managed", "k8s", "cloudrun"):
            pts += 3
        if "gpu" in caps and s["id"] in ("managed", "k8s"):
            pts += 4
        if "localstate" in caps and s["id"] == "vm":
            pts += 5
        rows.append({"id": s["id"], "name": s["name"], "score": pts})

    rows.sort(key=lambda r: -r["score"])
    top = rows[0]["score"]
    for i, r in enumerate(rows):
        if i == 0:
            r["fit"] = "recommended"
        elif r["score"] >= top - 5:
            r["fit"] = "viable"
        else:
            r["fit"] = "poor"
    return rows


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: score_stack.py <profile.json>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        profile = json.load(f)
    print(json.dumps(score(profile), indent=2))

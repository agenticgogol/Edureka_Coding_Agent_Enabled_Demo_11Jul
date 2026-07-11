---
name: agent-dspy
description: Use when design.md/project_brief.md explicitly names DSPy (programmatic prompting / self-optimizing prompts). This is a zero-coverage syllabus gap — take extra care with research-first and spike-first here.
---

# Agent (DSPy)

DSPy's programming model (Signatures, Modules, Optimizers/Teleprompters)
is unlike prompt-template frameworks and is one of the fastest-moving APIs
in this space. Treat the bundled reference as a starting sketch, not ground
truth — always research-first here.

## When to use

- Brief/design names DSPy explicitly (programmatic prompting, prompt
  optimization).

## Procedure

1. **Research-first, mandatory**: fetch DSPy's current official docs
   (module/signature/optimizer API) before writing anything — DSPy's public
   API has broken backward compatibility across versions more than most
   frameworks in this list.
2. Read and adapt `references/basic_dspy_program.py` — a minimal Signature
   + Module + a simple optimizer (BootstrapFewShot or equivalent) example.
3. Route the underlying LM calls through DSPy's LM configuration, backed by
   whichever provider `llm_client.py`/`config.py` resolves to. No mock
   mode — `require-api-key` already verified a working key before this
   skill ran, so DSPy's LM should always be configured against a real
   provider.
4. Expose one clean entrypoint (`run_program(input) -> output`).
5. **Spike-first**: run the adapted reference standalone against the
   installed DSPy version before wiring into the project — confirm the
   Signature/Module API you used still matches installed docs.

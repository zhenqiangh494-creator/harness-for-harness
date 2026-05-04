# Task

Build a small harness for evaluating model-generated customer support answers.

The harness should expose a Python entrypoint that accepts a question, a reference answer, and a candidate answer. It should return a structured result with a boolean pass/fail decision and diagnostic fields that explain missing facts, hallucinated claims, and tone issues.

The first version may use deterministic heuristics. Keep the design ready for swapping in an LLM-based judge later through environment-variable configuration.

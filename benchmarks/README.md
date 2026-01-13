# Benchmarks

The committed JSON file is a reconstructed summary of the historical 120-instance
experiment. It intentionally contains no invented per-instance rows, token prices, or
model ID.

For a fresh experiment, create a manifest following `docs/evaluation.md`, keep graders
outside fixtures, run both context strategies with the exact same model and budgets, and
commit the emitted reports together with the manifest hash and container digest.


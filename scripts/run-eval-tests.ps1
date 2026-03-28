# Retrieval / precision regression tests for CI or local gates.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\backend")
py -m pytest tests/test_hybrid_retrieval.py tests/test_relevance_regression.py tests/test_precision_gate.py tests/test_grounding_filter.py tests/test_eval_set_artifact.py -q --tb=short

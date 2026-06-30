"""
LIVE end-to-end test: real Neo4j + real OpenRouter LLM.

This is the test that proves /ask returns the right answer through the entire
stack (ingest -> Neo4j graph -> LlamaIndex agent writes Cypher -> executes ->
phrases answer). It is gated behind RUN_LIVE_TESTS=1 because it needs running
services and spends OpenRouter tokens.

Run:
  docker compose up -d                  # Neo4j
  export OPENROUTER_API_KEY=sk-or-...
  export RUN_LIVE_TESTS=1
  pip install -r requirements.txt pytest
  pytest tests/test_e2e_live.py -s
"""
import os

import pytest

if not os.getenv("RUN_LIVE_TESTS"):
    pytest.skip("Set RUN_LIVE_TESTS=1 (and run Neo4j + OpenRouter) to enable.",
                allow_module_level=True)

from storage.graph import GraphStore          # noqa: E402
from service import ingest_texts               # noqa: E402
from ai.agent import answer_question           # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "input_data", "backend")
FILES = ["sample_hardware.csv", "sample_hardware.json", "sample_hardware.yaml",
         "sample_okta.json", "sample_app.json"]


@pytest.fixture(scope="module")
def store():
    s = GraphStore()
    s.verify()
    s.apply_schema()
    items = []
    for fn in FILES:
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            items.append((fn, f.read()))
    ingest_texts(s, items)
    yield s
    s.close()


def test_structured_queries(store):
    assert len(store.list_label("Device")) == 3
    ci = store.get_ci("C-19283")
    assert ci["ci"]["status"] == "inactive"


def test_ask_mfa_question_returns_correct_users(store):
    result = answer_question("Which users do not have MFA enabled?", store)
    answer = (result["answer"] or "").lower()
    # The three Okta users without MFA must appear in the grounded answer.
    for name in ("carlos", "michael brown", "alex johnson"):
        assert name in answer, f"expected {name!r} in answer: {result['answer']}"
    # And it must NOT name an MFA-enabled user.
    assert "jane doe" not in answer


def test_ask_slack_blast_radius(store):
    result = answer_question("How many users use Slack?", store)
    assert "6" in (result["answer"] or "") or (result["rows"] and
           any("6" in str(v) for row in result["rows"] for v in row.values()))

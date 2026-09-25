import json
from pathlib import Path

import pytest


CORPUS = json.loads((Path(__file__).parent / 'fixtures' / 'classification_evaluation.json').read_text())


@pytest.mark.parametrize('case', CORPUS, ids=lambda case: case['id'])
def test_deterministic_classification_evaluation_corpus(case):
    """Broad routing and uncertainty contract; not a claim of forecast correctness."""
    from app.monitoring.classification import DeterministicEvaluationClassifier

    relevance, materiality = DeterministicEvaluationClassifier(case['result']).classify_both(case['question'], case['finding'])
    assert 0 <= relevance.score <= 1 and 0 <= relevance.confidence <= 1
    assert 0 <= materiality.score <= 1 and 0 <= materiality.confidence <= 1
    assert len(relevance.reason) <= 500 and len(materiality.reason) <= 500
    assert (relevance.relevance_class, materiality.materiality_class) == tuple(case['expected_route'])
    if case['id'] == 'malicious-prompt-injection':
        assert materiality.materiality_class == 'irrelevant'
    if case['id'] == 'ambiguous-case':
        assert relevance.relevance_class == 'uncertain'

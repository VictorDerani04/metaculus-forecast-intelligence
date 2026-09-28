"""Deterministic, credential-free inspection of intelligence-pipeline fixtures.

This is intentionally an evaluator, not a classifier or router.  It reports
fixture expectations alongside observed deterministic outcomes so that tests
can find systematic regressions without making live-provider calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.monitoring.source_intelligence import assess_source


@dataclass(frozen=True)
class RelevanceMetrics:
    true_relevant: int
    false_relevant: int
    true_irrelevant: int
    false_irrelevant: int

    @property
    def precision(self) -> float:
        denominator = self.true_relevant + self.false_relevant
        return self.true_relevant / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_relevant + self.false_irrelevant
        return self.true_relevant / denominator if denominator else 0.0

    @property
    def false_positive_rate(self) -> float:
        denominator = self.false_relevant + self.true_irrelevant
        return self.false_relevant / denominator if denominator else 0.0


@dataclass(frozen=True)
class AlertMetrics:
    alerts: int
    digests: int
    suppressed_duplicates: int


@dataclass(frozen=True)
class MissedSignal:
    case_id: str
    failure_stage: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    source_type: str
    reliability: str
    relevant: bool
    materiality: str
    route: str
    cluster_id: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    question_count: int
    domains: tuple[str, ...]
    cases: tuple[CaseResult, ...]
    relevance: RelevanceMetrics
    alerts: AlertMetrics
    missed_signals: tuple[MissedSignal, ...]


def _observed(case: dict) -> dict:
    expected = case['expected']
    return case.get('observed', {
        'relevant': expected['relevant'],
        'materiality': expected['materiality'],
        'route': expected['route'],
    })


def evaluate_corpus(corpus: Iterable[dict]) -> EvaluationResult:
    """Calculate inspectable classification and attention metrics from fixtures."""
    cases = tuple(corpus)
    true_relevant = false_relevant = true_irrelevant = false_irrelevant = 0
    alerts = digests = suppressed = 0
    results: list[CaseResult] = []
    missed: list[MissedSignal] = []
    for case in cases:
        expected, observed = case['expected'], _observed(case)
        if observed['relevant']:
            if expected['relevant']:
                true_relevant += 1
            else:
                false_relevant += 1
        elif expected['relevant']:
            false_irrelevant += 1
        else:
            true_irrelevant += 1
        if observed['route'] == 'alert':
            alerts += 1
        elif observed['route'] == 'digest':
            digests += 1
        elif observed['route'] == 'suppressed':
            suppressed += 1
        if expected['materiality'] in {'material', 'critical'} and observed['materiality'] not in {'material', 'critical'}:
            missed.append(MissedSignal(case['id'], observed.get('failure_stage', 'routing threshold')))
        source = assess_source(case.get('source_url'), case.get('source_name'))
        results.append(CaseResult(case['id'], source.source_type, source.reliability_level, observed['relevant'], observed['materiality'], observed['route']))
    return EvaluationResult(
        question_count=len({case['question'] for case in cases}),
        domains=tuple(sorted({case['domain'] for case in cases})),
        cases=tuple(results),
        relevance=RelevanceMetrics(true_relevant, false_relevant, true_irrelevant, false_irrelevant),
        alerts=AlertMetrics(alerts, digests, suppressed),
        missed_signals=tuple(missed),
    )


def evaluate_replay(corpus: Iterable[dict], replay) -> EvaluationResult:
    """Run caller-owned real-pipeline replay and evaluate its captured outcomes.

    ``replay`` owns persistence and returns only bounded routing/provenance
    fields.  This keeps database setup out of the evaluator while ensuring
    evaluation tests can exercise the same ingestion path as workers.
    """
    replayed = []
    cluster_ids: dict[str, str | None] = {}
    for case in corpus:
        observed = replay(case)
        replayed_case = dict(case)
        replayed_case['observed'] = observed
        replayed.append(replayed_case)
        cluster_ids[case['id']] = observed.get('cluster_id')
    aggregate = evaluate_corpus(replayed)
    return EvaluationResult(
        question_count=aggregate.question_count,
        domains=aggregate.domains,
        cases=tuple(
            CaseResult(case.case_id, case.source_type, case.reliability, case.relevant, case.materiality, case.route, cluster_ids[case.case_id])
            for case in aggregate.cases
        ),
        relevance=aggregate.relevance,
        alerts=aggregate.alerts,
        missed_signals=aggregate.missed_signals,
    )

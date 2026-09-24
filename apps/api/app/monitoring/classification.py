from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class RelevanceResult:
    relevance_class: str; score: float; reason: str
    def __post_init__(self):
        if self.relevance_class not in {'relevant', 'irrelevant', 'uncertain'} or not 0 <= self.score <= 1: raise ValueError('Invalid relevance result')

@dataclass(frozen=True)
class MaterialityResult:
    materiality_class: str; score: float; reason: str
    def __post_init__(self):
        if self.materiality_class not in {'irrelevant', 'digest', 'material', 'critical'} or not 0 <= self.score <= 1: raise ValueError('Invalid materiality result')

class RelevanceClassifier(Protocol):
    def classify(self, question, finding) -> RelevanceResult: ...
class MaterialityClassifier(Protocol):
    def classify(self, question, finding) -> MaterialityResult: ...

class FakeRelevanceClassifier:
    def __init__(self, result=RelevanceResult('relevant', .9, 'fixture')): self.result = result
    def classify(self, question, finding): return self.result
class FakeMaterialityClassifier:
    def __init__(self, result=MaterialityResult('material', .8, 'fixture')): self.result = result
    def classify(self, question, finding): return self.result

def validate_relevance(value) -> RelevanceResult:
    if not isinstance(value, RelevanceResult): raise ValueError('Malformed relevance classifier result')
    return value

def validate_materiality(value) -> MaterialityResult:
    if not isinstance(value, MaterialityResult): raise ValueError('Malformed materiality classifier result')
    return value

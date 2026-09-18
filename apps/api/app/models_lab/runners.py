from dataclasses import dataclass
from math import isfinite
from random import Random


@dataclass(frozen=True)
class ModelRunResult:
    probability: float
    distribution: dict | None = None
    trace: list[str] | None = None
    warnings: list[str] | None = None
    sensitivity_inputs: dict | None = None


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def _probability(value: object, label: str = 'Probability') -> float:
    probability = _finite_number(value, label)
    if not 0 <= probability <= 1:
        raise ValueError(f'{label} must be between 0 and 1')
    return probability


def run_model(spec: dict, seed: int | None = None) -> ModelRunResult:
    if not isinstance(spec, dict):
        raise ValueError('Model specification must be an object')
    family = spec.get('family')
    parameters = spec.get('parameters')
    if not isinstance(parameters, dict):
        raise ValueError('Model parameters must be an object')
    if family == 'bayesian_likelihood_ratio':
        prior = _probability(parameters.get('prior_probability'), 'Prior probability')
        likelihood_ratio = _finite_number(parameters.get('likelihood_ratio'), 'Likelihood ratio')
        if likelihood_ratio <= 0:
            raise ValueError('Likelihood ratio must be positive')
        if not 0 < prior < 1:
            raise ValueError('Prior probability must be between 0 and 1')
        odds = prior / (1 - prior) * likelihood_ratio
        return ModelRunResult(probability=odds / (1 + odds), trace=['bayesian_likelihood_ratio'])
    if family == 'weighted_driver':
        drivers = parameters.get('drivers')
        if not isinstance(drivers, list) or not drivers:
            raise ValueError('At least one driver is required')
        parsed_drivers = []
        for driver in drivers:
            if not isinstance(driver, dict):
                raise ValueError('Each driver must be an object')
            parsed_drivers.append((_probability(driver.get('probability')), _finite_number(driver.get('weight'), 'Driver weight')))
        total_weight = sum(weight for _, weight in parsed_drivers)
        if total_weight <= 0:
            raise ValueError('Driver weights must be positive')
        probability = sum(probability * weight for probability, weight in parsed_drivers) / total_weight
        if not 0 <= probability <= 1:
            raise ValueError('Driver probabilities must be between 0 and 1')
        return ModelRunResult(probability=float(probability), trace=['weighted_driver'])
    if family == 'scenario_tree':
        scenarios = parameters.get('scenarios')
        if not isinstance(scenarios, list) or not scenarios:
            raise ValueError('At least one scenario is required')
        parsed_scenarios = []
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                raise ValueError('Each scenario must be an object')
            parsed_scenarios.append((_finite_number(scenario.get('weight'), 'Scenario weight'), _probability(scenario.get('probability'))))
        total_weight = sum(weight for weight, _ in parsed_scenarios)
        if total_weight <= 0:
            raise ValueError('Scenario weights must be positive')
        probability = sum(weight * probability for weight, probability in parsed_scenarios) / total_weight
        return ModelRunResult(probability=probability, trace=['scenario_tree'])
    if family == 'seeded_monte_carlo':
        probability = _probability(parameters.get('probability'))
        trials = parameters.get('trials')
        if isinstance(trials, bool) or not isinstance(trials, int) or trials <= 0:
            raise ValueError('Trials must be a positive integer')
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise ValueError('Seed must be an integer')
        generator = Random(seed)
        successes = sum(generator.random() < probability for _ in range(trials))
        return ModelRunResult(probability=successes / trials, trace=['seeded_monte_carlo'], sensitivity_inputs={'seed': seed, 'trials': trials})
    if family == 'base_rate':
        return ModelRunResult(probability=_probability(parameters.get('probability'), 'Base-rate probability'), trace=['base_rate'])
    raise ValueError('Unsupported model family')

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import {
  ProbabilityHistoryChart,
  DistributionChart,
  SensitivityChart,
  EvidenceImpactChart,
  ScenarioChart,
  ModelMapChart,
} from '../components/charts';

afterEach(() => cleanup());

it('renders chart labels and provenance for analytical outputs', () => {
  const metadata = {
    model_version: 2,
    generated_at: '2026-09-17T12:00:00Z',
    why_this_chart: 'Compare approved model outputs.',
  };
  render(<>
    <ProbabilityHistoryChart data={{...metadata, human: [], model: [], crowd: []}} />
    <DistributionChart data={{...metadata, available: false, probability: null, values: [], unavailable_reason: 'Unavailable'}} />
    <SensitivityChart data={{...metadata, impacts: []}} />
    <EvidenceImpactChart data={{...metadata, evidence: []}} />
    <ScenarioChart data={{...metadata, scenarios: []}} />
    <ModelMapChart data={{...metadata, nodes: [], edges: []}} />
  </>);

  expect(screen.getAllByText('Why this chart?')).toHaveLength(6);
  expect(screen.getByText('Probability History')).toBeInTheDocument();
  expect(screen.getByText('Distribution unavailable')).toBeInTheDocument();
  expect(screen.getAllByText('Model version 2')).toHaveLength(6);
});

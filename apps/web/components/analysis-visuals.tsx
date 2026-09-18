"use client";
import { useEffect, useState } from 'react';
import { getAnalysis, listModels, type AnalysisData } from '../lib/api';
import {
  ProbabilityHistoryChart, DistributionChart, SensitivityChart,
  EvidenceImpactChart, ScenarioChart, ModelMapChart,
} from './charts';

export function AnalysisVisuals({questionId}: {questionId: string}) {
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [message, setMessage] = useState('Loading analysis...');
  useEffect(() => {
    let active = true;
    listModels(questionId).then(models => {
      const model = [...models].reverse().find(item => item.status === 'approved');
      if (!model) { if (active) setMessage('Approve a model to view analysis.'); return null; }
      return getAnalysis(questionId, model.id);
    }).then(value => {
      if (active && value) setAnalysis(value);
    }).catch(() => { if (active) setMessage('Analysis is unavailable.'); });
    return () => { active = false; };
  }, [questionId]);
  return <section aria-label="Analysis / Visuals">
    <h2>Analysis / Visuals</h2>
    {!analysis && <p role="status">{message}</p>}
    {analysis && <>
      <ProbabilityHistoryChart data={analysis.probability_history} />
      <DistributionChart data={analysis.distribution} />
      <SensitivityChart data={analysis.sensitivity} />
      <EvidenceImpactChart data={analysis.evidence_impact} />
      <ScenarioChart data={analysis.scenarios} />
      <ModelMapChart data={analysis.model_map} />
    </>}
  </section>;
}

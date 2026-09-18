"use client";
import { useEffect, useState } from 'react';
import { approveModel, createModel, listModels, runModel, type ModelFamily, type ModelSpec } from '../lib/api';
import { ModelCard } from './model-card';

export function ModelWorkspace({questionId, onRun}: {questionId: string; onRun: (probability: number) => void}) {
  const [models, setModels] = useState<ModelSpec[] | null>(null);
  const [error, setError] = useState('');
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [family, setFamily] = useState<ModelFamily>('base_rate');
  const [rationale, setRationale] = useState('');
  const [parameters, setParameters] = useState('{"probability": 0.5}');
  const [evidenceIds, setEvidenceIds] = useState('');
  useEffect(() => { let active = true; listModels(questionId).then(value => active && setModels(value)).catch(() => active && setError('Failed to load models')); return () => {active = false;}; }, [questionId]);
  async function approve(model: ModelSpec) {
    if (pendingId) return; setPendingId(model.id); setError('');
    try { const approved = await approveModel(model.id); setModels(current => current?.map(item => item.id === model.id ? approved : item) ?? null); }
    catch { setError('Failed to approve model'); } finally { setPendingId(null); }
  }
  async function run(model: ModelSpec) {
    if (pendingId) return; setPendingId(model.id); setError('');
    try { const result = await runModel(model.id); if (result.probability !== null) onRun(result.probability); }
    catch { setError('Failed to run model'); } finally { setPendingId(null); }
  }
  async function create(event: React.FormEvent) {
    event.preventDefault(); if (pendingId) return;
    let parsed: Record<string, unknown>;
    try { parsed = JSON.parse(parameters) as Record<string, unknown>; } catch { setError('Model parameters must be valid JSON'); return; }
    setPendingId('new'); setError('');
    try { const model = await createModel(questionId, {family, rationale, parameters: parsed, assumptions: [], evidence_ids: evidenceIds.split(',').map(id => id.trim()).filter(Boolean)}); setModels(current => [...(current ?? []), model]); setRationale(''); }
    catch { setError('Failed to create model'); } finally { setPendingId(null); }
  }
  return <section aria-label="Model Workspace"><h2>Model Workspace</h2>
    {error && <p role={models ? 'alert' : 'status'}>{error}</p>}
    {!models && !error && <p>Loading models...</p>}
    {models?.length === 0 && <p>No models yet. Create a draft to begin.</p>}
    {models?.map(model => <ModelCard key={model.id} model={model} pending={pendingId === model.id} onApprove={() => approve(model)} onRun={() => run(model)} />)}
    <form onSubmit={create}>
      <h3>Create draft model</h3>
      <label>Model family<select disabled={pendingId !== null} value={family} onChange={event => setFamily(event.target.value as ModelFamily)}>
        <option value="base_rate">Base rate</option><option value="bayesian_likelihood_ratio">Bayesian likelihood ratio</option><option value="weighted_driver">Weighted driver</option><option value="scenario_tree">Scenario tree</option><option value="seeded_monte_carlo">Seeded Monte Carlo</option>
      </select></label>
      <label>Model rationale<input required disabled={pendingId !== null} value={rationale} onChange={event => setRationale(event.target.value)} /></label>
      <label>Model parameters JSON<textarea required disabled={pendingId !== null} value={parameters} onChange={event => setParameters(event.target.value)} /></label>
      <label>Approved evidence IDs (comma separated)<input disabled={pendingId !== null} value={evidenceIds} onChange={event => setEvidenceIds(event.target.value)} /></label>
      <button disabled={pendingId !== null} type="submit">{pendingId === 'new' ? 'Creating...' : 'Create Draft Model'}</button>
    </form>
  </section>;
}

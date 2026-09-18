import type { ModelSpec } from '../lib/api';

export function ModelCard({model, pending, onApprove, onRun}: {model: ModelSpec; pending: boolean; onApprove: () => void; onRun: () => void}) {
  return <article>
    <h3>{model.family.replaceAll('_', ' ')} — v{model.version}</h3>
    <p>{model.status === 'draft' ? 'Draft model' : 'Approved model'}</p>
    <p>{model.rationale}</p>
    <p>Evidence: {model.evidence_ids.length ? model.evidence_ids.join(', ') : 'None'}</p>
    <p>Parameters: <code>{JSON.stringify(model.parameters)}</code></p>
    {model.status === 'draft'
      ? <button disabled={pending} type="button" onClick={onApprove}>{pending ? 'Approving...' : 'Approve Model'}</button>
      : <button disabled={pending} type="button" onClick={onRun}>{pending ? 'Running...' : 'Run Model'}</button>}
  </article>;
}

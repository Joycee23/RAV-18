import type { AnalysisRun, Evidence } from '../types';

export function WorkflowTrace({ runs, evidence }: { runs: AnalysisRun[]; evidence: Evidence[] }) {
  if (!runs.length) return <p className="muted">Chưa chạy phân tích.</p>;
  const evidenceIds = new Set(evidence.map((item) => item.id));
  return <div className="runs">{[...runs].reverse().map((run) => <article className="run-card" key={run.id}>
    <header><strong>{run.steps.some((step) => step.name.includes('gemini')) ? 'Gemini video analysis' : run.steps.some((step) => step.name === 'video_analysis') ? 'Video analysis unavailable' : 'Deterministic demo workflow'}</strong><span className={`status status-${run.status}`}>{run.status.replace(/_/g, ' ')}</span></header>
    <p className="muted">{new Date(run.started_at).toLocaleString('vi-VN')}</p>
    <ol className="steps">{run.steps.map((step, index) => <li key={`${step.name}-${index}`}><strong>{step.name.replace(/_/g, ' ')}</strong><span>{step.message}</span></li>)}</ol>
    {run.warning && <p className="warning">{run.warning}</p>}
    {run.findings.map((finding) => <section className="finding" key={finding.id}>
      <h4>{finding.title}</h4><p>{finding.description}</p><small>Confidence heuristic: {Math.round(finding.confidence * 100)}%</small>
      <div className="finding-evidence"><strong>Evidence</strong>{finding.evidence_ids.filter((id) => evidenceIds.has(id)).map((id) => {
        const item = evidence.find((entry) => entry.id === id)!;
        return <a key={id} href={`#evidence-${id}`}>{item.label} · {new Date(item.timestamp).toLocaleTimeString('vi-VN', { timeZone: 'UTC' })} UTC</a>;
      })}</div>
    </section>)}
    {run.reviews.map((review) => <p className="review-result" key={review.id}>Review: {review.decision} bởi {review.actor_name}{review.note ? ` — ${review.note}` : ''}</p>)}
  </article>)}</div>;
}

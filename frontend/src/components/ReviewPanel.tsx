import { useState } from 'react';
import type { AnalysisRun } from '../types';

type Props = { run: AnalysisRun | undefined; busy: boolean; onReview: (decision: 'approve' | 'reject', actorName: string, note: string) => void };

export function ReviewPanel({ run, busy, onReview }: Props) {
  const [actorName, setActorName] = useState('Reviewer demo');
  const [note, setNote] = useState('');
  if (!run || run.status !== 'awaiting_review') return <div className="review-box"><strong>Human review</strong><p className="muted">Chọn một workflow đang chờ duyệt để xem hành động.</p></div>;
  return <form className="review-box" onSubmit={(event) => event.preventDefault()}>
    <strong>Human review · demo role</strong><label>Tên reviewer<input value={actorName} onChange={(event) => setActorName(event.target.value)} maxLength={120} /></label>
    <label>Ghi chú<textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} rows={3} /></label>
    <div className="button-row"><button disabled={busy || !actorName.trim()} onClick={() => onReview('approve', actorName, note)}>Approve</button><button className="secondary" disabled={busy || !actorName.trim()} onClick={() => onReview('reject', actorName, note)}>Reject</button></div>
  </form>;
}

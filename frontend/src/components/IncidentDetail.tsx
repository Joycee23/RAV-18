import { useState } from 'react';
import type { IncidentDetail as IncidentDetailType } from '../types';
import { EvidenceCard } from './EvidenceCard';
import { Timeline } from './Timeline';
import { WorkflowTrace } from './WorkflowTrace';

export function IncidentDetail({ incident, onAnalyze, onUpload, busy }: { incident: IncidentDetailType; onAnalyze: () => void; onUpload: (file: File, recordedAt?: string) => void; busy: boolean }) {
  const hasClip = incident.evidence.some((item) => item.evidence_type === 'video_clip');
  const [recordedAt, setRecordedAt] = useState('');
  return <main className="detail">
    <div className="detail-heading"><div><span className="eyebrow">INCIDENT · {incident.vehicle_id}</span><h2>{incident.title}</h2><p>{incident.summary}</p></div><div><label>Thời gian ghi clip (để trống = thời điểm sự cố)<input type="datetime-local" value={recordedAt} disabled={busy} onChange={(event) => setRecordedAt(event.target.value)} /></label> <label className="button">Tải video<input type="file" accept="video/mp4,video/quicktime,video/webm" disabled={busy} hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file, recordedAt || undefined); event.target.value = ''; }} /></label> <button onClick={onAnalyze} disabled={busy}>{busy ? 'Đang chạy…' : hasClip ? 'Phân tích video' : 'Chạy phân tích demo'}</button></div></div>
    <div className="notice"><strong>{hasClip ? 'REAL VIDEO' : 'SIMULATED DATA'}</strong><span>{hasClip ? 'Clip riêng tư đã tải lên; phân tích Gemini tùy chọn, cần cấu hình GOOGLE_API_KEY.' : 'Workflow deterministic; chưa có clip video thật.'}</span></div>
    <section className="panel"><h3>Event timeline</h3><Timeline events={incident.events} /></section>
    <section className="panel"><h3>Evidence</h3><EvidenceCard evidence={incident.evidence} incidentId={incident.id} /></section>
    <section className="panel"><h3>Analysis workflow & findings</h3><WorkflowTrace runs={incident.runs} evidence={incident.evidence} /></section>
  </main>;
}

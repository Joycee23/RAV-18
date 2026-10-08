import type { Evidence } from '../types';
import { useState } from 'react';
import { getMediaUrl } from '../api';

export function EvidenceCard({ evidence, incidentId }: { evidence: Evidence[]; incidentId: string }) {
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({});
  const [mediaError, setMediaError] = useState<string | null>(null);
  if (!evidence.length) return <p className="muted">Chưa có evidence. Không thể suy luận finding nếu thiếu bằng chứng.</p>;
  return <>{mediaError && <p className="warning" role="alert">{mediaError}</p>}<ul className="evidence-list">{evidence.map((item) => <li key={item.id} id={`evidence-${item.id}`}>
    <span className="tag">{item.evidence_type === 'log' ? 'LOG' : item.evidence_type === 'video_clip' ? 'PRIVATE VIDEO' : 'METADATA ONLY'}{item.evidence_type !== 'video_clip' ? ' · SIMULATED' : ''}</span>
    <strong>{item.label}</strong><time>{new Date(item.timestamp).toLocaleString('vi-VN', { timeZone: 'UTC' })} UTC</time>
    <p>{item.description}</p>{item.evidence_type === 'video_clip' && (videoUrls[item.id] ? <video controls preload="none" src={videoUrls[item.id]} /> : <button onClick={async () => { try { setMediaError(null); const result = await getMediaUrl(incidentId, item.id); setVideoUrls((current) => ({ ...current, [item.id]: result.url })); } catch (cause) { setMediaError(cause instanceof Error ? cause.message : 'Không mở được video.'); } }}>Mở video riêng tư</button>)}<code>{item.id}</code>
  </li>)}</ul></>;
}

import type { IncidentSummary } from '../types';

type Props = { incidents: IncidentSummary[]; selectedId: string | null; onSelect: (id: string) => void };
const severityLabel: Record<string, string> = { high: 'Cao', medium: 'Vừa', low: 'Thấp' };

export function IncidentList({ incidents, selectedId, onSelect }: Props) {
  if (!incidents.length) return <div className="empty-state">Không có sự cố phù hợp.</div>;
  return <nav className="incident-list" aria-label="Danh sách sự cố">
    {incidents.map((incident) => <button key={incident.id} className={`incident-item ${selectedId === incident.id ? 'selected' : ''}`} onClick={() => onSelect(incident.id)}>
      <span className={`severity severity-${incident.severity}`}>{severityLabel[incident.severity] ?? incident.severity}</span>
      <strong>{incident.title}</strong><span className="muted">{incident.vehicle_id} · {new Date(incident.occurred_at).toLocaleString('vi-VN')}</span>
      <span className="muted clamp">{incident.summary}</span>
    </button>)}
  </nav>;
}

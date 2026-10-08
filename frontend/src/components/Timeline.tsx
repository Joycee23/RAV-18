import type { IncidentEvent } from '../types';

export function Timeline({ events }: { events: IncidentEvent[] }) {
  if (!events.length) return <p className="muted">Không có log sự kiện.</p>;
  return <ol className="timeline">{events.map((event) => <li key={event.id}>
    <time>{new Date(event.timestamp).toLocaleString('vi-VN', { timeZone: 'UTC' })} UTC</time>
    <strong>{event.event_type.replace(/_/g, ' ')}</strong><span>{event.message}</span><small>{event.source} · SIMULATED</small>
  </li>)}</ol>;
}

import { useCallback, useEffect, useState } from 'react';
import { analyzeIncident, getIncident, listIncidents, reviewAnalysis, uploadIncidentMedia } from './api';
import { IncidentDetail } from './components/IncidentDetail';
import { IncidentList } from './components/IncidentList';
import { ReviewPanel } from './components/ReviewPanel';
import type { AnalysisRun, IncidentDetail as IncidentDetailType, IncidentSummary } from './types';

function initialId(): string | null { return new URLSearchParams(window.location.search).get('incident'); }

export default function App() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialId);
  const [detail, setDetail] = useState<IncidentDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (id: string | null = selectedId) => {
    setError(null);
    try {
      const list = await listIncidents();
      setIncidents(list.items);
      const chosen = id && list.items.some((item) => item.id === id) ? id : list.items[0]?.id ?? null;
      setSelectedId(chosen);
      if (chosen) {
        const loaded = await getIncident(chosen);
        setDetail(loaded);
        const url = new URL(window.location.href);
        url.searchParams.set('incident', chosen);
        window.history.replaceState({}, '', url);
      } else setDetail(null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không tải được dữ liệu.'); }
    finally { setLoading(false); }
  }, [selectedId]);

  useEffect(() => { void refresh(initialId()); }, []);
  const selectIncident = (id: string) => { setSelectedId(id); void refresh(id); };

  const runAnalysis = async () => {
    if (!selectedId) return;
    setBusy(true); setError(null);
    try { await analyzeIncident(selectedId); await refresh(selectedId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Phân tích thất bại.'); }
    finally { setBusy(false); }
  };

  const uploadMedia = async (file: File, recordedAt?: string) => {
    if (!selectedId) return;
    setBusy(true); setError(null);
    try { await uploadIncidentMedia(selectedId, file, recordedAt ? new Date(recordedAt).toISOString() : undefined); await refresh(selectedId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Không tải được video.'); }
    finally { setBusy(false); }
  };

  const submitReview = async (run: AnalysisRun, decision: 'approve' | 'reject', actorName: string, note: string) => {
    if (!selectedId) return;
    setBusy(true); setError(null);
    try { await reviewAnalysis(selectedId, run.id, decision, actorName, note); await refresh(selectedId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Không lưu được review.'); }
    finally { setBusy(false); }
  };

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="/">Incident<span>Lens</span></a><div><span className="top-label">RAV-18 · INCIDENT REVIEW</span><span className="demo-pill">DEMO</span></div></header>
    <div className="workspace"><aside className="sidebar"><div className="sidebar-heading"><div><span className="eyebrow">OPERATIONS</span><h1>Incidents</h1></div><span className="count">{incidents.length}</span></div>
      {loading ? <p className="muted pad">Đang tải sự cố…</p> : <IncidentList incidents={incidents} selectedId={selectedId} onSelect={selectIncident} />}
    </aside><div className="content-column">
      {error && <div className="error-banner" role="alert"><span>{error}</span><button className="icon-button" onClick={() => void refresh()}>Thử lại</button></div>}
      {loading ? <div className="loading">Đang kết nối IncidentLens…</div> : detail ? <><IncidentDetail incident={detail} onAnalyze={() => void runAnalysis()} onUpload={uploadMedia} busy={busy} /><aside className="review-dock"><ReviewPanel run={[...detail.runs].reverse().find((run) => run.status === 'awaiting_review')} busy={busy} onReview={(decision, name, note) => {
        const run = [...detail.runs].reverse().find((item) => item.status === 'awaiting_review');
        if (run) void submitReview(run, decision, name, note);
      }} /></aside></> : <div className="empty-main">{error ? 'Không tải được dashboard.' : 'Chưa có sự cố.'}</div>}
    </div></div>
  </div>;
}

import type { AnalysisRun, Evidence, IncidentDetail, IncidentList, ReviewAction } from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers: init?.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init?.headers } });
  } catch {
    throw new Error('Không kết nối được API. Hãy kiểm tra backend và cấu hình mạng.');
  }
  if (!response.ok) {
    let message = `API trả lỗi (${response.status}).`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch { /* Keep the safe fallback message. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const listIncidents = () => request<IncidentList>('/api/incidents');
export const getIncident = (id: string) => request<IncidentDetail>(`/api/incidents/${id}`);
export const analyzeIncident = (id: string) => request<AnalysisRun>(`/api/incidents/${id}/analyze`, { method: 'POST' });
export const uploadIncidentMedia = (id: string, file: File, recordedAt?: string) => { const body = new FormData(); body.append('file', file); if (recordedAt) body.append('recorded_at', recordedAt); return request<Evidence>(`/api/incidents/${id}/media`, { method: 'POST', body }); };
export const getMediaUrl = (incidentId: string, evidenceId: string) => request<{url: string; expires_at: string}>(`/api/incidents/${incidentId}/media/${evidenceId}/url`);
export const reviewAnalysis = (incidentId: string, runId: string, decision: 'approve' | 'reject', actorName: string, note: string) =>
  request<ReviewAction>(`/api/incidents/${incidentId}/actions/${runId}/review`, {
    method: 'POST', body: JSON.stringify({ decision, actor_role: 'reviewer', actor_name: actorName, note: note || null }),
  });

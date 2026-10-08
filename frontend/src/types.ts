export type IncidentSummary = {
  id: string; title: string; severity: string; status: string; occurred_at: string;
  vehicle_id: string; summary: string;
};
export type IncidentEvent = {
  id: string; timestamp: string; source: string; event_type: string; message: string; details: Record<string, unknown>;
};
export type Evidence = {
  id: string; timestamp: string; evidence_type: string; label: string; description: string; metadata: Record<string, unknown>;
};
export type Finding = {
  id: string; title: string; description: string; confidence: number; evidence_ids: string[]; timestamp: string;
};
export type WorkflowStep = {
  name: string; status: string; started_at: string; finished_at: string; message: string;
};
export type ReviewAction = {
  id: string; decision: string; actor_role: string; actor_name: string; note: string | null; created_at: string;
};
export type AnalysisRun = {
  id: string; incident_id: string; status: string; steps: WorkflowStep[]; warning: string | null;
  started_at: string; finished_at: string | null; findings: Finding[]; reviews: ReviewAction[];
};
export type IncidentDetail = IncidentSummary & {
  metadata: Record<string, unknown>; events: IncidentEvent[]; evidence: Evidence[]; runs: AnalysisRun[];
};
export type IncidentList = { items: IncidentSummary[] };

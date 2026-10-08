import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';
import { getIncident, listIncidents } from './api';
import type { IncidentDetail, IncidentSummary } from './types';

vi.mock('./api', () => ({
  analyzeIncident: vi.fn(),
  getIncident: vi.fn(),
  listIncidents: vi.fn(),
  reviewAnalysis: vi.fn(),
}));

const summary: IncidentSummary = {
  id: 'incident-1',
  title: 'Unexpected hard braking',
  severity: 'high',
  status: 'open',
  occurred_at: '2026-01-01T12:00:00Z',
  vehicle_id: 'demo-01',
  summary: 'Vehicle braked suddenly near an intersection.',
};

const detail: IncidentDetail = {
  ...summary,
  metadata: {},
  events: [],
  evidence: [],
  runs: [],
};

const mockedListIncidents = vi.mocked(listIncidents);
const mockedGetIncident = vi.mocked(getIncident);

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
  });

  it('shows an incident after the API loads successfully', async () => {
    mockedListIncidents.mockResolvedValue({ items: [summary] });
    mockedGetIncident.mockResolvedValue(detail);

    render(<App />);

    expect(await screen.findByRole('heading', { name: summary.title })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Danh sách sự cố' })).toBeInTheDocument();
    expect(mockedGetIncident).toHaveBeenCalledWith(summary.id);
  });

  it('shows the empty state when there are no incidents', async () => {
    mockedListIncidents.mockResolvedValue({ items: [] });

    render(<App />);

    expect(await screen.findByText('Chưa có sự cố.')).toBeInTheDocument();
    expect(screen.getByText('Không có sự cố phù hợp.')).toBeInTheDocument();
    expect(mockedGetIncident).not.toHaveBeenCalled();
  });

  it('shows an accessible alert when loading incidents fails', async () => {
    mockedListIncidents.mockRejectedValue(new Error('API unavailable'));

    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent('API unavailable');
    expect(screen.getByText('Không tải được dashboard.')).toBeInTheDocument();
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { IncidentDetail as IncidentDetailType } from '../types';
import { IncidentDetail } from './IncidentDetail';
import { WorkflowTrace } from './WorkflowTrace';
import { getMediaUrl } from '../api';

vi.mock('../api', () => ({ getMediaUrl: vi.fn() }));

const incident: IncidentDetailType = {
  id: 'incident-1', title: 'Hard braking', severity: 'high', status: 'open',
  occurred_at: '2026-01-01T12:00:00Z', vehicle_id: 'car-1', summary: 'Test incident',
  metadata: {}, events: [], runs: [], evidence: [{
    id: 'video-1', timestamp: '2026-01-01T12:00:00Z', evidence_type: 'video_clip',
    label: 'Uploaded clip', description: 'Private uploaded video', metadata: { source: 'user_upload' },
  }],
};

describe('IncidentDetail video controls', () => {
  beforeEach(() => vi.clearAllMocks());

  it('offers upload and video analysis and identifies real video status', () => {
    render(<IncidentDetail incident={incident} onAnalyze={vi.fn()} onUpload={vi.fn()} busy={false} />);
    expect(screen.getByText('Tải video')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Phân tích video' })).toBeInTheDocument();
    expect(screen.getByText('REAL VIDEO')).toBeInTheDocument();
    expect(screen.getByText('PRIVATE VIDEO')).toBeInTheDocument();
    expect(screen.queryByText(/PRIVATE VIDEO · SIMULATED/)).not.toBeInTheDocument();
  });

  it('uploads a selected clip and disables controls while busy', () => {
    const onUpload = vi.fn();
    const file = new File(['video'], 'sample.mp4', { type: 'video/mp4' });
    render(<IncidentDetail incident={incident} onAnalyze={vi.fn()} onUpload={onUpload} busy />);
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledWith(file, undefined);
    expect(screen.getByRole('button', { name: 'Đang chạy…' })).toBeDisabled();
  });

  it('passes an optional recording time with the selected video', () => {
    const onUpload = vi.fn();
    const file = new File(['video'], 'sample.mp4', { type: 'video/mp4' });
    render(<IncidentDetail incident={incident} onAnalyze={vi.fn()} onUpload={onUpload} busy={false} />);
    const timeInput = screen.getByLabelText(/Thời gian ghi clip/);
    fireEvent.change(timeInput, { target: { value: '2026-10-08T20:30' } });
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledWith(file, '2026-10-08T20:30');
  });

  it('loads a private signed URL and plays uploaded video', async () => {
    vi.mocked(getMediaUrl).mockResolvedValue({ url: 'https://private.example/signed', expires_at: '2026-01-01T12:05:00Z' });
    render(<IncidentDetail incident={incident} onAnalyze={vi.fn()} onUpload={vi.fn()} busy={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Mở video riêng tư' }));
    await vi.waitFor(() => expect(document.querySelector('video')).toBeInTheDocument());
    const player = document.querySelector('video')!;
    expect(player).toHaveAttribute('src', 'https://private.example/signed');
    expect(getMediaUrl).toHaveBeenCalledWith('incident-1', 'video-1');
  });

  it('shows playback URL errors to the operator', async () => {
    vi.mocked(getMediaUrl).mockRejectedValue(new Error('Private storage unavailable'));
    render(<IncidentDetail incident={incident} onAnalyze={vi.fn()} onUpload={vi.fn()} busy={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Mở video riêng tư' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Private storage unavailable');
  });

  it('distinguishes provider-unavailable from failed Gemini status and shows warning', () => {
    const run = (id: string, name: string, status: string, warning: string | null) => ({
      id, incident_id: incident.id, status, steps: [{ name, status, started_at: '2026-01-01T12:00:00Z',
        finished_at: '2026-01-01T12:00:01Z', message: 'Video was not analyzed.' }], warning,
      started_at: '2026-01-01T12:00:00Z', finished_at: '2026-01-01T12:00:01Z', findings: [], reviews: [],
    });
    render(<WorkflowTrace runs={[run('run-1', 'video_analysis', 'completed', 'Gemini key is missing'),
      run('run-2', 'gemini_video_analysis', 'failed', 'Provider failed safely')]} evidence={incident.evidence} />);
    expect(screen.getByText('Video analysis unavailable')).toBeInTheDocument();
    expect(screen.getByText('Gemini video analysis')).toBeInTheDocument();
    expect(screen.getByText('Provider failed safely')).toBeInTheDocument();
  });
});

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Timeline } from './Timeline';
import { WorkflowTrace } from './WorkflowTrace';
import type { AnalysisRun, IncidentEvent } from '../types';

const event = (event_type: string): IncidentEvent => ({
  id: 'event-1',
  timestamp: '2026-01-01T12:00:00Z',
  source: 'test',
  event_type,
  message: 'Test event',
  details: {},
});

const run = (status: string, stepName: string): AnalysisRun => ({
  id: 'run-1',
  incident_id: 'incident-1',
  status,
  steps: [{
    name: stepName,
    status: 'completed',
    started_at: '2026-01-01T12:00:00Z',
    finished_at: '2026-01-01T12:00:01Z',
    message: 'Step message',
  }],
  warning: null,
  started_at: '2026-01-01T12:00:00Z',
  finished_at: '2026-01-01T12:00:01Z',
  findings: [],
  reviews: [],
});

describe('display formatting for underscore-separated labels', () => {
  it('keeps labels without underscores unchanged', () => {
    const { container } = render(<Timeline events={[event('hardbrake')]} />);
    expect(container.querySelector('strong')).toHaveTextContent('hardbrake');
  });

  it('replaces every underscore in an event label', () => {
    const { container } = render(<Timeline events={[event('vehicle_hard_brake')]} />);
    expect(container.querySelector('strong')).toHaveTextContent('vehicle hard brake');
  });

  it('renders an empty event label as an empty string', () => {
    const { container } = render(<Timeline events={[event('')]} />);
    expect(container.querySelector('strong')).toBeEmptyDOMElement();
  });

  it('formats workflow status and step names with multiple underscores', () => {
    render(<WorkflowTrace runs={[run('awaiting_human_review', 'sample_video_frames')]} evidence={[]} />);
    expect(screen.getByText('awaiting human review')).toBeInTheDocument();
    expect(screen.getByText('sample video frames')).toBeInTheDocument();
  });

  it('renders empty workflow status and step names as empty strings', () => {
    const { container } = render(<WorkflowTrace runs={[run('', '')]} evidence={[]} />);
    expect(container.querySelector('.status')).toBeEmptyDOMElement();
    expect(container.querySelector('.steps li strong')).toBeEmptyDOMElement();
  });
});

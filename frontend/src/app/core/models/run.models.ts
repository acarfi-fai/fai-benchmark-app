export interface PrimaryMetric {
  name: string;
  metric: unknown;
}

export interface RunSummary {
  id: string;
  file: string;
  task?: string | null;
  task_id?: string | null;
  status?: string | null;
  model?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  primary_metric?: PrimaryMetric | null;
  sample_count?: number | null;
  tags?: string[] | null;
  metadata?: unknown;
  mtime?: number | null;
  size?: number | null;
  header_error?: string | null;
}

export interface RunsResponse {
  log_dir: string;
  runs: RunSummary[];
}

export interface RunDetailResponse {
  id: string;
  file: string;
  summary: RunSummary;
  log: unknown;
}

export interface SamplePreview {
  id: unknown;
  epoch?: number | null;
  uuid?: string | null;
  input?: unknown;
  target?: unknown;
  completion?: string | null;
  scores?: unknown;
  metadata?: unknown;
  error?: unknown;
  attachments?: Record<string, string> | null;
}

export interface SamplesResponse {
  id: string;
  file: string;
  offset: number;
  limit: number;
  count: number;
  total_seen: number;
  samples: SamplePreview[];
}

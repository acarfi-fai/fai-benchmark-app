import { CommonModule } from '@angular/common';
import { Component, Input, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RunsService } from '../../core/services/runs.service';
import { RunDetailResponse, SamplePreview, SamplesResponse } from '../../core/models/run.models';
import { compactJson, formatDate, formatDuration, prettyJson } from '../../shared/format';

interface ScoreRow {
  scorer: string;
  metric: string;
  value: string;
}

interface SampleScoreRow {
  name: string;
  value: string;
}

@Component({
  selector: 'fai-run-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <a class="back-link" routerLink="/runs"><span aria-hidden="true">←</span> Runs</a>

    <div *ngIf="loading()" class="panel state">Loading run…</div>
    <div *ngIf="error()" class="panel state error-text">{{ error() }}</div>

    <ng-container *ngIf="detail() as detail">
      <section class="page-heading detail-heading">
        <div>
          <p class="eyebrow">Run detail</p>
          <h1>{{ detail.summary.task || detail.file }}</h1>
          <p class="muted mono">{{ detail.file }}</p>
        </div>
        <span class="status-cell" [ngClass]="statusClass(detail.summary.status)"><span class="status-icon">{{ statusIcon(detail.summary.status) }}</span>{{ detail.summary.status || 'unknown' }}</span>
      </section>

      <section class="summary-grid compact">
        <div class="metric-card"><span>Model</span><strong>{{ detail.summary.model || '—' }}</strong></div>
        <div class="metric-card"><span>Started</span><strong>{{ formatDate(detail.summary.started_at) }}</strong></div>
        <div class="metric-card"><span>Duration</span><strong>{{ formatDuration(detail.summary.duration_seconds) }}</strong></div>
      </section>

      <section class="panel">
        <h2>Scores</h2>
        <table class="scores-table" *ngIf="scoreRows(detail).length; else noScores">
          <thead>
            <tr><th>Scorer</th><th>Metric</th><th>Value</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let score of scoreRows(detail)">
              <td>{{ score.scorer }}</td>
              <td>{{ score.metric }}</td>
              <td class="mono">{{ score.value }}</td>
            </tr>
          </tbody>
        </table>
        <ng-template #noScores><div class="state compact-state">No scores available.</div></ng-template>
      </section>

      <section class="panel">
        <h2>Metadata</h2>
        <pre>{{ prettyJson(detail.summary.metadata) }}</pre>
        <details class="raw-json">
          <summary>View compact run JSON</summary>
          <pre>{{ prettyJson(detail.log) }}</pre>
        </details>
      </section>

      <section class="panel">
        <h2>Samples</h2>
        <div *ngIf="samplesLoading()" class="state">Loading samples…</div>
        <div *ngIf="samplesError()" class="error-text">{{ samplesError() }}</div>
        <div class="samples" *ngIf="samples() as sampleResponse">
          <div class="sample-list-header" [style.gridTemplateColumns]="sampleGridColumns(sampleResponse.samples)">
            <span>Sample</span>
            <span *ngFor="let scoreName of sampleScoreNames(sampleResponse.samples)">{{ scoreName }}</span>
          </div>
          <article class="sample-card" *ngFor="let sample of sampleResponse.samples; let i = index">
            <button class="sample-header" [style.gridTemplateColumns]="sampleGridColumns(sampleResponse.samples)" type="button" (click)="toggleSample(sample, sampleResponse.offset + i)">
              <span class="mono">{{ sample.id ?? i + 1 }}</span>
              <span class="mono" *ngFor="let scoreName of sampleScoreNames(sampleResponse.samples)">{{ sampleScoreValue(sample, scoreName) }}</span>
            </button>
            <div class="sample-grid" *ngIf="selectedSample() === sample">
              <section class="sample-pane input-pane">
                <h3>Input</h3>
                <div class="media-list" *ngIf="imageAttachments(sample).length">
                  <img *ngFor="let image of imageAttachments(sample)" [src]="image.src" [alt]="image.name" />
                </div>
                <div class="plain-text" *ngIf="inputText(sample.input)">{{ inputText(sample.input) }}</div>
              </section>

              <section class="sample-pane target-pane">
                <h3>Target</h3>
                <ng-container *ngIf="alignedRows(sample).length; else targetPlain">
                  <table class="structured-table">
                    <tbody>
                      <tr *ngFor="let row of alignedRows(sample)"><td>{{ row.key }}</td><td>{{ row.target }}</td></tr>
                    </tbody>
                  </table>
                </ng-container>
                <ng-template #targetPlain><div class="plain-text">{{ plainText(sample.target) }}</div></ng-template>
              </section>

              <section class="sample-pane output-pane">
                <h3>Model output</h3>
                <ng-container *ngIf="alignedRows(sample).length; else outputPlain">
                  <table class="structured-table output-table">
                    <tbody>
                      <tr *ngFor="let row of alignedRows(sample)"><td>{{ row.output }}</td></tr>
                    </tbody>
                  </table>
                </ng-container>
                <ng-template #outputPlain><div class="plain-text">{{ plainText(sample.completion) }}</div></ng-template>
              </section>

              <section class="sample-pane scores-pane">
                <h3>Scores</h3>
                <div class="sample-score simple" *ngFor="let score of sampleScoreRows(sample)">
                  <strong>{{ score.name }}</strong><span class="mono">{{ score.value }}</span>
                </div>
                <div class="state compact-state" *ngIf="!sampleScoreRows(sample).length">No scores available.</div>
              </section>
            </div>
          </article>
          <div class="pager" *ngIf="sampleResponse.count">
            <button class="button secondary" type="button" [disabled]="sampleResponse.offset === 0" (click)="previousPage()">Previous</button>
            <span>{{ sampleResponse.offset + 1 }}–{{ sampleResponse.offset + sampleResponse.count }} seen {{ sampleResponse.total_seen }}</span>
            <button class="button secondary" type="button" [disabled]="sampleResponse.count < sampleResponse.limit" (click)="nextPage()">Next</button>
          </div>
        </div>
      </section>
    </ng-container>
  `,
})
export class RunDetailComponent {
  private readonly runsService = inject(RunsService);

  readonly detail = signal<RunDetailResponse | null>(null);
  readonly samples = signal<SamplesResponse | null>(null);
  readonly selectedSample = signal<SamplePreview | null>(null);
  readonly loading = signal(true);
  readonly samplesLoading = signal(false);
  readonly error = signal<string | null>(null);
  readonly samplesError = signal<string | null>(null);

  private currentRunId = '';
  private offset = 0;
  private readonly limit = 50;

  @Input()
  set runId(value: string) {
    this.currentRunId = value;
    this.offset = 0;
    this.samples.set(null);
    this.loadRun();
  }

  loadRun(): void {
    this.loading.set(true);
    this.error.set(null);
    this.runsService.getRun(this.currentRunId).subscribe({
      next: (response) => {
        this.detail.set(response);
        this.loading.set(false);
        this.loadSamples();
      },
      error: (err: unknown) => {
        this.error.set(err instanceof Error ? err.message : 'Failed to load run.');
        this.loading.set(false);
      },
    });
  }

  private loadSamples(): void {
    this.samplesError.set(null);
    this.samplesLoading.set(true);
    this.selectedSample.set(null);

    this.runsService.getSamples(this.currentRunId, this.limit, this.offset).subscribe({
      next: (response) => {
        this.samples.set(response);
        this.samplesLoading.set(false);
      },
      error: (err: unknown) => {
        this.samplesError.set(err instanceof Error ? err.message : 'Failed to load samples.');
        this.samplesLoading.set(false);
      },
    });
  }

  previousPage(): void {
    this.offset = Math.max(0, this.offset - this.limit);
    this.loadSamples();
  }

  nextPage(): void {
    this.offset += this.limit;
    this.loadSamples();
  }

  toggleSample(sample: SamplePreview, absoluteOffset: number): void {
    if (this.selectedSample() === sample) {
      this.selectedSample.set(null);
      return;
    }

    if (sample.attachments) {
      this.selectedSample.set(sample);
      return;
    }

    this.runsService.getSample(this.currentRunId, absoluteOffset).subscribe({
      next: (response) => this.replaceAndSelectSample(sample, response.sample),
      error: () => this.selectedSample.set(sample),
    });
  }

  private replaceAndSelectSample(original: SamplePreview, expanded: SamplePreview): void {
    const response = this.samples();
    if (!response) {
      this.selectedSample.set(expanded);
      return;
    }

    const sameSample = (item: SamplePreview) => expanded.uuid
      ? item.uuid === expanded.uuid
      : item === original || (item.id === expanded.id && item.epoch === expanded.epoch);
    const updatedSamples = response.samples.map((item) => sameSample(item) ? { ...item, ...expanded } : item);
    const selected = updatedSamples.find((item) => sameSample(item)) || expanded;
    this.samples.set({ ...response, samples: updatedSamples });
    this.selectedSample.set(selected);
  }

  scoreRows(detail: RunDetailResponse): ScoreRow[] {
    const log = detail.log as { results?: { scores?: Array<{ name?: string; metrics?: Record<string, unknown> }> } };
    const scores = log.results?.scores || [];
    return scores.flatMap((score) => {
      const metrics = score.metrics || {};
      return Object.entries(metrics).map(([metric, value]) => ({
        scorer: score.name || '—',
        metric,
        value: this.metricValue(value),
      }));
    });
  }

  imageAttachments(sample: SamplePreview): Array<{ name: string; src: string }> {
    const attachments = sample.attachments || {};
    const images: Array<{ name: string; src: string }> = [];
    const seen = new Set<string>();

    const addImage = (name: string, value: unknown): void => {
      if (typeof value !== 'string') return;
      const src = value.startsWith('attachment://') ? attachments[value.slice('attachment://'.length)] : value;
      if (!this.isImageSource(src) || seen.has(src)) return;
      seen.add(src);
      images.push({ name, src });
    };

    for (const [name, value] of Object.entries(attachments)) addImage(name, value);

    let index = 1;
    const walk = (value: unknown): void => {
      if (typeof value === 'string') {
        addImage(`image-${index++}`, value);
        return;
      }
      if (Array.isArray(value)) {
        for (const item of value) walk(item);
        return;
      }
      if (this.isRecord(value)) {
        for (const item of Object.values(value)) walk(item);
      }
    };
    walk(sample.input);
    walk(sample.target);
    walk(sample.metadata);

    return images;
  }

  sampleScoreRows(sample: SamplePreview): SampleScoreRow[] {
    if (!sample.scores || typeof sample.scores !== 'object') return [];
    return Object.entries(sample.scores as Record<string, unknown>).map(([name, raw]) => ({
      name,
      value: this.scoreValue(raw),
    }));
  }

  sampleScoreNames(samples: SamplePreview[]): string[] {
    const names = new Set<string>();
    for (const sample of samples) {
      if (!sample.scores || typeof sample.scores !== 'object') continue;
      for (const name of Object.keys(sample.scores as Record<string, unknown>)) names.add(name);
    }
    return [...names];
  }

  sampleScoreValue(sample: SamplePreview, scoreName: string): string {
    if (!sample.scores || typeof sample.scores !== 'object') return '—';
    const score = (sample.scores as Record<string, unknown>)[scoreName];
    return score == null ? '—' : this.scoreValue(score);
  }

  sampleGridColumns(samples: SamplePreview[]): string {
    const scoreCount = this.sampleScoreNames(samples).length;
    return `minmax(180px, 1.5fr) repeat(${scoreCount}, minmax(90px, 0.7fr))`;
  }

  private scoreValue(raw: unknown): string {
    const score = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : null;
    return this.metricValue(score?.['value'] ?? raw);
  }

  alignedRows(sample: SamplePreview): Array<{ key: string; target: string; output: string }> {
    const target = this.parseJsonLike(sample.target);
    const output = this.parseJsonLike(sample.completion);
    if (!this.isRecord(target) || !this.isRecord(output)) return [];
    const keys = [...new Set([...Object.keys(target), ...Object.keys(output)])];
    return keys.map((key) => ({
      key,
      target: this.renderCell(target[key]),
      output: this.renderCell(output[key]),
    }));
  }

  plainText(value: unknown): string {
    if (value == null) return '—';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map((item) => this.plainText(item)).filter(Boolean).join('\n');
    if (typeof value === 'object') return this.extractText(value) || compactJson(value);
    return String(value);
  }

  inputText(value: unknown): string {
    if (value == null) return '';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map((item) => this.inputText(item)).filter(Boolean).join('\n');
    if (typeof value === 'object') return this.extractText(value);
    return String(value);
  }

  private parseJsonLike(value: unknown): unknown | null {
    if (typeof value !== 'string') return value && typeof value === 'object' ? value : null;
    const trimmed = value.trim();
    if (!trimmed || !['{', '['].includes(trimmed[0])) return null;
    try {
      return JSON.parse(trimmed);
    } catch {
      return null;
    }
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return !!value && typeof value === 'object' && !Array.isArray(value);
  }

  private renderCell(value: unknown): string {
    if (value == null) return '—';
    if (Array.isArray(value)) return value.map((item) => this.renderCell(item)).join('\n');
    if (this.isRecord(value)) return Object.entries(value).map(([key, item]) => `${key}: ${this.renderCell(item)}`).join('\n');
    return String(value);
  }

  private isImageSource(value: unknown): value is string {
    if (typeof value !== 'string') return false;
    if (value.startsWith('data:image/')) return true;
    if (!value.startsWith('http://') && !value.startsWith('https://')) return false;
    return /\.(png|jpe?g|gif|webp|bmp|svg)(\?|#|$)/i.test(value) || value.includes('.blob.core.windows.net/');
  }

  private extractText(value: unknown): string {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map((item) => this.extractText(item)).filter(Boolean).join('\n');
    if (!this.isRecord(value)) return '';
    const type = value['type'];
    if (type === 'text' && typeof value['text'] === 'string') return value['text'];
    if (typeof value['content'] === 'string') return value['content'];
    if (Array.isArray(value['content'])) return this.extractText(value['content']);
    return '';
  }

  metricValue(metric: unknown): string {
    if (typeof metric === 'number') return String(metric);
    if (metric && typeof metric === 'object' && 'value' in metric) {
      const value = (metric as { value: unknown }).value;
      return typeof value === 'number' ? String(value) : compactJson(value);
    }
    return compactJson(metric);
  }

  statusClass(status?: string | null): string {
    const normalized = (status || '').toLowerCase();
    if (normalized.includes('success')) return 'success';
    if (normalized.includes('error') || normalized.includes('fail')) return 'danger';
    return 'neutral';
  }

  statusIcon(status?: string | null): string {
    const normalized = (status || '').toLowerCase();
    if (normalized.includes('success')) return '✓';
    if (normalized.includes('error') || normalized.includes('fail')) return '×';
    return '•';
  }

  protected readonly formatDate = formatDate;
  protected readonly formatDuration = formatDuration;
  protected readonly prettyJson = prettyJson;
}

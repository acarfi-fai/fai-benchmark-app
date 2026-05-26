import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { RunsService } from '../../core/services/runs.service';
import { RunSummary } from '../../core/models/run.models';
import { compactJson, formatDate, formatDuration } from '../../shared/format';

@Component({
  selector: 'fai-runs-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="page-heading">
      <div>
        <p class="eyebrow">Benchmark logs</p>
        <h1>Runs</h1>
        <p class="muted">Inspect AI evaluation logs from Azure Blob Storage.</p>
        <p class="table-count">{{ filteredRuns().length }} of {{ runs().length }} runs</p>
      </div>
    </section>

    <div *ngIf="loading()" class="panel state">Loading runs…</div>
    <div *ngIf="error()" class="panel state error-text">{{ error() }}</div>

    <section class="table-panel" *ngIf="!loading() && !error()">
      <table>
        <thead>
          <tr>
            <th>
              <div class="column-head">
                <span>Status</span>
                <select class="column-filter" [ngModel]="statusFilter()" (ngModelChange)="statusFilter.set($event)" aria-label="Filter status">
                  <option value="">All</option>
                  <option *ngFor="let status of statuses()" [value]="status">{{ status }}</option>
                </select>
              </div>
            </th>
            <th>
              <div class="column-head">
                <span>Task</span>
                <input class="column-filter" type="search" [ngModel]="taskFilter()" (ngModelChange)="taskFilter.set($event)" placeholder="Filter" aria-label="Filter task" />
              </div>
            </th>
            <th>
              <div class="column-head">
                <span>Model</span>
                <input class="column-filter" type="search" [ngModel]="modelFilter()" (ngModelChange)="modelFilter.set($event)" placeholder="Filter" aria-label="Filter model" />
              </div>
            </th>
            <th>
              <div class="column-head">
                <span>Started</span>
                <input class="column-filter" type="search" [ngModel]="startedFilter()" (ngModelChange)="startedFilter.set($event)" placeholder="Filter" aria-label="Filter started" />
              </div>
            </th>
            <th>
              <div class="column-head">
                <span>Duration</span>
                <input class="column-filter" type="search" [ngModel]="durationFilter()" (ngModelChange)="durationFilter.set($event)" placeholder="Filter" aria-label="Filter duration" />
              </div>
            </th>
            <th>
              <div class="column-head">
                <span>Primary score</span>
                <input class="column-filter" type="search" [ngModel]="scoreFilter()" (ngModelChange)="scoreFilter.set($event)" placeholder="Filter" aria-label="Filter primary score" />
              </div>
            </th>
            <th>
              <div class="column-head">
                <span>Samples</span>
                <input class="column-filter" type="search" [ngModel]="samplesFilter()" (ngModelChange)="samplesFilter.set($event)" placeholder="Filter" aria-label="Filter samples" />
              </div>
            </th>
            <th>
              <div class="column-head">
                <span>Tags</span>
                <input class="column-filter" type="search" [ngModel]="tagsFilter()" (ngModelChange)="tagsFilter.set($event)" placeholder="Filter" aria-label="Filter tags" />
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let run of filteredRuns()" [routerLink]="['/runs', run.id]">
            <td><span class="status-cell" [ngClass]="statusClass(run.status)"><span class="status-icon">{{ statusIcon(run.status) }}</span>{{ run.status || 'unknown' }}</span></td>
            <td>
              <strong>{{ run.task || '—' }}</strong>
              <div class="subtle mono">{{ run.task_id || '' }}</div>
              <div *ngIf="run.header_error" class="error-text small">{{ run.header_error }}</div>
            </td>
            <td>{{ run.model || '—' }}</td>
            <td>{{ formatDate(run.started_at || run.mtime) }}</td>
            <td>{{ formatDuration(run.duration_seconds) }}</td>
            <td class="mono">{{ metric(run) }}</td>
            <td>{{ run.sample_count ?? '—' }}</td>
            <td>{{ (run.tags || []).join(', ') || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <div *ngIf="filteredRuns().length === 0" class="state">No runs match the current filters.</div>
    </section>
  `,
})
export class RunsListComponent {
  private readonly runsService = inject(RunsService);

  readonly runs = signal<RunSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly statusFilter = signal('');
  readonly taskFilter = signal('');
  readonly modelFilter = signal('');
  readonly startedFilter = signal('');
  readonly durationFilter = signal('');
  readonly scoreFilter = signal('');
  readonly samplesFilter = signal('');
  readonly tagsFilter = signal('');

  readonly statuses = computed(() =>
    [...new Set(this.runs().map((run) => run.status).filter((status): status is string => !!status))].sort(),
  );

  readonly filteredRuns = computed(() => {
    const status = this.statusFilter();
    const task = this.normalized(this.taskFilter());
    const model = this.normalized(this.modelFilter());
    const started = this.normalized(this.startedFilter());
    const duration = this.normalized(this.durationFilter());
    const score = this.normalized(this.scoreFilter());
    const samples = this.normalized(this.samplesFilter());
    const tags = this.normalized(this.tagsFilter());

    return this.runs().filter((run) => {
      if (status && run.status !== status) return false;
      if (task && !this.includes([run.task, run.task_id], task)) return false;
      if (model && !this.includes([run.model], model)) return false;
      if (started && !this.includes([formatDate(run.started_at || run.mtime)], started)) return false;
      if (duration && !this.includes([formatDuration(run.duration_seconds)], duration)) return false;
      if (score && !this.includes([this.metric(run)], score)) return false;
      if (samples && !this.includes([run.sample_count ?? '—'], samples)) return false;
      if (tags && !this.includes([(run.tags || []).join(', ')], tags)) return false;
      return true;
    });
  });

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.runsService.listRuns().subscribe({
      next: (response) => {
        this.runs.set(response.runs);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(err instanceof Error ? err.message : 'Failed to load runs.');
        this.loading.set(false);
      },
    });
  }

  private normalized(value: string): string {
    return value.trim().toLowerCase();
  }

  private includes(values: unknown[], filter: string): boolean {
    return values.some((value) => String(value ?? '').toLowerCase().includes(filter));
  }

  metric(run: RunSummary): string {
    if (!run.primary_metric) return '—';
    return this.metricValue(run.primary_metric.metric);
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
}

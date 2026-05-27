import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { RunDetailResponse, RunsResponse, SampleResponse, SamplesResponse } from '../models/run.models';

@Injectable({ providedIn: 'root' })
export class RunsService {
  private readonly http = inject(HttpClient);

  listRuns(limit = 200): Observable<RunsResponse> {
    return this.http.get<RunsResponse>('/api/runs', { params: { limit } });
  }

  getRun(runId: string): Observable<RunDetailResponse> {
    return this.http.get<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}`);
  }

  getSamples(runId: string, limit = 100, offset = 0): Observable<SamplesResponse> {
    return this.http.get<SamplesResponse>(`/api/runs/${encodeURIComponent(runId)}/samples`, {
      params: { limit, offset },
    });
  }

  getSample(runId: string, offset: number): Observable<SampleResponse> {
    return this.http.get<SampleResponse>(`/api/runs/${encodeURIComponent(runId)}/samples/${offset}`);
  }
}

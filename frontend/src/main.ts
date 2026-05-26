import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter, Routes, withComponentInputBinding } from '@angular/router';
import { AppComponent } from './app/app.component';
import { RunsListComponent } from './app/features/runs/runs-list.component';
import { RunDetailComponent } from './app/features/runs/run-detail.component';

const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'runs' },
  { path: 'runs', component: RunsListComponent },
  { path: 'runs/:runId', component: RunDetailComponent },
  { path: '**', redirectTo: 'runs' },
];

bootstrapApplication(AppComponent, {
  providers: [provideHttpClient(), provideRouter(routes, withComponentInputBinding())],
}).catch((err) => console.error(err));

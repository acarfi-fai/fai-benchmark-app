import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'fai-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <header class="app-header">
      <a class="brand" routerLink="/runs" aria-label="FusionAI Eval Console home">
        <img src="assets/brand/logo.png" alt="FusionAI" />
        <span>FusionAI Eval Console</span>
      </a>
    </header>
    <main class="app-main">
      <router-outlet />
    </main>
  `,
})
export class AppComponent {}

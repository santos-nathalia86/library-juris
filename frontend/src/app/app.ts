import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ThemeService } from './core/theme.service';
import { Icon, IconName } from './shared/icon';

interface NavItem {
  path: string;
  label: string;
  icon: IconName;
}

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
  template: `
    <header class="topbar">
      <button
        type="button" class="menu-button" (click)="menuOpen.set(!menuOpen())"
        [attr.aria-expanded]="menuOpen()" aria-controls="menu-lateral"
        [attr.aria-label]="menuOpen() ? 'Fechar menu' : 'Abrir menu'"
      >
        <app-icon [name]="menuOpen() ? 'close' : 'menu'" [size]="24" />
      </button>
      <a class="brand" routerLink="/inicio" (click)="menuOpen.set(false)">
        <img [src]="theme.theme() === 'dark' ? 'logo-dark.png' : 'logo.png'" alt="JurisFind" width="542" height="132" />
      </a>
      <span class="tagline">Sua pesquisa jurídica, mais simples.</span>
      <button
        type="button" class="theme-toggle" (click)="theme.toggle()"
        [attr.aria-label]="theme.theme() === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'"
      >
        <app-icon name="moon" [size]="17" [class.on]="theme.theme() === 'dark'" />
        <app-icon name="sun" [size]="17" [class.on]="theme.theme() === 'light'" />
      </button>
    </header>

    <div class="shell">
      @if (menuOpen()) {
        <div class="backdrop" (click)="menuOpen.set(false)"></div>
      }
      <aside class="sidebar" id="menu-lateral" [class.open]="menuOpen()">
        <nav aria-label="Seções">
          @for (item of nav; track item.path) {
            <a [routerLink]="item.path" routerLinkActive="active" (click)="menuOpen.set(false)">
              <app-icon [name]="item.icon" />
              <span>{{ item.label }}</span>
            </a>
          }
        </nav>
        <div class="tip">
          <strong><app-icon name="info" [size]="18" /> Dica</strong>
          <p>Use aspas para expressão exata. Só dados confirmados na ficha do livro entram na citação ABNT.</p>
        </div>
      </aside>
      <main class="page">
        <router-outlet />
      </main>
    </div>
  `,
  host: { '(document:keydown.escape)': 'menuOpen.set(false)' },
})
export class App {
  protected readonly theme = inject(ThemeService);
  /** Em telas estreitas a barra lateral vira uma gaveta aberta por este botão. */
  protected readonly menuOpen = signal(false);
  protected readonly nav: NavItem[] = [
    { path: '/inicio', label: 'Início', icon: 'home' },
    { path: '/jurisprudencia', label: 'Jurisprudência', icon: 'scale' },
    { path: '/legislacao', label: 'Legislação', icon: 'book' },
    { path: '/livros-online', label: 'Livros e Doutrina', icon: 'library' },
    // Meus Documentos desativado temporariamente.
    // { path: '/biblioteca', label: 'Meus Documentos', icon: 'file' },
    { path: '/citacoes', label: 'Citações', icon: 'quote' },
    { path: '/historico', label: 'Histórico', icon: 'clock' },
  ];
}

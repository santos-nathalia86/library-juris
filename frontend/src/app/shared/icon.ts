import { Component, computed, input } from '@angular/core';

/** Ícones de traço desenhados no próprio projeto (sem biblioteca externa). */
const ICONS = {
  home: ['M3 10.5 12 3l9 7.5', 'M5 9.5V21h14V9.5', 'M10 21v-6h4v6'],
  scale: ['M12 3v18', 'M7 21h10', 'M5 7h14', 'M5 7l-3 7a3 3 0 0 0 6 0L5 7z', 'M19 7l-3 7a3 3 0 0 0 6 0l-3-7z'],
  book: [
    'M2 4h7a3 3 0 0 1 3 3v13a2.5 2.5 0 0 0-2.5-2.5H2z',
    'M22 4h-7a3 3 0 0 0-3 3v13a2.5 2.5 0 0 1 2.5-2.5H22z',
  ],
  library: ['M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14z', 'M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5'],
  file: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', 'M14 2v6h6', 'M8 13h8', 'M8 17h6'],
  quote: ['M10 7H6a2 2 0 0 0-2 2v3h5v1a3 3 0 0 1-3 3', 'M20 7h-4a2 2 0 0 0-2 2v3h5v1a3 3 0 0 1-3 3'],
  clock: ['M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18z', 'M12 7v5l3 2'],
  search: ['M11 4a7 7 0 1 0 0 14a7 7 0 0 0 0-14z', 'M20 20l-3.9-3.9'],
  arrow: ['M5 12h14', 'M13 6l6 6-6 6'],
  chevron: ['M9 6l6 6-6 6'],
  upload: ['M12 16V4', 'M7 9l5-5 5 5', 'M4 17v3h16v-3'],
  info: ['M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18z', 'M12 11v5', 'M12 8h.01'],
  sun: [
    'M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8z', 'M12 2v2', 'M12 20v2', 'M2 12h2', 'M20 12h2', 'M4.9 4.9l1.4 1.4',
    'M17.7 17.7l1.4 1.4', 'M4.9 19.1l1.4-1.4', 'M17.7 6.3l1.4-1.4',
  ],
  moon: ['M20 14.5A8 8 0 0 1 9.5 4a7 7 0 1 0 10.5 10.5z'],
  landmark: ['M3 21h18', 'M4 10h16', 'M12 3l9 7H3z', 'M6 10v8', 'M10 10v8', 'M14 10v8', 'M18 10v8'],
  menu: ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  close: ['M6 6l12 12', 'M18 6L6 18'],
  grid: ['M4 4h6v6H4z', 'M14 4h6v6h-6z', 'M4 14h6v6H4z', 'M14 14h6v6h-6z'],
} as const;

export type IconName = keyof typeof ICONS;

@Component({
  selector: 'app-icon',
  template: `
    <svg
      [attr.width]="size()" [attr.height]="size()" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
    >
      @for (d of paths(); track d) {
        <path [attr.d]="d" />
      }
    </svg>
  `,
  styles: ':host { display: inline-flex; flex: none; }',
})
export class Icon {
  readonly name = input.required<IconName>();
  readonly size = input(22);
  protected readonly paths = computed(() => ICONS[this.name()]);
}

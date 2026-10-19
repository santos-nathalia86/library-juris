import { Component, input, signal } from '@angular/core';

@Component({
  selector: 'app-copy-button',
  template: `
    <button type="button" class="btn" [class.done]="state() === 'done'" (click)="copy()" [disabled]="!text()">
      {{ state() === 'done' ? 'Copiado' : state() === 'error' ? 'Não foi possível copiar' : label() }}
    </button>
  `,
})
export class CopyButton {
  readonly text = input.required<string>();
  readonly label = input('Copiar');
  protected readonly state = signal<'idle' | 'done' | 'error'>('idle');

  protected async copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.text());
      this.state.set('done');
    } catch {
      this.state.set(this.fallbackCopy() ? 'done' : 'error');
    }
    setTimeout(() => this.state.set('idle'), 2000);
  }

  /** Para navegadores que negam a Clipboard API fora de contexto seguro. */
  private fallbackCopy(): boolean {
    const area = document.createElement('textarea');
    area.value = this.text();
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try {
      return document.execCommand('copy');
    } catch {
      return false;
    } finally {
      area.remove();
    }
  }
}

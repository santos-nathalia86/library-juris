import { Component, computed, input } from '@angular/core';

import { FIELD_LABELS, Reference } from '../core/models';
import { CopyButton } from './copy-button';

@Component({
  selector: 'app-reference-view',
  imports: [CopyButton],
  template: `
    <div class="reference">
      <p class="reference-text">
        {{ reference().before }}<strong>{{ reference().emphasis }}</strong>{{ reference().after }}
      </p>
      @if (unconfirmed()) {
        <p class="note warn">
          Ficaram fora da referência por ainda não estarem confirmados: {{ unconfirmed() }}.
          Revise os dados do livro antes de citar.
        </p>
      }
      @if (missing()) {
        <p class="note">Informações faltantes na referência: {{ missing() }}.</p>
      }
      @if (showCopy()) {
        <app-copy-button [text]="reference().text" label="Copiar referência" />
      }
    </div>
  `,
})
export class ReferenceView {
  readonly reference = input.required<Reference>();
  readonly showCopy = input(true);

  protected readonly unconfirmed = computed(() => this.names(this.reference().unconfirmed));
  protected readonly missing = computed(() => this.names(this.reference().missing));

  private names(fields: Reference['missing']): string {
    return fields.map((f) => (f === 'isbn' ? 'ISBN' : FIELD_LABELS[f].toLowerCase())).join(', ');
  }
}

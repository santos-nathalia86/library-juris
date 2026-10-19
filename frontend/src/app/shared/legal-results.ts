import { Component, computed, input } from '@angular/core';
import { KeyValuePipe } from '@angular/common';

import { LegalSearchResponse } from '../core/models';
import { CopyButton } from './copy-button';

/** Resultados de fontes públicas (jurisprudência e legislação) e links para pesquisa manual. */
@Component({
  selector: 'app-legal-results',
  imports: [CopyButton, KeyValuePipe],
  template: `
    @let data = result();
    <section class="results" aria-live="polite">
      <p class="source-note"><strong>{{ data.source }}.</strong> {{ data.source_note }}</p>

      @if (data.error) {
        <p class="alert error">{{ data.error }} Nenhum resultado foi obtido; use os links abaixo para pesquisar no site.</p>
      } @else if (data.items.length === 0) {
        <p class="alert">Nenhum resultado para “{{ data.query }}” nesta fonte.</p>
      } @else {
        <p class="count">{{ countText() }}</p>
        @for (item of data.items; track $index) {
          <article class="card">
            <h3>{{ item.title }}</h3>
            @if (item.summary) {
              <p class="summary">{{ item.summary }}</p>
            }
            <dl class="meta">
              @for (detail of item.details | keyvalue: keepOrder; track detail.key) {
                <div><dt>{{ detail.key }}</dt><dd>{{ detail.value }}</dd></div>
              }
            </dl>
            <div class="actions">
              @if (item.summary) {
                <app-copy-button [text]="item.summary" [label]="copyLabel()" />
              }
              <app-copy-button [text]="item.title" label="Copiar identificação" />
              @if (item.url) {
                <a class="btn" [href]="item.url" target="_blank" rel="noopener noreferrer">Abrir na fonte oficial</a>
              }
            </div>
          </article>
        }
      }

      <h3 class="links-title">Pesquisa manual em outras fontes oficiais</h3>
      <ul class="links">
        @for (link of data.manual_links; track link.url) {
          <li>
            <a [href]="link.url" target="_blank" rel="noopener noreferrer">{{ link.name }}</a>
            <span>{{ link.note }}</span>
          </li>
        }
      </ul>
    </section>
  `,
})
export class LegalResults {
  readonly result = input.required<LegalSearchResponse>();
  readonly copyLabel = input('Copiar ementa');

  protected readonly keepOrder = () => 0;
  protected readonly countText = computed(() => {
    const { total, items } = this.result();
    const shown = total !== null && total > items.length ? `, exibindo ${items.length}` : '';
    return `${total ?? items.length} resultado(s)${shown}.`;
  });
}

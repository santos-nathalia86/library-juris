import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { ApiService, errorMessage } from '../core/api.service';
import { LegalSearchResponse } from '../core/models';
import { Icon } from '../shared/icon';
import { LegalResults } from '../shared/legal-results';

const COURTS: [string, string][] = [
  ['stj', 'STJ'], ['tst', 'TST'], ['tse', 'TSE'], ['stm', 'STM'],
  ['trf1', 'TRF1'], ['trf2', 'TRF2'], ['trf3', 'TRF3'], ['trf4', 'TRF4'], ['trf5', 'TRF5'], ['trf6', 'TRF6'],
  ['tjsp', 'TJSP'], ['tjrj', 'TJRJ'], ['tjmg', 'TJMG'], ['tjrs', 'TJRS'], ['tjpr', 'TJPR'], ['tjsc', 'TJSC'],
  ['tjba', 'TJBA'], ['tjpe', 'TJPE'], ['tjce', 'TJCE'], ['tjgo', 'TJGO'], ['tjdft', 'TJDFT'],
];

@Component({
  selector: 'app-jurisprudence-page',
  imports: [ReactiveFormsModule, LegalResults, Icon],
  template: `
    <header class="page-head">
      <span class="bubble"><app-icon name="scale" [size]="26" /></span>
      <div>
        <h1>Jurisprudência</h1>
        <p class="lead">
          Consulta direta às fontes oficiais que aceitam pesquisa automatizada. Para os tribunais que a bloqueiam, há o
          link de pesquisa no site oficial.
        </p>
      </div>
    </header>

    <form class="search-panel hero-search" [formGroup]="form" (ngSubmit)="search(1)">
      <div class="search-box">
        <app-icon name="search" />
        <input
          type="search" formControlName="q" autocomplete="off"
          [attr.aria-label]="isTst() ? 'Termos da pesquisa' : 'Assunto ou número do processo'"
          [placeholder]="isTst() ? 'Ex: adicional de insalubridade' : 'Ex: direito do consumidor, ou o número do processo'"
        />
        <button type="submit" class="btn primary" [disabled]="loading()">
          {{ loading() ? 'Consultando…' : 'Pesquisar' }} <app-icon name="arrow" [size]="18" />
        </button>
      </div>
      <div class="filters">
        <label class="filter">
          <app-icon name="grid" />
          <span>
            <small>Fonte</small>
            <select formControlName="fonte" (change)="fonteValue.set(form.controls.fonte.value)">
              <option value="tst">TST — acórdãos (ementas)</option>
              <option value="datajud">CNJ DataJud — processos</option>
            </select>
          </span>
        </label>
        @if (isTst()) {
          <label class="filter toggle">
            <input type="checkbox" formControlName="soEmenta" />
            <span>
              <small>Onde procurar</small>
              <b>Apenas na ementa</b>
            </span>
          </label>
        } @else {
          <label class="filter">
            <app-icon name="landmark" />
            <span>
              <small>Tribunal</small>
              <select formControlName="tribunal">
                @for (court of courts; track court[0]) {
                  <option [value]="court[0]">{{ court[1] }}</option>
                }
              </select>
            </span>
          </label>
        }
      </div>
      @if (form.controls.q.touched && form.controls.q.invalid) {
        <p class="field-error">Informe ao menos três caracteres.</p>
      }
      @if (loading() && !isTst()) {
        <p class="note">O DataJud costuma levar cerca de 20 segundos para responder.</p>
      }
    </form>

    @if (error()) {
      <p class="alert error">{{ error() }}</p>
    }

    @if (result(); as data) {
      <app-legal-results [result]="data" [copyLabel]="isTst() ? 'Copiar ementa' : 'Copiar assuntos'" />
      @if (!data.error && data.items.length > 0) {
        <div class="pager">
          <button type="button" class="btn" (click)="search(page() - 1)" [disabled]="page() === 1 || loading()">Anterior</button>
          <span>Página {{ page() }}</span>
          <button type="button" class="btn" (click)="search(page() + 1)" [disabled]="!hasNext() || loading()">Próxima</button>
        </div>
      }
    } @else if (!loading()) {
      <section>
        <h2 class="section-title">Experimente</h2>
        <div class="chips">
          @for (example of examples; track example) {
            <button type="button" class="chip-button" (click)="tryExample(example)">{{ example }}</button>
          }
        </div>
      </section>

      <section>
        <h2 class="section-title">O que cada fonte entrega</h2>
        <div class="quick">
          <article class="quick-card static">
            <span class="bubble"><app-icon name="scale" /></span>
            <strong>TST — acórdãos</strong>
            <span>
              Ementa, órgão judicante, relator, datas de julgamento e publicação, com link para o inteiro teor.
              Matéria trabalhista. Use aspas para expressão exata.
            </span>
          </article>
          <article class="quick-card static">
            <span class="bubble"><app-icon name="landmark" /></span>
            <strong>DataJud (CNJ) — processos</strong>
            <span>
              Classe, assuntos, órgão julgador e datas de processos do STJ, TRFs, TJs e outros tribunais. Não traz
              ementa nem inteiro teor: serve para localizar o processo.
            </span>
          </article>
          <article class="quick-card static">
            <span class="bubble"><app-icon name="arrow" /></span>
            <strong>Outros tribunais</strong>
            <span>
              STF e STJ bloqueiam consultas automatizadas. Pesquise no site oficial:
              <a href="https://jurisprudencia.stf.jus.br/" target="_blank" rel="noopener noreferrer">STF</a> ·
              <a href="https://scon.stj.jus.br/SCON/" target="_blank" rel="noopener noreferrer">STJ</a> ·
              <a href="https://jurisprudencia.cjf.jus.br/unificada/" target="_blank" rel="noopener noreferrer">CJF (unificada)</a>
            </span>
          </article>
        </div>
      </section>
    }
  `,
})
export class JurisprudencePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);

  /** Parâmetros da rota (`?q=&fonte=&tribunal=`): abrem a página já pesquisando. */
  readonly q = input<string>();
  readonly fonte = input<string>();
  readonly tribunal = input<string>();

  protected readonly courts = COURTS;
  protected readonly examples = ['adicional de insalubridade', '"dano moral coletivo"', 'horas extras banco de horas', 'justa causa abandono de emprego'];
  /** Espelha o campo "fonte" como sinal, para a tela reagir à troca. */
  protected readonly fonteValue = signal('tst');
  protected readonly isTst = computed(() => this.fonteValue() === 'tst');
  protected readonly form = this.fb.nonNullable.group({
    q: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(200)]],
    fonte: ['tst'],
    tribunal: ['stj'],
    soEmenta: [false],
  });
  protected readonly result = signal<LegalSearchResponse | null>(null);
  protected readonly page = signal(1);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    const query = this.q()?.trim();
    if (!query) return;
    const tribunal = COURTS.some(([code]) => code === this.tribunal()) ? this.tribunal()! : 'stj';
    this.form.patchValue({ q: query, fonte: this.fonte() === 'datajud' ? 'datajud' : 'tst', tribunal });
    this.fonteValue.set(this.form.controls.fonte.value);
    this.search(1);
  }

  protected tryExample(example: string): void {
    this.form.patchValue({ q: example, fonte: 'tst' });
    this.fonteValue.set('tst');
    this.search(1);
  }

  protected hasNext(): boolean {
    const data = this.result();
    return !!data && data.total !== null && this.page() * 20 < data.total && this.page() < 50;
  }

  protected search(page: number): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { q, fonte, tribunal, soEmenta } = this.form.getRawValue();
    this.loading.set(true);
    this.error.set(null);
    this.api.jurisprudence(q.trim(), fonte, tribunal, page, soEmenta && fonte === 'tst').subscribe({
      next: (response) => {
        this.result.set(response);
        this.page.set(page);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }
}

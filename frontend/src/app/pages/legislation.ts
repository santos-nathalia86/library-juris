import { Component, OnInit, inject, input, signal } from '@angular/core';
import { KeyValuePipe } from '@angular/common';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';

import { ApiService, errorMessage } from '../core/api.service';
import { LegalSearchResponse } from '../core/models';
import { Icon } from '../shared/icon';
import { LegalResults } from '../shared/legal-results';

function numberOrYear(group: AbstractControl): ValidationErrors | null {
  return group.get('numero')?.value || group.get('ano')?.value ? null : { criterion: true };
}

const TYPE_WORDS: [RegExp, string][] = [
  [/\blei complementar\b/i, 'LCP'], [/\bdecreto-lei\b/i, 'DEL'], [/\bmedida provis[óo]ria\b/i, 'MPV'],
  [/\bemenda constitucional\b/i, 'EMC'], [/\bdecreto\b/i, 'DEC'], [/\blei\b/i, 'LEI'],
];

/** Separa tipo, número e ano de uma frase livre; o que sobra vira filtro de palavras da ementa. */
function parseFreeText(text: string): { tipo: string; numero: string; ano: string; termo: string } {
  let rest = text;
  let tipo = '';
  for (const [pattern, code] of TYPE_WORDS) {
    if (pattern.test(rest)) {
      tipo = code;
      rest = rest.replace(pattern, ' ');
      break;
    }
  }
  const numbers = rest.match(/\d[\d.]*/g)?.map((n) => n.replace(/\./g, '')) ?? [];
  const isYear = (n: string) => /^(1[89]|20)\d{2}$/.test(n);
  const ano = numbers.length > 1 ? (numbers.slice(1).find(isYear) ?? '') : numbers.length === 1 && isYear(numbers[0]) && !tipo ? numbers[0] : '';
  const numero = numbers.find((n) => n !== ano && n.length <= 6) ?? '';
  // Sobram as palavras da ementa: saem os números, "nº", preposições soltas e sinais.
  const termo = rest
    .replace(/\d[\d.]*/g, ' ')
    .replace(/[ºª°]/g, ' ')
    .replace(/[^\p{L}\s-]/gu, ' ')
    .split(/\s+/)
    .filter((word) => word.length > 1 && !['de', 'do', 'da', 'no', 'na', 'nº'].includes(word.toLowerCase()))
    .join(' ');
  return { tipo, numero, ano, termo };
}

interface Example {
  label: string;
  values: { tipo: string; numero: string; ano: string; texto: string };
}

const EXAMPLES: Example[] = [
  { label: 'Código de Defesa do Consumidor', values: { tipo: 'LEI', numero: '8078', ano: '1990', texto: '' } },
  { label: 'Código Civil', values: { tipo: 'LEI', numero: '10406', ano: '2002', texto: '' } },
  { label: 'Código Penal', values: { tipo: 'DEL', numero: '2848', ano: '1940', texto: '' } },
  { label: 'Leis de 1990 sobre consumidor', values: { tipo: 'LEI', numero: '', ano: '1990', texto: 'consumidor' } },
];

@Component({
  selector: 'app-legislation-page',
  imports: [ReactiveFormsModule, KeyValuePipe, LegalResults, Icon],
  template: `
    <header class="page-head">
      <span class="bubble"><app-icon name="book" [size]="26" /></span>
      <div>
        <h1>Legislação federal</h1>
        <p class="lead">
          Normas catalogadas pelo Senado Federal. Informe o número ou o ano; as palavras filtram as ementas das normas
          encontradas.
        </p>
      </div>
    </header>

    <form class="search-panel hero-search" [formGroup]="form" (ngSubmit)="submit()">
      <div class="search-box">
        <app-icon name="search" />
        <input
          type="search" formControlName="texto" autocomplete="off" aria-label="Norma ou palavras da ementa"
          placeholder="Ex: lei 8078 de 1990 — ou palavras da ementa, como consumidor"
        />
        <button type="submit" class="btn primary" [disabled]="loading()">
          {{ loading() ? 'Consultando…' : 'Pesquisar' }} <app-icon name="arrow" [size]="18" />
        </button>
      </div>
      <div class="filters">
        <label class="filter">
          <app-icon name="grid" />
          <span>
            <small>Tipo</small>
            <select formControlName="tipo">
              <option value="">Qualquer tipo</option>
              @for (type of types() | keyvalue; track type.key) {
                <option [value]="type.key">{{ type.value }}</option>
              }
            </select>
          </span>
        </label>
        <label class="filter narrow">
          <app-icon name="file" />
          <span>
            <small>Número</small>
            <input type="text" inputmode="numeric" formControlName="numero" placeholder="8078" autocomplete="off" />
          </span>
        </label>
        <label class="filter narrow">
          <app-icon name="clock" />
          <span>
            <small>Ano</small>
            <input type="text" inputmode="numeric" formControlName="ano" placeholder="1990" autocomplete="off" />
          </span>
        </label>
      </div>
      @if (submitted() && form.hasError('criterion')) {
        <p class="field-error">
          Informe o número ou o ano da norma — a fonte oficial não pesquisa só por palavras. Você pode escrever tudo
          na busca, como “lei 8078 de 1990”.
        </p>
      }
      @if (form.controls.numero.invalid || form.controls.ano.invalid) {
        <p class="field-error">Número e ano aceitam apenas algarismos (ano com quatro dígitos).</p>
      }
    </form>

    @if (error()) {
      <p class="alert error">{{ error() }}</p>
    }

    @if (result(); as data) {
      <app-legal-results [result]="data" />
    } @else if (!loading()) {
      <section>
        <h2 class="section-title">Experimente</h2>
        <div class="chips">
          @for (example of examples; track example.label) {
            <button type="button" class="chip-button" (click)="tryExample(example)">{{ example.label }}</button>
          }
        </div>
      </section>

      <section>
        <h2 class="section-title">Como funciona</h2>
        <div class="quick">
          <article class="quick-card static">
            <span class="bubble"><app-icon name="search" /></span>
            <strong>Como pesquisar</strong>
            <span>
              Escreva a norma na busca (“decreto 9.830 de 2019”) ou preencha tipo, número e ano. Com o ano e palavras,
              a lista traz as normas daquele ano cuja ementa contém as palavras.
            </span>
          </article>
          <article class="quick-card static">
            <span class="bubble"><app-icon name="file" /></span>
            <strong>O que você recebe</strong>
            <span>
              Nome oficial da norma, ementa, data de assinatura, nomes pelos quais é conhecida e o link para a página
              da norma no Senado, com o texto e as alterações.
            </span>
          </article>
          <article class="quick-card static">
            <span class="bubble"><app-icon name="arrow" /></span>
            <strong>Texto compilado e busca por assunto</strong>
            <span>
              Essas fontes não aceitam consulta automatizada. Pesquise no site:
              <a href="https://www.planalto.gov.br/legislacao" target="_blank" rel="noopener noreferrer">Planalto</a> ·
              <a href="https://www.lexml.gov.br/" target="_blank" rel="noopener noreferrer">LexML</a> ·
              <a href="https://normas.leg.br/busca" target="_blank" rel="noopener noreferrer">Normas.leg.br</a>
            </span>
          </article>
        </div>
      </section>
    }
  `,
})
export class LegislationPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);

  /** Parâmetros da rota. `texto` é a frase livre da página inicial ("lei 8078 de 1990 consumidor"). */
  readonly tipo = input<string>();
  readonly numero = input<string>();
  readonly ano = input<string>();
  readonly termo = input<string>();
  readonly texto = input<string>();

  protected readonly form = this.fb.nonNullable.group(
    {
      texto: ['', Validators.maxLength(200)],
      tipo: [''],
      numero: ['', Validators.pattern(/^\d{1,6}$/)],
      ano: ['', Validators.pattern(/^(1[89]|20)\d{2}$/)],
    },
    { validators: numberOrYear },
  );
  protected readonly examples = EXAMPLES;
  protected readonly types = signal<Record<string, string>>({});
  protected readonly result = signal<LegalSearchResponse | null>(null);
  protected readonly loading = signal(false);
  protected readonly submitted = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.api.legislationTypes().subscribe({ next: (types) => this.types.set(types), error: () => undefined });
    const values = {
      tipo: this.tipo() ?? '', numero: this.numero() ?? '', ano: this.ano() ?? '',
      texto: this.texto() ?? this.termo() ?? '',
    };
    if (values.numero || values.ano || values.texto) {
      this.form.patchValue(values);
      this.submit();
    }
  }

  protected tryExample(example: Example): void {
    this.form.setValue(example.values);
    this.submit();
  }

  /** Tira tipo, número e ano do texto livre para os filtros; o que sobra filtra as ementas. */
  protected submit(): void {
    const current = this.form.getRawValue();
    const parsed = parseFreeText(current.texto);
    this.form.patchValue({
      texto: parsed.termo,
      tipo: parsed.tipo || current.tipo,
      numero: parsed.numero || current.numero,
      ano: parsed.ano || current.ano,
    });
    this.submitted.set(true);
    if (this.form.invalid) return;

    const { texto, tipo, numero, ano } = this.form.getRawValue();
    this.loading.set(true);
    this.error.set(null);
    this.api.legislation({ tipo, numero, ano, termo: texto }).subscribe({
      next: (response) => {
        this.result.set(response);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }
}

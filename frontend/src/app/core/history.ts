import { Params } from '@angular/router';

import { SearchLog } from './models';

export const KIND_LABELS: Record<SearchLog['kind'], string> = {
  citacoes: 'Meus documentos',
  livros_online: 'Livros e doutrina',
  jurisprudencia: 'Jurisprudência',
  legislacao: 'Legislação',
};

/** Rota e parâmetros que repetem uma pesquisa registrada no histórico. */
export function historyLink(log: SearchLog): { path: string; queryParams: Params } {
  const p = log.params;
  switch (log.kind) {
    case 'livros_online':
      return { path: '/livros-online', queryParams: { q: log.query, fonte: p['fonte'] ?? null, tipo: p['tipo'] ?? null } };
    case 'jurisprudencia':
      return { path: '/jurisprudencia', queryParams: { q: log.query, fonte: p['fonte'] ?? null, tribunal: p['tribunal'] ?? null } };
    case 'legislacao':
      return {
        path: '/legislacao',
        queryParams: { tipo: p['tipo'] ?? null, numero: p['numero'] ?? null, ano: p['ano'] ?? null, termo: p['termo'] ?? null },
      };
    default:
      return { path: '/citacoes', queryParams: { q: log.query, modo: p['mode'] ?? null, livro: p['book_id'] ?? null } };
  }
}

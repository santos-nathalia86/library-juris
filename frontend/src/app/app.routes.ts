import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'inicio' },
  {
    path: 'inicio',
    title: 'JurisFind',
    loadComponent: () => import('./pages/home').then((m) => m.HomePage),
  },
  {
    path: 'historico',
    title: 'Histórico — JurisFind',
    loadComponent: () => import('./pages/history').then((m) => m.HistoryPage),
  },
  {
    path: 'citacoes',
    title: 'Citações — JurisFind',
    loadComponent: () => import('./pages/citations').then((m) => m.CitationsPage),
  },
  // Meus Documentos desativado temporariamente; /biblioteca cai no redirecionamento para o início.
  // {
  //   path: 'biblioteca',
  //   title: 'Meus Documentos — JurisFind',
  //   loadComponent: () => import('./pages/library').then((m) => m.LibraryPage),
  // },
  {
    path: 'biblioteca/:id',
    title: 'Dados do livro — JurisFind',
    loadComponent: () => import('./pages/book-detail').then((m) => m.BookDetailPage),
  },
  {
    path: 'livros-online',
    title: 'Livros e Doutrina — JurisFind',
    loadComponent: () => import('./pages/online-books').then((m) => m.OnlineBooksPage),
  },
  {
    path: 'jurisprudencia',
    title: 'Jurisprudência — JurisFind',
    loadComponent: () => import('./pages/jurisprudence').then((m) => m.JurisprudencePage),
  },
  {
    path: 'legislacao',
    title: 'Legislação — JurisFind',
    loadComponent: () => import('./pages/legislation').then((m) => m.LegislationPage),
  },
  { path: '**', redirectTo: 'inicio' },
];

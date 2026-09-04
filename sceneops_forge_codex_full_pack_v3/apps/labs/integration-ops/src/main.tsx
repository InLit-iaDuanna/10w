import { createRoot } from 'react-dom/client';
import { lazy, Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { loadIntegrationOpsWorkbench } from '../../../../modules/integration-center/frontend/src/index';

const queries = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
const IntegrationOpsWorkbench = lazy(loadIntegrationOpsWorkbench);
createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queries}><Suspense fallback={<p>正在打开集成工作台…</p>}><IntegrationOpsWorkbench /></Suspense></QueryClientProvider>,
);

import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConceptAssetsWorkbench } from '../../../modules/asset-factory/frontend/src/index';
const queryClient = new QueryClient();
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={queryClient}><ConceptAssetsWorkbench /></QueryClientProvider>);

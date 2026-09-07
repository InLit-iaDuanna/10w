// Isolated acceptance entry: render the product workbench, not a substitute UI.
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AgentTaskWorkbench } from '../../../../modules/ai-agent-runtime/frontend/src/AgentTaskWorkbench';

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={new QueryClient()}><AgentTaskWorkbench projectId={null} /></QueryClientProvider>,
);

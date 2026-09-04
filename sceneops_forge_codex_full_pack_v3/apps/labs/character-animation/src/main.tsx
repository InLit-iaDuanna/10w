import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CharacterAnimationWorkbench } from '@sceneops/character-animation';
import { api } from './transport';
import './theme.css';

class StartupBoundary extends React.Component<React.PropsWithChildren, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  render() {
    return this.state.error ? <main role="alert"><h1>工作台加载失败</h1><p>{this.state.error}</p><button onClick={() => location.reload()}>重新加载</button></main> : this.props.children;
  }
}
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
createRoot(document.getElementById('root')!).render(
  <StartupBoundary><QueryClientProvider client={queryClient}><CharacterAnimationWorkbench api={api}/></QueryClientProvider></StartupBoundary>,
);

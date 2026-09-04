import { Component, lazy, Suspense, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { loadAIPlaytestWorkbench } from "../../../../modules/ai-playtest/frontend/src/index.ts";

const AIPlaytestWorkbench = lazy(async () => ({ default: (await loadAIPlaytestWorkbench()).AIPlaytestWorkbench }));

class WorkbenchBoundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  render() {
    return this.state.error
      ? <main role="alert"><h1>工作台无法加载</h1><p>请检查本地依赖和开发服务输出。重新加载不会启动 AI 测试。</p><button onClick={() => location.reload()}>重新加载</button></main>
      : this.props.children;
  }
}
createRoot(document.getElementById("root")!).render(<WorkbenchBoundary><Suspense fallback={<p>正在加载本地证据工作台…</p>}><AIPlaytestWorkbench /></Suspense></WorkbenchBoundary>);

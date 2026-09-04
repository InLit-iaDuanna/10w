import { useEffect, useState } from 'react';
import type { DockviewPanelApi } from 'dockview-react';

export function usePanelVisibility(api: DockviewPanelApi, onVisibility: (visible: boolean) => void): boolean {
  const [visible, setVisible] = useState(api.isVisible);
  useEffect(() => {
    onVisibility(api.isVisible);
    const disposable = api.onDidVisibilityChange(({ isVisible }) => {
      setVisible(isVisible);
      onVisibility(isVisible);
    });
    return () => disposable.dispose();
  }, [api, onVisibility]);
  return visible;
}

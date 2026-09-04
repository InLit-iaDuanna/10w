import { buildWorldEditorScreen, type WorldEditorInput, type WorldEditorScreen } from '../editor-state.ts';

export default function LightingEditor(input: WorldEditorInput): WorldEditorScreen {
  return buildWorldEditorScreen('scene.lighting', '灯光目标', input, [
    { id: 'targets', label: '目标', value: ['illuminanceLux', 'colorTemperatureKelvin', 'intent'] },
    { id: 'mutation', label: '写入', value: '仅通过 typed adapter' },
  ]);
}

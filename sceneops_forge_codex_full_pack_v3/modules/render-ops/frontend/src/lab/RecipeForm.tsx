import * as React from 'react';
import type { LabRecipeInput, LabState } from './api';

export const recipeLabels: Record<string, string> = {
  'render.lighting-visibility': '灯光 / 目标可见度',
  'render.asset-turntable': '资产转台',
  'render.material-variant': '材质变体',
  'render.fixed-camera-regression': '固定相机回归',
  'render.marketing-still': '宣传静帧',
};

export function RecipeForm({ state, busy, onPlan }: {
  state: LabState; busy: boolean; onPlan: (input: LabRecipeInput) => void;
}) {
  const [input, setInput] = React.useState<LabRecipeInput>({
    recipe_id: 'render.lighting-visibility', prompt: '让门廊钥匙区域更清晰，保留门体轮廓。',
    negative_prompt: '不改变门体和固定相机', seed: 42, samples: 64,
    geometry_version: 'geometry-v8', camera_version: 'camera-v4',
    ai_provider: 'codebuddycli', ai_model: 'cli-default',
  });
  const update = (patch: Partial<LabRecipeInput>) => setInput(value => ({ ...value, ...patch }));
  return <aside className="rl-recipe">
    <div className="rl-section-heading"><span>01 / 配方编辑</span><span className="rl-mode">MOCK</span></div>
    <form onSubmit={event => { event.preventDefault(); onPlan(input); }}>
      <label>配方<select value={input.recipe_id} onChange={e => update({ recipe_id: e.target.value })}>
        {state.recipes.map(recipe => <option key={recipe.recipe_id} value={recipe.recipe_id}>{recipeLabels[recipe.recipe_id]}</option>)}
      </select></label>
      <label>AI 模型 · CodeBuddy CLI<select value={input.ai_model} onChange={e => update({ ai_model: e.target.value as LabRecipeInput['ai_model'] })}>
        <option value="cli-default">CLI 默认模型</option>
        {(['hy4-preview', 'hy3', 'hy3-x', 'glm-5.3', 'glm-5.3-flash', 'glm-5.2', 'glm-5.1', 'glm-5v-turbo', 'minimax-m3', 'minimax-m2.7', 'kimi-k3-1', 'kimi-k2.7', 'kimi-k2.6', 'deepseek-v4-pro', 'deepseek-v4-flash'] as const).map(model => <option key={model} value={model}>{model}</option>)}
      </select></label>
      <p className="rl-help">模型选项来自本机 CLI 帮助，实际可用性由账号决定。本轮仅记录选择，不调用 AI；这不是图像生成模型选择。</p>
      <label>创作意图<textarea required maxLength={8000} rows={4} value={input.prompt} onChange={e => update({ prompt: e.target.value })} /></label>
      <label>负向约束<textarea rows={2} maxLength={8000} value={input.negative_prompt} onChange={e => update({ negative_prompt: e.target.value })} /></label>
      <div className="rl-two-fields">
        <label>Seed<input required type="number" min="0" max="2147483647" value={input.seed} onChange={e => update({ seed: Number(e.target.value) })} /></label>
        <label>采样数<input required type="number" min="1" max="4096" value={input.samples} onChange={e => update({ samples: Number(e.target.value) })} /></label>
      </div>
      <details><summary>依赖版本与缓存</summary>
        <label>几何版本<input required maxLength={80} value={input.geometry_version} onChange={e => update({ geometry_version: e.target.value })} /></label>
        <label>相机版本<input required maxLength={80} value={input.camera_version} onChange={e => update({ camera_version: e.target.value })} /></label>
        <p>只改提示词可复用 mock AOV；改变采样或版本会重新规划所需通道。</p>
      </details>
      <button className="rl-primary" disabled={busy} type="submit">＋ 创建本地任务</button>
      <p className="rl-help">创建任务调用实际规划服务。载入样本后会显示固定图像；提示词和 Seed 不会生成新图。</p>
    </form>
    <div className="rl-context"><span>当前场景</span><strong>归家 · 门廊</strong>
      <code>{state.brief.scene.scene_id}</code><code>{state.brief.scene.scene_version}</code>
      <span>允许编辑对象</span><code>sceneops_light_porch</code>
      <span>保护区域</span><code>sceneops_door_home</code>
    </div>
  </aside>;
}

import type { EvidenceSample } from "./evidence.ts";

export function EvidenceViewport({ sample, selected, onSelect }: { sample: EvidenceSample; selected: number; onSelect: (index: number) => void }) {
  const frames = sample.fixture.frames;
  const point = (p: number[]) => [90 + p[0] * 61, 250 - p[2] * 54];
  const path = frames.map(frame => point(frame.position_m).join(",")).join(" ");
  const frame = frames[selected];
  return <section className="ap-viewport" aria-label="模拟轨迹视图">
    <div className="ap-view-caption"><span>场景观察 / TOP VIEW</span><span>MOCK · 示意图，非游戏截图</span></div>
    <svg viewBox="0 0 700 360" role="img" aria-label={`观察 ${selected + 1}，位置 ${frame.position_m.join(', ')} 米`}>
      <defs><pattern id="ap-grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M 30 0 L 0 0 0 30" fill="none" stroke="#26343b" strokeWidth="0.6" /></pattern></defs>
      <rect width="700" height="360" fill="url(#ap-grid)" />
      <path d="M50 300V80H635V300Z" fill="#253238" fillOpacity=".3" stroke="#607078" strokeWidth="2" />
      <path d="M65 310H155M65 310V215" stroke="#58c8c5" /><text x="163" y="316">X</text><text x="58" y="207">Z</text>
      <rect x="525" y="188" width="45" height="113" fill="#533b32" stroke="#eca85b" strokeWidth="2" />
      <text x="497" y="170">{sample.id === "sample.warehouse" ? "出口 / 障碍候选" : "家门 / 交互对象"}</text>
      <circle cx="243" cy="250" r="10" fill="#eca85b" /><text x="206" y="284">{sample.id === "sample.warehouse" ? "开关" : "钥匙"}</text>
      <polyline points={path} fill="none" stroke="#58c8c5" strokeWidth="3" strokeDasharray="7 5" />
      {frames.map((item, index) => {
        const [x, y] = point(item.position_m);
        return <g key={index} opacity={index === selected ? 1 : .45}>
          <circle cx={x} cy={y} r={index === selected ? 15 : 5} fill={index === selected ? "#58c8c5" : "#dae5e4"} />
        </g>;
      })}
      <text x="35" y="35">{sample.fixture.build.scene_id}</text>
    </svg>
    <div className="ap-frame-selector" aria-label="观察选择">
      {frames.map((_, index) => <button key={index} aria-pressed={index === selected} onClick={() => onSelect(index)}>观察 {index + 1}</button>)}
    </div>
    <div className="ap-view-caption"><span>Unity World · 左手坐标 · Y 向上 · 米</span><span>相机截图：未提供</span></div>
  </section>;
}

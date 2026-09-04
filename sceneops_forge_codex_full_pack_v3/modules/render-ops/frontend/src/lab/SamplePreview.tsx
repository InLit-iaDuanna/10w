import * as React from 'react';
import type { LabImage } from './api';

export function SamplePreview({ image, mask = false }: { image: LabImage; mask?: boolean }) {
  return <figure className="rl-preview">
    <svg viewBox={`0 0 ${image.width} ${image.height}`} role="img" aria-label={`${image.label}，固定 mock 样本`} shapeRendering="crispEdges">
      {image.values.map((value, index) => <rect key={index}
        x={index % image.width} y={Math.floor(index / image.width)} width="1" height="1"
        fill={`rgb(${value},${value},${value})`} />)}
      {mask && <rect x="5" y="5" width="4" height="6" fill="none" stroke="#58c8c5" strokeWidth=".12" />}
    </svg>
    <figcaption><span>{image.label}</span><code>16 × 16 · MOCK</code></figcaption>
  </figure>;
}

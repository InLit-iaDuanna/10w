import type { QualityReport, SkinVersion } from '../api-types';
import EditorStateFrame from '../components/EditorStateFrame';
import type { SkinQaState } from '../editorStates';
import type { EditorProps } from '../types';

export interface SkinQaData {
  skin: SkinVersion;
  report: QualityReport;
}

export default function SkinQaEditor({ runtime, updateLocalState }: EditorProps<SkinQaState, SkinQaData>) {
  return (
    <EditorStateFrame title="蒙皮质量" state={runtime}>
      {({ skin, report }) => (
        <>
          <dl className="character-animation-grid">
            <dt>Skin 版本</dt><dd>{skin.skin_version_id}</dd>
            <dt>采样顶点</dt><dd>{skin.vertices.length}</dd>
            <dt>自动结果</dt><dd>{report.automated_outcome}</dd>
            <dt>人工质量批准</dt><dd>{report.human_quality_approval ? '是' : '否'}</dd>
          </dl>
          <ul className="character-animation-list" aria-label="质量检查">
            {report.checks.filter((check) => check.code.startsWith('character.')).map((check) => (
              <li key={check.code}>
                <button onClick={() => updateLocalState({ selectedCheckCode: check.code })}>{check.code}</button>
                <span className={`character-animation-${check.status}`}>{check.status}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </EditorStateFrame>
  );
}

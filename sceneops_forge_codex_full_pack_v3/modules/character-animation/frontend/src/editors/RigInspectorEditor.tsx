import type { RigVersion, RigVersionDiff } from '../api-types';
import EditorStateFrame from '../components/EditorStateFrame';
import type { RigInspectorState } from '../editorStates';
import type { EditorProps } from '../types';

export interface RigInspectorData {
  rig: RigVersion;
  comparison?: RigVersionDiff;
}

export default function RigInspectorEditor({ runtime, localState, updateLocalState }: EditorProps<RigInspectorState, RigInspectorData>) {
  return (
    <EditorStateFrame title="Rig 检查器" state={runtime}>
      {({ rig, comparison }) => (
        <>
          <dl className="character-animation-grid">
            <dt>版本</dt><dd>v{rig.version_number} · {rig.approval.state}</dd>
            <dt>坐标</dt><dd>{rig.coordinate_system.handedness} / {rig.coordinate_system.up_axis} up / {rig.coordinate_system.meters_per_unit} m</dd>
            <dt>回退版本</dt><dd>{rig.previous_version_id ?? '首个版本'}</dd>
            <dt>差异</dt><dd>{comparison ? `${comparison.bone_changes.length} 项，可逆` : '未选择比较版本'}</dd>
          </dl>
          <ul className="character-animation-list" aria-label="骨骼层级">
            {rig.bones.map((bone) => (
              <li key={bone.bone_id}>
                <button onClick={() => updateLocalState({ selectedBoneId: bone.bone_id })}>{bone.name}</button>
                <span>{localState.showHierarchyIds ? (bone.parent_bone_id ?? 'ROOT') : ''}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </EditorStateFrame>
  );
}

import type { CharacterBundle, UnityCharacterMapping } from '../api-types';
import EditorStateFrame from '../components/EditorStateFrame';
import type { CharacterEditorState } from '../editorStates';
import type { EditorProps } from '../types';

export interface CharacterEditorData {
  bundle: CharacterBundle;
  unityMapping?: UnityCharacterMapping;
}

export default function CharacterEditor({ runtime }: EditorProps<CharacterEditorState, CharacterEditorData>) {
  return (
    <EditorStateFrame title="角色编辑器" state={runtime}>
      {({ bundle, unityMapping }) => (
        <>
          <dl className="character-animation-grid">
            <dt>角色</dt><dd>{bundle.character.display_name}</dd>
            <dt>角色 ID</dt><dd>{bundle.character.character_id}</dd>
            <dt>源资产</dt><dd>{bundle.character.source_asset_id}</dd>
            <dt>来源</dt><dd>{bundle.character.source_kind === 'imported' ? '导入' : '生成源（可选）'}</dd>
            <dt>Rig / Skin</dt><dd>{bundle.rig.rig_version_id} / {bundle.skin.skin_version_id}</dd>
            <dt>Unity</dt><dd>{unityMapping?.unity_prefab_id ?? '尚未映射'}</dd>
          </dl>
          <ul className="character-animation-list" aria-label="关联功能规格">
            {bundle.character.feature_links.map((link) => (
              <li key={link.feature_spec_id}>
                <span>{link.feature_spec_id}</span>
                <span>{link.task_ids.join('、')}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </EditorStateFrame>
  );
}

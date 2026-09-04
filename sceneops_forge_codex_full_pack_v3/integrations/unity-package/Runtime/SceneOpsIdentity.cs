using System;
using UnityEngine;

namespace SceneOps.Forge.Unity.Runtime
{
    [DisallowMultipleComponent]
    [AddComponentMenu("SceneOps/SceneOps Identity")]
    public sealed class SceneOpsIdentity : MonoBehaviour
    {
        [SerializeField] private string sceneopsId = string.Empty;
        [SerializeField] private string sourceAssetId = string.Empty;
        [SerializeField] private string sourceAssetVersionId = string.Empty;
        [SerializeField] private string sourceObjectId = string.Empty;
        [SerializeField] private string unityAssetGuid = string.Empty;
        [SerializeField] private string prefabId = string.Empty;
        [SerializeField] private string sceneInstanceId = string.Empty;
        [SerializeField] private string copiedFromSceneInstanceId = string.Empty;

        public string SceneOpsId => sceneopsId;
        public string SourceAssetId => sourceAssetId;
        public string SourceAssetVersionId => sourceAssetVersionId;
        public string SourceObjectId => sourceObjectId;
        public string UnityAssetGuid => unityAssetGuid;
        public string PrefabId => prefabId;
        public string SceneInstanceId => sceneInstanceId;
        public string CopiedFromSceneInstanceId => copiedFromSceneInstanceId;

        public bool HasPublishedObjectIdentity =>
            !string.IsNullOrWhiteSpace(sceneopsId) &&
            !string.IsNullOrWhiteSpace(sourceAssetId) &&
            !string.IsNullOrWhiteSpace(sourceAssetVersionId);

        public SceneOpsIdentitySnapshot Capture()
        {
            return new SceneOpsIdentitySnapshot
            {
                sceneopsId = sceneopsId,
                sourceAssetId = sourceAssetId,
                sourceAssetVersionId = sourceAssetVersionId,
                sourceObjectId = sourceObjectId,
                unityAssetGuid = unityAssetGuid,
                prefabId = prefabId,
                sceneInstanceId = sceneInstanceId,
                copiedFromSceneInstanceId = copiedFromSceneInstanceId,
            };
        }
    }

    [Serializable]
    public sealed class SceneOpsIdentitySnapshot
    {
        public string sceneopsId = string.Empty;
        public string sourceAssetId = string.Empty;
        public string sourceAssetVersionId = string.Empty;
        public string sourceObjectId = string.Empty;
        public string unityAssetGuid = string.Empty;
        public string prefabId = string.Empty;
        public string sceneInstanceId = string.Empty;
        public string copiedFromSceneInstanceId = string.Empty;
    }
}

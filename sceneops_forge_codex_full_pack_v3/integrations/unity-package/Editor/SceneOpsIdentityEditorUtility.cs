using System;
using System.Collections.Generic;
using System.Linq;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SceneOps.Forge.Unity.Editor
{
    public static class SceneOpsIdentityEditorUtility
    {
        public static void Apply(
            SceneOpsIdentity identity,
            string sceneopsId,
            string sourceAssetId,
            string sourceAssetVersionId,
            string sourceObjectId,
            string unityAssetGuid,
            string prefabId,
            string sceneInstanceId,
            string copiedFromSceneInstanceId = "")
        {
            if (identity == null)
            {
                throw new ArgumentNullException(nameof(identity));
            }
            SerializedObject serialized = new SerializedObject(identity);
            Set(serialized, "sceneopsId", sceneopsId);
            Set(serialized, "sourceAssetId", sourceAssetId);
            Set(serialized, "sourceAssetVersionId", sourceAssetVersionId);
            Set(serialized, "sourceObjectId", sourceObjectId);
            Set(serialized, "unityAssetGuid", unityAssetGuid);
            Set(serialized, "prefabId", prefabId);
            Set(serialized, "sceneInstanceId", sceneInstanceId);
            Set(serialized, "copiedFromSceneInstanceId", copiedFromSceneInstanceId);
            serialized.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(identity);
        }

        public static void AssignCopyIdentity(
            SceneOpsIdentity original,
            SceneOpsIdentity copy,
            string newSceneInstanceId)
        {
            if (original == null || copy == null)
            {
                throw new ArgumentNullException(original == null ? nameof(original) : nameof(copy));
            }
            if (string.IsNullOrWhiteSpace(original.SceneInstanceId) ||
                string.Equals(original.SceneInstanceId, newSceneInstanceId, StringComparison.Ordinal))
            {
                throw new SceneOpsCommandException(
                    "UNITY_IDENTITY_CONFLICT",
                    "A copied GameObject must receive a new scene-instance ID.");
            }

            SceneOpsIdentitySnapshot source = original.Capture();
            Apply(
                copy,
                source.sceneopsId,
                source.sourceAssetId,
                source.sourceAssetVersionId,
                source.sourceObjectId,
                source.unityAssetGuid,
                source.prefabId,
                newSceneInstanceId,
                source.sceneInstanceId);
        }

        internal static SceneOpsIdentity FindLoadedIdentity(
            string sceneopsId,
            string sceneInstanceId = null)
        {
            SceneOpsIdentity[] identities = Resources.FindObjectsOfTypeAll<SceneOpsIdentity>();
            return identities
                .Where(identity => !EditorUtility.IsPersistent(identity))
                .OrderBy(identity => GlobalObjectId.GetGlobalObjectIdSlow(identity).ToString(), StringComparer.Ordinal)
                .FirstOrDefault(identity =>
                    string.Equals(identity.SceneOpsId, sceneopsId, StringComparison.Ordinal) &&
                    (string.IsNullOrWhiteSpace(sceneInstanceId) ||
                     string.Equals(identity.SceneInstanceId, sceneInstanceId, StringComparison.Ordinal)));
        }

        internal static SceneOpsIdentity FindPrefabIdentity(string sceneopsId)
        {
            foreach (string guid in AssetDatabase.FindAssets("t:Prefab"))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (prefab == null)
                {
                    continue;
                }
                SceneOpsIdentity match = prefab.GetComponentsInChildren<SceneOpsIdentity>(true)
                    .FirstOrDefault(identity =>
                        string.Equals(identity.SceneOpsId, sceneopsId, StringComparison.Ordinal));
                if (match != null)
                {
                    return match;
                }
            }
            return null;
        }

        private static void Set(SerializedObject serialized, string propertyName, string value)
        {
            SerializedProperty property = serialized.FindProperty(propertyName);
            if (property == null)
            {
                throw new InvalidOperationException($"SceneOpsIdentity property '{propertyName}' is missing.");
            }
            property.stringValue = value ?? string.Empty;
        }
    }
}

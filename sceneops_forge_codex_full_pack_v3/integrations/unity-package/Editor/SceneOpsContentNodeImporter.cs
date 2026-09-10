using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEngine;
namespace SceneOps.Forge.Unity.Editor
{
    internal sealed class SceneOpsContentNodeImporter : AssetPostprocessor
    {
        private void OnPreprocessModel()
        {
            if (!assetPath.StartsWith("Assets/SceneOpsContent/Models/", System.StringComparison.Ordinal)) return;
            var importer = (ModelImporter)assetImporter;
            importer.extraUserProperties = new[] { "sceneops_id" };
        }
        private void OnPostprocessGameObjectWithUserProperties(GameObject node, string[] names, object[] values)
        {
            if (!assetPath.StartsWith("Assets/SceneOpsContent/Models/", System.StringComparison.Ordinal)) return;
            for (int i = 0; i < names.Length; i++)
                if (names[i] == "sceneops_id" && values[i] is string value && !string.IsNullOrWhiteSpace(value))
                {
                    var identity = node.GetComponent<SceneOpsSourceNode>();
                    if (identity == null) identity = node.AddComponent<SceneOpsSourceNode>();
                    identity.source_node_id = value;
                }
        }
    }
}

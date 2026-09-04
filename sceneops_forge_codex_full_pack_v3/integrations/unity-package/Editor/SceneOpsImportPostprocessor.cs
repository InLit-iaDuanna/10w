using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace SceneOps.Forge.Unity.Editor
{
    internal sealed class SceneOpsImportPostprocessor : AssetPostprocessor
    {
        private static void OnPostprocessAllAssets(
            string[] importedAssets,
            string[] deletedAssets,
            string[] movedAssets,
            string[] movedFromAssetPaths)
        {
            foreach (string path in importedAssets)
            {
                if (!path.EndsWith(".sceneops-unity.json", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                string absolute = Path.Combine(Directory.GetParent(Application.dataPath)?.FullName ?? "", path);
                try
                {
                    SceneOpsImportManifest manifest = JsonUtility.FromJson<SceneOpsImportManifest>(
                        File.ReadAllText(absolute));
                    if (manifest == null || manifest.schema_version != 1 ||
                        string.IsNullOrWhiteSpace(manifest.source_asset_id) ||
                        string.IsNullOrWhiteSpace(manifest.source_asset_version_id))
                    {
                        Debug.LogError($"SceneOps import manifest is invalid: {path}");
                        continue;
                    }
                    Debug.Log(
                        $"SceneOps import manifest ready: {manifest.source_asset_id} / " +
                        $"{manifest.source_asset_version_id} ({manifest.objects?.Length ?? 0} objects)");
                }
                catch (Exception exception)
                {
                    Debug.LogError($"SceneOps import manifest could not be read: {path}\n{exception.Message}");
                }
            }
        }
    }

    [Serializable]
    internal sealed class SceneOpsImportManifest
    {
        public int schema_version;
        public string project_id = string.Empty;
        public string source_asset_id = string.Empty;
        public string source_asset_version_id = string.Empty;
        public string source_file = string.Empty;
        public SceneOpsImportObject[] objects = Array.Empty<SceneOpsImportObject>();
    }

    [Serializable]
    internal sealed class SceneOpsImportObject
    {
        public string source_object_id = string.Empty;
        public string sceneops_id = string.Empty;
        public string display_name = string.Empty;
    }
}

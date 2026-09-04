using System;
using System.Collections.Generic;
using System.Linq;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEngine;

namespace SceneOps.Forge.Unity.Editor
{
    internal static class SceneOpsUnityInspectionCommands
    {
        internal static string Health()
        {
            return JsonUtility.ToJson(new HealthResult
            {
                connected = true,
                editorVersion = Application.unityVersion,
                packageVersion = "0.1.0",
                executionMode = "live",
            });
        }

        internal static string ScanProject(string payloadJson)
        {
            ScanProjectPayload payload = JsonUtility.FromJson<ScanProjectPayload>(payloadJson)
                ?? new ScanProjectPayload();
            string[] scenePaths = AssetDatabase.FindAssets("t:Scene")
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(path => payload.include_packages || path.StartsWith("Assets/", StringComparison.Ordinal))
                .OrderBy(path => path, StringComparer.Ordinal)
                .ToArray();
            string[] prefabPaths = AssetDatabase.FindAssets("t:Prefab")
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(path => payload.include_packages || path.StartsWith("Assets/", StringComparison.Ordinal))
                .OrderBy(path => path, StringComparer.Ordinal)
                .ToArray();

            int identityCount = 0;
            int missingScripts = 0;
            int missingMaterials = 0;
            foreach (string prefabPath in prefabPaths)
            {
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                if (prefab == null)
                {
                    continue;
                }
                identityCount += prefab.GetComponentsInChildren<SceneOpsIdentity>(true).Length;
                missingScripts += CountMissingScripts(prefab);
                missingMaterials += CountMissingMaterials(prefab);
            }

            foreach (SceneOpsIdentity identity in Resources.FindObjectsOfTypeAll<SceneOpsIdentity>())
            {
                if (!EditorUtility.IsPersistent(identity))
                {
                    identityCount += 1;
                }
            }

            return JsonUtility.ToJson(new ScanProjectResult
            {
                sceneCount = scenePaths.Length,
                prefabCount = prefabPaths.Length,
                identityCount = identityCount,
                missingMaterials = missingMaterials,
                missingScripts = missingScripts,
                scenePaths = scenePaths,
                prefabPaths = prefabPaths,
                executionMode = "live",
            });
        }

        internal static string InspectGameObject(string payloadJson)
        {
            InspectGameObjectPayload payload = JsonUtility.FromJson<InspectGameObjectPayload>(payloadJson);
            if (payload == null || string.IsNullOrWhiteSpace(payload.sceneops_id))
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "sceneops_id is required.");
            }
            SceneOpsIdentity identity = SceneOpsIdentityEditorUtility.FindLoadedIdentity(
                payload.sceneops_id, payload.scene_instance_id);
            identity = identity ?? SceneOpsIdentityEditorUtility.FindPrefabIdentity(payload.sceneops_id);
            if (identity == null)
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE",
                    $"No Unity GameObject is mapped to '{payload.sceneops_id}'.");
            }
            GameObject target = identity.gameObject;
            return JsonUtility.ToJson(new InspectGameObjectResult
            {
                sceneopsId = identity.SceneOpsId,
                sceneInstanceId = identity.SceneInstanceId,
                unityGlobalObjectId = GlobalObjectId.GetGlobalObjectIdSlow(identity).ToString(),
                displayName = target.name,
                componentTypes = target.GetComponents<Component>()
                    .Where(component => component != null)
                    .Select(component => component.GetType().Name)
                    .OrderBy(name => name, StringComparer.Ordinal)
                    .ToArray(),
                missingScripts = GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(target),
                missingMaterials = CountMissingMaterials(target),
                executionMode = "live",
            });
        }

        internal static int CountMissingScripts(GameObject root)
        {
            return root.GetComponentsInChildren<Transform>(true)
                .Sum(item => GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(item.gameObject));
        }

        internal static int CountMissingMaterials(GameObject root)
        {
            int count = 0;
            foreach (Renderer renderer in root.GetComponentsInChildren<Renderer>(true))
            {
                count += renderer.sharedMaterials.Count(material => material == null);
            }
            return count;
        }
    }
}

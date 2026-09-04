using System;
using System.Collections.Generic;
using System.IO;
using SceneOps.Forge.Unity.Editor;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SceneOps.Fixtures.Editor
{
    public static class SceneOpsFixtureBuilder
    {
        public static void BuildAll()
        {
            string outputRoot = Argument("-sceneopsOutputRoot");
            string resultPath = Argument("-sceneopsSmokeResult");
            Directory.CreateDirectory(outputRoot);
            EnsureFolder("Assets/Generated");
            EnsureFolder("Assets/Generated/Scenes");
            EnsureFolder("Assets/Generated/Prefabs");
            EnsureFolder("Assets/Generated/Materials");

            List<SmokeBuildRecord> records = new List<SmokeBuildRecord>
            {
                BuildRememberHome(outputRoot, false),
                BuildRememberHome(outputRoot, true),
                BuildWarehouseEscape(outputRoot),
            };
            File.WriteAllText(resultPath, JsonUtility.ToJson(new SmokeBuildBatch
            {
                schemaVersion = 1,
                executionMode = "live",
                unityVersion = Application.unityVersion,
                builds = records.ToArray(),
            }, true));
        }

        private static SmokeBuildRecord BuildRememberHome(string outputRoot, bool approvedFix)
        {
            string suffix = approvedFix ? "B" : "A";
            string scenePath = $"Assets/Generated/Scenes/RememberHome{suffix}.unity";
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            CreateEnvironment(new Color(0.18f, 0.16f, 0.14f));
            SceneOpsTelemetryBridge telemetry = CreateTelemetry("prj_remember_home", $"bld_remember_home_{suffix.ToLowerInvariant()}");
            CreatePlayer(new Vector3(0f, 1f, -5f));
            CreateKeyPrefabAndInstance(approvedFix, telemetry);
            CreateDoor(
                "Home Entrance",
                new Vector3(0f, 1.5f, 4f),
                SceneOpsAccessDoor.Requirement.Key,
                "sobj_home_door",
                "sinst_home_door_a",
                telemetry);
            CreateExit(new Vector3(0f, 0.75f, 8f), "sobj_home_exit", "sinst_home_exit_a", telemetry);
            CreateOverlay(
                $"Remember Home {suffix} · LIVE",
                approvedFix
                    ? "WASD：拾取高可见钥匙，打开家门并抵达出口。"
                    : "WASD：寻找钥匙，打开家门并抵达出口。 Build A 保留低可见度问题。"
            );
            EditorSceneManager.SaveScene(scene, scenePath);
            return BuildScene(
                approvedFix ? "bld_remember_home_b" : "bld_remember_home_a",
                $"Remember Home {suffix}",
                scenePath,
                Path.Combine(outputRoot, $"RememberHome{suffix}.app"));
        }

        private static SmokeBuildRecord BuildWarehouseEscape(string outputRoot)
        {
            string scenePath = "Assets/Generated/Scenes/WarehouseEscape.unity";
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            CreateEnvironment(new Color(0.10f, 0.14f, 0.16f));
            SceneOpsTelemetryBridge telemetry = CreateTelemetry("prj_warehouse_escape", "bld_warehouse_escape");
            CreatePlayer(new Vector3(-4f, 1f, -5f));
            CreateSwitch(new Vector3(-4f, 0.75f, 0f), telemetry);
            CreateDoor(
                "Warehouse Door",
                new Vector3(0f, 1.5f, 4f),
                SceneOpsAccessDoor.Requirement.Switch,
                "sobj_warehouse_door",
                "sinst_warehouse_door_a",
                telemetry);
            CreateExit(new Vector3(4f, 0.75f, 8f), "sobj_warehouse_exit", "sinst_warehouse_exit_a", telemetry);
            CreateOverlay("Warehouse Escape · LIVE", "WASD：触发开关，穿过仓门并抵达出口。");
            EditorSceneManager.SaveScene(scene, scenePath);
            return BuildScene(
                "bld_warehouse_escape",
                "Warehouse Escape",
                scenePath,
                Path.Combine(outputRoot, "WarehouseEscape.app"));
        }

        private static void CreateEnvironment(Color groundColor)
        {
            GameObject cameraObject = new GameObject("Main Camera", typeof(Camera), typeof(AudioListener));
            cameraObject.tag = "MainCamera";
            cameraObject.transform.position = new Vector3(0f, 10f, -12f);
            cameraObject.transform.rotation = Quaternion.Euler(35f, 0f, 0f);

            GameObject lightObject = new GameObject("Directional Light", typeof(Light));
            Light light = lightObject.GetComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            lightObject.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Cube);
            ground.name = "Ground";
            ground.transform.position = new Vector3(0f, -0.25f, 2f);
            ground.transform.localScale = new Vector3(18f, 0.5f, 24f);
            ground.GetComponent<Renderer>().sharedMaterial = Material("Ground", groundColor, false);
        }

        private static SceneOpsTelemetryBridge CreateTelemetry(string projectId, string buildId)
        {
            GameObject root = new GameObject("SceneOps Runtime", typeof(SceneOpsTelemetryBridge));
            SceneOpsTelemetryBridge bridge = root.GetComponent<SceneOpsTelemetryBridge>();
            SerializedObject serialized = new SerializedObject(bridge);
            serialized.FindProperty("projectId").stringValue = projectId;
            serialized.FindProperty("buildId").stringValue = buildId;
            serialized.FindProperty("executionMode").stringValue = "live";
            serialized.ApplyModifiedPropertiesWithoutUndo();
            return bridge;
        }

        private static void CreatePlayer(Vector3 position)
        {
            GameObject player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            player.name = "Player";
            player.transform.position = position;
            UnityEngine.Object.DestroyImmediate(player.GetComponent<CapsuleCollider>());
            player.AddComponent<CharacterController>();
            player.AddComponent<SceneOpsInventory>();
            player.AddComponent<SceneOpsSimplePlayerController>();
            SceneOpsIdentity identity = player.AddComponent<SceneOpsIdentity>();
            ApplyIdentity(identity, "sobj_player", "ast_player", "astv_player_001", "prefab_player", "sinst_player_a");
        }

        private static void CreateKeyPrefabAndInstance(bool approvedFix, SceneOpsTelemetryBridge telemetry)
        {
            GameObject key = GameObject.CreatePrimitive(PrimitiveType.Cube);
            key.name = "Home Key";
            key.transform.localScale = new Vector3(0.35f, 0.10f, 0.70f);
            Color color = approvedFix ? new Color(1f, 0.58f, 0.12f) : new Color(0.20f, 0.18f, 0.16f);
            key.GetComponent<Renderer>().sharedMaterial = Material(
                approvedFix ? "HomeKeyB" : "HomeKeyA", color, approvedFix);
            key.GetComponent<BoxCollider>().isTrigger = true;
            SceneOpsIdentity prefabIdentity = key.AddComponent<SceneOpsIdentity>();
            ApplyIdentity(prefabIdentity, "sobj_home_key", "ast_home_key", "astv_home_key_001", "prefab_home_key", "");
            key.AddComponent<SceneOpsKeyPickup>();

            string prefabPath = approvedFix
                ? "Assets/Generated/Prefabs/HomeKeyB.prefab"
                : "Assets/Generated/Prefabs/HomeKeyA.prefab";
            GameObject prefab = PrefabUtility.SaveAsPrefabAsset(key, prefabPath);
            UnityEngine.Object.DestroyImmediate(key);
            GameObject instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
            instance.transform.position = approvedFix ? new Vector3(0f, 0.9f, -1f) : new Vector3(3.8f, 0.55f, 0f);
            SetTelemetry(instance.GetComponent<SceneOpsKeyPickup>(), telemetry);
            SceneOpsIdentityEditorUtility.Apply(
                instance.GetComponent<SceneOpsIdentity>(),
                "sobj_home_key",
                "ast_home_key",
                "astv_home_key_001",
                "blobj_home_key",
                AssetDatabase.AssetPathToGUID(prefabPath),
                "prefab_home_key",
                "sinst_home_key_a");
        }

        private static void CreateSwitch(Vector3 position, SceneOpsTelemetryBridge telemetry)
        {
            GameObject trigger = GameObject.CreatePrimitive(PrimitiveType.Cube);
            trigger.name = "Warehouse Switch";
            trigger.transform.position = position;
            trigger.transform.localScale = new Vector3(1f, 0.25f, 1f);
            trigger.GetComponent<Renderer>().sharedMaterial = Material("WarehouseSwitch", new Color(0.10f, 0.75f, 0.82f), true);
            trigger.GetComponent<BoxCollider>().isTrigger = true;
            SceneOpsSwitchTrigger switchTrigger = trigger.AddComponent<SceneOpsSwitchTrigger>();
            SetTelemetry(switchTrigger, telemetry);
            SceneOpsIdentity identity = trigger.AddComponent<SceneOpsIdentity>();
            ApplyIdentity(identity, "sobj_warehouse_switch", "ast_warehouse_switch", "astv_warehouse_switch_001", "prefab_warehouse_switch", "sinst_warehouse_switch_a");
        }

        private static void CreateDoor(
            string name,
            Vector3 position,
            SceneOpsAccessDoor.Requirement requirement,
            string sceneopsId,
            string instanceId,
            SceneOpsTelemetryBridge telemetry)
        {
            GameObject door = GameObject.CreatePrimitive(PrimitiveType.Cube);
            door.name = name;
            door.transform.position = position;
            door.transform.localScale = new Vector3(3f, 3f, 0.5f);
            door.GetComponent<Renderer>().sharedMaterial = Material(name.Replace(" ", ""), new Color(0.66f, 0.38f, 0.18f), false);
            door.GetComponent<BoxCollider>().isTrigger = true;
            SceneOpsAccessDoor accessDoor = door.AddComponent<SceneOpsAccessDoor>();
            SerializedObject serialized = new SerializedObject(accessDoor);
            serialized.FindProperty("requirement").enumValueIndex = (int)requirement;
            serialized.FindProperty("telemetry").objectReferenceValue = telemetry;
            serialized.ApplyModifiedPropertiesWithoutUndo();
            SceneOpsIdentity identity = door.AddComponent<SceneOpsIdentity>();
            ApplyIdentity(identity, sceneopsId, $"ast_{sceneopsId.Substring(5)}", $"astv_{sceneopsId.Substring(5)}_001", $"prefab_{sceneopsId.Substring(5)}", instanceId);
        }

        private static void CreateExit(
            Vector3 position,
            string sceneopsId,
            string instanceId,
            SceneOpsTelemetryBridge telemetry)
        {
            GameObject exit = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            exit.name = "Goal Exit";
            exit.transform.position = position;
            exit.transform.localScale = new Vector3(1.2f, 0.1f, 1.2f);
            exit.GetComponent<Renderer>().sharedMaterial = Material("GoalExit", new Color(0.2f, 0.9f, 0.45f), true);
            exit.GetComponent<CapsuleCollider>().isTrigger = true;
            SceneOpsGoalExit goalExit = exit.AddComponent<SceneOpsGoalExit>();
            SetTelemetry(goalExit, telemetry);
            SceneOpsIdentity identity = exit.AddComponent<SceneOpsIdentity>();
            ApplyIdentity(identity, sceneopsId, $"ast_{sceneopsId.Substring(5)}", $"astv_{sceneopsId.Substring(5)}_001", $"prefab_{sceneopsId.Substring(5)}", instanceId);
        }

        private static void CreateOverlay(string title, string objective)
        {
            GameObject overlay = new GameObject("Build Overlay", typeof(SceneOpsBuildOverlay));
            overlay.GetComponent<SceneOpsBuildOverlay>().Configure(title, objective);
        }

        private static void SetTelemetry(Component component, SceneOpsTelemetryBridge telemetry)
        {
            SerializedObject serialized = new SerializedObject(component);
            serialized.FindProperty("telemetry").objectReferenceValue = telemetry;
            serialized.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void ApplyIdentity(
            SceneOpsIdentity identity,
            string sceneopsId,
            string assetId,
            string assetVersionId,
            string prefabId,
            string instanceId)
        {
            SceneOpsIdentityEditorUtility.Apply(
                identity,
                sceneopsId,
                assetId,
                assetVersionId,
                $"src_{sceneopsId}",
                "fixture-guid",
                prefabId,
                instanceId);
        }

        private static Material Material(string name, Color color, bool emission)
        {
            string path = $"Assets/Generated/Materials/{name}.mat";
            Material existing = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (existing != null)
            {
                return existing;
            }
            Shader shader = Shader.Find("Standard");
            if (shader == null)
            {
                throw new InvalidOperationException("Built-in Standard shader is unavailable.");
            }
            Material material = new Material(shader) { color = color };
            if (emission)
            {
                material.EnableKeyword("_EMISSION");
                material.SetColor("_EmissionColor", color * 1.8f);
            }
            AssetDatabase.CreateAsset(material, path);
            return material;
        }

        private static SmokeBuildRecord BuildScene(
            string buildId,
            string profile,
            string scenePath,
            string outputPath)
        {
            BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { scenePath },
                locationPathName = outputPath,
                target = BuildTarget.StandaloneOSX,
                options = BuildOptions.Development,
            });
            if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            {
                throw new InvalidOperationException(
                    $"{profile} build failed: {report.summary.result}, {report.summary.totalErrors} errors.");
            }
            return new SmokeBuildRecord
            {
                buildId = buildId,
                profile = profile,
                scenePath = scenePath,
                outputPath = outputPath,
                result = report.summary.result.ToString(),
                totalSizeBytes = report.summary.totalSize,
            };
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
            {
                return;
            }
            string parent = Path.GetDirectoryName(path)?.Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }

        private static string Argument(string name)
        {
            string[] arguments = Environment.GetCommandLineArgs();
            for (int index = 0; index < arguments.Length - 1; index++)
            {
                if (string.Equals(arguments[index], name, StringComparison.Ordinal))
                {
                    return arguments[index + 1];
                }
            }
            throw new ArgumentException($"Missing required argument {name}.");
        }
    }

    [Serializable]
    internal sealed class SmokeBuildBatch
    {
        public int schemaVersion;
        public string executionMode = "live";
        public string unityVersion = string.Empty;
        public SmokeBuildRecord[] builds = Array.Empty<SmokeBuildRecord>();
    }

    [Serializable]
    internal sealed class SmokeBuildRecord
    {
        public string buildId = string.Empty;
        public string profile = string.Empty;
        public string scenePath = string.Empty;
        public string outputPath = string.Empty;
        public string result = string.Empty;
        public ulong totalSizeBytes;
    }
}

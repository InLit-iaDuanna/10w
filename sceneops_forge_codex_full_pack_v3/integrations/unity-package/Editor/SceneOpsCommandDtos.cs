using System;

namespace SceneOps.Forge.Unity.Editor
{
    [Serializable]
    internal sealed class BatchCommandRequest
    {
        public string requestId = string.Empty;
        public string command = string.Empty;
        public string projectId = string.Empty;
        public string projectRoot = string.Empty;
        public string baseVersion = string.Empty;
        public string executionMode = string.Empty;
        public string payloadJson = "{}";
        public string changeSetJson = string.Empty;
    }

    [Serializable]
    internal sealed class BatchCommandResult
    {
        public string requestId = string.Empty;
        public string command = string.Empty;
        public string status = "failed";
        public string mode = "live";
        public string message = string.Empty;
        public string errorCode = string.Empty;
        public bool retryable;
        public string resultJson = "{}";
        public SceneOpsCommandLog[] logs = Array.Empty<SceneOpsCommandLog>();
    }

    [Serializable]
    internal sealed class SceneOpsCommandLog
    {
        public string level = "info";
        public string code = string.Empty;
        public string message = string.Empty;
        public string occurredAt = string.Empty;
    }

    [Serializable]
    internal sealed class HealthResult
    {
        public bool connected;
        public string editorVersion = string.Empty;
        public string packageVersion = string.Empty;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class ScanProjectPayload
    {
        public bool include_packages;
    }

    [Serializable]
    internal sealed class ScanProjectResult
    {
        public int sceneCount;
        public int prefabCount;
        public int identityCount;
        public int missingMaterials;
        public int missingScripts;
        public string[] scenePaths = Array.Empty<string>();
        public string[] prefabPaths = Array.Empty<string>();
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class ImportAssetPayload
    {
        public string source_asset_id = string.Empty;
        public string source_asset_version_id = string.Empty;
        public string source_path = string.Empty;
        public string destination_asset_path = string.Empty;
        public string manifest_path = string.Empty;
        public float import_scale = 1f;
        public string material_mode = "import";
        public bool generate_colliders;
        public float[] lod_screen_percentages = Array.Empty<float>();
    }

    [Serializable]
    internal sealed class ImportAssetResult
    {
        public string assetGuid = string.Empty;
        public string assetPath = string.Empty;
        public string sourceAssetId = string.Empty;
        public string sourceAssetVersionId = string.Empty;
        public int manifestObjectCount;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class MapIdentityPayload
    {
        public string source_asset_id = string.Empty;
        public string source_asset_version_id = string.Empty;
        public string source_object_id = string.Empty;
        public string sceneops_id = string.Empty;
        public string unity_asset_guid = string.Empty;
        public string prefab_id = string.Empty;
        public string scene_instance_id = string.Empty;
        public string unity_global_object_id = string.Empty;
        public string relationship = string.Empty;
        public string display_name = string.Empty;
        public string copied_from_scene_instance_id = string.Empty;
    }

    [Serializable]
    internal sealed class IdentityResult
    {
        public string sceneopsId = string.Empty;
        public string sourceAssetId = string.Empty;
        public string sourceAssetVersionId = string.Empty;
        public string prefabId = string.Empty;
        public string sceneInstanceId = string.Empty;
        public string copiedFromSceneInstanceId = string.Empty;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class UpsertPrefabPayload
    {
        public string source_asset_guid = string.Empty;
        public string prefab_asset_path = string.Empty;
        public string sceneops_id = string.Empty;
        public string prefab_id = string.Empty;
        public string source_asset_id = string.Empty;
        public string source_asset_version_id = string.Empty;
        public string[] component_types = Array.Empty<string>();
        public float[] lod_screen_percentages = Array.Empty<float>();
    }

    [Serializable]
    internal sealed class PrefabResult
    {
        public string prefabPath = string.Empty;
        public string prefabGuid = string.Empty;
        public string prefabId = string.Empty;
        public string sceneopsId = string.Empty;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class InspectGameObjectPayload
    {
        public string sceneops_id = string.Empty;
        public string scene_instance_id = string.Empty;
    }

    [Serializable]
    internal sealed class InspectGameObjectResult
    {
        public string sceneopsId = string.Empty;
        public string sceneInstanceId = string.Empty;
        public string unityGlobalObjectId = string.Empty;
        public string displayName = string.Empty;
        public string[] componentTypes = Array.Empty<string>();
        public int missingScripts;
        public int missingMaterials;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class SetComponentPropertyPayload
    {
        public string sceneops_id = string.Empty;
        public string scene_instance_id = string.Empty;
        public string component_type = string.Empty;
        public string property_path = string.Empty;
        public string value_json = string.Empty;
    }

    [Serializable]
    internal sealed class ComponentPropertyResult
    {
        public string sceneopsId = string.Empty;
        public string componentType = string.Empty;
        public string propertyPath = string.Empty;
        public string previousValueJson = string.Empty;
        public string proposedValueJson = string.Empty;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class UpsertColliderPayload
    {
        public string sceneops_id = string.Empty;
        public string scene_instance_id = string.Empty;
        public string collider_type = string.Empty;
        public bool is_trigger;
        public float[] center_meters = Array.Empty<float>();
        public float[] size_meters = Array.Empty<float>();
    }

    [Serializable]
    internal sealed class ColliderResult
    {
        public string sceneopsId = string.Empty;
        public string sceneInstanceId = string.Empty;
        public string colliderType = string.Empty;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class NavMeshPayload
    {
        public string scene_id = string.Empty;
        public string operation = string.Empty;
        public string scene_asset_path = string.Empty;
        public int agent_type_id;
    }

    [Serializable]
    internal sealed class NavMeshResult
    {
        public string operation = string.Empty;
        public int triangulationVertices;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class PlayPayload
    {
        public string scene_asset_path = string.Empty;
    }

    [Serializable]
    internal sealed class PlayResult
    {
        public string playState = string.Empty;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class CapturePayload
    {
        public string output_path = string.Empty;
        public int width = 1280;
        public int height = 720;
    }

    [Serializable]
    internal sealed class CaptureResult
    {
        public string artifactPath = string.Empty;
        public int width;
        public int height;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class ReadConsolePayload
    {
        public string minimum_level = "info";
        public int max_entries = 500;
    }

    [Serializable]
    internal sealed class ConsoleResult
    {
        public string logPath = string.Empty;
        public string[] entries = Array.Empty<string>();
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class ProfilerPayload
    {
        public string output_path = "Artifacts/ProfilerSnapshot.json";
        public int sample_frames = 1;
    }

    [Serializable]
    internal sealed class ProfilerResult
    {
        public long totalAllocatedBytes;
        public long totalReservedBytes;
        public long monoUsedBytes;
        public int sampleFrames;
        public string outputPath = string.Empty;
        public string executionMode = "live";
    }

    [Serializable]
    internal sealed class BuildPayload
    {
        public string build_id = string.Empty;
        public string profile = string.Empty;
        public string target = string.Empty;
        public string output_path = string.Empty;
        public string[] scenes = Array.Empty<string>();
        public bool development;
        public string source_commit = string.Empty;
        public SourceAssetReference[] source_assets = Array.Empty<SourceAssetReference>();
        public string[] required_test_runs = Array.Empty<string>();
    }

    [Serializable]
    internal sealed class SourceAssetReference
    {
        public string source_asset_id = string.Empty;
        public string source_asset_version_id = string.Empty;
    }

    [Serializable]
    internal sealed class BuildResult
    {
        public string buildId = string.Empty;
        public string profile = string.Empty;
        public string outputPath = string.Empty;
        public string result = string.Empty;
        public ulong totalSizeBytes;
        public string unityVersion = string.Empty;
        public string executionMode = "live";
    }
}

using System;
namespace SceneOps.Forge.Unity.Editor
{
    [Serializable] internal sealed class ContentNodes { public string frame, leaf, hinge; }
    [Serializable] internal sealed class ContentValues { public float[] position; public float interaction_distance; public bool requires_key; }
    [Serializable] internal sealed class ContentInput { public float move_x, move_z; public bool interact; public int duration_frames = 1; }
    [Serializable] internal sealed class ContentPayload
    {
        public string asset_id, source_version, expected_source_version, source_path, instance_id, base_revision, run_id, operation;
        public ContentNodes nodes;
        public string[] instance_ids;
        public ContentValues expected;
        public bool set_position, set_distance, set_requires_key, requires_key, reopen;
        public float[] position;
        public float interaction_distance;
        public ContentInput input;
    }
    [Serializable] internal sealed class ContentInstance
    {
        public string instance_id, asset_id, source_version, global_object_id, prefab_id;
        public float[] position;
        public float interaction_distance;
        public bool requires_key, opened;
        public string last_interaction;
        public ContentNodes node_ids;
        public ContentNodeReadback[] nodes;
    }
    [Serializable] internal sealed class ContentNodeReadback
    { public string source_node_id, global_object_id; public float[] position, dimensions; public int colliders; }
    [Serializable] internal sealed class ContentPlayerState
    { public float[] position; public bool has_key, release_confirmed; public int frames_consumed, collision_count; public string last_action, active_request; }
    [Serializable] internal sealed class ContentState
    {
        public string asset_id = "", source_version = "", scene_path = "", prefab_guid = "", model_guid = "", revision = "empty", run_id = "", session_id;
        public string mode = "live", editor_version;
        public bool dirty, playing, compiling;
        public ContentInstance[] instances;
        public ContentPlayerState player;
        public string[] errors;
    }
    [Serializable] internal sealed class ContentHead
    {
        public string asset_id = "", source_version = "", revision = "empty", prefab_guid = "", model_guid = "", run_id = "";
        public string previous_model_guid = "", previous_source_version = "";
    }
}

using System;

namespace SceneOps.Forge.Unity.Editor
{
    [Serializable] internal sealed class PrototypeSpec
    {
        public string prototype_id, title;
        public int seed = 1, arena_size = 20, enemy_count = 4, player_health = 100;
        public int weapon_damage = 25, enemy_health = 50, enemy_damage = 10, goal_kills = 4;
        public float enemy_speed = 1.2f, player_speed = 4f, fire_interval = .25f;
    }
    [Serializable] internal sealed class PrototypeInput
    {
        public float move_x, move_z, yaw_delta, pitch_delta;
        public bool fire, jump;
        public int duration_frames = 1, width = 1280, height = 720;
    }
    [Serializable] internal sealed class PrototypePlayPayload
    { public string operation, expected_revision, run_id; public PrototypeInput input = new PrototypeInput(); }
    [Serializable] internal sealed class PrototypeReadback
    {
        public string state_json = "{}", spec_json = "{}", scene_path, session_id, artifact_path;
        public string project_revision, run_id, component_package_version, effect_state, capture_kind;
        public bool revision_drift, effects_reused;
        public bool playing, compiling, prototype_exists;
        public int frame_count, width, height;
        public string[] errors;
        public string status = "ready";
    }
    [Serializable] internal sealed class PrototypeUnavailableState
    {
        public string prototype_id, state = "not_initialized";
        public bool playing, grounded, agent_controlled;
        public int health, kills, shots, hits, enemy_count, goal_kills, round;
        public float elapsed, yaw, pitch;
        public UnityEngine.Vector3 player_position;
        public PrototypeEnemyReadback[] enemies = Array.Empty<PrototypeEnemyReadback>();
    }
    [Serializable] internal sealed class PrototypeEnemyReadback
    {
        public string sceneops_id;
        public UnityEngine.Vector3 position;
        public int health;
    }
}

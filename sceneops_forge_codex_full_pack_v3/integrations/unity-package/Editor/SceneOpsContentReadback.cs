using System.Linq;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;
namespace SceneOps.Forge.Unity.Editor
{
    internal static class SceneOpsContentReadback
    {
        internal static ContentState Read(string root, string session, string[] errors)
        {
            var head = SceneOpsContentCommands.Head(root);
            var player = SceneOpsContentCommands.Player();
            return new ContentState {
                asset_id = head.asset_id, source_version = head.source_version, revision = head.revision,
                model_guid = head.model_guid, prefab_guid = head.prefab_guid, run_id = head.run_id,
                session_id = session, editor_version = Application.unityVersion,
                scene_path = SceneManager.GetActiveScene().path, dirty = SceneManager.GetActiveScene().isDirty,
                compiling = EditorApplication.isCompiling || EditorApplication.isUpdating, playing = EditorApplication.isPlaying,
                errors = errors, instances = SceneOpsContentAssets.Actors().Select(ReadActor).ToArray(),
                player = player == null ? null : new ContentPlayerState {
                    position = SceneOpsContentCommands.Vector(player.transform.position), has_key = player.HasKey,
                    release_confirmed = player.ReleaseConfirmed, frames_consumed = player.FramesConsumed,
                    collision_count = player.CollisionCount, last_action = player.LastAction, active_request = player.ActiveRequest }
            };
        }
        private static ContentInstance ReadActor(SceneOpsDoorActor actor)
        {
            var identity = actor.GetComponent<SceneOpsIdentity>();
            return new ContentInstance {
                instance_id = identity.SceneInstanceId, asset_id = actor.asset_id, source_version = actor.source_version,
                global_object_id = GlobalObjectId.GetGlobalObjectIdSlow(actor.gameObject).ToString(), prefab_id = identity.PrefabId,
                position = SceneOpsContentCommands.Vector(actor.transform.position), interaction_distance = actor.interaction_distance,
                requires_key = actor.requires_key, opened = actor.Opened, last_interaction = actor.LastInteraction,
                node_ids = new ContentNodes { frame = actor.frame_node_id, leaf = actor.leaf_node_id, hinge = actor.hinge_node_id },
                nodes = actor.GetComponentsInChildren<SceneOpsSourceNode>(true).Select(Node).ToArray()
            };
        }
        private static ContentNodeReadback Node(SceneOpsSourceNode node)
        {
            var renderers = node.GetComponentsInChildren<Renderer>(true);
            var bounds = renderers.Length == 0 ? new Bounds(node.transform.position, Vector3.zero) : renderers[0].bounds;
            foreach (var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
            return new ContentNodeReadback {
                source_node_id = node.source_node_id, global_object_id = GlobalObjectId.GetGlobalObjectIdSlow(node.gameObject).ToString(),
                position = SceneOpsContentCommands.Vector(node.transform.position), dimensions = SceneOpsContentCommands.Vector(bounds.size),
                colliders = node.GetComponentsInChildren<Collider>(true).Length
            };
        }
    }
}

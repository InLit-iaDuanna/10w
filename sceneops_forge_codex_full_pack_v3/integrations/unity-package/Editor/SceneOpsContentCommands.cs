using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
namespace SceneOps.Forge.Unity.Editor
{
    internal static class SceneOpsContentCommands
    {
        private static string activeRequest;
        internal static ContentHead Head(string root)
        {
            string path = SceneOpsCommandSecurity.ResolveInsideProject(root, ".sceneops-agent/content-head.json");
            return File.Exists(path) ? JsonUtility.FromJson<ContentHead>(File.ReadAllText(path)) : new ContentHead();
        }
        internal static void SaveHead(string root, ContentHead head) => SceneOpsPrototypeJournal.WriteJson(
            SceneOpsCommandSecurity.ResolveInsideProject(root, ".sceneops-agent/content-head.json"), JsonUtility.ToJson(head));
        internal static void Abort(string request)
        {
            if (activeRequest != null && (request == null || activeRequest == request))
            { Player()?.Cancel(); activeRequest = null; }
        }
        internal static bool TryProcess(AgentRequest request, string root, AgentSessionConfig config, string[] errors, out AgentReply reply)
        {
            reply = null;
            SceneOpsCommandSecurity.ValidateCommand(request.command);
            SceneOpsCommandSecurity.ValidateVersion();
            if (!config.grant.allowed_capabilities.Contains(request.command))
                throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Content capability is outside the bound grant.");
            if (request.command == "unity.content.inspect")
            { reply = Success(Read(root, config.session_id, errors)); return true; }
            SceneOpsPrototypeCommands.ValidateAuthorization(request, root, config);
            if (EditorApplication.isCompiling || EditorApplication.isUpdating) return false;
            var payload = JsonUtility.FromJson<ContentPayload>(request.batch.payloadJson);
            Validate(payload, request.command);
            string marker = SceneOpsCommandSecurity.ResolveInsideProject(root, ".sceneops-agent/" + request.request_id + ".content-started.json");
            bool started = File.Exists(marker);
            Action mark = () => { SceneOpsAgentConnection.WriteReply(root, marker, new AgentReply { status = "started", message = request.authorization.action_id }); started = true; };
            try
            {
                if (request.command == "unity.content.play")
                { if (!Play(root, request, payload, started, mark)) return false; }
                else
                {
                    if (started) throw new SceneOpsCommandException("UNITY_OUTCOME_UNCERTAIN", "A content write started without its durable result. Inspect before recovery.");
                    if (EditorApplication.isPlayingOrWillChangePlaymode)
                        throw new SceneOpsCommandException("UNITY_EXIT_PLAY_REQUIRED", "Exit Play Mode before editing saved content.");
                    if (Head(root).revision != payload.base_revision)
                        throw new SceneOpsCommandException("UNITY_REVISION_CONFLICT", "Content revision changed after this operation was prepared.");
                    switch (request.command)
                    {
                        case "unity.content.import":
                            SceneOpsContentAssets.Import(root, payload, request.authorization.change_set_id, request.request_id, mark); break;
                        case "unity.content.edit": Edit(root, payload, request.authorization.change_set_id, mark); break;
                        case "unity.content.focus":
                            var target = Instance(payload.instance_id); mark(); Selection.activeGameObject = target.gameObject;
                            EditorGUIUtility.PingObject(target.gameObject); SceneView.lastActiveSceneView?.FrameSelected(); break;
                        case "unity.content.save": Save(root, payload, request.authorization.change_set_id, mark); break;
                        default: throw new SceneOpsCommandException("UNITY_COMMAND_NOT_ALLOWED", "Unsupported content command.");
                    }
                }
                reply = Success(Read(root, config.session_id, errors)); return true;
            }
            catch (Exception error)
            {
                Abort(request.request_id);
                var typed = error as SceneOpsCommandException;
                // These validation failures occur after a versioned model import but before any scene/prefab change.
                // The failed durable result retains the model for inspection and must never be reported as applied.
                bool validatedImportFailure = request.command == "unity.content.import" && typed != null &&
                    new[] { "UNITY_SOURCE_NODE_MISSING", "UNITY_SOURCE_GEOMETRY_MISSING", "UNITY_IMPORTER_UNAVAILABLE" }.Contains(typed.Code);
                reply = new AgentReply { status = "failed", error_code = started && !validatedImportFailure ? "UNITY_OUTCOME_UNCERTAIN" : typed?.Code ?? "UNITY_COMMAND_FAILED",
                    cause_code = typed?.Code ?? "UNITY_COMMAND_FAILED", message = error.Message }; return true;
            }
        }
        private static void Validate(ContentPayload p, string command)
        {
            if (p == null) throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Content payload is required.");
            if (command == "unity.content.import")
            {
                if (!Id(p.asset_id) || !Id(p.source_version) || p.nodes == null ||
                    !Id(p.nodes.frame) || !Id(p.nodes.leaf) || !Id(p.nodes.hinge) ||
                    new[] { p.nodes.frame, p.nodes.leaf, p.nodes.hinge }.Distinct().Count() != 3 ||
                    p.instance_ids == null || p.instance_ids.Length != 2 || p.instance_ids.Any(i => !Id(i)) || p.instance_ids.Distinct().Count() != 2 ||
                    p.source_path != "Staging/Content/" + p.asset_id + "/" + p.source_version + "/model.fbx")
                    throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Content import IDs or approved FBX staging path are invalid.");
            }
            if ((command == "unity.content.edit" || command == "unity.content.focus") && !Id(p.instance_id))
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "A persistent scene instance identity is required.");
            if (command == "unity.content.edit" && (p.expected == null || !VectorValid(p.expected.position) ||
                (p.set_position && !VectorValid(p.position)) || (p.set_distance && (!Finite(p.interaction_distance) || p.interaction_distance < .2f || p.interaction_distance > 10f)) ||
                !(p.set_position || p.set_distance || p.set_requires_key)))
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Invalid editable door fields or previous values.");
            if (command == "unity.content.play" && (p.input == null || !new[] { "enter", "exit", "act" }.Contains(p.operation) ||
                !Finite(p.input.move_x) || !Finite(p.input.move_z) || Mathf.Abs(p.input.move_x) > 1 || Mathf.Abs(p.input.move_z) > 1 ||
                p.input.duration_frames < 1 || p.input.duration_frames > 120))
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Invalid bounded gameplay input.");
        }
        private static bool Id(string s) => s != null && Regex.IsMatch(s, "^[A-Za-z0-9_-]{1,120}$");
        private static bool Finite(float f) => !float.IsNaN(f) && !float.IsInfinity(f);
        private static bool VectorValid(float[] v) => v != null && v.Length == 3 && v.All(Finite);
        internal static float[] Vector(Vector3 v) => new[] { v.x, v.y, v.z };
        private static SceneOpsDoorActor Instance(string id)
        {
            var matches = SceneOpsContentAssets.Actors().Where(a => a.GetComponent<SceneOpsIdentity>()?.SceneInstanceId == id).ToArray();
            if (matches.Length != 1) throw new SceneOpsCommandException("UNITY_IDENTITY_CONFLICT", "Exactly one loaded content instance must match the persistent ID.");
            return matches[0];
        }
        private static void Edit(string root, ContentPayload p, string revision, Action mark)
        {
            var actor = Instance(p.instance_id);
            if (actor.gameObject.scene.isDirty) throw new SceneOpsCommandException("UNITY_UNSAVED_SCENE", "Inspector has unsaved edits. Save and reread them before this edit.");
            if (!Vector(actor.transform.position).Zip(p.expected.position, (a, b) => Mathf.Abs(a - b) < .00001f).All(v => v) ||
                Mathf.Abs(actor.interaction_distance - p.expected.interaction_distance) > .00001f || actor.requires_key != p.expected.requires_key)
                throw new SceneOpsCommandException("UNITY_FIELD_CONFLICT", "Actual Inspector fields differ from the values read for this edit.");
            mark(); Undo.RecordObjects(new UnityEngine.Object[] { actor, actor.transform }, "SceneOps content edit");
            if (p.set_position) actor.transform.position = new Vector3(p.position[0], p.position[1], p.position[2]);
            if (p.set_distance) actor.interaction_distance = p.interaction_distance;
            if (p.set_requires_key) actor.requires_key = p.requires_key;
            PrefabUtility.RecordPrefabInstancePropertyModifications(actor); PrefabUtility.RecordPrefabInstancePropertyModifications(actor.transform);
            EditorSceneManager.MarkSceneDirty(actor.gameObject.scene);
            SceneOpsAgentPlacement.SaveVerified(actor.gameObject.scene, root, SceneOpsContentAssets.ScenePath);
            var head = Head(root); head.revision = revision; SaveHead(root, head);
        }
        private static void Save(string root, ContentPayload p, string revision, Action mark)
        {
            var scene = SceneManager.GetActiveScene();
            if (p.reopen)
            {
                if (scene.isDirty) throw new SceneOpsCommandException("UNITY_UNSAVED_SCENE", "Save Inspector edits before reopening the scene.");
                if (!File.Exists(SceneOpsCommandSecurity.ResolveInsideProject(root, SceneOpsContentAssets.ScenePath)))
                    throw new SceneOpsCommandException("UNITY_MISSING_REFERENCE", "The managed content scene has not been saved.");
                mark(); EditorSceneManager.OpenScene(SceneOpsContentAssets.ScenePath, OpenSceneMode.Single);
            }
            else
            {
                if (scene.path != SceneOpsContentAssets.ScenePath)
                    throw new SceneOpsCommandException("UNITY_SCENE_MISMATCH", "Open the managed content scene before saving.");
                mark(); SceneOpsAgentPlacement.SaveVerified(scene, root, SceneOpsContentAssets.ScenePath);
            }
            var head = Head(root); head.revision = revision; SaveHead(root, head);
        }
        private static bool Play(string root, AgentRequest request, ContentPayload p, bool started, Action mark)
        {
            var head = Head(root);
            if (p.operation == "enter")
            {
                if (started)
                {
                    if (!EditorApplication.isPlaying || Player() == null) return false;
                    head.run_id = request.request_id; SaveHead(root, head); return true;
                }
                if (EditorApplication.isPlayingOrWillChangePlaymode) throw new SceneOpsCommandException("UNITY_PLAY_CONFLICT", "Another play session is already running.");
                var scene = SceneManager.GetActiveScene();
                if (scene.isDirty) throw new SceneOpsCommandException("UNITY_UNSAVED_SCENE", "Save scene changes before play.");
                if (head.source_version == "" || head.revision != p.base_revision) throw new SceneOpsCommandException("UNITY_REVISION_CONFLICT", "Read current imported content before play.");
                mark(); EditorSceneManager.OpenScene(SceneOpsContentAssets.ScenePath, OpenSceneMode.Single);
                EditorApplication.isPlaying = true; return false;
            }
            if (p.operation == "exit")
            {
                if (!started)
                {
                    if (head.run_id != p.run_id || head.run_id == "") throw new SceneOpsCommandException("UNITY_RUN_MISMATCH", "Exit belongs to another run.");
                    mark(); Abort(null); EditorApplication.isPlaying = false;
                }
                if (EditorApplication.isPlayingOrWillChangePlaymode) return false;
                head.run_id = ""; SaveHead(root, head); return true;
            }
            var player = Player();
            if (!EditorApplication.isPlaying || player == null || head.run_id == "" || head.run_id != p.run_id)
                throw new SceneOpsCommandException("UNITY_RUN_MISMATCH", "Input requires this managed content run.");
            if (started)
            {
                if (activeRequest != request.request_id) throw new SceneOpsCommandException("UNITY_OUTCOME_UNCERTAIN", "Input was interrupted by reload; inspect its last receipt before continuing.");
                if (!player.ReleaseConfirmed) return false;
                activeRequest = null; return true;
            }
            if (activeRequest != null) throw new SceneOpsCommandException("UNITY_BUSY", "Another bounded input is running.");
            mark(); activeRequest = request.request_id;
            player.Begin(request.request_id, p.input.move_x, p.input.move_z, p.input.interact, p.input.duration_frames); return false;
        }
        internal static SceneOpsContentPlayer Player() => Resources.FindObjectsOfTypeAll<SceneOpsContentPlayer>()
            .FirstOrDefault(p => !EditorUtility.IsPersistent(p) && p.gameObject.scene.path == SceneOpsContentAssets.ScenePath);
        private static AgentReply Success(ContentState state) => new AgentReply { status = "succeeded", resultJson = JsonUtility.ToJson(state) };
        internal static ContentState Read(string root, string session, string[] errors) => SceneOpsContentReadback.Read(root, session, errors);
    }
}

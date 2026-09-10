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
    internal static class SceneOpsPrototypeCommands
    {
        private const string ScenePath = "Assets/SceneOpsPrototype.unity";
        private static string activeRequest;
        private static SceneOpsVoxelSurvival activeGame;
        internal static bool HasActiveAction => activeRequest != null;

        internal static bool TryProcess(AgentRequest request, string root, AgentSessionConfig config, string[] errors, out AgentReply reply)
        {
            reply = null;
            SceneOpsCommandSecurity.ValidateCommand(request.command);
            SceneOpsCommandSecurity.ValidateVersion();
            if (!config.grant.allowed_capabilities.Contains(request.command))
                throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Prototype capability is outside the task grant.");
            if (request.command == "unity.prototype.inspect")
            {
                reply = Success(Read(root, config.session_id, errors));
                return true;
            }
            ValidateAuthorization(request, root, config);
            if (EditorApplication.isCompiling || EditorApplication.isUpdating) return false;
            string marker = SceneOpsCommandSecurity.ResolveInsideProject(root, ".sceneops-agent/" + request.request_id + ".prototype-started.json");
            bool started = File.Exists(marker);
            try
            {
                if (request.command == "unity.prototype.compose")
                {
                    string applied = marker.Replace(".prototype-started.json", ".prototype-applied.json");
                    if (started && File.Exists(applied))
                    {
                        var prior = JsonUtility.FromJson<PrototypeHead>(File.ReadAllText(applied));
                        if (prior.revision_id != request.authorization.change_set_id || prior.base_revision != request.batch.baseVersion)
                            throw new SceneOpsCommandException("UNITY_REVISION_CONFLICT", "Applied receipt belongs to another revision.");
                        SceneOpsPrototypeJournal.RequireCurrent(prior.revision_id, FindGame());
                        var observed = Read(root, config.session_id, errors); observed.effects_reused = true;
                        reply = Success(observed);
                        reply.mode = "cached";
                        return true;
                    }
                    if (started) throw Uncertain();
                    if (EditorApplication.isPlayingOrWillChangePlaymode)
                        throw new SceneOpsCommandException("UNITY_EXIT_PLAY_REQUIRED", "Exit Play Mode before changing the saved prototype specification.");
                    var spec = JsonUtility.FromJson<PrototypeSpec>(request.batch.payloadJson);
                    ValidateSpec(spec);
                    if (request.batch.baseVersion != SceneOpsPrototypeJournal.Read().revision_id)
                        throw new SceneOpsCommandException("UNITY_REVISION_CONFLICT", "Compose base revision is no longer current.");
                    MarkStarted(root, marker, request);
                    started = true;
                    Compose(root, spec, request.authorization.change_set_id);
                    SceneOpsPrototypeJournal.WriteJson(applied, JsonUtility.ToJson(SceneOpsPrototypeJournal.Read()));
                }
                else
                {
                    var payload = JsonUtility.FromJson<PrototypePlayPayload>(request.batch.payloadJson);
                    ValidateInput(payload, request.command);
                    if (!Play(request, payload, root, marker, started)) return false;
                    if (payload.operation == "capture")
                    {
                        var captured = Read(root, config.session_id, errors);
                        captured.artifact_path = Path.Combine(root, "Artifacts", request.request_id + ".png");
                        captured.width = payload.input.width; captured.height = payload.input.height;
                        reply = Success(captured);
                        return true;
                    }
                }
                reply = Success(Read(root, config.session_id, errors));
                return true;
            }
            catch (Exception error)
            {
                Abort(request.request_id);
                bool uncertain = started || File.Exists(marker);
                var typed = error as SceneOpsCommandException;
                reply = new AgentReply { status = "failed", error_code = uncertain ? "UNITY_OUTCOME_UNCERTAIN" : typed?.Code ?? "UNITY_COMMAND_FAILED",
                    cause_code = typed?.Code ?? "UNITY_COMMAND_FAILED", message = error.Message };
                return true;
            }
        }

        internal static void ValidateAuthorization(AgentRequest request, string root, AgentSessionConfig config)
        {
            var auth = request.authorization;
            if (auth == null || auth.capability_id != request.command || auth.session_id != config.session_id ||
                auth.task_id != config.grant.task_id || auth.grant_id != config.grant.grant_id ||
                auth.project_id != config.project_id || auth.workspace_root != config.grant.workspace_root ||
                auth.expires_at != config.grant.expires_at || string.IsNullOrWhiteSpace(auth.action_id) ||
                string.IsNullOrWhiteSpace(auth.approval_id) || string.IsNullOrWhiteSpace(auth.change_set_id) ||
                request.batch == null || request.batch.command != request.command || request.batch.requestId != request.request_id ||
                request.batch.projectRoot != root || request.batch.projectId != config.project_id || request.batch.executionMode != "live" ||
                !Regex.IsMatch(request.request_id, "^[A-Za-z0-9_.-]{1,160}$"))
                throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Prototype action is not bound to this task, project, session and ChangeSet.");
            SceneOpsCommandSecurity.ValidateChangeSet(request.batch);
            var change = JsonUtility.FromJson<ChangeSetEnvelope>(request.batch.changeSetJson);
            if (change.change_set_id != auth.change_set_id)
                throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Prototype ChangeSet ID differs from the authorization record.");
        }

        private static void ValidateSpec(PrototypeSpec spec)
        {
            if (spec == null || !Regex.IsMatch(spec.prototype_id ?? "", "^sobj_[A-Za-z0-9_-]{1,120}$") ||
                string.IsNullOrEmpty(spec.title) || spec.title.Length > 80 || spec.seed < 0 ||
                !In(spec.arena_size, 12, 40) || !In(spec.enemy_count, 1, 12) || !In(spec.enemy_speed, .5f, 3) ||
                !In(spec.player_health, 20, 200) || !In(spec.weapon_damage, 5, 100) || !In(spec.enemy_health, 10, 150) ||
                !In(spec.enemy_damage, 1, 30) || !In(spec.player_speed, 2, 8) || !In(spec.fire_interval, .1f, 1) || !In(spec.goal_kills, 1, 30))
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Prototype specification exceeds its bounded identity/gameplay fields.");
        }

        private static bool In(float value, float minimum, float maximum) => !float.IsNaN(value) && !float.IsInfinity(value) && value >= minimum && value <= maximum;

        private static void ValidateInput(PrototypePlayPayload payload, string command)
        {
            var input = payload?.input;
            if (payload == null || !new[] { "enter", "exit", "reset", "act", "capture" }.Contains(payload.operation) ||
                (payload.operation == "capture") != (command == "unity.prototype.capture") || input == null ||
                !In(input.move_x, -1, 1) || !In(input.move_z, -1, 1) || !In(input.yaw_delta, -180, 180) ||
                !In(input.pitch_delta, -90, 90) || !In(input.duration_frames, 1, 120) ||
                !In(input.width, 320, 1920) || !In(input.height, 240, 1080))
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Prototype input or operation is outside its bounded capability.");
        }

        private static void Compose(string root, PrototypeSpec spec, string revision)
        {
            string absolute = SceneOpsCommandSecurity.ResolveInsideProject(root, ScenePath);
            Scene scene = SceneManager.GetActiveScene();
            if (scene.path != ScenePath && scene.isDirty)
                throw new SceneOpsCommandException("UNITY_UNSAVED_SCENE", "Unrelated scene has unsaved edits; no scene switch was performed.");
            if (scene.path != ScenePath)
                scene = File.Exists(absolute) ? EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single)
                    : EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var game = FindGame();
            if (game == null)
            {
                if (scene.rootCount != 0) throw new SceneOpsCommandException("UNITY_AGENT_SCOPE_DENIED", "Prototype scene contains unowned objects.");
                game = new GameObject("SceneOps Voxel Survival").AddComponent<SceneOpsVoxelSurvival>();
                game.prototype_id = spec.prototype_id;
            }
            if (!string.IsNullOrEmpty(game.prototype_id) && game.prototype_id != spec.prototype_id)
                throw new SceneOpsCommandException("UNITY_IDENTITY_CONFLICT", "Saved prototype belongs to a different stable identity.");
            // Serialize the validated DTO, never overwrite a component from raw client JSON.
            JsonUtility.FromJsonOverwrite(JsonUtility.ToJson(spec), game);
            game.project_revision = revision;
            var identity = game.GetComponent<SceneOpsIdentity>() ?? game.gameObject.AddComponent<SceneOpsIdentity>();
            string suffix = spec.prototype_id.Substring(5);
            SceneOpsIdentityEditorUtility.Apply(identity, spec.prototype_id, "ast_" + suffix, "astv_" + suffix + "_v1", spec.prototype_id, "", "", "sinst_" + suffix);
            EditorUtility.SetDirty(game);
            EditorSceneManager.MarkSceneDirty(scene);
            SceneOpsPrototypeJournal.Saving = true;
            try { SceneOpsAgentPlacement.SaveVerified(scene, root, ScenePath); }
            finally { SceneOpsPrototypeJournal.Saving = false; }
            SceneOpsPrototypeJournal.Write(new PrototypeHead { revision_id = revision,
                base_revision = SceneOpsPrototypeJournal.Read().revision_id, scene_path = ScenePath,
                component_version = SceneOpsVoxelSurvival.ComponentVersion });
        }

        private static bool Play(AgentRequest request, PrototypePlayPayload payload, string root, string marker, bool started)
        {
            string absolute = SceneOpsCommandSecurity.ResolveInsideProject(root, ScenePath);
            if (payload.operation == "enter")
            {
                if (EditorApplication.isPlaying && !EditorApplication.isPlayingOrWillChangePlaymode) return false;
                if (EditorApplication.isPlaying && FindGame() != null && FindGame().GameCamera != null)
                {
                    SceneOpsPrototypeJournal.RequireCurrent(payload.expected_revision, FindGame());
                    FindGame().BindRun(request.request_id, payload.expected_revision);
                    var head = SceneOpsPrototypeJournal.Read(); head.run_id = request.request_id; head.phase = "RUNNING"; SceneOpsPrototypeJournal.Write(head);
                    return true;
                }
                if (!started)
                {
                    if (!File.Exists(absolute)) throw new SceneOpsCommandException("UNITY_MISSING_REFERENCE", "Compose the prototype scene before entering Play Mode.");
                    if (SceneManager.GetActiveScene().isDirty && SceneManager.GetActiveScene().path != ScenePath)
                        throw new SceneOpsCommandException("UNITY_UNSAVED_SCENE", "Unrelated scene has unsaved edits; no scene switch was performed.");
                    EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
                    SceneOpsPrototypeJournal.RequireCurrent(payload.expected_revision, FindGame());
                    MarkStarted(root, marker, request);
                    var head = SceneOpsPrototypeJournal.Read(); head.run_id = request.request_id; head.phase = "ENTERING_PLAY"; SceneOpsPrototypeJournal.Write(head);
                    EditorApplication.isPlaying = true;
                }
                return false;
            }
            if (payload.operation == "exit")
            {
                Abort(null);
                if (!EditorApplication.isPlaying && !EditorApplication.isPlayingOrWillChangePlaymode)
                { var head = SceneOpsPrototypeJournal.Read(); head.phase = "CLOSED"; SceneOpsPrototypeJournal.Write(head); return true; }
                if (!started) { MarkStarted(root, marker, request); EditorApplication.isPlaying = false; }
                return false;
            }
            var game = FindGame();
            if (!EditorApplication.isPlaying || game == null)
                throw new SceneOpsCommandException("UNITY_PLAY_REQUIRED", "This action requires the actual prototype in Play Mode.");
            SceneOpsPrototypeJournal.RequireCurrent(payload.expected_revision, game);
            if (payload.run_id != game.ActiveRunId)
                throw new SceneOpsCommandException("UNITY_RUN_MISMATCH", "Input/capture belongs to another run.");
            if (payload.operation == "act" || payload.operation == "reset")
            {
                if (started && activeRequest != request.request_id) throw Uncertain();
                if (!started)
                {
                    if (activeRequest != null) throw new SceneOpsCommandException("UNITY_BUSY", "Another bounded player action is running.");
                    MarkStarted(root, marker, request);
                    activeRequest = request.request_id; activeGame = game;
                    game.AgentControlled = true;
                    var input = new SurvivalInputFrame { move_x = payload.input.move_x, move_z = payload.input.move_z,
                        yaw_delta = payload.input.yaw_delta, pitch_delta = payload.input.pitch_delta,
                        fire = payload.input.fire, jump = payload.input.jump, restart = payload.operation == "reset" };
                    game.InputDriver.Begin(request.request_id, payload.run_id, payload.operation == "reset" ? 1 : payload.input.duration_frames, input);
                }
                if (!game.InputDriver.Receipt.release_confirmed) return false;
                Abort(request.request_id);
                return true;
            }
            if (started) throw Uncertain();
            MarkStarted(root, marker, request);
            Capture(root, request.request_id, payload.input, game);
            return true;
        }

        internal static void Abort(string requestId)
        {
            if (requestId != null && activeRequest != requestId) return;
            if (activeGame != null) activeGame.InputDriver.Cancel();
            activeGame = null; activeRequest = null;
        }

        private static void Capture(string root, string requestId, PrototypeInput input, SceneOpsVoxelSurvival game)
        {
            Camera camera = game.GameCamera;
            if (camera == null) throw new SceneOpsCommandException("UNITY_MISSING_REFERENCE", "Prototype has no active main camera.");
            string output = SceneOpsCommandSecurity.ResolveInsideProject(root, "Artifacts/" + requestId + ".png");
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            var render = new RenderTexture(input.width, input.height, 24);
            var pixels = new Texture2D(input.width, input.height, TextureFormat.RGB24, false);
            var previousTarget = camera.targetTexture;
            var previousActive = RenderTexture.active;
            try
            {
                camera.targetTexture = render; camera.Render(); RenderTexture.active = render;
                pixels.ReadPixels(new Rect(0, 0, input.width, input.height), 0, 0); pixels.Apply();
                using (var file = new FileStream(output, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                { byte[] png = pixels.EncodeToPNG(); file.Write(png, 0, png.Length); file.Flush(true); }
                if (!File.Exists(output) || new FileInfo(output).Length == 0)
                    throw new SceneOpsCommandException("UNITY_CAPTURE_FAILED", "Prototype camera capture was not durably written.");
            }
            finally
            {
                camera.targetTexture = previousTarget; RenderTexture.active = previousActive;
                UnityEngine.Object.DestroyImmediate(pixels); UnityEngine.Object.DestroyImmediate(render);
            }
        }

        private static SceneOpsVoxelSurvival FindGame() => Resources.FindObjectsOfTypeAll<SceneOpsVoxelSurvival>()
            .FirstOrDefault(game => !EditorUtility.IsPersistent(game) && game.gameObject.scene.path == ScenePath);

        private static PrototypeReadback Read(string root, string sessionId, string[] errors)
        {
            SceneOpsCommandSecurity.ResolveInsideProject(root, ScenePath);
            var game = FindGame();
            string stateJson = JsonUtility.ToJson(new PrototypeUnavailableState());
            string specJson = "{}";
            if (game != null)
            {
                specJson = JsonUtility.ToJson(CaptureSpec(game));
                stateJson = EditorApplication.isPlaying
                    ? game.CaptureStateJson()
                    : JsonUtility.ToJson(new PrototypeUnavailableState {
                        prototype_id = game.prototype_id, health = game.player_health,
                        goal_kills = game.goal_kills
                    });
            }
            return new PrototypeReadback { session_id = sessionId, scene_path = SceneManager.GetActiveScene().path,
                project_revision = SceneOpsPrototypeJournal.Read().revision_id,
                run_id = SceneOpsPrototypeJournal.Read().run_id,
                component_package_version = SceneOpsVoxelSurvival.ComponentVersion,
                revision_drift = SceneOpsPrototypeJournal.Read().drifted,
                effect_state = SceneOpsPrototypeJournal.Read().revision_id == "empty" ? "NONE" : "COMMITTED",
                capture_kind = "camera_render",
                playing = EditorApplication.isPlaying, compiling = EditorApplication.isCompiling || EditorApplication.isUpdating,
                frame_count = Time.frameCount, prototype_exists = game != null, errors = errors,
                state_json = stateJson, spec_json = specJson };
        }

        private static PrototypeSpec CaptureSpec(SceneOpsVoxelSurvival game) => new PrototypeSpec {
            prototype_id = game.prototype_id, title = game.title, seed = game.seed,
            arena_size = game.arena_size, enemy_count = game.enemy_count,
            enemy_speed = game.enemy_speed, player_health = game.player_health,
            weapon_damage = game.weapon_damage, enemy_health = game.enemy_health,
            enemy_damage = game.enemy_damage, player_speed = game.player_speed,
            fire_interval = game.fire_interval, goal_kills = game.goal_kills
        };

        private static void MarkStarted(string root, string marker, AgentRequest request) => SceneOpsAgentConnection.WriteReply(root, marker,
            new AgentReply { status = "APPLYING", message = request.authorization.action_id });
        private static SceneOpsCommandException Uncertain() => new SceneOpsCommandException("UNITY_OUTCOME_UNCERTAIN", "Prototype action previously started without a durable result; inspect actual gameplay before a new approved action.");
        private static AgentReply Success(PrototypeReadback state) => new AgentReply { status = "succeeded", resultJson = JsonUtility.ToJson(state) };
    }
}

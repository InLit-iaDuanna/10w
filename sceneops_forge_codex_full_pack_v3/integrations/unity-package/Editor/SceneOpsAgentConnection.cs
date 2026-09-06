using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SceneOps.Forge.Unity.Editor
{
    // The mailbox is owner-only, outside Assets, and exists only in an app-created project.
    // No network listener, evaluation, reflection command or arbitrary script entry point is exposed.
    [InitializeOnLoad]
    internal static class SceneOpsAgentConnection
    {
        private static readonly string Root = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        private static readonly string Mailbox = Path.Combine(Root, ".sceneops-agent");
        private static AgentSessionConfig config;
        private static readonly List<string> Errors = new List<string>();
        private static double nextCheck;

        static SceneOpsAgentConnection()
        {
            if (!IsDedicatedProject(Root)) return;
            config = JsonUtility.FromJson<AgentSessionConfig>(File.ReadAllText(Path.Combine(Mailbox, "session.json")));
            if (config == null || config.closed || config.project_root != Root || string.IsNullOrWhiteSpace(config.token)) return;
            Application.logMessageReceived += (message, stack, type) => {
                if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert)
                {
                    Errors.Add(message.Replace(config.token, "[redacted]"));
                    if (Errors.Count > 50) Errors.RemoveAt(0);
                }
            };
            EditorApplication.update += Update;
        }

        internal static bool IsDedicatedProject(string root)
        {
            string marker = Path.Combine(root, ".sceneops-agent", "session.json");
            if (!File.Exists(marker)) return false;
            SceneOpsCommandSecurity.ResolveInsideProject(root, marker);
            AgentSessionConfig value = JsonUtility.FromJson<AgentSessionConfig>(File.ReadAllText(marker));
            return value != null && value.project_root == Path.GetFullPath(root) && value.created_by == "sceneops-agent-v1";
        }

        private static void Update()
        {
            if (!SceneOpsPrototypeCommands.HasActiveAction && EditorApplication.timeSinceStartup < nextCheck) return;
            nextCheck = EditorApplication.timeSinceStartup + .1;
            foreach (string file in Directory.GetFiles(Mailbox, "*.request.json")) Process(file);
        }

        private static void Process(string file)
        {
            string resultPath = SceneOpsCommandSecurity.ResolveInsideProject(Root, file.Replace(".request.json", ".result.json"));
            if (File.Exists(resultPath)) return;
            AgentRequest request = null;
            AgentReply reply;
            bool mutationStarted = false;
            bool authenticated = false;
            try
            {
                SceneOpsCommandSecurity.ResolveInsideProject(Root, file);
                request = JsonUtility.FromJson<AgentRequest>(File.ReadAllText(file));
                if (request == null || request.token != config.token || request.session_id != config.session_id)
                    throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Session authentication failed.");
                authenticated = true;
                if (config.grant == null || !DateTimeOffset.TryParse(config.grant.expires_at, out var expires) ||
                    expires <= DateTimeOffset.UtcNow || config.grant.project_id != config.project_id ||
                    config.grant.workspace_root != Directory.GetParent(Root).FullName)
                    throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Bound task grant is expired or outside the connected workspace.");
                if (File.Exists(file.Replace(".request.json", ".cancelled.json")))
                {
                    SceneOpsPrototypeCommands.Abort(request.request_id);
                    throw new SceneOpsCommandException("UNITY_CANCELLED", "The request was cancelled before completion.");
                }
                if (request.command != null && request.command.StartsWith("unity.prototype.", StringComparison.Ordinal))
                {
                    if (!SceneOpsPrototypeCommands.TryProcess(request, Root, config, Errors.ToArray(), out reply)) return;
                }
                else if (request.command == "inspect")
                {
                    if (!config.grant.allowed_capabilities.Contains("unity.scene.inspect") && !config.grant.allowed_capabilities.Contains("unity.prototype.inspect"))
                        throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Scene reading is outside the bound task grant.");
                    SceneOpsCommandSecurity.ValidateVersion();
                    string saved = "Assets/SceneOpsAgent.unity";
                    string savedAbsolute = SceneOpsCommandSecurity.ResolveInsideProject(Root, saved);
                    if (!EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                        SceneManager.GetActiveScene().path == "" && File.Exists(savedAbsolute))
                        EditorSceneManager.OpenScene(saved, OpenSceneMode.Single);
                    reply = new AgentReply { status = "succeeded", resultJson = JsonUtility.ToJson(new AgentState {
                        session_id = config.session_id, project_root = Root, editor_version = Application.unityVersion,
                        compiling = EditorApplication.isCompiling || EditorApplication.isUpdating,
                        capabilities = EditorApplication.isCompiling || EditorApplication.isUpdating ? Array.Empty<string>() :
                            ConnectedCapabilities(config.grant.allowed_capabilities),
                        pid = System.Diagnostics.Process.GetCurrentProcess().Id, scene_path = SceneManager.GetActiveScene().path,
                        objects = SceneOpsAgentPlacement.Objects(), errors = Errors.ToArray() }) };
                }
                else if (request.command == "unity.asset.import")
                {
                    if (EditorApplication.isCompiling || EditorApplication.isUpdating) return;
                    if (request.authorization == null || request.authorization.capability_id != "unity.asset.import" ||
                        !config.grant.allowed_capabilities.Contains(request.authorization.capability_id) ||
                        request.authorization.task_id != config.grant.task_id || request.authorization.grant_id != config.grant.grant_id ||
                        request.authorization.project_id != config.grant.project_id || request.authorization.workspace_root != config.grant.workspace_root ||
                        request.authorization.expires_at != config.grant.expires_at ||
                        request.authorization.session_id != config.session_id ||
                        string.IsNullOrWhiteSpace(request.authorization.action_id) ||
                        string.IsNullOrWhiteSpace(request.authorization.task_id) || string.IsNullOrWhiteSpace(request.authorization.grant_id) ||
                        string.IsNullOrWhiteSpace(request.authorization.approval_id) || request.batch == null)
                        throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "Task grant is not bound to this import session.");
                    if (request.batch.command != request.command || request.batch.projectRoot != Root ||
                        request.batch.projectId != config.project_id || request.batch.requestId != request.request_id)
                        throw new SceneOpsCommandException("UNITY_AGENT_SCOPE_DENIED", "Command does not match the connected project.");
                    var change = JsonUtility.FromJson<ChangeSetEnvelope>(request.batch.changeSetJson);
                    if (change.change_set_id != request.authorization.change_set_id)
                        throw new SceneOpsCommandException("UNITY_AGENT_AUTH_DENIED", "ChangeSet does not match task authorization.");
                    string startedPath = SceneOpsCommandSecurity.ResolveInsideProject(Root, file.Replace(".request.json", ".started.json"));
                    if (File.Exists(startedPath))
                        throw new SceneOpsCommandException("UNITY_OUTCOME_UNCERTAIN", "A previous import started without a durable result; inspect the saved project before recovery.");
                    // Compilation leaves the original request queued. Once dispatch begins, a crash
                    // cannot silently replay a partially applied cross-system mutation.
                    WriteReply(Root, startedPath, new AgentReply { status = "started", message = request.authorization.action_id });
                    mutationStarted = true;
                    BatchCommandResult result = SceneOpsBatchCommandRouter.Run(request.batch);
                    reply = new AgentReply { status = result.status, resultJson = result.resultJson,
                        error_code = result.errorCode, message = result.message };
                }
                else throw new SceneOpsCommandException("UNITY_COMMAND_NOT_ALLOWED", "Agent session command is not allowlisted.");
            }
            catch (SceneOpsCommandException error)
            { if (authenticated) SceneOpsPrototypeCommands.Abort(request.request_id);
              reply = new AgentReply { status = "failed", error_code = mutationStarted ? "UNITY_OUTCOME_UNCERTAIN" : error.Code,
                message = error.Message, cause_code = error.Code }; }
            catch (Exception error)
            { if (authenticated) SceneOpsPrototypeCommands.Abort(request.request_id);
              reply = new AgentReply { status = "failed", error_code = mutationStarted ? "UNITY_OUTCOME_UNCERTAIN" : "UNITY_COMMAND_FAILED", message = error.Message }; }
            WriteReply(Root, resultPath, reply);
        }

        private static string[] ConnectedCapabilities(string[] granted)
        {
            var supported = new HashSet<string>(StringComparer.Ordinal) {
                "unity.asset.import", "unity.scene.inspect", "unity.prototype.compose",
                "unity.prototype.inspect", "unity.prototype.play", "unity.prototype.capture"
            };
            return (granted ?? Array.Empty<string>()).Where(supported.Contains).ToArray();
        }

        internal static void WriteReply(string root, string resultPath, AgentReply reply)
        {
            resultPath = SceneOpsCommandSecurity.ResolveInsideProject(root, resultPath);
            string temporary = SceneOpsCommandSecurity.ResolveInsideProject(root, resultPath + "." + Guid.NewGuid().ToString("N") + ".tmp");
            using (var file = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            using (var writer = new StreamWriter(file))
            {
                writer.Write(JsonUtility.ToJson(reply));
                writer.Flush();
                file.Flush(true);
            }
            File.Move(temporary, resultPath);
        }
    }
    [Serializable] internal sealed class AgentSessionConfig
    { public string token, session_id, project_id, project_root, created_by; public AgentGrant grant; public bool closed; }
    [Serializable] internal sealed class AgentGrant
    { public string task_id, grant_id, project_id, workspace_root, expires_at; public string[] allowed_capabilities; }
    [Serializable] internal sealed class AgentAuthorization
    { public string task_id, grant_id, action_id, change_set_id, approval_id, capability_id, session_id, project_id, workspace_root, expires_at; }
    [Serializable] internal sealed class AgentRequest
    { public string token, session_id, request_id, command; public AgentAuthorization authorization; public BatchCommandRequest batch; }
    [Serializable] internal sealed class AgentReply
    { public string status, resultJson, error_code, cause_code, message; public string mode = "live"; }
    [Serializable] internal sealed class AgentState
    {
        public string session_id, project_root, editor_version, scene_path;
        public bool connected = true, compiling = false;
        public int pid;
        public AgentObject[] objects;
        public string[] errors;
        public string[] capabilities = { "unity.asset.import", "unity.game_object.inspect", "unity.console.read" };
    }
}

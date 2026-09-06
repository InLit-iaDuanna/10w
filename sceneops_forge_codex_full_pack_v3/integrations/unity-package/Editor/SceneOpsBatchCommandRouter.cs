using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace SceneOps.Forge.Unity.Editor
{
    public static class SceneOpsBatchCommandRouter
    {
        public static void Execute()
        {
            string requestPath = Argument("-sceneopsRequest");
            string resultPath = Argument("-sceneopsResult");
            BatchCommandRequest request = null;
            BatchCommandResult result;
            try
            {
                request = JsonUtility.FromJson<BatchCommandRequest>(File.ReadAllText(requestPath));
                if (request == null)
                {
                    throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Command request is empty.");
                }
                result = Run(request);
            }
            catch (SceneOpsCommandException exception)
            {
                result = Failure(request, exception.Code, exception.Message, exception.Retryable);
            }
            catch (Exception exception)
            {
                result = Failure(request, "UNITY_COMMAND_FAILED", exception.ToString(), false);
            }
            Write(resultPath, result);
            if (!string.Equals(result.status, "succeeded", StringComparison.Ordinal))
            {
                Debug.LogError($"SceneOps Unity command failed: {result.errorCode}: {result.message}");
            }
        }

        internal static BatchCommandResult Run(BatchCommandRequest request)
        {
            SceneOpsCommandSecurity.ValidateCommand(request.command);
            SceneOpsCommandSecurity.ValidateVersion();
            string projectRoot = SceneOpsCommandSecurity.ValidateProjectRoot(request.projectRoot);
            if (!string.Equals(request.executionMode, "live", StringComparison.Ordinal))
            {
                throw new SceneOpsCommandException(
                    "UNITY_INVALID_EXECUTION_MODE",
                    "The Unity package executes only live commands; cached and mock modes stay in the adapter.");
            }
            SceneOpsCommandSecurity.ValidateChangeSet(request);
            string data = Dispatch(
                request.command, request.payloadJson, projectRoot, request.projectId);
            return new BatchCommandResult
            {
                requestId = request.requestId,
                command = request.command,
                status = "succeeded",
                mode = "live",
                message = "Unity command completed.",
                resultJson = data,
                logs = new[]
                {
                    Log("info", "UNITY_COMMAND_COMPLETED", $"{request.command} completed."),
                },
            };
        }

        private static string Dispatch(
            string command,
            string payloadJson,
            string projectRoot,
            string projectId)
        {
            switch (command)
            {
                case "unity.prototype.compose":
                case "unity.prototype.inspect":
                case "unity.prototype.play":
                case "unity.prototype.capture":
                    throw new SceneOpsCommandException("UNITY_CONNECTED_EDITOR_REQUIRED", "Prototype commands require the authenticated persistent Editor session.");
                case "unity.health":
                    return SceneOpsUnityInspectionCommands.Health();
                case "unity.project.scan":
                    return SceneOpsUnityInspectionCommands.ScanProject(payloadJson);
                case "unity.asset.import":
                    return SceneOpsUnityAssetCommands.ImportAsset(
                        payloadJson, projectRoot, projectId);
                case "unity.identity.map":
                    return SceneOpsUnityAssetCommands.MapIdentity(payloadJson);
                case "unity.prefab.upsert":
                    return SceneOpsUnityAssetCommands.UpsertPrefab(payloadJson, projectRoot);
                case "unity.game_object.inspect":
                    return SceneOpsUnityInspectionCommands.InspectGameObject(payloadJson);
                case "unity.component_property.set":
                    return SceneOpsUnityMutationCommands.SetComponentProperty(payloadJson);
                case "unity.collider.upsert":
                    return SceneOpsUnityMutationCommands.UpsertCollider(payloadJson);
                case "unity.navmesh.run":
                    return SceneOpsUnityExecutionCommands.RunNavMesh(payloadJson, projectRoot);
                case "unity.play.enter":
                    return SceneOpsUnityExecutionCommands.EnterPlay(payloadJson);
                case "unity.play.exit":
                    return SceneOpsUnityExecutionCommands.ExitPlay();
                case "unity.capture":
                    return SceneOpsUnityExecutionCommands.Capture(payloadJson, projectRoot);
                case "unity.console.read":
                    return SceneOpsUnityExecutionCommands.ReadConsole(payloadJson);
                case "unity.tests.run":
                    throw new SceneOpsCommandException(
                        "UNITY_TEST_RUNNER_REQUIRED",
                        "Use the typed adapter test-runner path for Edit Mode or Play Mode tests.");
                case "unity.profiler.snapshot":
                    return SceneOpsUnityExecutionCommands.SnapshotProfiler(payloadJson, projectRoot);
                case "unity.build.run":
                    return SceneOpsUnityExecutionCommands.Build(payloadJson, projectRoot);
                default:
                    throw new SceneOpsCommandException(
                        "UNITY_COMMAND_NOT_ALLOWED", $"Command '{command}' is not allowlisted.");
            }
        }

        private static BatchCommandResult Failure(
            BatchCommandRequest request,
            string code,
            string message,
            bool retryable)
        {
            return new BatchCommandResult
            {
                requestId = request?.requestId ?? string.Empty,
                command = request?.command ?? string.Empty,
                status = "failed",
                mode = "live",
                message = message,
                errorCode = code,
                retryable = retryable,
                logs = new[] { Log("error", code, message) },
            };
        }

        private static SceneOpsCommandLog Log(string level, string code, string message)
        {
            return new SceneOpsCommandLog
            {
                level = level,
                code = code,
                message = message,
                occurredAt = DateTime.UtcNow.ToString("O"),
            };
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
            throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", $"Missing required argument {name}.");
        }

        private static void Write(string path, BatchCommandResult result)
        {
            string directory = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }
            File.WriteAllText(path, JsonUtility.ToJson(result, true));
        }
    }
}

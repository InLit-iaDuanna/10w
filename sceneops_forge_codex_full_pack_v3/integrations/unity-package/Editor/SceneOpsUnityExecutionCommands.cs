using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Profiling;

namespace SceneOps.Forge.Unity.Editor
{
    internal static class SceneOpsUnityExecutionCommands
    {
        internal static string RunNavMesh(string payloadJson, string projectRoot)
        {
            NavMeshPayload payload = JsonUtility.FromJson<NavMeshPayload>(payloadJson);
            if (payload == null || string.IsNullOrWhiteSpace(payload.scene_asset_path))
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "NavMesh payload is required.");
            }
            SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, payload.scene_asset_path);
            if (!File.Exists(Path.Combine(projectRoot, payload.scene_asset_path)))
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE", "NavMesh scene asset does not exist.");
            }
            EditorSceneManager.OpenScene(payload.scene_asset_path, OpenSceneMode.Single);
            if (string.Equals(payload.operation, "bake", StringComparison.Ordinal))
            {
                InvokeNavMeshBuilder("BuildNavMesh");
            }
            else if (string.Equals(payload.operation, "clear", StringComparison.Ordinal))
            {
                InvokeNavMeshBuilder("ClearAllNavMeshes");
            }
            else if (!string.Equals(payload.operation, "validate", StringComparison.Ordinal))
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Unknown NavMesh operation.");
            }
            NavMeshTriangulation triangulation = NavMesh.CalculateTriangulation();
            return JsonUtility.ToJson(new NavMeshResult
            {
                operation = payload.operation,
                triangulationVertices = triangulation.vertices?.Length ?? 0,
                executionMode = "live",
            });
        }

        internal static string EnterPlay(string payloadJson)
        {
            if (Application.isBatchMode)
            {
                throw new SceneOpsCommandException(
                    "UNITY_CONNECTED_EDITOR_REQUIRED",
                    "Entering Play Mode requires a connected interactive Unity Editor.",
                    true);
            }
            PlayPayload payload = JsonUtility.FromJson<PlayPayload>(payloadJson) ?? new PlayPayload();
            if (!string.IsNullOrWhiteSpace(payload.scene_asset_path))
            {
                EditorSceneManager.OpenScene(payload.scene_asset_path, OpenSceneMode.Single);
            }
            EditorApplication.isPlaying = true;
            return JsonUtility.ToJson(new PlayResult { playState = "entering", executionMode = "live" });
        }

        internal static string ExitPlay()
        {
            EditorApplication.isPlaying = false;
            return JsonUtility.ToJson(new PlayResult { playState = "exiting", executionMode = "live" });
        }

        internal static string Capture(string payloadJson, string projectRoot)
        {
            CapturePayload payload = JsonUtility.FromJson<CapturePayload>(payloadJson);
            if (payload == null || payload.width < 64 || payload.height < 64)
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Capture dimensions are invalid.");
            }
            if (!EditorApplication.isPlaying)
            {
                throw new SceneOpsCommandException(
                    "UNITY_CONNECTED_EDITOR_REQUIRED", "Capture requires an active Play Mode session.", true);
            }
            string output = SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, payload.output_path);
            Directory.CreateDirectory(Path.GetDirectoryName(output) ?? projectRoot);
            ScreenCapture.CaptureScreenshot(output);
            return JsonUtility.ToJson(new CaptureResult
            {
                artifactPath = payload.output_path,
                width = payload.width,
                height = payload.height,
                executionMode = "live",
            });
        }

        internal static string ReadConsole(string payloadJson)
        {
            ReadConsolePayload payload = JsonUtility.FromJson<ReadConsolePayload>(payloadJson)
                ?? new ReadConsolePayload();
            string logPath = Application.consoleLogPath;
            string[] entries = File.Exists(logPath)
                ? File.ReadLines(logPath).TakeLast(Math.Max(1, payload.max_entries)).ToArray()
                : Array.Empty<string>();
            return JsonUtility.ToJson(new ConsoleResult
            {
                logPath = logPath,
                entries = entries,
                executionMode = "live",
            });
        }

        internal static string SnapshotProfiler(string payloadJson, string projectRoot)
        {
            ProfilerPayload payload = JsonUtility.FromJson<ProfilerPayload>(payloadJson)
                ?? new ProfilerPayload();
            string output = SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, payload.output_path);
            ProfilerResult result = new ProfilerResult
            {
                totalAllocatedBytes = Profiler.GetTotalAllocatedMemoryLong(),
                totalReservedBytes = Profiler.GetTotalReservedMemoryLong(),
                monoUsedBytes = Profiler.GetMonoUsedSizeLong(),
                sampleFrames = payload.sample_frames,
                outputPath = payload.output_path,
                executionMode = "live",
            };
            Directory.CreateDirectory(Path.GetDirectoryName(output) ?? projectRoot);
            File.WriteAllText(output, JsonUtility.ToJson(result, true));
            return JsonUtility.ToJson(result);
        }

        internal static string Build(string payloadJson, string projectRoot)
        {
            BuildPayload payload = JsonUtility.FromJson<BuildPayload>(payloadJson);
            if (payload == null || string.IsNullOrWhiteSpace(payload.build_id) ||
                payload.scenes == null || payload.scenes.Length == 0)
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Build payload is incomplete.");
            }
            foreach (string scene in payload.scenes)
            {
                SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, scene);
                if (!File.Exists(Path.Combine(projectRoot, scene)))
                {
                    throw new SceneOpsCommandException(
                        "UNITY_MISSING_REFERENCE", $"Build scene '{scene}' does not exist.");
                }
            }
            string output = SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, payload.output_path);
            Directory.CreateDirectory(Path.GetDirectoryName(output) ?? projectRoot);
            BuildPlayerOptions options = new BuildPlayerOptions
            {
                scenes = payload.scenes,
                locationPathName = output,
                target = BuildTarget(payload.target),
                options = payload.development ? BuildOptions.Development : BuildOptions.None,
            };
            BuildReport report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            {
                throw new SceneOpsCommandException(
                    "UNITY_BUILD_FAILED",
                    $"Unity build failed with result {report.summary.result}; " +
                    $"{report.summary.totalErrors} errors, {report.summary.totalWarnings} warnings.");
            }
            return JsonUtility.ToJson(new BuildResult
            {
                buildId = payload.build_id,
                profile = payload.profile,
                outputPath = payload.output_path,
                result = report.summary.result.ToString(),
                totalSizeBytes = report.summary.totalSize,
                unityVersion = Application.unityVersion,
                executionMode = "live",
            });
        }

        private static BuildTarget BuildTarget(string target)
        {
            switch (target)
            {
                case "StandaloneOSX": return UnityEditor.BuildTarget.StandaloneOSX;
                case "StandaloneWindows64": return UnityEditor.BuildTarget.StandaloneWindows64;
                case "StandaloneLinux64": return UnityEditor.BuildTarget.StandaloneLinux64;
                case "WebGL": return UnityEditor.BuildTarget.WebGL;
                default:
                    throw new SceneOpsCommandException(
                        "UNITY_INVALID_PAYLOAD", $"Build target '{target}' is unsupported.");
            }
        }

        private static void InvokeNavMeshBuilder(string methodName)
        {
            Type builder = Type.GetType("UnityEditor.AI.NavMeshBuilder, UnityEditor")
                ?? Type.GetType("UnityEditor.AI.NavMeshBuilder, UnityEditor.AIModule");
            MethodInfo method = builder?.GetMethod(methodName, BindingFlags.Public | BindingFlags.Static);
            if (method == null)
            {
                throw new SceneOpsCommandException(
                    "UNITY_NAVMESH_UNAVAILABLE", "Unity NavMesh editor tooling is unavailable.");
            }
            method.Invoke(null, null);
        }
    }
}

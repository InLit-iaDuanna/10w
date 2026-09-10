using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace SceneOps.Forge.Unity.Editor
{
    public sealed class SceneOpsCommandException : Exception
    {
        public string Code { get; }
        public bool Retryable { get; }

        public SceneOpsCommandException(string code, string message, bool retryable = false)
            : base(message)
        {
            Code = code;
            Retryable = retryable;
        }
    }

    internal static class SceneOpsCommandSecurity
    {
        internal static readonly HashSet<string> CommandAllowlist = new HashSet<string>(StringComparer.Ordinal)
        {
            "unity.content.import", "unity.content.inspect", "unity.content.edit", "unity.content.focus", "unity.content.save", "unity.content.play",
            "unity.prototype.compose", "unity.prototype.inspect", "unity.prototype.play", "unity.prototype.capture",
            "unity.health",
            "unity.project.scan",
            "unity.asset.import",
            "unity.identity.map",
            "unity.prefab.upsert",
            "unity.game_object.inspect",
            "unity.component_property.set",
            "unity.collider.upsert",
            "unity.navmesh.run",
            "unity.play.enter",
            "unity.play.exit",
            "unity.capture",
            "unity.console.read",
            "unity.tests.run",
            "unity.profiler.snapshot",
            "unity.build.run",
        };

        internal static readonly HashSet<string> MutatingCommands = new HashSet<string>(StringComparer.Ordinal)
        {
            "unity.content.import", "unity.content.edit", "unity.content.focus", "unity.content.save", "unity.content.play",
            "unity.prototype.compose", "unity.prototype.play", "unity.prototype.capture",
            "unity.asset.import",
            "unity.identity.map",
            "unity.prefab.upsert",
            "unity.component_property.set",
            "unity.collider.upsert",
            "unity.navmesh.run",
            "unity.play.enter",
            "unity.play.exit",
            "unity.capture",
            "unity.build.run",
        };

        internal static readonly HashSet<string> ApprovalCommands = new HashSet<string>(StringComparer.Ordinal)
        {
            "unity.content.import", "unity.content.edit", "unity.content.focus", "unity.content.save", "unity.content.play",
            "unity.prototype.compose", "unity.prototype.play", "unity.prototype.capture",
            "unity.asset.import",
            "unity.identity.map",
            "unity.prefab.upsert",
            "unity.component_property.set",
            "unity.collider.upsert",
            "unity.navmesh.run",
            "unity.build.run",
        };

        internal static readonly Dictionary<string, HashSet<string>> ComponentPropertyAllowlist =
            new Dictionary<string, HashSet<string>>(StringComparer.Ordinal)
            {
                ["Transform"] = Set("m_LocalPosition", "m_LocalRotation", "m_LocalScale"),
                ["BoxCollider"] = Set("m_IsTrigger", "m_Center", "m_Size"),
                ["SphereCollider"] = Set("m_IsTrigger", "m_Center", "m_Radius"),
                ["CapsuleCollider"] = Set("m_IsTrigger", "m_Center", "m_Radius", "m_Height", "m_Direction"),
                ["MeshCollider"] = Set("m_IsTrigger", "m_Convex"),
                ["Rigidbody"] = Set("m_Mass", "m_Drag", "m_AngularDrag", "m_UseGravity", "m_IsKinematic"),
                ["Light"] = Set("m_Intensity", "m_Range", "m_Color"),
            };

        private static readonly HashSet<string> ModelImportExtensions =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                ".3ds",
                ".dae",
                ".dxf",
                ".fbx",
                ".obj",
            };

        internal static void ValidateCommand(string command)
        {
            if (!CommandAllowlist.Contains(command))
            {
                throw new SceneOpsCommandException(
                    "UNITY_COMMAND_NOT_ALLOWED",
                    $"Command '{command}' is not on the Unity command allowlist.");
            }
        }

        internal static string ValidateProjectRoot(string requestedRoot)
        {
            string actual = NormalizePath(Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty);
            string requested = NormalizePath(requestedRoot);
            if (!string.Equals(actual, requested, PathComparison()))
            {
                throw new SceneOpsCommandException(
                    "UNITY_PATH_OUTSIDE_PROJECT",
                    "Command project root does not match the Unity project opened by the editor.");
            }
            return actual;
        }

        internal static string ResolveInsideProject(string projectRoot, string path)
        {
            string candidate = Path.IsPathRooted(path)
                ? NormalizePath(path)
                : NormalizePath(Path.Combine(projectRoot, path));
            string normalizedRoot = NormalizePath(projectRoot);
            string prefix = normalizedRoot + Path.DirectorySeparatorChar;
            if (!candidate.StartsWith(prefix, PathComparison()) &&
                !string.Equals(candidate, normalizedRoot, PathComparison()))
            {
                throw new SceneOpsCommandException(
                    "UNITY_PATH_OUTSIDE_PROJECT",
                    $"Path '{path}' resolves outside the configured Unity project root.");
            }
            RejectSymlinkSegments(candidate, normalizedRoot);
            return candidate;
        }

        internal static void ValidateChangeSet(BatchCommandRequest request)
        {
            if (!MutatingCommands.Contains(request.command))
            {
                return;
            }
            if (string.IsNullOrWhiteSpace(request.changeSetJson))
            {
                throw new SceneOpsCommandException(
                    "UNITY_CHANGESET_REQUIRED",
                    $"Command '{request.command}' requires a typed ChangeSet.");
            }
            ChangeSetEnvelope changeSet = JsonUtility.FromJson<ChangeSetEnvelope>(request.changeSetJson);
            if (changeSet == null || string.IsNullOrWhiteSpace(changeSet.change_set_id))
            {
                throw new SceneOpsCommandException("UNITY_CHANGESET_REQUIRED", "ChangeSet is invalid.");
            }
            if (!string.Equals(changeSet.base_version, request.baseVersion, StringComparison.Ordinal))
            {
                throw new SceneOpsCommandException(
                    "UNITY_BASE_VERSION_MISMATCH",
                    "ChangeSet base version does not match the command base version.");
            }
            if (!string.Equals(changeSet.command, request.command, StringComparison.Ordinal) ||
                changeSet.target_object_ids == null || changeSet.target_object_ids.Length == 0 ||
                !string.Equals(
                    changeSet.proposed_payload_json,
                    request.payloadJson,
                    StringComparison.Ordinal))
            {
                throw new SceneOpsCommandException(
                    "UNITY_CHANGESET_MISMATCH",
                    "ChangeSet command, targets, or approved payload do not match the request.");
            }
            if (ApprovalCommands.Contains(request.command) &&
                !string.Equals(changeSet.approval_state, "approved", StringComparison.Ordinal))
            {
                throw new SceneOpsCommandException(
                    "UNITY_APPROVAL_REQUIRED",
                    $"Command '{request.command}' requires explicit ChangeSet approval.");
            }
        }

        internal static void ValidateModelImportPaths(
            string sourcePath,
            string destinationAssetPath,
            string manifestPath)
        {
            string sourceExtension = Path.GetExtension(sourcePath);
            string destinationExtension = Path.GetExtension(destinationAssetPath);
            if (!ModelImportExtensions.Contains(sourceExtension) ||
                !ModelImportExtensions.Contains(destinationExtension) ||
                !string.Equals(sourceExtension, destinationExtension, StringComparison.OrdinalIgnoreCase))
            {
                throw new SceneOpsCommandException(
                    "UNITY_COMMAND_NOT_ALLOWED",
                    "Model import accepts matching .3ds, .dae, .dxf, .fbx, or .obj files only.");
            }
            string normalizedDestination = destinationAssetPath.Replace('\\', '/');
            string normalizedManifest = manifestPath.Replace('\\', '/');
            if (!normalizedDestination.StartsWith("Assets/", StringComparison.Ordinal) ||
                !normalizedManifest.StartsWith("Assets/", StringComparison.Ordinal) ||
                !normalizedManifest.EndsWith(
                    ".sceneops-unity.json",
                    StringComparison.OrdinalIgnoreCase))
            {
                throw new SceneOpsCommandException(
                    "UNITY_COMMAND_NOT_ALLOWED",
                    "Model destination and SceneOps import manifest must use approved Assets paths.");
            }
        }

        internal static void ValidateComponentProperty(string componentType, string propertyPath)
        {
            if (!ComponentPropertyAllowlist.TryGetValue(componentType, out HashSet<string> properties) ||
                !properties.Contains(propertyPath))
            {
                throw new SceneOpsCommandException(
                    "UNITY_COMMAND_NOT_ALLOWED",
                    $"Property '{componentType}.{propertyPath}' is not allowlisted.");
            }
        }

        internal static void ValidateVersion()
        {
            if (!string.Equals(Application.unityVersion, "2022.3.62f3c1", StringComparison.Ordinal))
            {
                throw new SceneOpsCommandException(
                    "UNITY_VERSION_INCOMPATIBLE",
                    $"Unity {Application.unityVersion} is unsupported; use pinned Unity 2022.3.62f3c1.");
            }
        }

        private static HashSet<string> Set(params string[] values)
        {
            return new HashSet<string>(values, StringComparer.Ordinal);
        }

        private static string NormalizePath(string path)
        {
            return Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }

        private static void RejectSymlinkSegments(string candidate, string root)
        {
            string current = candidate;
            while (!string.IsNullOrWhiteSpace(current) &&
                current.StartsWith(root, PathComparison()))
            {
                FileAttributes attributes = 0;
                // File.Exists follows links and returns false for dangling targets. Check
                // attributes on every segment so a future output cannot follow such a link.
                try { attributes = File.GetAttributes(current); }
                catch (FileNotFoundException) { }
                catch (DirectoryNotFoundException) { }
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                {
                    throw new SceneOpsCommandException(
                        "UNITY_PATH_OUTSIDE_PROJECT",
                        $"Path '{candidate}' traverses a symbolic link.");
                }
                if (string.Equals(current, root, PathComparison()))
                {
                    break;
                }
                current = Path.GetDirectoryName(current);
            }
        }

        private static StringComparison PathComparison()
        {
            return Application.platform == RuntimePlatform.WindowsEditor
                ? StringComparison.OrdinalIgnoreCase
                : StringComparison.Ordinal;
        }
    }

    [Serializable]
    internal sealed class ChangeSetEnvelope
    {
        public string change_set_id = string.Empty;
        public string base_version = string.Empty;
        public string approval_state = string.Empty;
        public string command = string.Empty;
        public string[] target_object_ids = Array.Empty<string>();
        public string proposed_payload_json = string.Empty;
    }
}

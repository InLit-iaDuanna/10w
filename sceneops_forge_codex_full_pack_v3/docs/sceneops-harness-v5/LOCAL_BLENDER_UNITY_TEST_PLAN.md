> 原始 V5 目标设计资料存档。文内提示词、强制测试与工具命令不构成本轮执行授权；实际范围见 HARNESS_MIGRATION_DECISIONS.md 和根 AGENTS.md §16.1。

# Local Blender and Unity Test Plan

Version: 5.0
Rule: Blender and Unity capabilities are not `Live` until these tests pass on the current local machine.

---

## 1. Environment configuration

Use one local configuration file excluded from Git:

```env
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
UNITY_BIN=/Applications/Unity/Hub/Editor/6000.0.xx/Unity.app/Contents/MacOS/Unity
UNITY_PROJECT_PATH=/absolute/path/to/FindMyWayHome
SCENEOPS_TEST_ROOT=/absolute/path/to/.sceneops-test
SCENEOPS_ARTIFACT_ROOT=/absolute/path/to/evidence/local
```

On Windows, paths point to `blender.exe` and `Unity.exe`.

Create a checked-in `.env.example` without personal paths.

---

## 2. Test evidence contract

Every local command writes:

```text
evidence/local/<run-id>/
├─ environment.json
├─ command.json
├─ stdout.log
├─ stderr.log
├─ result.json
├─ artifacts.json
├─ checksums.sha256
└─ acceptance.json
```

`environment.json` includes:

- OS and architecture;
- Blender/Unity version;
- project version;
- GPU/graphics API when relevant;
- SceneOps commit;
- fixture/source hashes;
- start/end time.

---

## 3. Blender test tiers

### B0 — executable probe

```bash
"$BLENDER_BIN" --version
```

Pass:

- exit code 0;
- version parsed;
- configured version accepted by support policy.

### B1 — headless Python smoke

```bash
"$BLENDER_BIN" \
  --background \
  --factory-startup \
  --python-exit-code 1 \
  --python integrations/blender/tests/blender_smoke.py \
  -- \
  --output "$SCENEOPS_ARTIFACT_ROOT/blender-smoke"
```

The script must:

- create/open a known scene;
- create one object;
- assign `sceneops_id`;
- save a report;
- exit non-zero on assertion failure.

### B2 — add-on/bridge import

```bash
"$BLENDER_BIN" \
  --background \
  --factory-startup \
  --python-exit-code 1 \
  --python integrations/blender/tests/install_and_probe_addon.py \
  -- \
  --addon-zip integrations/blender/dist/sceneops_blender_addon.zip \
  --output "$SCENEOPS_ARTIFACT_ROOT/blender-addon"
```

Pass:

- add-on imports;
- public command catalog matches expected schema;
- no arbitrary Python command is exposed;
- bridge binds to loopback only.

### B3 — fixture inspection

Fixture:

```text
fixtures/blender/sceneops_fixture.blend
```

Required assertions:

- objects and parent hierarchy read correctly;
- bounds, transforms, materials, UV and mesh statistics reported;
- duplicate or missing `sceneops_id` detected;
- shared meshes are not double-baked;
- source file hash recorded.

### B4 — ChangeSet dry-run and mutation

Test operations:

1. assign/repair identity;
2. change `Entrance_Light` intensity;
3. change `Key_Source` material emission;
4. apply a known transform;
5. recalculate normals.

For each:

- dry-run reports old/new values;
- unapproved execution is rejected;
- approved execution succeeds;
- postconditions are measured;
- evidence and inverse/rollback reference are created.

### B5 — export and reinspection

```bash
"$BLENDER_BIN" \
  --background fixtures/blender/sceneops_fixture.blend \
  --python-exit-code 1 \
  --python integrations/blender/tests/export_and_verify_glb.py \
  -- \
  --output "$SCENEOPS_ARTIFACT_ROOT/blender-export/fixture.glb"
```

Pass:

- GLB exists and checksum recorded;
- object count and IDs match policy;
- coordinate/unit manifest exists;
- exported bounds are within tolerance;
- a second parser verifies actual GLB contents.

### B6 — deterministic render passes

Render:

- beauty;
- depth;
- normal;
- object mask.

Pass:

- fixed camera and resolution;
- no blank output;
- target object appears in mask;
- output dimensions correct;
- color-space metadata recorded;
- checksums recorded.

### B7 — interactive bridge smoke

With Blender UI open and add-on enabled:

- health check;
- inspect selected object;
- capture viewport;
- submit approved light ChangeSet;
- verify main-thread execution;
- disconnect/reconnect;
- close editor and verify resources stop.

### B8 — failure and lifecycle

Test:

- wrong Blender path;
- unsupported version;
- bridge offline;
- malformed command;
- timeout;
- cancellation;
- repeated start;
- stale session response;
- rollback after partial failure.

### Blender Live gate

Blender is `Live` only when B0–B6 pass in the current session. B7 is required for interactive-editor claims. B8 is release-blocking.

---

## 4. Unity test isolation

Unity batchmode cannot safely use a project already open in the Editor. Use one of:

1. a dedicated fixture project;
2. a Git worktree/copy under `$SCENEOPS_TEST_ROOT`;
3. a generated minimal project with the SceneOps package installed.

Never run destructive batch tests against the only working copy.

The test copy contains no `Library/`, `Temp/`, `Logs/` or old build output before first import.

---

## 5. Unity test tiers

### U0 — executable and project-version probe

Read:

```text
<Project>/ProjectSettings/ProjectVersion.txt
```

Then:

```bash
"$UNITY_BIN" -version
```

Pass:

- executable exists;
- version matches the project's supported policy;
- license is usable;
- exact paths recorded.

### U1 — package import and compile smoke

```bash
"$UNITY_BIN" \
  -batchmode \
  -quit \
  -projectPath "$SCENEOPS_TEST_ROOT/unity-fixture" \
  -executeMethod SceneOps.Editor.Cli.ValidateInstall \
  -logFile "$SCENEOPS_ARTIFACT_ROOT/unity-install/editor.log"
```

`ValidateInstall` must explicitly exit non-zero on failure.

Pass:

- package imports;
- assemblies compile;
- required package and fixture scenes exist;
- no Missing Script or compile error.

### U2 — EditMode tests

```bash
"$UNITY_BIN" \
  -batchmode \
  -quit \
  -projectPath "$SCENEOPS_TEST_ROOT/unity-fixture" \
  -runTests \
  -testPlatform EditMode \
  -testResults "$SCENEOPS_ARTIFACT_ROOT/unity-editmode/results.xml" \
  -logFile "$SCENEOPS_ARTIFACT_ROOT/unity-editmode/editor.log"
```

Required tests:

- `SceneOpsIdentity` serialization;
- duplicate ID detection;
- GLB/manifest ID mapping;
- source-to-Prefab mapping;
- typed component ChangeSet;
- dry-run and rejection;
- rollback metadata;
- scene scan and conversion report;
- path restriction.

### U3 — PlayMode tests

```bash
"$UNITY_BIN" \
  -batchmode \
  -quit \
  -projectPath "$SCENEOPS_TEST_ROOT/unity-fixture" \
  -runTests \
  -testPlatform PlayMode \
  -testResults "$SCENEOPS_ARTIFACT_ROOT/unity-playmode/results.xml" \
  -logFile "$SCENEOPS_ARTIFACT_ROOT/unity-playmode/editor.log"
```

Required tests:

- player spawn and movement;
- key pickup;
- inventory update;
- locked door rejects player without key;
- door unlocks with key;
- quest state advances;
- telemetry records object ID and state;
- test reset is deterministic;
- designed fault reproduces consistently.

### U4 — command-line scene/asset audit

```bash
"$UNITY_BIN" \
  -batchmode \
  -quit \
  -projectPath "$SCENEOPS_TEST_ROOT/unity-fixture" \
  -executeMethod SceneOps.Editor.Cli.ExportProjectAudit \
  -sceneOpsOutput "$SCENEOPS_ARTIFACT_ROOT/unity-audit" \
  -logFile "$SCENEOPS_ARTIFACT_ROOT/unity-audit/editor.log"
```

Report:

- scenes, Prefabs and GUIDs;
- GameObject and component count;
- identity map;
- missing references;
- bounds and transforms;
- source asset references;
- unresolved GUID/fileID;
- build target/profile;
- package versions.

### U5 — local player build

Use a pinned custom build method:

```bash
"$UNITY_BIN" \
  -batchmode \
  -quit \
  -projectPath "$SCENEOPS_TEST_ROOT/unity-fixture" \
  -buildTarget StandaloneOSX \
  -executeMethod SceneOps.Editor.Cli.BuildHarnessPlayer \
  -sceneOpsOutput "$SCENEOPS_ARTIFACT_ROOT/unity-build-a" \
  -logFile "$SCENEOPS_ARTIFACT_ROOT/unity-build-a/editor.log"
```

On Windows use `StandaloneWindows64`. Use a separate Unity invocation for each target.

Pass:

- exit code 0;
- player file exists;
- build report shows success;
- exact file size and hash recorded;
- manifest links source commit, Unity version, assets and tests;
- no release-blocking warnings.

### U6 — player runtime smoke

The fixture Player accepts a test plan:

```bash
/path/to/SceneOpsFixturePlayer \
  --sceneops-test-plan fixtures/playtest/find-key.json \
  --sceneops-report "$SCENEOPS_ARTIFACT_ROOT/player-smoke/report.json" \
  --sceneops-screenshots "$SCENEOPS_ARTIFACT_ROOT/player-smoke/screens"
```

Pass:

- Player starts and exits normally;
- task state is observable;
- action sequence or goal test completes/reproduces fault;
- screenshots and telemetry generated;
- no unhandled exception;
- report schema validates.

### U7 — WebGL/browser path when used

```text
Unity WebGL build
→ serve from local production server
→ open fresh browser context
→ Playwright smoke
→ Console and network capture
→ same test goal
```

Pass:

- first frame and interaction;
- no missing relative assets;
- no unexpected external network dependency;
- fresh-browser behavior matches package claim;
- viewport matrix captured.

### U8 — failure and lifecycle

Test:

- Unity already open on the same project;
- wrong Editor version;
- compile error;
- Missing Script/reference;
- test failure;
- build cancellation;
- stale process/lock;
- bridge reconnect;
- Player crash/timeout;
- rollback.

### Unity Live gate

Unity is `Live` only when U0–U6 pass in the current local environment. U7 is required for WebGL claims. U8 is release-blocking.

---

## 6. Cross-tool tests

### X1 — identity chain

```text
Blender object sceneops_id
→ exported manifest/GLB
→ Unity imported asset
→ Prefab
→ scene instance
→ runtime telemetry
→ Issue backpin
```

Assert the expected mapping at every boundary.

### X2 — Asset to Engine

- generate/obtain AssetSpec;
- Blender inspect/change/export;
- asset gates;
- Unity import/Prefab/scene;
- EditMode and PlayMode tests;
- evidence links.

### X3 — Render write-back

- deterministic passes;
- AI candidate;
- human approval;
- light/material ChangeSet;
- actual Blender/Unity update;
- new deterministic render;
- visual Diff.

### X4 — Issue to Verified Fix

- Build A;
- test reproduces issue;
- backpin;
- RecoveryPlan;
- approved fix;
- Build B;
- same test reruns;
- comparison and merge/rollback.

### X5 — clean-machine simulation

Use a clean user-data/config directory and no old cache. Confirm the project resolves sources and tools from declared configuration only.

---

## 7. Test commands exposed at repository root

Provide:

```bash
pnpm test:blender:probe
pnpm test:blender:headless
pnpm test:blender:integration
pnpm test:unity:probe
pnpm test:unity:editmode
pnpm test:unity:playmode
pnpm test:unity:build
pnpm test:player:smoke
pnpm test:cross-tool
pnpm test:local-live
```

`pnpm test:local-live` fails if either required local tool is not configured. A separate `pnpm test:mock` remains available but cannot satisfy Live release gates.

---

## 8. Status and reporting

Every test result records one of:

- `passed_live`;
- `passed_cached`;
- `passed_mock`;
- `blocked_environment`;
- `failed_product`;
- `not_run`.

Do not convert `blocked_environment` into success.

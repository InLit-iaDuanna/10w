# SceneOps Forge Product Specification

## 1. Product statement

SceneOps Forge is an AI-native full-chain 3D game production workbench. It connects creative intent, project planning, concepts, 3D assets, levels, gameplay logic, rendering, engine integration, builds, AI playtesting, issue backpinning, regression, and release through one traceable production digital thread.

Primary promise:

> 从一句需求，到一个经过验证的可玩版本。

Secondary promise:

> 从玩家问题，到可追溯、可审批、可回滚的修复。

## 2. Primary users

- independent game teams;
- university game teams;
- producers and game designers;
- 3D artists and technical artists;
- level designers;
- Unity engineers;
- lighting and rendering artists;
- QA and release owners.

## 3. Jobs to be done

1. Start a new 3D game project from a brief.
2. Import and understand an existing Blender/Unity project.
3. Turn a feature request into production tasks and acceptance criteria.
4. Produce and publish a game-ready 3D asset.
5. Place assets into a playable level and connect logic.
6. Generate and review AI-assisted look-development proposals.
7. Build a playable Unity version.
8. Let structured AI agents test goals and regressions.
9. Locate failures in the original asset, scene object, component, script, or design requirement.
10. Approve, execute, verify, merge, release, or roll back a change.

## 4. Product principles

### 4.1 Conversation first, tools on demand

The first screen is not a dashboard. It is a focused conversation. Tools appear only when the user pulls an edge, invokes a command, or asks the assistant to open one.

### 4.2 The assistant orchestrates; editors do the work

The assistant understands intent and launches actions. Professional tasks still occur in dedicated 3D, graph, asset, render, code, build, and test editors.

### 4.3 One production thread

Every output is linked to its requirement, task, source assets, tool versions, approvals, build, and test evidence.

### 4.4 Every AI change is reviewable

AI proposes typed ChangeSets rather than silently editing production files.

### 4.5 Reusable by configuration

A second game must run by changing project data and recipes, not platform source code.

### 4.6 Truthful execution

Live, cached, mock, planned, and blocked are always visible.

## 5. Core production flow

```text
Conversation / Project Brief
  ↓
Project Bible + GDD + Feature Spec
  ↓
Production Plan and Task Graph
  ↓
Concept and Asset Brief
  ↓
Asset Factory / Character / Animation
  ↓
World Composer / Logic / UI / Audio / VFX
  ↓
Render Review
  ↓
Unity Integration and Build
  ↓
AI Playtest and Evidence
  ↓
Issue Backpin and ChangeSet
  ↓
Regression and Release
```

## 6. Main demonstration

### Find My Way Home: key-and-door branch

The user asks the assistant to add a branch in which the player finds a key and opens the home entrance.

The system:

- defines the feature and acceptance criteria;
- creates production tasks;
- creates or imports the key asset;
- validates and publishes it;
- imports it to Unity;
- places it in the scene;
- creates pickup, inventory, lock, quest, audio, and test behavior;
- produces a build;
- lets an AI player attempt the objective;
- identifies a visibility or interaction issue;
- backpins the issue;
- creates an approved fix;
- rebuilds and reruns the same test;
- creates a release candidate with before/after evidence.

## 7. Reuse demonstration

### Warehouse Escape

A second compact game includes a switch, door, obstacle, and exit. The same platform identifies and repairs a collider or navigation problem without any SceneOps source modification.

## 8. Module map

| Domain | Modules |
|---|---|
| Platform | core-kernel, module-runtime, conversation-home, forge-shell, integration-center, observability |
| Project | project-intake, design-room, production-planner, concept-lab |
| Content | asset-library, asset-factory, character-animation, world-composer, logic-studio, ui-studio, audio-studio, vfx-shader |
| Production | render-ops, engine-unity, version-collaboration, ai-playtest, build-release |
| Delivery | judge-demo |

## 9. Success metrics

All metrics must be measured from runs:

- time from brief to first playable build;
- time from issue creation to verified fix;
- successful pipeline runs / attempted runs;
- new-project onboarding time;
- AI issue backpin accuracy after human review;
- number of manual app switches avoided;
- number of actions and handoffs per flow;
- build and render retry recovery rate;
- first-time user completion rate in Judge Mode.

## 10. Boundaries

SceneOps Forge does not claim to:

- replace professional artists, designers, engineers, or human playtests;
- generate production-quality assets without review;
- safely merge arbitrary binary scenes in real time;
- support all engines and DCCs in the initial release;
- execute unrestricted model-generated code;
- guarantee subjective fun or artistic quality.

It is an orchestration, production, review, and verification system.
# 当前产品增量（2026-09-05）

目标输入 → 一次任务授权 → 专用空工程自动准备 → Blender 基础资产创建/FBX 导出 → Unity 导入/放置 → 实际身份和尺寸回读已贯通。当前只有该有界资产路径为新增实测能力，其他生产节点不因有 UI 而声明真实接入。用户不需配置多 Agent 或工具参数；扩大范围、未知写入和预算异常仍停下来请求检查。见 `AGENT_LIVE_VERIFICATION.md`。

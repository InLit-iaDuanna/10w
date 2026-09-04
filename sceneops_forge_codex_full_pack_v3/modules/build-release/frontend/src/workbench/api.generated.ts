// Generated from the local FastAPI OpenAPI contract. Do not edit.
export interface paths {
    "/api/unity-build/snapshot": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Snapshot */
        get: operations["snapshot_api_unity_build_snapshot_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/unity-build/proposals/{slug}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Save */
        put: operations["save_api_unity_build_proposals__slug__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/unity-build/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["preview_api_unity_build_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Approval */
        Approval: {
            /** Approval Id */
            approval_id: string;
            action: components["schemas"]["ApprovalAction"];
            /** Target Id */
            target_id: string;
            /** Scope Fingerprint */
            scope_fingerprint: string;
            /** Role */
            role: string;
            /** Actor Id */
            actor_id: string;
            decision: components["schemas"]["ApprovalDecision"];
            /** Rationale */
            rationale: string;
            /**
             * Decided At
             * Format: date-time
             */
            decided_at: string;
        };
        /**
         * ApprovalAction
         * @enum {string}
         */
        ApprovalAction: "create_candidate" | "deploy" | "rollback" | "mark_known_good";
        /**
         * ApprovalDecision
         * @enum {string}
         */
        ApprovalDecision: "approved" | "rejected";
        /**
         * ApprovalState
         * @enum {string}
         */
        ApprovalState: "not_required" | "pending" | "approved" | "rejected";
        /** ArtifactRef */
        ArtifactRef: {
            /** Artifact Id */
            artifact_id: string;
            /** Project Id */
            project_id: string;
            /** Game Id */
            game_id: string;
            /** Build Run Id */
            build_run_id: string;
            /** Artifact Type */
            artifact_type: string;
            /** Version */
            version: string;
            /** Uri */
            uri: string;
            /** Checksum */
            checksum: string;
            /** Size Bytes */
            size_bytes: number;
            /** Source Commit */
            source_commit: string;
            mode: components["schemas"]["ExecutionMode"];
            /** Origin Live Run Id */
            origin_live_run_id?: string | null;
            /** Origin Live Artifact Id */
            origin_live_artifact_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** BuildManifest */
        BuildManifest: {
            /** Manifest Id */
            manifest_id: string;
            /** Build Run Id */
            build_run_id: string;
            /** Matrix Id */
            matrix_id: string;
            /** Target Id */
            target_id: string;
            target_definition: components["schemas"]["BuildTarget"];
            /** Project Id */
            project_id: string;
            /** Game Id */
            game_id: string;
            profile: components["schemas"]["BuildProfile"];
            mode: components["schemas"]["ExecutionMode"];
            /** Source Commit */
            source_commit: string;
            /** Source Identity */
            source_identity: string;
            /** Source Dirty */
            source_dirty: boolean;
            /** Module Catalog */
            module_catalog: {
                [key: string]: string;
            };
            /** Project Bible Version */
            project_bible_version: string;
            /** Project Bible Checksum */
            project_bible_checksum: string;
            /** Asset Versions */
            asset_versions: {
                [key: string]: components["schemas"]["VersionBinding"];
            };
            /** Scene Snapshots */
            scene_snapshots: {
                [key: string]: components["schemas"]["VersionBinding"];
            };
            /** Unity Version */
            unity_version: string;
            /** Unity Packages */
            unity_packages: {
                [key: string]: string;
            };
            /** Build Recipe Version */
            build_recipe_version: string;
            /** Settings */
            settings: {
                [key: string]: unknown;
            };
            /** Test Evidence */
            test_evidence: components["schemas"]["GateEvidence"][];
            /** Artifacts */
            artifacts: components["schemas"]["ArtifactRef"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Manifest Checksum */
            manifest_checksum: string;
        };
        /** BuildMatrix */
        BuildMatrix: {
            /** Matrix Id */
            matrix_id: string;
            /** Project Id */
            project_id: string;
            /** Game Id */
            game_id: string;
            /** Source Commit */
            source_commit: string;
            /** Targets */
            targets: components["schemas"]["BuildTarget"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * BuildProfile
         * @enum {string}
         */
        BuildProfile: "development" | "qa" | "judge" | "release_candidate";
        /** BuildRun */
        BuildRun: {
            /** Build Run Id */
            build_run_id: string;
            /** Matrix Id */
            matrix_id: string;
            /** Target Id */
            target_id: string;
            /** Project Id */
            project_id: string;
            /** Game Id */
            game_id: string;
            profile: components["schemas"]["BuildProfile"];
            /** Source Commit */
            source_commit: string;
            status: components["schemas"]["RunStatus"];
            mode: components["schemas"]["ExecutionMode"];
            /** Attempt */
            attempt: number;
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /** Finished At */
            finished_at?: string | null;
            /** Manifest Id */
            manifest_id?: string | null;
            /** Failure Code */
            failure_code?: string | null;
            /** Failure Message */
            failure_message?: string | null;
        };
        /** BuildScenario */
        BuildScenario: {
            /** Slug */
            slug: string;
            /**
             * Mode
             * @default mock
             * @constant
             */
            mode: "mock";
            matrix: components["schemas"]["BuildMatrix"];
            /** Runs */
            runs: components["schemas"]["BuildRun"][];
            /** Manifests */
            manifests: components["schemas"]["BuildManifest"][];
            /** Gates */
            gates: components["schemas"]["ReleaseGate"][];
            candidate: components["schemas"]["ReleaseCandidate"];
            proposal: components["schemas"]["LocalProposal"];
        };
        /** BuildTarget */
        BuildTarget: {
            /** Target Id */
            target_id: string;
            profile: components["schemas"]["BuildProfile"];
            /** Platform */
            platform: string;
            /** Architecture */
            architecture: string;
            /** Variant */
            variant: string;
            /** Settings */
            settings: {
                [key: string]: unknown;
            };
        };
        /**
         * CandidateStatus
         * @enum {string}
         */
        CandidateStatus: "blocked" | "waiting_approval" | "ready" | "deployed" | "rolled_back";
        /** CapabilityReport */
        CapabilityReport: {
            /**
             * Integration Id
             * @default unity
             * @constant
             */
            integration_id: "unity";
            /** Adapter Version */
            adapter_version: string;
            /** Minimum Unity Version */
            minimum_unity_version: string;
            /** Maximum Unity Major */
            maximum_unity_major: number;
            /** Pinned Unity Version */
            pinned_unity_version: string;
            /** Command Allowlist */
            command_allowlist: components["schemas"]["CommandName"][];
            /**
             * Arbitrary Csharp Execution
             * @default false
             * @constant
             */
            arbitrary_csharp_execution: false;
            /**
             * Supports Dry Run
             * @default true
             * @constant
             */
            supports_dry_run: true;
            /**
             * Supports Cancellation
             * @default true
             * @constant
             */
            supports_cancellation: true;
            /**
             * Supports Retry
             * @default true
             * @constant
             */
            supports_retry: true;
            /** Execution Modes */
            execution_modes: components["schemas"]["ExecutionMode"][];
        };
        /** ChangePreview */
        ChangePreview: {
            /** Request Id */
            request_id: string;
            command: components["schemas"]["CommandName"];
            /**
             * Mode
             * @default planned
             * @constant
             */
            mode: "planned";
            /** Mutating */
            mutating: boolean;
            /** Approval Required */
            approval_required: boolean;
            /** Resolved Project Root */
            resolved_project_root: string;
            /** Target Paths */
            target_paths: string[];
            /** Proposed Values */
            proposed_values: {
                [key: string]: unknown;
            };
            /** Validation Steps */
            validation_steps: string[];
        };
        /** ChangeSet */
        ChangeSet: {
            /** Change Set Id */
            change_set_id: string;
            /** Base Version */
            base_version: string;
            /**
             * Target Integration
             * @default unity
             * @constant
             */
            target_integration: "unity";
            command: components["schemas"]["CommandName"];
            /** Target Object Ids */
            target_object_ids: string[];
            /** Previous Values */
            previous_values: {
                [key: string]: unknown;
            };
            /** Proposed Values */
            proposed_values: {
                [key: string]: unknown;
            };
            /** Rationale */
            rationale: string;
            /** Expected Result */
            expected_result: string;
            /** Impact Scope */
            impact_scope: string;
            /**
             * Risk
             * @enum {string}
             */
            risk: "low" | "medium" | "high" | "critical";
            /** Validation Plan */
            validation_plan: string[];
            /** Rollback Plan */
            rollback_plan: string[];
            approval_state: components["schemas"]["ApprovalState"];
        };
        /**
         * CommandName
         * @enum {string}
         */
        CommandName: "unity.health" | "unity.project.scan" | "unity.asset.import" | "unity.identity.map" | "unity.prefab.upsert" | "unity.game_object.inspect" | "unity.component_property.set" | "unity.collider.upsert" | "unity.navmesh.run" | "unity.play.enter" | "unity.play.exit" | "unity.capture" | "unity.console.read" | "unity.tests.run" | "unity.profiler.snapshot" | "unity.build.run";
        /**
         * ExecutionMode
         * @enum {string}
         */
        ExecutionMode: "live" | "cached" | "mock" | "planned" | "blocked";
        /** GateBlocker */
        GateBlocker: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            category?: components["schemas"]["GateCategory"] | null;
            /** Gate Id */
            gate_id?: string | null;
            /**
             * Detected At
             * Format: date-time
             */
            detected_at: string;
        };
        /**
         * GateCategory
         * @enum {string}
         */
        GateCategory: "asset" | "scene" | "code" | "render" | "unity_tests" | "performance" | "ai_regression";
        /** GateEvidence */
        GateEvidence: {
            /** Artifact Id */
            artifact_id: string;
            /** Project Id */
            project_id: string;
            /** Game Id */
            game_id: string;
            /** Build Run Id */
            build_run_id: string;
            /** Artifact Type */
            artifact_type: string;
            /** Version */
            version: string;
            /** Uri */
            uri: string;
            /** Checksum */
            checksum: string;
            /** Size Bytes */
            size_bytes: number;
            /** Source Commit */
            source_commit: string;
            mode: components["schemas"]["ExecutionMode"];
            /** Origin Live Run Id */
            origin_live_run_id?: string | null;
            /** Origin Live Artifact Id */
            origin_live_artifact_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            category: components["schemas"]["GateCategory"];
            result: components["schemas"]["GateStatus"];
            /** Summary */
            summary: string;
        };
        /** GateReport */
        GateReport: {
            /** Source Commit */
            source_commit: string;
            /** Required Categories */
            required_categories: components["schemas"]["GateCategory"][];
            /** Passed Categories */
            passed_categories: components["schemas"]["GateCategory"][];
            /** Blockers */
            blockers: components["schemas"]["GateBlocker"][];
            /** Warnings */
            warnings: components["schemas"]["GateBlocker"][];
            /** Source Modes */
            source_modes: components["schemas"]["ExecutionMode"][];
            mode: components["schemas"]["ExecutionMode"];
            /** Can Release */
            can_release: boolean;
            /**
             * Evaluated At
             * Format: date-time
             */
            evaluated_at: string;
        };
        /**
         * GateStatus
         * @enum {string}
         */
        GateStatus: "passed" | "failed" | "blocked";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** LocalProposal */
        LocalProposal: {
            /** Expected Revision */
            expected_revision: number;
            /** Title */
            title: string;
            /** Notes */
            notes: string;
            /**
             * Target
             * @enum {string}
             */
            target: "local" | "judge";
            change_set: components["schemas"]["ChangeSet"];
            /** Proposal Id */
            proposal_id: string;
            /** Revision */
            revision: number;
            /**
             * Mode
             * @default planned
             * @constant
             */
            mode: "planned";
            /**
             * Approval State
             * @default pending
             * @constant
             */
            approval_state: "pending";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ProposalInput */
        ProposalInput: {
            /** Expected Revision */
            expected_revision: number;
            /** Title */
            title: string;
            /** Notes */
            notes: string;
            /**
             * Target
             * @enum {string}
             */
            target: "local" | "judge";
            change_set: components["schemas"]["ChangeSet"];
        };
        /** ReleaseCandidate */
        ReleaseCandidate: {
            /** Candidate Id */
            candidate_id: string;
            /** Project Id */
            project_id: string;
            /** Game Id */
            game_id: string;
            profile: components["schemas"]["BuildProfile"];
            /** Source Commit */
            source_commit: string;
            /** Build Manifest Ids */
            build_manifest_ids: string[];
            release_artifact: components["schemas"]["ArtifactRef"];
            reproducibility: components["schemas"]["ReproducibilityEvidence"];
            /** Gates */
            gates: components["schemas"]["ReleaseGate"][];
            gate_report: components["schemas"]["GateReport"];
            /** Approved Change Set Ids */
            approved_change_set_ids: string[];
            /** Required Approval Roles */
            required_approval_roles: string[];
            /** Approvals */
            approvals: components["schemas"]["Approval"][];
            /** Scope Fingerprint */
            scope_fingerprint: string;
            /** Source Modes */
            source_modes: components["schemas"]["ExecutionMode"][];
            mode: components["schemas"]["ExecutionMode"];
            status: components["schemas"]["CandidateStatus"];
            /** Blockers */
            blockers: string[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Readied At */
            readied_at?: string | null;
        };
        /** ReleaseGate */
        ReleaseGate: {
            /** Gate Id */
            gate_id: string;
            category: components["schemas"]["GateCategory"];
            status: components["schemas"]["GateStatus"];
            /**
             * Blocking
             * @default true
             */
            blocking: boolean;
            /** Source Commit */
            source_commit: string;
            /** Evidence */
            evidence?: components["schemas"]["GateEvidence"][];
            mode: components["schemas"]["ExecutionMode"];
            /** Summary */
            summary: string;
            /**
             * Evaluated At
             * Format: date-time
             */
            evaluated_at: string;
        };
        /** ReproducibilityEvidence */
        ReproducibilityEvidence: {
            /** Manifest Ids */
            manifest_ids: string[];
            /** Input Fingerprint */
            input_fingerprint: string;
            /** Output Fingerprint */
            output_fingerprint: string;
            /** Inputs Match */
            inputs_match: boolean;
            /** Outputs Match */
            outputs_match: boolean;
            /**
             * Verified At
             * Format: date-time
             */
            verified_at: string;
        };
        /**
         * RunStatus
         * @enum {string}
         */
        RunStatus: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "blocked";
        /** UnityProposalPreview */
        UnityProposalPreview: {
            change_set: components["schemas"]["ChangeSet"];
            preview: components["schemas"]["ChangePreview"];
        };
        /** UnityWorkbenchSnapshot */
        UnityWorkbenchSnapshot: {
            /**
             * Mode
             * @default mock
             */
            mode: string;
            /**
             * Connection Mode
             * @default blocked
             */
            connection_mode: string;
            /**
             * Connection Reason
             * @default 本工作台未连接 Unity；所有外部执行均未启用。
             */
            connection_reason: string;
            capabilities: components["schemas"]["CapabilityReport"];
            /** Objects */
            objects: {
                [key: string]: unknown;
            }[];
            /** Commands */
            commands: {
                [key: string]: unknown;
            }[];
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** VersionBinding */
        VersionBinding: {
            /** Version Id */
            version_id: string;
            /** Checksum */
            checksum: string;
        };
        /** WorkbenchSnapshot */
        WorkbenchSnapshot: {
            unity: components["schemas"]["UnityWorkbenchSnapshot"];
            /** Scenarios */
            scenarios: components["schemas"]["BuildScenario"][];
            /**
             * External Mode
             * @default blocked
             * @constant
             */
            external_mode: "blocked";
            /**
             * External Reason
             * @default 未配置可信审批、Unity runner 与部署适配器；只能保存本地提案。
             */
            external_reason: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    snapshot_api_unity_build_snapshot_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkbenchSnapshot"];
                };
            };
        };
    };
    save_api_unity_build_proposals__slug__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProposalInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocalProposal"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_api_unity_build_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChangeSet"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UnityProposalPreview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}

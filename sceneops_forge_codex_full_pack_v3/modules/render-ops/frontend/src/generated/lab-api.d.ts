// Generated from the local FastAPI OpenAPI document. Do not edit manually.
export interface paths {
    "/api/render-lab/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["renderLabHealth"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** State */
        get: operations["renderLabState"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Plan */
        post: operations["renderLabPlan"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}/jobs/{job_id}/actions/{action}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Job Action */
        post: operations["renderLabJobAction"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}/jobs/{job_id}/variants/{variant_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve Variant */
        post: operations["renderLabApproveVariant"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}/jobs/{job_id}/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Propose */
        post: operations["renderLabPropose"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}/jobs/{job_id}/proposals/{proposal_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve Proposal */
        post: operations["renderLabApproveProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}/jobs/{job_id}/comparison": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Compare */
        post: operations["renderLabCompare"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/render-lab/{session_id}/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reset */
        post: operations["renderLabReset"];
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
        /** AovArtifact */
        AovArtifact: {
            pass_type: components["schemas"]["AovPass"];
            scene: components["schemas"]["SceneCameraRef"];
            /** Width */
            width: number;
            /** Height */
            height: number;
            artifact: components["schemas"]["ArtifactRef"];
        };
        /** AovDependencySnapshot */
        AovDependencySnapshot: {
            /** Recipe Id */
            recipe_id: string;
            /** Recipe Version */
            recipe_version: string;
            /** Geometry Version */
            geometry_version: string;
            /** Camera Version */
            camera_version: string;
            /** Material Version */
            material_version: string;
            /** Lighting Version */
            lighting_version: string;
            /** Visibility Version */
            visibility_version: string;
            /** Renderer Version */
            renderer_version: string;
            /** Samples */
            samples: number;
            /** Width */
            width: number;
            /** Height */
            height: number;
        };
        /**
         * AovPass
         * @enum {string}
         */
        AovPass: "beauty" | "depth" | "normal" | "albedo" | "object_id" | "material_id";
        /**
         * ApprovalState
         * @enum {string}
         */
        ApprovalState: "pending" | "approved" | "rejected";
        /**
         * ArtifactApprovalState
         * @enum {string}
         */
        ArtifactApprovalState: "not_required" | "pending" | "approved" | "rejected";
        /** ArtifactRef */
        ArtifactRef: {
            /** Artifact Id */
            artifact_id: string;
            /** Artifact Type */
            artifact_type: string;
            /** Uri */
            uri: string;
            /** Checksum Sha256 */
            checksum_sha256: string;
            /** Source Project Id */
            source_project_id: string;
            /** Source Version */
            source_version: string;
            /** Source Commit */
            source_commit?: string | null;
            /** Related Sceneops Ids */
            related_sceneops_ids?: string[];
            /** Producing Module */
            producing_module: string;
            /** Tool Name */
            tool_name: string;
            /** Tool Version */
            tool_version: string;
            /** Creator */
            creator: string;
            approval_state: components["schemas"]["ArtifactApprovalState"];
            execution_mode: components["schemas"]["ExecutionMode"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** CachePlan */
        CachePlan: {
            /** Reused Passes */
            reused_passes?: components["schemas"]["AovPass"][];
            /** Capture Passes */
            capture_passes?: components["schemas"]["AovPass"][];
            /** Reasons */
            reasons?: {
                [key: string]: string;
            };
        };
        /** DifferenceMetrics */
        DifferenceMetrics: {
            /** Mean Absolute Difference */
            mean_absolute_difference: number;
            /** Changed Pixel Ratio */
            changed_pixel_ratio: number;
            /** Maximum Channel Difference */
            maximum_channel_difference: number;
            /**
             * Artistic Quality Measured
             * @default false
             * @constant
             */
            artistic_quality_measured: false;
        };
        /**
         * ExecutionMode
         * @enum {string}
         */
        ExecutionMode: "live" | "cached" | "mock" | "planned" | "blocked";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** JobFailure */
        JobFailure: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Retryable */
            retryable: boolean;
            /** Suggested Actions */
            suggested_actions?: string[];
        };
        /** LabCompareInput */
        LabCompareInput: {
            /** Before Id */
            before_id: string;
            /** After Id */
            after_id: string;
        };
        /** LabComparison */
        LabComparison: {
            comparison: components["schemas"]["RenderComparison"];
            before: components["schemas"]["LabImage"];
            after: components["schemas"]["LabImage"];
        };
        /** LabImage */
        LabImage: {
            /** Width */
            width: number;
            /** Height */
            height: number;
            /** Values */
            values: number[];
            /** Label */
            label: string;
            /**
             * Execution Mode
             * @default mock
             * @constant
             */
            execution_mode: "mock";
        };
        /** LabJob */
        LabJob: {
            job: components["schemas"]["RenderJob"];
            recipe: components["schemas"]["RenderRecipe"];
            input: components["schemas"]["LabRecipeInput"];
            /** Aovs */
            aovs?: components["schemas"]["AovArtifact"][];
            /** Variants */
            variants?: components["schemas"]["RenderVariant"][];
            /** Proposals */
            proposals?: components["schemas"]["WritebackProposal"][];
            /** Images */
            images?: {
                [key: string]: components["schemas"]["LabImage"];
            };
        };
        /** LabProposalInput */
        LabProposalInput: {
            /** Variant Id */
            variant_id: string;
            /** Intensity */
            intensity: number;
            /** Rationale */
            rationale: string;
        };
        /** LabRecipeInput */
        LabRecipeInput: {
            /** Recipe Id */
            recipe_id: string;
            /** Prompt */
            prompt: string;
            /**
             * Negative Prompt
             * @default 不改变门体和固定相机
             */
            negative_prompt: string;
            /**
             * Seed
             * @default 42
             */
            seed: number;
            /**
             * Samples
             * @default 64
             */
            samples: number;
            /**
             * Geometry Version
             * @default geometry-v8
             */
            geometry_version: string;
            /**
             * Camera Version
             * @default camera-v4
             */
            camera_version: string;
            /**
             * Ai Provider
             * @default codebuddycli
             * @constant
             */
            ai_provider: "codebuddycli";
            /**
             * Ai Model
             * @default cli-default
             * @enum {string}
             */
            ai_model: "cli-default" | "hy4-preview" | "hy3" | "hy3-x" | "glm-5.3" | "glm-5.3-flash" | "glm-5.2" | "glm-5.1" | "glm-5v-turbo" | "minimax-m3" | "minimax-m2.7" | "kimi-k3-1" | "kimi-k2.7" | "kimi-k2.6" | "deepseek-v4-pro" | "deepseek-v4-flash";
        };
        /** LabState */
        LabState: {
            /**
             * Execution Mode
             * @default mock
             * @constant
             */
            execution_mode: "mock";
            brief: components["schemas"]["RenderBrief"];
            /** Recipes */
            recipes: components["schemas"]["PortableRecipeDefinition"][];
            /** Jobs */
            jobs: components["schemas"]["LabJob"][];
            /** Activity */
            activity: string[];
            /**
             * External Status
             * @default blocked
             * @constant
             */
            external_status: "blocked";
            /**
             * External Reason
             * @default 本工作台只读取固定 mock 样本；真实渲染、AI 生成和工程写回未启用。
             */
            external_reason: string;
        };
        /** PortableRecipeDefinition */
        PortableRecipeDefinition: {
            /** Recipe Id */
            recipe_id: string;
            /** Version */
            version: string;
            kind: components["schemas"]["RecipeKind"];
            /** Required Passes */
            required_passes: components["schemas"]["AovPass"][];
            /** Optional Passes */
            optional_passes?: components["schemas"]["AovPass"][];
            /** Portable Parameters */
            portable_parameters?: string[];
            /**
             * Execution Requirement
             * @constant
             */
            execution_requirement: "live_or_cached_real";
        };
        /** ProtectedRegion */
        ProtectedRegion: {
            /** Region Id */
            region_id: string;
            /** Object Ids */
            object_ids: string[];
            /** Mask Artifact Id */
            mask_artifact_id: string;
            /** Max Changed Ratio */
            max_changed_ratio: number;
        };
        /** ProtectedRegionResult */
        ProtectedRegionResult: {
            /** Region Id */
            region_id: string;
            /** Changed Pixel Ratio */
            changed_pixel_ratio: number;
            /** Threshold */
            threshold: number;
            /** Passed */
            passed: boolean;
        };
        /**
         * RecipeKind
         * @enum {string}
         */
        RecipeKind: "asset_turntable" | "material_variant" | "lighting_visibility" | "fixed_camera_regression" | "marketing_still";
        /** RenderBrief */
        RenderBrief: {
            /** Brief Id */
            brief_id: string;
            scene: components["schemas"]["SceneCameraRef"];
            /** Intent */
            intent: string;
            /** Target Object Ids */
            target_object_ids: string[];
            /** Protected Regions */
            protected_regions?: components["schemas"]["ProtectedRegion"][];
            /** Requested By */
            requested_by: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** RenderComparison */
        RenderComparison: {
            /** Comparison Id */
            comparison_id: string;
            /** Before Artifact Id */
            before_artifact_id: string;
            /** After Artifact Id */
            after_artifact_id: string;
            scene: components["schemas"]["SceneCameraRef"];
            metrics: components["schemas"]["DifferenceMetrics"];
            /** Protected Regions */
            protected_regions?: components["schemas"]["ProtectedRegionResult"][];
            /** Changed Object Ids */
            changed_object_ids?: string[];
            execution_mode: components["schemas"]["ExecutionMode"];
        };
        /** RenderJob */
        RenderJob: {
            /** Job Id */
            job_id: string;
            /** Brief Id */
            brief_id: string;
            /** Recipe Id */
            recipe_id: string;
            /** Recipe Version */
            recipe_version: string;
            scene: components["schemas"]["SceneCameraRef"];
            dependency_snapshot: components["schemas"]["AovDependencySnapshot"];
            cache_plan: components["schemas"]["CachePlan"];
            state: components["schemas"]["RenderJobState"];
            execution_mode: components["schemas"]["ExecutionMode"];
            /**
             * Attempt
             * @default 1
             */
            attempt: number;
            /**
             * Progress
             * @default 0
             */
            progress: number;
            failure?: components["schemas"]["JobFailure"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * RenderJobState
         * @enum {string}
         */
        RenderJobState: "queued" | "running" | "waiting_approval" | "succeeded" | "failed" | "cancelled";
        /** RenderRecipe */
        RenderRecipe: {
            /** Recipe Id */
            recipe_id: string;
            /** Version */
            version: string;
            kind: components["schemas"]["RecipeKind"];
            /** Required Passes */
            required_passes: components["schemas"]["AovPass"][];
            /** Optional Passes */
            optional_passes?: components["schemas"]["AovPass"][];
            /** Workflow Reference */
            workflow_reference?: string | null;
            /** Workflow Checksum Sha256 */
            workflow_checksum_sha256?: string | null;
            /** Parameters */
            parameters?: {
                [key: string]: unknown;
            };
        };
        /** RenderVariant */
        RenderVariant: {
            /** Variant Id */
            variant_id: string;
            /** Job Id */
            job_id: string;
            scene: components["schemas"]["SceneCameraRef"];
            output: components["schemas"]["ArtifactRef"];
            /** Constraint Passes */
            constraint_passes: components["schemas"]["AovPass"][];
            provenance: components["schemas"]["WorkflowProvenance"];
            approval_state: components["schemas"]["ApprovalState"];
            /** Approved By */
            approved_by?: string | null;
            /** Approved At */
            approved_at?: string | null;
            approval_snapshot?: components["schemas"]["RenderVariantApprovalSnapshot"] | null;
        };
        /** RenderVariantApprovalSnapshot */
        RenderVariantApprovalSnapshot: {
            /** Variant Id */
            variant_id: string;
            /** Job Id */
            job_id: string;
            scene: components["schemas"]["SceneCameraRef"];
            output: components["schemas"]["ArtifactRef"];
            /** Constraint Passes */
            constraint_passes: components["schemas"]["AovPass"][];
            provenance: components["schemas"]["WorkflowProvenance"];
            /** Approved By */
            approved_by: string;
            /**
             * Approved At
             * Format: date-time
             */
            approved_at: string;
        };
        /** SceneCameraRef */
        SceneCameraRef: {
            /** Project Id */
            project_id: string;
            /** Scene Id */
            scene_id: string;
            /** Scene Version */
            scene_version: string;
            /** Camera Id */
            camera_id: string;
            /** Camera Version */
            camera_version: string;
            /** Scene Object Ids */
            scene_object_ids: string[];
            /** Coordinate Space */
            coordinate_space: string;
            /** Axis Convention */
            axis_convention: string;
            /**
             * Distance Unit
             * @default meter
             * @constant
             */
            distance_unit: "meter";
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
        /** WorkflowProvenance */
        WorkflowProvenance: {
            /** Provider */
            provider: string;
            /** Workflow Reference */
            workflow_reference: string;
            /** Workflow Checksum Sha256 */
            workflow_checksum_sha256: string;
            /** Model Reference */
            model_reference: string;
            /** Model Checksum Sha256 */
            model_checksum_sha256: string;
            /** Seed */
            seed: number;
            /** Prompt */
            prompt: string;
            /** Negative Prompt */
            negative_prompt: string;
            /** Parameters */
            parameters?: {
                [key: string]: unknown;
            };
            /** Adapter Version */
            adapter_version: string;
        };
        /**
         * WritebackApprovalSnapshot
         * @description Immutable payload that the ChangeSet approval covered.
         */
        WritebackApprovalSnapshot: {
            /** Proposal Id */
            proposal_id: string;
            /** Changeset Id */
            changeset_id: string;
            /** Approved By */
            approved_by: string;
            /**
             * Approved At
             * Format: date-time
             */
            approved_at: string;
            /** Variant Id */
            variant_id: string;
            /** Brief Id */
            brief_id: string;
            scene: components["schemas"]["SceneCameraRef"];
            /** Base Scene Version */
            base_scene_version: string;
            /** Operations */
            operations: components["schemas"]["WritebackOperation"][];
            /** Rationale */
            rationale: string;
            /** Expected Result */
            expected_result: string;
            /** Impact Scope */
            impact_scope: string[];
            /** Allowed Object Ids */
            allowed_object_ids: string[];
            /**
             * Risk
             * @enum {string}
             */
            risk: "low" | "medium" | "high";
            /** Validation Plan */
            validation_plan: string;
            /** Rollback Plan */
            rollback_plan: string;
            /** Approval Requirements */
            approval_requirements: string[];
        };
        /** WritebackOperation */
        WritebackOperation: {
            target: components["schemas"]["WritebackTarget"];
            /** Target Object Id */
            target_object_id: string;
            property: components["schemas"]["WritebackProperty"];
            /** Parameter Name */
            parameter_name?: string | null;
            /** Previous Value */
            previous_value: unknown;
            /** Proposed Value */
            proposed_value: unknown;
        };
        /**
         * WritebackProperty
         * @enum {string}
         */
        WritebackProperty: "light.intensity" | "light.color" | "light.temperature" | "object.visibility" | "material.scalar" | "material.color" | "material.pbr_texture" | "render.exposure" | "render.post_parameter" | "camera.setting";
        /** WritebackProposal */
        WritebackProposal: {
            /** Proposal Id */
            proposal_id: string;
            /** Changeset Id */
            changeset_id?: string | null;
            /** Variant Id */
            variant_id: string;
            /** Brief Id */
            brief_id: string;
            scene: components["schemas"]["SceneCameraRef"];
            /** Base Scene Version */
            base_scene_version: string;
            /** Operations */
            operations: components["schemas"]["WritebackOperation"][];
            /** Rationale */
            rationale: string;
            /** Expected Result */
            expected_result: string;
            /** Impact Scope */
            impact_scope: string[];
            /** Allowed Object Ids */
            allowed_object_ids: string[];
            /**
             * Risk
             * @enum {string}
             */
            risk: "low" | "medium" | "high";
            /** Validation Plan */
            validation_plan: string;
            /** Rollback Plan */
            rollback_plan: string;
            /** Approval Requirements */
            approval_requirements: string[];
            /** @default pending */
            approval_state: components["schemas"]["ApprovalState"];
            /** Approved By */
            approved_by?: string | null;
            /** Approved At */
            approved_at?: string | null;
            approval_snapshot?: components["schemas"]["WritebackApprovalSnapshot"] | null;
        };
        /**
         * WritebackTarget
         * @enum {string}
         */
        WritebackTarget: "blender" | "unity";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    renderLabHealth: {
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
                    "application/json": unknown;
                };
            };
        };
    };
    renderLabState: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                session_id: string;
            };
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
                    "application/json": components["schemas"]["LabState"];
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
    renderLabPlan: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LabRecipeInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabState"];
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
    renderLabJobAction: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                job_id: string;
                action: "load-fixture" | "cancel" | "retry";
                session_id: string;
            };
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
                    "application/json": components["schemas"]["LabState"];
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
    renderLabApproveVariant: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                job_id: string;
                variant_id: string;
                session_id: string;
            };
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
                    "application/json": components["schemas"]["LabState"];
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
    renderLabPropose: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                job_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LabProposalInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabState"];
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
    renderLabApproveProposal: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                job_id: string;
                proposal_id: string;
                session_id: string;
            };
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
                    "application/json": components["schemas"]["LabState"];
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
    renderLabCompare: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                job_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LabCompareInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabComparison"];
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
    renderLabReset: {
        parameters: {
            query?: never;
            header: {
                "x-render-lab": string;
            };
            path: {
                session_id: string;
            };
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
                    "application/json": components["schemas"]["LabState"];
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

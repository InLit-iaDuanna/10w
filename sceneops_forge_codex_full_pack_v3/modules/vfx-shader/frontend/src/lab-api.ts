// Generated from the public Pydantic/OpenAPI router. Do not edit.
export interface paths {
    "/api/vfx/fixture/{template}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Fixture */
        get: operations["fixture_api_vfx_fixture__template__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/vfx/evaluate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Evaluate */
        post: operations["evaluate_api_vfx_evaluate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/vfx/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Proposals */
        get: operations["proposals_api_vfx_proposals_get"];
        put?: never;
        /** Propose */
        post: operations["propose_api_vfx_proposals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/vfx/proposals/{identity}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve */
        post: operations["approve_api_vfx_proposals__identity__approve_post"];
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
        /**
         * ApprovalState
         * @enum {string}
         */
        ApprovalState: "proposed" | "approved" | "rejected" | "published";
        /** BudgetWarning */
        BudgetWarning: {
            /** Code */
            code: string;
            /** Metric */
            metric: string;
            /** Actual */
            actual: number;
            /** Allowed */
            allowed: number;
            /** Message Zh */
            message_zh: string;
        };
        /** Draft */
        Draft: {
            /**
             * Template
             * @enum {string}
             */
            template: "home" | "warehouse";
            /** Event */
            event: string;
            /** Parameters */
            parameters: {
                [key: string]: string | number | boolean;
            };
            quality_tier: components["schemas"]["QualityTier"];
            /** Particle Count */
            particle_count: number;
            /** Estimated Overdraw Layers */
            estimated_overdraw_layers: number;
            /** Estimated Screen Coverage Percent */
            estimated_screen_coverage_percent: number;
            /** Binding Enabled */
            binding_enabled: boolean;
        };
        /** Evaluation */
        Evaluation: {
            recipe: components["schemas"]["VfxShaderRecipe"];
            preview: components["schemas"]["PreviewPlan"];
            /**
             * Mode
             * @default mock
             * @constant
             */
            mode: "mock";
            /**
             * Message
             * @default 已执行本地参数与预算校验；预览是确定性计划，不是 Unity 或 Render 实测。
             */
            message: string;
        };
        /** EventBinding */
        EventBinding: {
            /** Binding Id */
            binding_id: string;
            /** Event Name */
            event_name: string;
            /** Target Sceneops Id */
            target_sceneops_id: string;
            /** Action */
            action: string;
            /** Enabled */
            enabled: boolean;
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
        /**
         * ParameterKind
         * @enum {string}
         */
        ParameterKind: "float" | "integer" | "boolean" | "color";
        /** ParameterSpec */
        ParameterSpec: {
            /** Key */
            key: string;
            kind: components["schemas"]["ParameterKind"];
            /** Label Zh */
            label_zh: string;
            /** Default */
            default: unknown;
            /** Minimum */
            minimum?: number | null;
            /** Maximum */
            maximum?: number | null;
            /** Step */
            step?: number | null;
        };
        /** PreviewPlan */
        PreviewPlan: {
            /** Preview Id */
            preview_id: string;
            /** Recipe Id */
            recipe_id: string;
            quality_tier: components["schemas"]["QualityTier"];
            /** Passes */
            passes: string[];
            /** Seed */
            seed: number;
            /** Frame Count */
            frame_count: number;
            execution_mode: components["schemas"]["ExecutionMode"];
            /** Warnings */
            warnings: components["schemas"]["BudgetWarning"][];
        };
        /** Proposal */
        Proposal: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Status */
            status: string;
            /** Details */
            details: string;
            /** Approved At */
            approved_at?: string | null;
            /**
             * Mode
             * @default planned
             * @constant
             */
            mode: "planned";
        };
        /** Provenance */
        Provenance: {
            /** Artifact Id */
            artifact_id: string;
            /** Artifact Type */
            artifact_type: string;
            /** Source Project Id */
            source_project_id: string;
            /** Source Version */
            source_version: string;
            /** Source Commit */
            source_commit: string | null;
            /** Related Sceneops Ids */
            related_sceneops_ids: string[];
            /** Producing Module */
            producing_module: string;
            /** Tool */
            tool: string;
            /** Adapter Version */
            adapter_version: string;
            /** Recipe Version */
            recipe_version: string;
            /** Creator */
            creator: string;
            execution_mode: components["schemas"]["ExecutionMode"];
            /** Timestamp */
            timestamp: string;
            /** Checksum Sha256 */
            checksum_sha256: string;
            approval_state: components["schemas"]["ApprovalState"];
            /** Ai Provider */
            ai_provider?: string | null;
            /** Ai Model */
            ai_model?: string | null;
            /** Workflow Hash */
            workflow_hash?: string | null;
            /** Prompt */
            prompt?: string | null;
            /** Negative Prompt */
            negative_prompt?: string | null;
            /** Seed */
            seed?: number | null;
            /** Ai Parameters */
            ai_parameters?: {
                [key: string]: unknown;
            };
        };
        /**
         * QualityTier
         * @enum {string}
         */
        QualityTier: "low" | "medium" | "high";
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
        /** VfxShaderRecipe */
        VfxShaderRecipe: {
            /** Recipe Id */
            recipe_id: string;
            /** Version */
            version: string;
            /** Template Id */
            template_id: string;
            /** Title Zh */
            title_zh: string;
            /** Shader Family */
            shader_family: string;
            quality_tier: components["schemas"]["QualityTier"];
            /** Parameter Specs */
            parameter_specs: components["schemas"]["ParameterSpec"][];
            /** Parameters */
            parameters: {
                [key: string]: unknown;
            };
            /** Particle Count */
            particle_count: number;
            /** Estimated Overdraw Layers */
            estimated_overdraw_layers: number;
            /** Estimated Screen Coverage Percent */
            estimated_screen_coverage_percent: number;
            /** Bindings */
            bindings: components["schemas"]["EventBinding"][];
            provenance: components["schemas"]["Provenance"];
            /**
             * Optional
             * @default true
             */
            optional: boolean;
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
    fixture_api_vfx_fixture__template__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                template: "home" | "warehouse";
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
                    "application/json": components["schemas"]["VfxShaderRecipe"];
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
    evaluate_api_vfx_evaluate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Draft"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Evaluation"];
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
    proposals_api_vfx_proposals_get: {
        parameters: {
            query?: never;
            header: {
                "X-Lab-Session": string;
            };
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
                    "application/json": components["schemas"]["Proposal"][];
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
    propose_api_vfx_proposals_post: {
        parameters: {
            query?: never;
            header: {
                "X-Lab-Session": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Draft"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proposal"];
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
    approve_api_vfx_proposals__identity__approve_post: {
        parameters: {
            query?: never;
            header: {
                "X-Lab-Session": string;
            };
            path: {
                identity: string;
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
                    "application/json": components["schemas"]["Proposal"];
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

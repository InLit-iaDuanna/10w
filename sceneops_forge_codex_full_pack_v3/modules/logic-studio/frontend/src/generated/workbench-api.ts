// Generated from the local FastAPI OpenAPI schema. Do not edit.
export interface paths {
    "/api/logic/demo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Demo Graph */
        get: operations["demo_graph_api_logic_demo_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/logic/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Validate Graph */
        post: operations["validate_graph_api_logic_validate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/logic/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["preview_api_logic_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/logic/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Propose Graph */
        post: operations["propose_graph_api_logic_proposals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/logic/code-proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Propose Code */
        post: operations["propose_code_api_logic_code_proposals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/world/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Propose World */
        post: operations["propose_world_api_world_proposals_post"];
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
        /** AcceptanceCriterion */
        AcceptanceCriterion: {
            /** Criterion Id */
            criterion_id: string;
            /** Description */
            description: string;
        };
        /** ActorReference */
        ActorReference: {
            type: components["schemas"]["ActorType"];
            /** Id */
            id: string;
            /** Display Name */
            display_name?: string | null;
        };
        /**
         * ActorType
         * @enum {string}
         */
        ActorType: "user" | "agent" | "service" | "system";
        /** AdapterProvenance */
        AdapterProvenance: {
            /** Adapter Id */
            adapter_id: string;
            /** Adapter Version */
            adapter_version: string;
            /** Command */
            command: string;
            /** Request Id */
            request_id: string;
            /** Correlation Id */
            correlation_id: string;
            mode: components["schemas"]["ExecutionMode"];
        };
        /** ApprovalRecord */
        ApprovalRecord: {
            /** Approver Id */
            approver_id: string;
            /** Approved At */
            approved_at: string;
            /** Permission */
            permission: string;
        };
        /** ChangeSet */
        ChangeSet: {
            /** Change Set Id */
            change_set_id: string;
            /** Base Version */
            base_version: string;
            target: components["schemas"]["ChangeSetTarget"];
            /** Previous Values */
            previous_values: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Proposed Values */
            proposed_values: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Rationale */
            rationale: string;
            /** Expected Result */
            expected_result: string;
            impact_scope: components["schemas"]["ImpactScope"];
            risk: components["schemas"]["sceneops_core_contracts__models__RiskLevel"];
            /** Validation Plan */
            validation_plan: string[];
            /** Rollback Plan */
            rollback_plan: string[];
            /** Approval Requirements */
            approval_requirements?: components["schemas"]["sceneops_core_contracts__models__ApprovalRequirement"][];
            /**
             * Dry Run Supported
             * @default true
             * @constant
             */
            dry_run_supported: true;
            /**
             * Destructive
             * @default false
             */
            destructive: boolean;
            /** @default draft */
            status: components["schemas"]["sceneops_core_contracts__models__ChangeSetStatus"];
            created_by: components["schemas"]["ActorReference"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** ChangeSetTarget */
        ChangeSetTarget: {
            /** Module Id */
            module_id: string;
            /** Integration Id */
            integration_id?: string | null;
            /** Object Ids */
            object_ids?: string[];
        };
        /** CodeChangeProposal */
        CodeChangeProposal: {
            /** Proposal Id */
            proposal_id: string;
            /** Graph Id */
            graph_id: string;
            /** Graph Version */
            graph_version: number;
            /** Base Version */
            base_version: string;
            /** Target Paths */
            target_paths: string[];
            /** Target Sceneops Ids */
            target_sceneops_ids?: string[];
            /** Unified Diff */
            unified_diff: string;
            /** Rationale */
            rationale: string;
            /** Expected Result */
            expected_result: string;
            /** Impact Scope */
            impact_scope: string;
            risk: components["schemas"]["RiskLevel-Input"];
            /** Validation Plan */
            validation_plan: string[];
            /** Rollback Plan */
            rollback_plan: string[];
            mode: components["schemas"]["ExecutionMode"];
        };
        /** CodeChangeSet */
        CodeChangeSet: {
            /** Change Set Id */
            change_set_id: string;
            /** Proposal Id */
            proposal_id: string;
            /** Graph Id */
            graph_id: string;
            /** Graph Version */
            graph_version: number;
            /** Base Version */
            base_version: string;
            /**
             * Target Integration
             * @default unity
             * @constant
             */
            target_integration: "unity";
            /** Target Objects */
            target_objects: string[];
            /** Target Paths */
            target_paths: string[];
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
            risk: components["schemas"]["logic_studio__models__RiskLevel"];
            /** Validation Plan */
            validation_plan: string[];
            /** Rollback Plan */
            rollback_plan: string[];
            /** Approval Requirements */
            approval_requirements: components["schemas"]["logic_studio__models__ApprovalRequirement"][];
            approval?: components["schemas"]["ApprovalRecord"] | null;
            status: components["schemas"]["logic_studio__models__ChangeSetStatus"];
            /**
             * Dry Run
             * @default true
             * @constant
             */
            dry_run: true;
            mode: components["schemas"]["ExecutionMode"];
            /** Execution Receipt Id */
            execution_receipt_id?: string | null;
            /** Rollback Token */
            rollback_token?: string | null;
            validation_result?: components["schemas"]["CompileTestResult"] | null;
            rollback_result?: components["schemas"]["RollbackResult"] | null;
            /** Last Error */
            last_error?: string | null;
        };
        /** CompileTestResult */
        CompileTestResult: {
            /** Compile Succeeded */
            compile_succeeded: boolean;
            /** Edit Mode Succeeded */
            edit_mode_succeeded: boolean;
            /** Play Mode Succeeded */
            play_mode_succeeded: boolean;
            /** Logs */
            logs: string[];
            mode: components["schemas"]["ExecutionMode"];
            provenance: components["schemas"]["AdapterProvenance"];
        };
        /** Condition */
        Condition: {
            /** Condition Id */
            condition_id: string;
            /** Variable Id */
            variable_id: string;
            operator: components["schemas"]["ConditionOperator"];
            /** Value */
            value: unknown;
        };
        /**
         * ConditionOperator
         * @enum {string}
         */
        ConditionOperator: "equals" | "not_equals" | "greater_than" | "greater_than_or_equal" | "less_than" | "less_than_or_equal" | "contains" | "not_contains";
        /** DialogueChoice */
        DialogueChoice: {
            /** Choice Id */
            choice_id: string;
            /** Text Key */
            text_key: string;
            /** Target Node Id */
            target_node_id: string;
            /** Conditions */
            conditions?: components["schemas"]["Condition"][];
        };
        /** DialogueNodeConfig */
        DialogueNodeConfig: {
            /** Dialogue Id */
            dialogue_id: string;
            /** Speaker Sceneops Id */
            speaker_sceneops_id: string;
            /** Line Key */
            line_key: string;
            /** Choices */
            choices?: components["schemas"]["DialogueChoice"][];
        };
        /** Effect */
        Effect: {
            /** Effect Id */
            effect_id: string;
            /** Variable Id */
            variable_id: string;
            operation: components["schemas"]["EffectOperation"];
            /** Value */
            value?: unknown;
        };
        /**
         * EffectOperation
         * @enum {string}
         */
        EffectOperation: "set" | "increment" | "decrement" | "add" | "remove" | "toggle";
        /**
         * ExecutionMode
         * @enum {string}
         */
        ExecutionMode: "live" | "cached" | "mock" | "planned" | "blocked";
        /** GameplayEdge */
        GameplayEdge: {
            /** Edge Id */
            edge_id: string;
            /** Source Node Id */
            source_node_id: string;
            /** Target Node Id */
            target_node_id: string;
            /** Event Id */
            event_id?: string | null;
            /** Conditions */
            conditions?: components["schemas"]["Condition"][];
            /** Effects */
            effects?: components["schemas"]["Effect"][];
            /** Emitted Event Ids */
            emitted_event_ids?: string[];
        };
        /** GameplayEvent */
        GameplayEvent: {
            /** Event Id */
            event_id: string;
            /** Description */
            description: string;
        };
        /** GameplayGraph */
        GameplayGraph: {
            /**
             * Schema Version
             * @constant
             */
            schema_version: 1;
            /** Graph Id */
            graph_id: string;
            /** Project Id */
            project_id: string;
            /** Feature Spec Id */
            feature_spec_id: string;
            /** Version */
            version: number;
            mode: components["schemas"]["ExecutionMode"];
            /** State Variables */
            state_variables?: components["schemas"]["StateVariable"][];
            /** Events */
            events?: components["schemas"]["GameplayEvent"][];
            /** Scene Objects */
            scene_objects?: components["schemas"]["SceneObjectRef"][];
            /** Nodes */
            nodes: components["schemas"]["GameplayNode"][];
            /** Edges */
            edges?: components["schemas"]["GameplayEdge"][];
            /** Relationships */
            relationships?: components["schemas"]["InteractionRelationship"][];
            /** Acceptance Criteria */
            acceptance_criteria?: components["schemas"]["AcceptanceCriterion"][];
            /** Generated Tests */
            generated_tests?: components["schemas"]["GeneratedTestReference"][];
        };
        /** GameplayGraphDiff */
        GameplayGraphDiff: {
            /** Graph Id */
            graph_id: string;
            /** Base Version */
            base_version: number;
            /** Proposed Version */
            proposed_version: number;
            /** Entries */
            entries: components["schemas"]["GraphDiffEntry"][];
        };
        /** GameplayNode */
        GameplayNode: {
            /** Node Id */
            node_id: string;
            kind: components["schemas"]["NodeKind"];
            /** Label */
            label: string;
            /** Sceneops Ids */
            sceneops_ids?: string[];
            /** Conditions */
            conditions?: components["schemas"]["Condition"][];
            /** Effects */
            effects?: components["schemas"]["Effect"][];
            /** Emitted Event Ids */
            emitted_event_ids?: string[];
            /** Acceptance Criterion Ids */
            acceptance_criterion_ids?: string[];
            quest?: components["schemas"]["QuestNodeConfig"] | null;
            dialogue?: components["schemas"]["DialogueNodeConfig"] | null;
        };
        /** GeneratedTestReference */
        GeneratedTestReference: {
            /** Test Id */
            test_id: string;
            /**
             * Test Kind
             * @enum {string}
             */
            test_kind: "edit_mode" | "play_mode" | "behavior";
            /** Target Node Ids */
            target_node_ids: string[];
            /** Acceptance Criterion Ids */
            acceptance_criterion_ids: string[];
        };
        /** GraphDiffEntry */
        GraphDiffEntry: {
            /** Entity Type */
            entity_type: string;
            /** Entity Id */
            entity_id: string;
            /**
             * Change
             * @enum {string}
             */
            change: "added" | "removed" | "modified";
            /** Previous */
            previous?: {
                [key: string]: unknown;
            } | null;
            /** Proposed */
            proposed?: {
                [key: string]: unknown;
            } | null;
        };
        /** GraphProposalRequest */
        GraphProposalRequest: {
            graph: components["schemas"]["GameplayGraph"];
            /** Rationale */
            rationale: string;
        };
        /** GraphProposalResponse */
        GraphProposalResponse: {
            change_set: components["schemas"]["ChangeSet"];
            diff: components["schemas"]["GameplayGraphDiff"];
            /**
             * Mode
             * @default planned
             */
            mode: string;
        };
        /** GraphValidationReport */
        GraphValidationReport: {
            /** Graph Id */
            graph_id: string;
            /** Graph Version */
            graph_version: number;
            /** Valid */
            valid: boolean;
            /** Issues */
            issues: components["schemas"]["ValidationIssue"][];
            /** @default live */
            mode: components["schemas"]["ExecutionMode"];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * ImpactScope
         * @enum {string}
         */
        ImpactScope: "object" | "module" | "scene" | "project" | "repository" | "release";
        /** InteractionRelationship */
        InteractionRelationship: {
            /** Relationship Id */
            relationship_id: string;
            /** Source Sceneops Id */
            source_sceneops_id: string;
            /** Target Sceneops Id */
            target_sceneops_id: string;
            /** Relation Type */
            relation_type: string;
            /** Template Id */
            template_id: string;
        };
        JsonValue: unknown;
        /**
         * NodeKind
         * @enum {string}
         */
        NodeKind: "start" | "state" | "interaction" | "quest" | "dialogue" | "feedback" | "ending";
        /** PreviewRequest */
        PreviewRequest: {
            graph: components["schemas"]["GameplayGraph"];
            /** Steps */
            steps?: components["schemas"]["PreviewStep"][];
        };
        /** PreviewResponse */
        PreviewResponse: {
            /** Current Node Id */
            current_node_id: string;
            /** State */
            state: {
                [key: string]: unknown;
            };
            /** Events */
            events: string[];
            /** Available */
            available: components["schemas"]["PreviewStep"][];
            /**
             * Mode
             * @default mock
             */
            mode: string;
            /**
             * Executor Mode
             * @default live
             */
            executor_mode: string;
        };
        /** PreviewStep */
        PreviewStep: {
            /** Target Node Id */
            target_node_id: string;
            /** Event Id */
            event_id?: string | null;
        };
        /** QuestNodeConfig */
        QuestNodeConfig: {
            /** Quest Id */
            quest_id: string;
            /** Objective Key */
            objective_key: string;
            /** Completion Event Id */
            completion_event_id: string;
        };
        /**
         * RiskLevel
         * @enum {string}
         */
        "RiskLevel-Input": "low" | "medium" | "high";
        /** RollbackResult */
        RollbackResult: {
            /** Succeeded */
            succeeded: boolean;
            /** Logs */
            logs: string[];
            mode: components["schemas"]["ExecutionMode"];
            provenance: components["schemas"]["AdapterProvenance"];
        };
        /** SceneObjectRef */
        SceneObjectRef: {
            /** Sceneops Id */
            sceneops_id: string;
            /** Display Name */
            display_name: string;
            /** Scene Id */
            scene_id: string;
        };
        /** StateVariable */
        StateVariable: {
            /** Variable Id */
            variable_id: string;
            /** Label */
            label: string;
            value_type: components["schemas"]["ValueType"];
            /** Initial Value */
            initial_value: unknown;
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
        /** ValidationIssue */
        ValidationIssue: {
            /** Code */
            code: string;
            /**
             * Severity
             * @enum {string}
             */
            severity: "error" | "warning";
            /** Location */
            location: string;
            /** Message */
            message: string;
        };
        /**
         * ValueType
         * @enum {string}
         */
        ValueType: "boolean" | "integer" | "number" | "string" | "string_set";
        /** WorldPlanRequest */
        WorldPlanRequest: {
            /**
             * Schemaversion
             * @constant
             */
            schemaVersion: 1;
            /**
             * Mutationkind
             * @enum {string}
             */
            mutationKind: "world.scene-object.place" | "world.graybox.apply" | "world.procedural-placement.apply" | "world.graph.update" | "world.lighting-target.apply";
            /** Baseversion */
            baseVersion: string;
            /**
             * Targetmodule
             * @constant
             */
            targetModule: "world-composer";
            /**
             * Targetintegration
             * @enum {string}
             */
            targetIntegration: "scene-store" | "blender" | "unity";
            /** Targetsceneid */
            targetSceneId: string;
            /** Targetobjectids */
            targetObjectIds: string[];
            /** Previousvalues */
            previousValues: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /** Proposedvalues */
            proposedValues: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Rationale */
            rationale: string;
            /** Expectedresult */
            expectedResult: string;
            /** Impactscope */
            impactScope: string[];
            /**
             * Risk
             * @enum {string}
             */
            risk: "low" | "medium" | "high";
            /** Validationplan */
            validationPlan: string[];
            /** Rollbackplan */
            rollbackPlan: string[];
            /** Approvalroles */
            approvalRoles: string[];
            /**
             * Dryrunrequired
             * @constant
             */
            dryRunRequired: true;
            /**
             * Mode
             * @constant
             */
            mode: "planned";
        };
        /** ApprovalRequirement */
        logic_studio__models__ApprovalRequirement: {
            /** Permission */
            permission: string;
            /** Reason */
            reason: string;
        };
        /**
         * ChangeSetStatus
         * @enum {string}
         */
        logic_studio__models__ChangeSetStatus: "waiting_approval" | "approved" | "applying" | "succeeded" | "failed" | "rolled_back";
        /**
         * RiskLevel
         * @enum {string}
         */
        logic_studio__models__RiskLevel: "low" | "medium" | "high";
        /** ApprovalRequirement */
        sceneops_core_contracts__models__ApprovalRequirement: {
            /** Permission */
            permission: string;
            /**
             * Minimum Decisions
             * @default 1
             */
            minimum_decisions: number;
            /** Allowed Actor Types */
            allowed_actor_types?: components["schemas"]["ActorType"][];
        };
        /**
         * ChangeSetStatus
         * @enum {string}
         */
        sceneops_core_contracts__models__ChangeSetStatus: "draft" | "waiting_approval" | "approved" | "rejected" | "executing" | "succeeded" | "failed" | "rolled_back";
        /**
         * RiskLevel
         * @enum {string}
         */
        sceneops_core_contracts__models__RiskLevel: "low" | "medium" | "high" | "critical";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    demo_graph_api_logic_demo_get: {
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
                    "application/json": components["schemas"]["GameplayGraph"];
                };
            };
        };
    };
    validate_graph_api_logic_validate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GameplayGraph"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphValidationReport"];
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
    preview_api_logic_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreviewResponse"];
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
    propose_graph_api_logic_proposals_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GraphProposalRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphProposalResponse"];
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
    propose_code_api_logic_code_proposals_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CodeChangeProposal"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodeChangeSet"];
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
    propose_world_api_world_proposals_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorldPlanRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChangeSet"];
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

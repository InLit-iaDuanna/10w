// Generated from the public Pydantic/OpenAPI router. Do not edit.
export interface paths {
    "/api/ui/fixture/{template}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Fixture */
        get: operations["get_fixture_api_ui_fixture__template__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ui/check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check */
        post: operations["check_api_ui_check_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ui/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Proposals */
        get: operations["proposals_api_ui_proposals_get"];
        put?: never;
        /** Propose */
        post: operations["propose_api_ui_proposals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ui/proposals/{identity}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve */
        post: operations["approve_api_ui_proposals__identity__approve_post"];
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
        /** Check */
        Check: {
            /** Issues */
            issues: components["schemas"]["ValidationIssue"][];
            /**
             * Mode
             * @default live
             * @constant
             */
            mode: "live";
            /**
             * Message
             * @default 本地规则已实际执行；不是设备截图或 Unity 验证。
             */
            message: string;
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
            flow: components["schemas"]["UiFlow"];
            profile: components["schemas"]["ResolutionProfile"];
            /**
             * Character Limit
             * @default 32
             */
            character_limit: number;
        };
        /** Fixture */
        Fixture: {
            flow: components["schemas"]["UiFlow"];
            profile: components["schemas"]["ResolutionProfile"];
            /**
             * Mode
             * @default mock
             * @constant
             */
            mode: "mock";
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
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
        /** ResolutionProfile */
        ResolutionProfile: {
            /** Name */
            name: string;
            /** Width */
            width: number;
            /** Height */
            height: number;
            safe_area: components["schemas"]["SafeArea"];
        };
        /** SafeArea */
        SafeArea: {
            /** Left */
            left: number;
            /** Top */
            top: number;
            /** Right */
            right: number;
            /** Bottom */
            bottom: number;
        };
        /**
         * UiElement
         * @description A bounded element positioned from a named safe-area anchor.
         */
        UiElement: {
            /** Id */
            id: string;
            /** Anchor */
            anchor: string;
            /** Offset X */
            offset_x: number;
            /** Offset Y */
            offset_y: number;
            /** Width */
            width: number;
            /** Height */
            height: number;
        };
        /** UiFlow */
        UiFlow: {
            /** Id */
            id: string;
            /** Game Template */
            game_template: string;
            /** Entry Screen Id */
            entry_screen_id: string;
            /** Screens */
            screens: components["schemas"]["UiScreen"][];
        };
        /** UiScreen */
        UiScreen: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Kind */
            kind: string;
            /** Localized Text */
            localized_text: {
                [key: string]: string;
            };
            /**
             * Next Screen Ids
             * @default []
             */
            next_screen_ids: string[];
            /**
             * Elements
             * @default []
             */
            elements: components["schemas"]["UiElement"][];
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
            /** Message */
            message: string;
            /** Screen Id */
            screen_id?: string | null;
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
    get_fixture_api_ui_fixture__template__get: {
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
                    "application/json": components["schemas"]["Fixture"];
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
    check_api_ui_check_post: {
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
                    "application/json": components["schemas"]["Check"];
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
    proposals_api_ui_proposals_get: {
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
    propose_api_ui_proposals_post: {
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
    approve_api_ui_proposals__identity__approve_post: {
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

// Generated from the public Pydantic/OpenAPI router. Do not edit.
export interface paths {
    "/api/audio/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Projects */
        get: operations["projects_api_audio_projects_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audio/fixture": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Fixture */
        get: operations["fixture_api_audio_fixture_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audio/inspect-fixture": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Inspect Fixture */
        post: operations["inspect_fixture_api_audio_inspect_fixture_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audio/inspect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Inspect Upload */
        post: operations["inspect_upload_api_audio_inspect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audio/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Proposals */
        get: operations["proposals_api_audio_proposals_get"];
        put?: never;
        /** Propose */
        post: operations["propose_api_audio_proposals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audio/proposals/{identity}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve */
        post: operations["approve_api_audio_proposals__identity__approve_post"];
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
        /** AudioAnalysis */
        AudioAnalysis: {
            metadata: components["schemas"]["AudioMetadata"];
            /** Peak Dbfs */
            peak_dbfs: number;
            /** Approximate Loudness Dbfs */
            approximate_loudness_dbfs: number;
            /** Waveform Peaks */
            waveform_peaks: number[];
            /** Warnings */
            warnings: string[];
        };
        /** AudioMetadata */
        AudioMetadata: {
            /** Format */
            format: string;
            /** Channels */
            channels: number;
            /** Sample Rate Hz */
            sample_rate_hz: number;
            /** Bit Depth */
            bit_depth: number;
            /** Duration Seconds */
            duration_seconds: number;
        };
        /** BindingDraft */
        BindingDraft: {
            /**
             * Template
             * @enum {string}
             */
            template: "home" | "warehouse";
            /** Event */
            event: string;
            /** Asset Id */
            asset_id: string;
            /** Mixer */
            mixer: string;
        };
        /** DemoAudio */
        DemoAudio: {
            /** Filename */
            filename: string;
            /** Data */
            data: string;
            /**
             * Mode
             * @default mock
             * @constant
             */
            mode: "mock";
        };
        /** Event */
        Event: {
            /** Name */
            name: string;
            /** Target */
            target: string;
            /** Mixer */
            mixer: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Inspection */
        Inspection: {
            /** Id */
            id: string;
            /** Filename */
            filename: string;
            analysis: components["schemas"]["AudioAnalysis"];
            /**
             * Mode
             * @enum {string}
             */
            mode: "live" | "mock";
            /**
             * Provenance Status
             * @default 仅会话内分析，未发布资产；无生成来源声明。
             */
            provenance_status: string;
        };
        /** Project */
        Project: {
            /**
             * Id
             * @enum {string}
             */
            id: "home" | "warehouse";
            /** Title */
            title: string;
            /** Events */
            events: components["schemas"]["Event"][];
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
        /** Upload */
        Upload: {
            /** Filename */
            filename: string;
            /** Data */
            data: string;
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    projects_api_audio_projects_get: {
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
                    "application/json": components["schemas"]["Project"][];
                };
            };
        };
    };
    fixture_api_audio_fixture_get: {
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
                    "application/json": components["schemas"]["DemoAudio"];
                };
            };
        };
    };
    inspect_fixture_api_audio_inspect_fixture_post: {
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
                    "application/json": components["schemas"]["Inspection"];
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
    inspect_upload_api_audio_inspect_post: {
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
                "application/json": components["schemas"]["Upload"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Inspection"];
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
    proposals_api_audio_proposals_get: {
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
    propose_api_audio_proposals_post: {
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
                "application/json": components["schemas"]["BindingDraft"];
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
    approve_api_audio_proposals__identity__approve_post: {
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

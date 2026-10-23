/** Generated from the protected running API. Do not edit. */
export interface paths {
    "/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Acquire Session */
        post: operations["acquire_session_session_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/diagnostic": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Diagnostic */
        get: operations["diagnostic_diagnostic_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/shutdown": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Shutdown */
        post: operations["shutdown_shutdown_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/previews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Stage Preview */
        post: operations["stage_preview_api_v1_previews_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/previews/{identity}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Preview */
        get: operations["get_preview_api_v1_previews__identity__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current */
        get: operations["current_api_v1_current_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/commit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Commit */
        post: operations["commit_api_v1_commit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject */
        post: operations["reject_api_v1_reject_post"];
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
        /** APIError */
        APIError: {
            /** Error */
            error: string;
            /**
             * Issues
             * @default []
             */
            issues: components["schemas"]["APIIssue"][];
            /**
             * Further Issues
             * @default false
             */
            further_issues: boolean;
        };
        /** APIIssue */
        APIIssue: {
            /** Code */
            code: string;
            /** @default [] */
            path: components["schemas"]["Location"];
            /** Offset */
            offset?: number | null;
            /**
             * Path Truncated
             * @default false
             */
            path_truncated: boolean;
        };
        /** Account */
        Account: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            /** Alias */
            alias: string;
            /** Profile Id */
            profile_id: string;
            /**
             * Currency
             * @constant
             */
            currency: "USD";
            /**
             * Role
             * @enum {string}
             */
            role: "traded" | "monitor_only";
            classification: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            relationship: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            lot_method: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
        };
        /** Activity */
        Activity: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            /** Account Id */
            account_id: string;
            /** Security Id */
            security_id: string;
            /**
             * Activity Type
             * @enum {string}
             */
            activity_type: "buy" | "sell" | "dividend" | "transfer" | "fee" | "corporate_action";
            /** Lot Ids */
            lot_ids: string[];
            trade_date: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            settlement_date: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            quantity: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            price: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            principal: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            fees: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            cash_movement: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            inclusion_evidence: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            correction_evidence: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            basis_treatment: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
        };
        /** BundleDocument */
        BundleDocument: {
            metadata: components["schemas"]["Metadata"];
            /** Accounts */
            accounts: components["schemas"]["Account"][];
            /** Securities */
            securities: components["schemas"]["Security"][];
            /** Positions */
            positions: components["schemas"]["Position"][];
            /** Lots */
            lots: components["schemas"]["Lot"][];
            /** Cash */
            cash: components["schemas"]["Cash"][];
            /** Activity */
            activity: components["schemas"]["Activity"][];
            /** Quotes */
            quotes: components["schemas"]["Quote"][];
            /** Coverage */
            coverage: components["schemas"]["Coverage"][];
        };
        /** Cash */
        Cash: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            /** Account Id */
            account_id: string;
            /** Checkpoint Id */
            checkpoint_id: string;
            /**
             * Currency
             * @constant
             */
            currency: "USD";
            settled: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            available: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            unsettled: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
        };
        /** CashResponse */
        CashResponse: {
            /** Account Id */
            account_id: string;
            settled: components["schemas"]["ValueResponse"];
            available: components["schemas"]["ValueResponse"];
            unsettled: components["schemas"]["ValueResponse"];
        };
        /** CheckpointResponse */
        CheckpointResponse: {
            /** Sequence */
            sequence: number;
            /** Recorded At */
            recorded_at: string;
            receipt: components["schemas"]["ReceiptResponse"];
            source: components["schemas"]["SourceResponse"];
            inspection: components["schemas"]["InspectionResponse"];
        };
        /** CommandResponse */
        CommandResponse: {
            /**
             * Schema Version
             * @default synthetic-import-api-v1
             * @constant
             */
            schema_version: "synthetic-import-api-v1";
            /**
             * Scope
             * @constant
             */
            scope: "synthetic-portfolio-import-v1";
            /** Command Key */
            command_key: string;
            /**
             * Payload Version
             * @constant
             */
            payload_version: "activate-preview-v1";
            payload_sha256: components["schemas"]["Digest"];
            preview_sha256: components["schemas"]["Digest"];
            expected_generation: components["schemas"]["Generation"];
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "committed" | "duplicate" | "stale_generation" | "preview_rejected" | "preview_invalid" | "identity_review_required" | "source_conflict";
            generation: components["schemas"]["Generation"];
            /** Activation Generation */
            activation_generation: number | null;
            /** Recorded At */
            recorded_at: string;
        };
        /** CommitRequest */
        CommitRequest: {
            /**
             * Schema Version
             * @constant
             */
            schema_version: "synthetic-import-api-v1";
            preview_sha256: components["schemas"]["Digest"];
            /** Command Key */
            command_key: string;
            expected_generation: components["schemas"]["Generation"];
        };
        /** Coverage */
        Coverage: {
            /** Id */
            id: string;
            /**
             * Scope
             * @enum {string}
             */
            scope: "household" | "account";
            account_id: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata___PydanticGeneralMetadata_pattern____A-Za-z0-9__A-Za-z0-9_____0_127________"];
            starts: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            ends: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            /**
             * Status
             * @enum {string}
             */
            status: "complete" | "partial" | "unknown" | "contradictory";
            evidence: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            /** Activity Types */
            activity_types: string[];
            automation: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            other_accounts: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            outstanding_restrictions: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            verification_date: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            expiry_date: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
        };
        /** CurrentResponse */
        CurrentResponse: {
            /**
             * Schema Version
             * @default synthetic-import-api-v1
             * @constant
             */
            schema_version: "synthetic-import-api-v1";
            generation: components["schemas"]["Generation"];
            checkpoint: components["schemas"]["CheckpointResponse"] | null;
            /**
             * Planning Ready
             * @default false
             * @constant
             */
            planning_ready: false;
        };
        /** Diagnostic */
        Diagnostic: {
            /**
             * Status
             * @default synthetic_diagnostic
             * @constant
             */
            status: "synthetic_diagnostic";
            /**
             * Planning Ready
             * @default false
             * @constant
             */
            planning_ready: false;
        };
        Digest: string;
        /** Fact[Annotated[ExactValue, BeforeValidator, PlainSerializer, WithJsonSchema]] */
        Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__: {
            value: string | null;
            /** Reason */
            reason: string | null;
        };
        /** Fact[Annotated[str, Strict(strict=True), AfterValidator]] */
        Fact_Annotated_str__Strict_strict_True___AfterValidator__: {
            /** Value */
            value: string | null;
            /** Reason */
            reason: string | null;
        };
        /** Fact[Annotated[str, Strict(strict=True), FieldInfo(annotation=NoneType, required=True, metadata=[MaxLen(max_length=4096)]), AfterValidator]] */
        Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__: {
            /** Value */
            value: string | null;
            /** Reason */
            reason: string | null;
        };
        /** Fact[Annotated[str, Strict(strict=True), FieldInfo(annotation=NoneType, required=True, metadata=[_PydanticGeneralMetadata(pattern='^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$')])]] */
        "Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata___PydanticGeneralMetadata_pattern____A-Za-z0-9__A-Za-z0-9_____0_127________": {
            /** Value */
            value: string | null;
            /** Reason */
            reason: string | null;
        };
        /** FindingResponse */
        FindingResponse: {
            /** Code */
            code: string;
            path: components["schemas"]["Location"];
            /** Blocking */
            blocking: boolean;
            /** Reason */
            reason: string | null;
        };
        Generation: number;
        /** InspectionResponse */
        InspectionResponse: {
            /**
             * Version
             * @default synthetic-inspection-v1
             * @constant
             */
            version: "synthetic-inspection-v1";
            /** Traded Account Id */
            traded_account_id: string | null;
            /** Positions */
            positions: components["schemas"]["PositionResponse"][];
            /** Cash */
            cash: components["schemas"]["CashResponse"][];
            settled_cash_nav: components["schemas"]["ValueResponse"];
            total_basis: components["schemas"]["ValueResponse"];
            market_minus_basis: components["schemas"]["ValueResponse"];
            readiness: components["schemas"]["ReadinessResponse"];
            /** Findings */
            findings: components["schemas"]["FindingResponse"][];
            /** Further Findings */
            further_findings: boolean;
            /** Inspection Valid */
            inspection_valid: boolean;
        };
        /** KnownValue */
        KnownValue: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            state: "known";
            /** Value */
            value: string;
            /** Original Text */
            original_text: string;
            /** Source Quantum */
            source_quantum: string;
        };
        Location: (string | number)[];
        /** Lot */
        Lot: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            /** Account Id */
            account_id: string;
            /** Security Id */
            security_id: string;
            /** Checkpoint Id */
            checkpoint_id: string;
            quantity: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            acquired: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            holding_evidence: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            basis: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            basis_quantum: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            adjustments: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
        };
        /** Metadata */
        Metadata: {
            /**
             * Schema Version
             * @constant
             */
            schema_version: "synthetic-checkpoint-v1";
            /**
             * Semantics Version
             * @constant
             */
            semantics_version: "authoritative-checkpoint-v1";
            /**
             * Fictional
             * @constant
             */
            fictional: true;
            /** Bundle Id */
            bundle_id: string;
            /** Source Id */
            source_id: string;
            /** Source Version */
            source_version: string;
            /** Profile Id */
            profile_id: string;
            /** Cutoff */
            cutoff: string;
            /** Source Timezone */
            source_timezone: string;
            inclusion: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            /** Included Activity Ids */
            included_activity_ids: string[];
            /** Stipulations */
            stipulations: string[];
        };
        /** Position */
        Position: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            /** Account Id */
            account_id: string;
            /** Security Id */
            security_id: string;
            /** Checkpoint Id */
            checkpoint_id: string;
            quantity: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
        };
        /** PositionResponse */
        PositionResponse: {
            /** Account Id */
            account_id: string;
            /** Security Id */
            security_id: string;
            quantity: components["schemas"]["ValueResponse"];
            lot_quantity: components["schemas"]["ValueResponse"];
            price: components["schemas"]["ValueResponse"];
            market_value: components["schemas"]["ValueResponse"];
            basis: components["schemas"]["ValueResponse"];
            market_minus_basis: components["schemas"]["ValueResponse"];
        };
        /** PreviewResponse */
        PreviewResponse: {
            /**
             * Schema Version
             * @default synthetic-import-api-v1
             * @constant
             */
            schema_version: "synthetic-import-api-v1";
            /**
             * Version
             * @default synthetic-preview-v1
             * @constant
             */
            version: "synthetic-preview-v1";
            receipt: components["schemas"]["ReceiptResponse"];
            /** Recorded At */
            recorded_at: string;
            /**
             * State
             * @enum {string}
             */
            state: "staged" | "rejected" | "committed";
            /** Rejected At */
            rejected_at: string | null;
            source: components["schemas"]["SourceResponse"] | null;
            /** Issues */
            issues: components["schemas"]["APIIssue"][];
            /** Further Issues */
            further_issues: boolean;
            inspection: components["schemas"]["InspectionResponse"] | null;
            /**
             * Planning Ready
             * @default false
             * @constant
             */
            planning_ready: false;
        };
        /** Quote */
        Quote: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            /** Security Id */
            security_id: string;
            /**
             * Currency
             * @constant
             */
            currency: "USD";
            price: components["schemas"]["Fact_Annotated_ExactValue__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            as_of: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            kind: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            session: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            adjustments: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
        };
        /** ReadinessResponse */
        ReadinessResponse: {
            inspection: components["schemas"]["ReadinessState"];
            basis: components["schemas"]["ReadinessState"];
            valuation: components["schemas"]["ReadinessState"];
            coverage: components["schemas"]["ReadinessState"];
            /**
             * Planning Ready
             * @default false
             * @constant
             */
            planning_ready: false;
            /** Planning Reasons */
            planning_reasons: string[];
        };
        /** @enum {string} */
        ReadinessState: "complete" | "incomplete" | "contradictory";
        /** ReceiptResponse */
        ReceiptResponse: {
            raw_sha256: components["schemas"]["Digest"];
            /** Byte Length */
            byte_length: number;
            /**
             * Storage Version
             * @default evidence-bytes-v1
             * @constant
             */
            storage_version: "evidence-bytes-v1";
        };
        /** RejectRequest */
        RejectRequest: {
            /**
             * Schema Version
             * @constant
             */
            schema_version: "synthetic-import-api-v1";
            preview_sha256: components["schemas"]["Digest"];
        };
        /** Security */
        Security: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            issuer_id: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata___PydanticGeneralMetadata_pattern____A-Za-z0-9__A-Za-z0-9_____0_127________"];
            share_class_id: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata___PydanticGeneralMetadata_pattern____A-Za-z0-9__A-Za-z0-9_____0_127________"];
            /** Ticker */
            ticker: string;
            /**
             * Currency
             * @constant
             */
            currency: "USD";
            security_type: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            tax_classification: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
            adjustments: components["schemas"]["Fact_Annotated_str__Strict_strict_True___FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_4096_____AfterValidator__"];
        };
        /** SourceResponse */
        SourceResponse: {
            /**
             * Status
             * @default parsed_unvalidated
             * @constant
             */
            status: "parsed_unvalidated";
            /**
             * Canonicalization Version
             * @default canonical-json-v1
             * @constant
             */
            canonicalization_version: "canonical-json-v1";
            canonical_sha256: components["schemas"]["Digest"];
            document: components["schemas"]["BundleDocument"];
            /** Source Values */
            source_values: components["schemas"]["SourceValue"][];
        };
        /** SourceValue */
        SourceValue: {
            path: components["schemas"]["Location"];
            exact: components["schemas"]["KnownValue"];
        };
        /** UnknownValue */
        UnknownValue: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            state: "unknown";
            /** Value */
            value?: null;
            /** Reasons */
            reasons: string[];
        };
        ValueResponse: components["schemas"]["KnownValue"] | components["schemas"]["UnknownValue"];
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    acquire_session_session_post: {
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
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    diagnostic_diagnostic_get: {
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
                    "application/json": components["schemas"]["Diagnostic"];
                };
            };
        };
    };
    shutdown_shutdown_post: {
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
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    stage_preview_api_v1_previews_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/octet-stream": Uint8Array<ArrayBuffer>;
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
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unsupported Media Type */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
        };
    };
    get_preview_api_v1_previews__identity__get: {
        parameters: {
            query?: never;
            header?: never;
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
                    "application/json": components["schemas"]["PreviewResponse"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unsupported Media Type */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
        };
    };
    current_api_v1_current_get: {
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
                    "application/json": components["schemas"]["CurrentResponse"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unsupported Media Type */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
        };
    };
    commit_api_v1_commit_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CommitRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandResponse"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unsupported Media Type */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
        };
    };
    reject_api_v1_reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RejectRequest"];
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
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unsupported Media Type */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIError"];
                };
            };
        };
    };
}

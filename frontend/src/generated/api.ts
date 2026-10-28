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
    "/runtime": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Runtime Info */
        get: operations["runtime_info_runtime_get"];
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
        /** Stage */
        post: operations["stage_api_v1_previews_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/holdings/cash-treatment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Treat Cash */
        post: operations["treat_cash_api_v1_holdings_cash_treatment_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/holdings/mapping-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Prepare Holdings */
        post: operations["prepare_holdings_api_v1_holdings_mapping_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/candidates/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Candidate */
        post: operations["start_candidate_api_v1_candidates_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/worksheets/check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check Worksheet */
        post: operations["check_worksheet_api_v1_worksheets_check_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/worksheets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Save Worksheet */
        post: operations["save_worksheet_api_v1_worksheets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/worksheets/{identity}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Worksheet */
        get: operations["read_worksheet_api_v1_worksheets__identity__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/worksheets/{identity}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export Worksheet */
        get: operations["export_worksheet_api_v1_worksheets__identity__export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/candidates/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Candidate */
        post: operations["cancel_candidate_api_v1_candidates_cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/candidates/results/{identity}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Candidate Result */
        get: operations["candidate_result_api_v1_candidates_results__identity__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/fetch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Fetch Benchmark */
        post: operations["fetch_benchmark_api_v1_benchmarks_fetch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inputs/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Inputs */
        post: operations["preview_inputs_api_v1_inputs_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inputs/diagnostics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Diagnose Inputs */
        post: operations["diagnose_inputs_api_v1_inputs_diagnostics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Benchmark */
        post: operations["import_benchmark_api_v1_benchmarks_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/observations/{identity}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Benchmark Observation */
        get: operations["benchmark_observation_api_v1_benchmarks_observations__identity__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/observations/{identity}/source": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Benchmark Source */
        get: operations["benchmark_source_api_v1_benchmarks_observations__identity__source_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/rows": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Benchmark Source Rows */
        post: operations["benchmark_source_rows_api_v1_benchmarks_rows_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/review-context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Benchmark Review Context */
        post: operations["benchmark_review_context_api_v1_benchmarks_review_context_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/prepare": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Prepare Benchmark */
        post: operations["prepare_benchmark_api_v1_benchmarks_prepare_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Benchmark */
        post: operations["preview_benchmark_api_v1_benchmarks_review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/diagnostics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Benchmark Diagnostic */
        post: operations["benchmark_diagnostic_api_v1_benchmarks_diagnostics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/benchmarks/select": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Select Benchmark */
        post: operations["select_benchmark_api_v1_benchmarks_select_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/fidelity/previews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Stage Fidelity */
        post: operations["stage_fidelity_api_v1_fidelity_previews_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/fidelity/opening": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Open Fidelity */
        post: operations["open_fidelity_api_v1_fidelity_opening_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lots/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Configure Lots */
        post: operations["configure_lots_api_v1_lots_settings_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lots/diagnostics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Lot Diagnostic */
        post: operations["lot_diagnostic_api_v1_lots_diagnostics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lots/settings/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Lot Settings */
        post: operations["preview_lot_settings_api_v1_lots_settings_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lots/results/{identity}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lot Result */
        get: operations["lot_result_api_v1_lots_results__identity__get"];
        put?: never;
        post?: never;
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
        /** Preview */
        get: operations["preview_api_v1_previews__identity__get"];
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
    "/api/v1/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Catalog */
        get: operations["catalog_api_v1_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/select": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Select */
        post: operations["select_api_v1_select_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Settings */
        post: operations["settings_api_v1_settings_post"];
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
    "/api/v1/diagnostics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Diagnose */
        post: operations["diagnose_api_v1_diagnostics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{identity}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Run */
        get: operations["run_api_v1_runs__identity__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/input-records/{identity}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Input Record */
        get: operations["input_record_api_v1_input_records__identity__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/rows": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** History Rows */
        post: operations["history_rows_api_v1_history_rows_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Refresh History */
        post: operations["refresh_history_api_v1_history_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview History */
        post: operations["preview_history_api_v1_history_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/parts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Stage History Part */
        post: operations["stage_history_part_api_v1_history_parts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/discard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Discard History Parts */
        post: operations["discard_history_parts_api_v1_history_discard_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Plan History */
        post: operations["plan_history_api_v1_history_plan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/diagnostics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** History Diagnostic */
        post: operations["history_diagnostic_api_v1_history_diagnostics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/history/clear": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Clear History */
        post: operations["clear_history_api_v1_history_clear_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/backup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Backup */
        get: operations["download_backup_api_v1_backup_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Backup */
        post: operations["upload_backup_api_v1_restore_post"];
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
        };
        /** APIIssue */
        APIIssue: {
            /** Code */
            code: string;
            /** Path */
            path: (string | number)[];
        };
        /** Account */
        Account: {
            /** Source Account */
            source_account: string;
            /** Account Id */
            account_id: string;
            /** Alias */
            alias: string;
            /**
             * Role
             * @enum {string}
             */
            role: "traded-taxable" | "household-taxable" | "spouse" | "ira-roth" | "scope-unresolved";
            evidence: components["schemas"]["prosper__lot_records__Evidence"];
        };
        /** Activity */
        Activity: {
            /** Id */
            id: string;
            identity: components["schemas"]["Fact_str_"];
            /** Account Ref */
            account_ref: string;
            /** Account Scope */
            account_scope: string;
            day: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            /**
             * Side
             * @enum {string}
             */
            side: "acquisition" | "sale";
            quantity: components["schemas"]["DecimalFact"];
            pnl: components["schemas"]["Fact_str_"];
            /** Source Ref */
            source_ref: string;
        };
        /** Alignment */
        Alignment: {
            request: components["schemas"]["HistoryRequest"];
            rows: components["schemas"]["HistoryTable"];
            /** Issues */
            issues: components["schemas"]["HistoryIssue"][];
            /** Intervals */
            intervals: components["schemas"]["Interval"][];
            /** Complete */
            complete: boolean;
            /** Required Sources */
            required_sources: components["schemas"]["Digest"][];
            /** Validated At */
            validated_at: {
                [key: string]: string;
            };
        };
        /** AnalysisRun */
        AnalysisRun: {
            /**
             * Version
             * @default advisory-analysis-v1
             * @constant
             */
            version: "advisory-analysis-v1";
            /** Id */
            id: string;
            snapshot_id: components["schemas"]["Digest"];
            input_revision: components["schemas"]["Revision"];
            /** Settings */
            settings: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Inputs */
            inputs: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Application Version */
            application_version: string;
            /** Model Version */
            model_version: string;
            /** As Of */
            as_of: string;
            /** Started At */
            started_at: string;
            /** Completed At */
            completed_at?: string | null;
            /**
             * Status
             * @default running
             * @enum {string}
             */
            status: "running" | "complete" | "partial" | "failed";
            /** Outputs */
            outputs?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /**
             * Exclusions
             * @default []
             */
            exclusions: components["schemas"]["Finding"][];
            /**
             * Warnings
             * @default []
             */
            warnings: string[];
        };
        /** BenchmarkDiagnostic */
        BenchmarkDiagnostic: {
            /** Run Id */
            run_id: string;
            expected_revision: components["schemas"]["Revision"];
            /** As Of */
            as_of: string;
            review: components["schemas"]["BenchmarkReview"];
        };
        /** BenchmarkFetch */
        BenchmarkFetch: {
            /** Observation Id */
            observation_id: string;
            /**
             * Ticker
             * @enum {string}
             */
            ticker: "ITOT" | "IVV" | "VTI" | "VOO";
            /** Requested Date */
            requested_date: string | null;
        };
        /** BenchmarkImport */
        BenchmarkImport: {
            request: components["schemas"]["BenchmarkFetch"];
            /** Collected At */
            collected_at: string;
            /** Source Base64 */
            source_base64: string;
            /** Http Status */
            http_status: number;
            /** Content Type */
            content_type: string;
            /** Response Url */
            response_url: string;
            /** Body Complete */
            body_complete: boolean;
        };
        /** BenchmarkObservation */
        BenchmarkObservation: {
            request: components["schemas"]["BenchmarkFetch"];
            /** Collected At */
            collected_at: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "observed" | "unavailable";
            /** Effective Date */
            effective_date?: string | null;
            source_sha256?: components["schemas"]["Digest"] | null;
            /** Http Status */
            http_status?: number | null;
            /** Response Url */
            response_url?: string | null;
            /** Content Type */
            content_type?: string | null;
            /**
             * Body Complete
             * @default true
             */
            body_complete: boolean;
            /**
             * Issues
             * @default []
             */
            issues: string[];
            /** Section Counts */
            section_counts?: {
                [key: string]: number;
            };
            request_sha256: components["schemas"]["Digest"];
            metadata?: components["schemas"]["FundMetadata"] | null;
        };
        /** BenchmarkResult */
        BenchmarkResult: {
            /**
             * Kind
             * @default benchmark-proxy-v1
             * @constant
             */
            kind: "benchmark-proxy-v1";
            /**
             * Label
             * @default equity-only disclosed-holdings proxy
             */
            label: string;
            /** Observation Id */
            observation_id: string;
            /**
             * Ticker
             * @enum {string}
             */
            ticker: "ITOT" | "IVV" | "VTI" | "VOO";
            /** Requested Date */
            requested_date: string | null;
            /** Effective Date */
            effective_date: string;
            /** Collected At */
            collected_at: string;
            /** Reviewed At */
            reviewed_at: string;
            /** Metadata Reference */
            metadata_reference: string;
            metadata_source_sha256: components["schemas"]["Digest"];
            /** Metadata Port Id */
            metadata_port_id: string;
            /** Metadata Cusip */
            metadata_cusip: string;
            /**
             * Status
             * @enum {string}
             */
            status: "estimated-equity-benchmark" | "incomplete" | "unavailable";
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Ledger */
            ledger: components["schemas"]["prosper__equity_benchmark__Row"][];
            /** Source Row Count */
            source_row_count: number;
            /** Included Count */
            included_count: number;
            /** Excluded Count */
            excluded_count: number;
            /** Linked Count */
            linked_count: number;
            /** Unresolved Count */
            unresolved_count: number;
            /** Retained Known Value */
            retained_known_value: string;
            /** Retained Unknown Values */
            retained_unknown_values: components["schemas"]["Locator"][];
            /** Excluded Known Usd Value */
            excluded_known_usd_value: string;
            /** Excluded Unknown Usd Values */
            excluded_unknown_usd_values: components["schemas"]["Locator"][];
            /** Equity Value Total */
            equity_value_total: string | null;
            /** Security Ids */
            security_ids: string[];
            /** Weights */
            weights: number[];
            /**
             * Warnings
             * @default [
             *       "Disclosed equity proxy only; no exact index or full-fund return replication",
             *       "Exclusions are not cash; published percentages are preserved separately",
             *       "Collection time does not establish original publication or point-in-time availability",
             *       "Identity/source review is supplied evidence; risk/tax qualification and financial use remain separate"
             *     ]
             */
            warnings: string[];
        };
        /** BenchmarkReview */
        BenchmarkReview: {
            /** Observation Id */
            observation_id: string;
            /** Reviewed At */
            reviewed_at: string;
            stipulation: components["schemas"]["Stipulation"];
            policy: components["schemas"]["Policy"];
            /** Metadata Base64 */
            metadata_base64: string;
            /** Metadata Reference */
            metadata_reference: string;
            /**
             * Metadata Ticker
             * @enum {string}
             */
            metadata_ticker: "ITOT" | "IVV" | "VTI" | "VOO";
            /**
             * Metadata Port Id
             * @enum {string}
             */
            metadata_port_id: "239724" | "239726" | "0970" | "0968";
            /**
             * Metadata Cusip
             * @enum {string}
             */
            metadata_cusip: "464287150" | "464287200" | "922908769" | "922908363";
            /** Metadata As Of */
            metadata_as_of: string;
            /**
             * Metadata Reviewed
             * @constant
             */
            metadata_reviewed: true;
        };
        /** BenchmarkReviewContext */
        BenchmarkReviewContext: {
            /** Observation Id */
            observation_id: string;
            source_sha256: components["schemas"]["Digest"];
            /** Ticker */
            ticker: string;
            /** Port Id */
            port_id: string;
            /** Requested Date */
            requested_date: string | null;
            /** Effective Date */
            effective_date: string;
            /** Collected At */
            collected_at: string;
            /** Sections */
            sections: components["schemas"]["ReviewSection"][];
            /** Rows */
            rows: components["schemas"]["ReviewRow"][];
            mapping: components["schemas"]["PreparedMapping"] | null;
            metadata: components["schemas"]["FundMetadata"] | null;
        };
        /** BenchmarkRowsRequest */
        BenchmarkRowsRequest: {
            /** Observation Id */
            observation_id: string;
            /**
             * Section
             * @default
             */
            section: string;
            /**
             * Query
             * @default
             */
            query: string;
            /**
             * Issue
             * @default
             */
            issue: string;
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /**
             * Limit
             * @default 50
             */
            limit: number;
        };
        /** BenchmarkSelect */
        BenchmarkSelect: {
            /** Run Id */
            run_id: string;
            /** Command Key */
            command_key: string;
            expected_revision: components["schemas"]["Revision"];
        };
        /** BenchmarkSourcePage */
        BenchmarkSourcePage: {
            /** Rows Available */
            rows_available: boolean;
            /** Section Counts */
            section_counts: {
                [key: string]: number;
            };
            /** Issue Groups */
            issue_groups: components["schemas"]["SourceIssueGroup"][];
            /** Total Rows */
            total_rows: number | null;
            /** Matched Rows */
            matched_rows: number | null;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
            /** Rows */
            rows: components["schemas"]["SourceRow"][];
        };
        /** BuyOrder */
        BuyOrder: {
            /** Security Id */
            security_id: string;
            /** Shares */
            shares: number;
        };
        /** BuyScreen */
        BuyScreen: {
            /** Security Id */
            security_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "conditional" | "blocked";
            /** Blockers */
            blockers: string[];
        };
        /** CandidateAsset */
        CandidateAsset: {
            security: components["schemas"]["prosper__advisory_records__Security"];
            sector: components["schemas"]["Fact_str_"];
            industry: components["schemas"]["Fact_str_"];
        };
        /** CandidateCheck */
        CandidateCheck: {
            orders: components["schemas"]["Orders"];
            /** Feasible */
            feasible: boolean;
            /** Unresolved */
            unresolved: boolean;
            /** Blockers */
            blockers: string[];
            metrics: components["schemas"]["CandidateMetrics"] | null;
            /** Warnings */
            warnings: string[];
        };
        /** CandidateControls */
        CandidateControls: {
            /**
             * Method
             * @enum {string}
             */
            method: "complete-cartesian-whole-share-reference" | "deterministic-loss-prefix-repair-v1";
            /** Max Candidates */
            max_candidates: number;
            /** Max Cost */
            max_cost: string;
            min_price_loss: components["schemas"]["OptionalLimit"];
            max_cost_to_loss: components["schemas"]["OptionalLimit"];
            min_scenario_net_value: components["schemas"]["OptionalLimit"];
            scenario: components["schemas"]["TaxScenario"] | null;
            /** Buy Fee Per Security Order */
            buy_fee_per_security_order: string;
            /** Buy Premium Bps */
            buy_premium_bps: string;
            /** Sale Bounds */
            sale_bounds: {
                [key: string]: number;
            };
            /** Buy Bounds */
            buy_bounds: {
                [key: string]: number;
            };
            /** Max States */
            max_states: number;
            /** Timeout Seconds */
            timeout_seconds: number;
        };
        /** CandidateFit */
        CandidateFit: {
            /**
             * Kind
             * @default candidate-fit-v1
             * @constant
             */
            kind: "candidate-fit-v1";
            /** Status */
            status: string;
            /** Issues */
            issues: string[];
            /** Version */
            version: string;
            /** Security Ids */
            security_ids: string[];
            /** Cutoff */
            cutoff: string;
            /** Sessions */
            sessions: number;
            /** Calendar */
            calendar: string;
            /** Timezone */
            timezone: string;
            /** Variant */
            variant: string;
            /** Source Units */
            source_units: string;
            /** Purpose */
            purpose: string;
            /** Horizon */
            horizon: number;
            configuration_sha256: components["schemas"]["Digest"];
            input_sha256: components["schemas"]["Digest"];
            output_sha256: components["schemas"]["Digest"];
            identity_sha256: components["schemas"]["Digest"];
            /** Scalars */
            scalars: components["schemas"]["ScalarDiagnostic"][];
            dcc_fit: components["schemas"]["CorrelationDiagnostic"] | null;
            projection: components["schemas"]["ProjectionDiagnostic"] | null;
        };
        /** CandidateIdentity */
        CandidateIdentity: {
            /** Run Id */
            run_id: string;
        };
        /** CandidateLimits */
        CandidateLimits: {
            /** Tracking Error */
            tracking_error: string;
            /** Max Cost */
            max_cost: string;
            /** Max Orders */
            max_orders: number;
            /** Max Turnover */
            max_turnover: string;
            /** Min Order Notional */
            min_order_notional: string;
            max_order_notional: components["schemas"]["OptionalLimit"];
            /** Max Position Weight */
            max_position_weight: string;
            /** Exposures */
            exposures: components["schemas"]["ExposureLimit"][];
            min_price_loss: components["schemas"]["OptionalLimit"];
            max_cost_to_loss: components["schemas"]["OptionalLimit"];
            min_scenario_net_value: components["schemas"]["OptionalLimit"];
            scenario: components["schemas"]["TaxScenario"] | null;
        };
        /** CandidateMetrics */
        CandidateMetrics: {
            /** Price Loss */
            price_loss: number;
            /** Short Term Loss */
            short_term_loss: number;
            /** Long Term Loss */
            long_term_loss: number;
            /** Unknown Term Loss */
            unknown_term_loss: number;
            /** Net Proceeds Tax Pnl */
            net_proceeds_tax_pnl: number;
            /** Modeled Cost */
            modeled_cost: number;
            /** Final Cash */
            final_cash: number;
            /** Final Nav */
            final_nav: number;
            /** Final Quantities */
            final_quantities: number[];
            /** Final Weights */
            final_weights: number[];
            /** Tracking Error */
            tracking_error: number;
            /** Risk Upper Bound */
            risk_upper_bound: number;
            /** Turnover */
            turnover: number;
            /** Order Count */
            order_count: number;
            /** Scenario Net Value */
            scenario_net_value: number | null;
        };
        /** CandidateOutput */
        CandidateOutput: {
            /**
             * Kind
             * @default candidate-workflow-v1
             * @constant
             */
            kind: "candidate-workflow-v1";
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "checked" | "unavailable" | "cancelled" | "timeout" | "interrupted" | "stale" | "failed";
            /** Issues */
            issues: string[];
            risk: components["schemas"]["CandidateFit"] | null;
            search: components["schemas"]["CandidateSearch"] | null;
            /**
             * Warnings
             * @default [
             *       "Unqualified proxy risk and conditional loss estimates; no financial-use authorization",
             *       "Independent tax/model review, real-source qualification and calibration remain open"
             *     ]
             */
            warnings: string[];
            /**
             * Financial Use Authorized
             * @default false
             * @constant
             */
            financial_use_authorized: false;
        };
        /** CandidateRequest */
        CandidateRequest: {
            /**
             * Version
             * @default tiny-candidate-request-v1
             * @constant
             */
            version: "tiny-candidate-request-v1";
            /**
             * Method
             * @enum {string}
             */
            method: "complete-cartesian-whole-share-reference" | "deterministic-loss-prefix-repair-v1";
            snapshot: components["schemas"]["ImportSnapshot"];
            /** Retained Snapshots */
            retained_snapshots: components["schemas"]["ImportSnapshot"][];
            /** Assets */
            assets: components["schemas"]["CandidateAsset"][];
            settings: components["schemas"]["LotSettings"];
            risk: components["schemas"]["RiskInput"];
            limits: components["schemas"]["CandidateLimits"];
            /** Buy Fee Per Security Order */
            buy_fee_per_security_order: string;
            /** Buy Premium Bps */
            buy_premium_bps: string;
            /** Sale Bounds */
            sale_bounds: {
                [key: string]: number;
            };
            /** Buy Bounds */
            buy_bounds: {
                [key: string]: number;
            };
            /** Max States */
            max_states: number;
            /** Max Candidates */
            max_candidates: number;
        };
        /** CandidateSearch */
        CandidateSearch: {
            /**
             * Version
             * @default tiny-candidate-result-v1
             * @constant
             */
            version: "tiny-candidate-result-v1";
            inputs: components["schemas"]["CandidateRequest"];
            /**
             * Method
             * @enum {string}
             */
            method: "complete-cartesian-whole-share-reference" | "deterministic-loss-prefix-repair-v1";
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "optimal-in-domain" | "no-feasible-harvest-in-domain" | "feasible-incumbent" | "no-candidate" | "invalid-input" | "numerical-failure";
            /**
             * Stopping
             * @enum {string}
             */
            stopping: "complete" | "state-limit" | "cancelled" | "invalid-input" | "numerical-failure" | "proposal-set-exhausted";
            /** Domain States */
            domain_states: number | null;
            /** Evaluated States */
            evaluated_states: number;
            /** Feasible Harvests */
            feasible_harvests: number;
            /** Unresolved States */
            unresolved_states: number;
            baseline: components["schemas"]["CandidateCheck"];
            best: components["schemas"]["CandidateCheck"] | null;
            /**
             * Candidates
             * @default []
             */
            candidates: components["schemas"]["CandidateCheck"][];
            /** Exclusions */
            exclusions: string[];
            /** Warnings */
            warnings: string[];
            /**
             * Financial Use Authorized
             * @default false
             * @constant
             */
            financial_use_authorized: false;
        };
        /** CandidateStart */
        CandidateStart: {
            /** Run Id */
            run_id: string;
            expected_revision: components["schemas"]["Revision"];
            /** As Of */
            as_of: string;
            /** Input Run Id */
            input_run_id: string;
            controls: components["schemas"]["CandidateControls"];
        };
        /** Cash */
        Cash: {
            /** Id */
            id: string;
            /** Account Id */
            account_id: string;
            /** Source Ref */
            source_ref: string;
            amount: components["schemas"]["DecimalFact"];
            /** Kind */
            kind: string;
            /**
             * Currency
             * @default USD
             * @constant
             */
            currency: "USD";
        };
        /** CashHolding */
        CashHolding: {
            /** Security Id */
            security_id: string;
            /** Ticker */
            ticker: string;
            name: components["schemas"]["Fact_str_"];
            /** Source Refs */
            source_refs: string[];
            reported_value: components["schemas"]["DecimalFact"];
            /**
             * Currency
             * @default USD
             * @constant
             */
            currency: "USD";
            treatment: components["schemas"]["CashTreatment"] | null;
        };
        /** CashTreatment */
        CashTreatment: {
            source_sha256: components["schemas"]["Digest"];
            /** Account Id */
            account_id: string;
            /** Source As Of */
            source_as_of: string;
            /** Security Id */
            security_id: string;
            /** Source Refs */
            source_refs: string[];
            /**
             * Kind
             * @enum {string}
             */
            kind: "cash" | "cash-equivalent";
            /** Recorded At */
            recorded_at: string;
            /**
             * Assertion
             * @default User classified this holding; funding is not asserted
             * @constant
             */
            assertion: "User classified this holding; funding is not asserted";
        };
        /** CashTreatmentRequest */
        CashTreatmentRequest: {
            snapshot_id: components["schemas"]["Digest"];
            /** Security Id */
            security_id: string;
            /** Kind */
            kind: ("cash" | "cash-equivalent") | null;
            /** Command Key */
            command_key: string;
            expected_revision: components["schemas"]["Revision"];
        };
        /** CatalogResponse */
        CatalogResponse: {
            /** Snapshots */
            snapshots: components["schemas"]["SnapshotEntry"][];
            /** Runs */
            runs: string[];
            /** Worksheets */
            worksheets: string[];
            /** Benchmarks */
            benchmarks: components["schemas"]["BenchmarkObservation"][];
            /** Pending History Parts */
            pending_history_parts: components["schemas"]["Digest"][];
        };
        /** ClassificationInput */
        ClassificationInput: {
            /** Security Id */
            security_id: string;
            sector: components["schemas"]["Fact_str_"];
            industry: components["schemas"]["Fact_str_"];
            evidence: components["schemas"]["SourceFact"];
        };
        /** ClearHistoryRequest */
        ClearHistoryRequest: {
            /** Command Key */
            command_key: string;
            expected_revision: components["schemas"]["Revision"];
        };
        /** CommandResponse */
        CommandResponse: {
            /** Outcome */
            outcome: string;
            revision: components["schemas"]["Revision"];
        };
        /** CorrelationDiagnostic */
        CorrelationDiagnostic: {
            /** Status */
            status: string;
            /** Issues */
            issues: string[];
            /** Version */
            version: string;
            configuration_sha256: components["schemas"]["Digest"];
            input_sha256: components["schemas"]["Digest"];
            output_sha256: components["schemas"]["Digest"];
            identity_sha256: components["schemas"]["Digest"];
            /** Starts */
            starts: components["schemas"]["StartDiagnostic"][];
            /** Selected Start */
            selected_start: number | null;
            /** Objective Range */
            objective_range: [
                number,
                number
            ] | null;
            /** Parameter Ranges */
            parameter_ranges: [
                number,
                number
            ][];
            /** Target Kind */
            target_kind: string;
            target_input_sha256: components["schemas"]["Digest"];
            target_identity_sha256: components["schemas"]["Digest"];
            /** Parameters */
            parameters: [
                number,
                number
            ] | null;
            /** Objective */
            objective: number | null;
            /** Gradient */
            gradient: [
                number,
                number
            ] | null;
            /** Target Symmetry Correction */
            target_symmetry_correction: number | null;
        };
        /** CurrentResponse */
        CurrentResponse: {
            revision: components["schemas"]["Revision"];
            snapshot_id: components["schemas"]["Digest"] | null;
            /** Settings */
            settings: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Current Run Id */
            current_run_id: string | null;
        };
        /** DecimalFact */
        DecimalFact: {
            /** Value */
            value: string | null;
            /** Reason */
            reason?: string | null;
        };
        /** Decision */
        Decision: {
            locator: components["schemas"]["Locator"];
            /**
             * Action
             * @enum {string}
             */
            action: "include" | "exclude";
            /** Reason */
            reason: string;
        };
        /** Diagnostic */
        Diagnostic: {
            /**
             * Status
             * @default local_diagnostic
             * @constant
             */
            status: "local_diagnostic";
            /**
             * Planning Ready
             * @default false
             * @constant
             */
            planning_ready: false;
        };
        /** DiagnosticRequest */
        DiagnosticRequest: {
            /** Run Id */
            run_id: string;
            expected_revision: components["schemas"]["Revision"];
            /** As Of */
            as_of: string;
        };
        Digest: string;
        /** ExposureLimit */
        ExposureLimit: {
            /**
             * Level
             * @enum {string}
             */
            level: "security" | "sector" | "industry";
            /** Group */
            group: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "absolute" | "active";
            /** Maximum */
            maximum: string;
        };
        /** Fact */
        Fact: {
            /** Raw */
            raw: string | null;
            evidence: components["schemas"]["prosper__basket__Evidence"];
            /**
             * Unknown Reasons
             * @default []
             */
            unknown_reasons: string[];
        };
        /** Fact[Annotated[str, Strict(strict=True), AfterValidator]] */
        Fact_Annotated_str__Strict_strict_True___AfterValidator__: {
            /** Value */
            value: string | null;
            /** Reason */
            reason?: string | null;
        };
        /** Fact[bool] */
        Fact_bool_: {
            /** Value */
            value: boolean | null;
            /** Reason */
            reason?: string | null;
        };
        /** Fact[float] */
        Fact_float_: {
            /** Value */
            value: number | null;
            /** Reason */
            reason?: string | null;
        };
        /** Fact[str] */
        Fact_str_: {
            /** Value */
            value: string | null;
            /** Reason */
            reason?: string | null;
        };
        /** FidelityContext */
        FidelityContext: {
            /**
             * Version
             * @constant
             */
            version: "fidelity-lot-context-v1";
            source_sha256: components["schemas"]["Digest"];
            /** Source As Of */
            source_as_of: string;
            /**
             * Currency
             * @constant
             */
            currency: "USD";
            /** Accounts */
            accounts: components["schemas"]["Account"][];
            /** Mappings */
            mappings: components["schemas"]["SecurityMapping"][];
            source_coverage: components["schemas"]["Fact_str_"];
            reported_basis_assumption: components["schemas"]["Fact_bool_"];
            evidence: components["schemas"]["prosper__lot_records__Evidence"];
            screening: components["schemas"]["ScreeningFacts"];
            /**
             * Independent Positions
             * @default []
             */
            independent_positions: components["schemas"]["IndependentPosition"][];
        };
        /**
         * FidelityOpening
         * @description Minimal user-supplied opening facts; unresolved identity stays unresolved.
         */
        FidelityOpening: {
            /** Source Base64 */
            source_base64: string;
            /** Source Account */
            source_account: string;
            /** Source As Of */
            source_as_of: string;
            /** Account Alias */
            account_alias: string;
            /**
             * Currency
             * @constant
             */
            currency: "USD";
            /** Recorded At */
            recorded_at: string;
        };
        /** FidelityPreviewResponse */
        FidelityPreviewResponse: {
            preview: components["schemas"]["PreviewResponse"] | null;
            /** Issues */
            issues: components["schemas"]["SourceIssue"][];
        };
        /** FidelityUpload */
        FidelityUpload: {
            context: components["schemas"]["FidelityContext"];
            /** Source Base64 */
            source_base64: string;
        };
        /** FinalCashTarget */
        FinalCashTarget: {
            /** Enabled */
            enabled: boolean;
            /** Amount */
            amount: string | null;
            /** Investor Tolerance */
            investor_tolerance: string | null;
        };
        /** Finding */
        Finding: {
            /** Code */
            code: string;
            /** Locator */
            locator: string;
            /** Reason */
            reason: string;
        };
        /** Fund */
        Fund: {
            /** Ticker */
            ticker: string;
            /** Port Id */
            port_id: string;
        };
        /** FundMetadata */
        FundMetadata: {
            /**
             * Ticker
             * @default IVV
             * @constant
             */
            ticker: "IVV";
            /**
             * Port Id
             * @default 239726
             * @constant
             */
            port_id: "239726";
            /**
             * Cusip
             * @default 464287200
             * @constant
             */
            cusip: "464287200";
            /**
             * Response Url
             * @default https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf
             */
            response_url: string;
            /** Canonical Url */
            canonical_url: string;
            /** Content Type */
            content_type: string;
            /** Collected At */
            collected_at: string;
            /** Holdings Date */
            holdings_date: string;
            source_sha256: components["schemas"]["Digest"];
            /** Byte Count */
            byte_count: number;
        };
        /** GroupWeight */
        GroupWeight: {
            /**
             * Level
             * @enum {string}
             */
            level: "sector" | "industry";
            classification: components["schemas"]["Fact_str_"];
            /** Weight */
            weight: number;
        };
        /** HistoryBatch */
        HistoryBatch: {
            /**
             * Version
             * @default advisory-history-v2
             * @constant
             */
            version: "advisory-history-v2";
            /** Source Name */
            source_name: string;
            source_sha256: components["schemas"]["Digest"];
            /** Collected At */
            collected_at: string;
            /** Validated At */
            validated_at: string;
            /** Contexts */
            contexts: components["schemas"]["SeriesContext"][];
            sessions: components["schemas"]["SessionGrid"];
            /**
             * Validation Scope
             * @enum {string}
             */
            validation_scope: "requested-interval" | "full-window";
            rows: components["schemas"]["HistoryTable"];
            /**
             * Findings
             * @default []
             */
            findings: string[];
        };
        /** HistoryDiagnosticRequest */
        HistoryDiagnosticRequest: {
            request: components["schemas"]["HistoryRequest"];
            /** Run Id */
            run_id: string;
            expected_revision: components["schemas"]["Revision"];
            /** As Of */
            as_of: string;
        };
        /** HistoryIssue */
        HistoryIssue: {
            /** Security Id */
            security_id: string;
            /** Session */
            session: string | null;
            /** Code */
            code: string;
            /** Reason */
            reason: string;
        };
        /** HistoryManifest */
        HistoryManifest: {
            /**
             * Version
             * @default advisory-history-manifest-v1
             * @constant
             */
            version: "advisory-history-manifest-v1";
            /** Part Count */
            part_count: number;
            /** Part Ids */
            part_ids: components["schemas"]["Digest"][];
            /** Command Key */
            command_key: string;
            expected_revision: components["schemas"]["Revision"];
        };
        /** HistoryPart */
        HistoryPart: {
            batch: components["schemas"]["HistoryBatch"];
            /** Source Zlib Base64 */
            source_zlib_base64: string;
        };
        /** HistoryPartReceipt */
        HistoryPartReceipt: {
            id: components["schemas"]["Digest"];
            batch: components["schemas"]["HistoryBatch"];
        };
        /** HistoryPlanRequest */
        HistoryPlanRequest: {
            request: components["schemas"]["HistoryRequest"];
        };
        /** HistoryRequest */
        HistoryRequest: {
            /** Series */
            series: components["schemas"]["SeriesContext"][];
            /** Sessions */
            sessions: string[];
            /** Predecessor */
            predecessor: string;
            /** Cutoff */
            cutoff: string;
            /** Known At */
            known_at: string;
            /** Calendar Evidence */
            calendar_evidence: string;
            /** Overlap Sessions */
            overlap_sessions: number;
            /**
             * Manual Security Ids
             * @default []
             */
            manual_security_ids: string[];
            profile?: components["schemas"]["Profile"] | null;
        };
        /** HistoryRowsPage */
        HistoryRowsPage: {
            /** Row Count */
            row_count: number;
            /** Offset */
            offset: number;
            /** Columns */
            columns: string[];
            /** Rows */
            rows: (string | number | null)[][];
        };
        /** HistoryRowsRequest */
        HistoryRowsRequest: {
            table: components["schemas"]["HistoryTable"];
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /**
             * Limit
             * @default 20
             */
            limit: number;
        };
        /** HistoryTable */
        HistoryTable: {
            /**
             * Encoding
             * @default bz2-column-json-v3
             * @constant
             */
            encoding: "bz2-column-json-v3";
            /**
             * Kind
             * @enum {string}
             */
            kind: "observations" | "alignment";
            /** Row Count */
            row_count: number;
            /** Data */
            data: string;
        };
        /** HoldingMappingRow */
        HoldingMappingRow: {
            source: components["schemas"]["prosper__advisory_records__Security"];
            /** Source Refs */
            source_refs: string[];
            /** Security Id */
            security_id: string;
            /**
             * Disposition
             * @enum {string}
             */
            disposition: "mapped" | "preserved" | "excluded" | "cash-treatment";
            /** Reason */
            reason: string;
            /** Benchmark Index */
            benchmark_index?: number | null;
            reported_value: components["schemas"]["DecimalFact"];
            /** Excluded Bps */
            excluded_bps?: number | null;
            /** Highlight */
            highlight?: boolean | null;
        };
        /** HoldingPreparation */
        HoldingPreparation: {
            /**
             * Method
             * @default same-date-ivv-holdings-v1
             * @constant
             */
            method: "same-date-ivv-holdings-v1";
            source_snapshot_id: components["schemas"]["Digest"];
            source_sha256: components["schemas"]["Digest"];
            /** Account Id */
            account_id: string;
            /** Source As Of */
            source_as_of: string;
            /** Benchmark Run Id */
            benchmark_run_id: string;
            benchmark_source_sha256: components["schemas"]["Digest"];
            metadata_source_sha256: components["schemas"]["Digest"];
            /** Benchmark Date */
            benchmark_date: string;
            /** Recorded At */
            recorded_at: string;
            /** Rows */
            rows: components["schemas"]["HoldingMappingRow"][];
            reference_value_usd: components["schemas"]["DecimalFact"];
            /** Excluded Known Value Usd */
            excluded_known_value_usd: string;
            /** Unknown Value Ids */
            unknown_value_ids: string[];
            /** Aggregate Excluded Bps */
            aggregate_excluded_bps: number | null;
            /** Aggregate Highlight */
            aggregate_highlight: boolean | null;
            /** Coverage Unknown Reasons */
            coverage_unknown_reasons: string[];
        };
        /** HoldingsMappingRequest */
        HoldingsMappingRequest: {
            snapshot_id: components["schemas"]["Digest"];
            /** Benchmark Run Id */
            benchmark_run_id: string;
            expected_revision: components["schemas"]["Revision"];
            /** Recorded At */
            recorded_at: string;
            /** Exclusions */
            exclusions?: {
                [key: string]: string;
            };
        };
        /** ImportSnapshot */
        ImportSnapshot: {
            /**
             * Version
             * @default advisory-import-v1
             * @constant
             */
            version: "advisory-import-v1";
            /** Source Type */
            source_type: string;
            /** Source Name */
            source_name: string;
            source_sha256: components["schemas"]["Digest"];
            /** Account Id */
            account_id: string;
            /** Account Alias */
            account_alias: string;
            /** Account Scope */
            account_scope: string;
            /** Source As Of */
            source_as_of: string;
            /** Securities */
            securities: components["schemas"]["prosper__advisory_records__Security"][];
            /** Lots */
            lots: components["schemas"]["Lot"][];
            /** Positions */
            positions: components["schemas"]["Position"][];
            /** Cash */
            cash: components["schemas"]["Cash"][];
            /**
             * Cash Treatments
             * @default []
             */
            cash_treatments: components["schemas"]["CashTreatment"][];
            holding_preparation?: components["schemas"]["HoldingPreparation"] | null;
            /**
             * Findings
             * @default []
             */
            findings: components["schemas"]["Finding"][];
            /**
             * Exclusions
             * @default []
             */
            exclusions: components["schemas"]["Finding"][];
            /** Observations */
            observations?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** IndependentPosition */
        IndependentPosition: {
            /** Security Id */
            security_id: string;
            quantity: components["schemas"]["DecimalFact"];
            /** Source Ref */
            source_ref: string;
        };
        /** InputIssue */
        InputIssue: {
            /**
             * Scope
             * @enum {string}
             */
            scope: "universe" | "identity" | "marks" | "history" | "taxonomy" | "profile" | "settings" | "source" | "benchmark";
            /** Security Id */
            security_id?: string | null;
            /** Locator */
            locator: string;
            /** Code */
            code: string;
            /** Reason */
            reason: string;
        };
        /** InputProfile */
        InputProfile: {
            /**
             * Variant
             * @constant
             */
            variant: "idr-dcc-nl";
            model: components["schemas"]["Profile"] | null;
            /** Model Reference */
            model_reference: string;
            /** Lookback Sessions */
            lookback_sessions: number;
            /** Minimum History Sessions */
            minimum_history_sessions: number;
            /** Horizon Sessions */
            horizon_sessions: number;
            /** Annualization Sessions */
            annualization_sessions: number;
            /** Max Mark Age Days */
            max_mark_age_days: number;
            /** Max Snapshot Age Days */
            max_snapshot_age_days: number;
            /** Max Benchmark Age Days */
            max_benchmark_age_days: number;
            /** Max History Age Days */
            max_history_age_days: number;
            /** Require Full Window Validation */
            require_full_window_validation: boolean;
            /** Maximum Universe Size */
            maximum_universe_size: number;
            /**
             * Short History Policy
             * @constant
             */
            short_history_policy: "block";
        };
        /** InputSource */
        InputSource: {
            sha256: components["schemas"]["Digest"];
            /** Source Base64 */
            source_base64: string;
        };
        /** Interval */
        Interval: {
            /** Security Id */
            security_id: string;
            /** Sessions */
            sessions: string[];
            /**
             * Reason
             * @enum {string}
             */
            reason: "new-name" | "leading" | "interior" | "tail" | "manual" | "coherence";
        };
        /** InvestorControl */
        InvestorControl: {
            /**
             * Name
             * @enum {string}
             */
            name: "tracking_error" | "max_orders" | "turnover" | "min_trade_notional" | "max_trade_notional" | "max_position_weight" | "sector_exposure" | "industry_exposure";
            /** Enabled */
            enabled: boolean;
            value: components["schemas"]["DecimalFact"];
            /**
             * Unit
             * @enum {string}
             */
            unit: "decimal-weight" | "USD" | "orders" | "annualized-decimal-volatility";
            /** Reference */
            reference: string;
            /** Group */
            group?: string | null;
            /** Kind */
            kind?: ("absolute" | "active") | null;
        };
        /** Issue */
        Issue: {
            /** Location */
            location: string;
            /** Code */
            code: string;
            /**
             * Reasons
             * @default []
             */
            reasons: string[];
        };
        JsonValue: unknown;
        /** Locator */
        Locator: {
            /** Section */
            section: string;
            /** Index */
            index: number;
        };
        /** Lot */
        Lot: {
            /** Id */
            id: string;
            /** Account Id */
            account_id: string;
            /** Security Id */
            security_id: string;
            /** Source Ref */
            source_ref: string;
            quantity: components["schemas"]["DecimalFact"];
            total_basis: components["schemas"]["DecimalFact"];
            acquired: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            term: components["schemas"]["Fact_str_"];
            /**
             * @default {
             *       "reason": "Reported value not supplied"
             *     }
             */
            reported_value: components["schemas"]["DecimalFact"];
        };
        /** LotDiagnosticRequest */
        LotDiagnosticRequest: {
            /** Run Id */
            run_id: string;
            expected_revision: components["schemas"]["Revision"];
            /** As Of */
            as_of: string;
            /** Sale Quantities */
            sale_quantities?: {
                [key: string]: number;
            };
            /**
             * Replacement Security Ids
             * @default []
             */
            replacement_security_ids: string[];
        };
        /** LotResult */
        LotResult: {
            /**
             * Kind
             * @default lot-opportunities-v1
             * @constant
             */
            kind: "lot-opportunities-v1";
            /** Rows */
            rows: components["schemas"]["prosper__lot_opportunities__Row"][];
            /** Buy Screens */
            buy_screens: components["schemas"]["BuyScreen"][];
            conditional_price_loss_subtotal: components["schemas"]["Fact_float_"];
            /** Counts */
            counts: {
                [key: string]: number;
            };
            /** Warnings */
            warnings: string[];
            /**
             * Validation Outcome
             * @default not_validated
             * @constant
             */
            validation_outcome: "not_validated";
        };
        /** LotSettings */
        LotSettings: {
            /** Analysis Date */
            analysis_date: string;
            /** Max Mark Age Days */
            max_mark_age_days: number;
            /** Max Snapshot Age Days */
            max_snapshot_age_days: number;
            /** Marks */
            marks: components["schemas"]["Mark"][];
            sell_fee_per_isolated_order: components["schemas"]["DecimalFact"];
            sell_discount_bps: components["schemas"]["DecimalFact"];
            /** Cash To Invest */
            cash_to_invest: string;
            /** Cash Budget Reviewed */
            cash_budget_reviewed: boolean;
            final_cash_target: components["schemas"]["FinalCashTarget"];
            funding_assumption: components["schemas"]["Fact_str_"];
            history_coverage: components["schemas"]["Fact_str_"];
            /**
             * Manual Restrictions
             * @default []
             */
            manual_restrictions: components["schemas"]["Restriction"][];
            /**
             * Supplied Activity
             * @default []
             */
            supplied_activity: components["schemas"]["Activity"][];
            /**
             * Relationships
             * @default []
             */
            relationships: components["schemas"]["Relationship"][];
        };
        /** LotSettingsInput */
        LotSettingsInput: {
            settings: components["schemas"]["LotSettings"];
        };
        /** LotSettingsRequest */
        LotSettingsRequest: {
            settings: components["schemas"]["LotSettings"];
            /** Command Key */
            command_key: string;
            expected_revision: components["schemas"]["Revision"];
        };
        /** Mark */
        Mark: {
            /** Security Id */
            security_id: string;
            /** Identity */
            identity: string;
            price: components["schemas"]["DecimalFact"];
            day: components["schemas"]["Fact_Annotated_str__Strict_strict_True___AfterValidator__"];
            /** Source Ref */
            source_ref: string;
            /**
             * Currency
             * @constant
             */
            currency: "USD";
        };
        /** MarkInput */
        MarkInput: {
            mark: components["schemas"]["Mark"];
            evidence: components["schemas"]["SourceFact"];
        };
        /** Member */
        Member: {
            /** Security Id */
            security_id: string;
            /** Roles */
            roles: ("held" | "benchmark" | "candidate")[];
            /** Locators */
            locators: string[];
            /** Held Quantity */
            held_quantity: number | null;
            /** Benchmark Weight */
            benchmark_weight: number | null;
            /** Mark */
            mark: number | null;
            /** Sector */
            sector: string | null;
            /** Industry */
            industry: string | null;
        };
        /** MetadataImport */
        MetadataImport: {
            /** Collected At */
            collected_at: string;
            /** Response Url */
            response_url: string;
            /** Content Type */
            content_type: string;
            /** Http Status */
            http_status: number;
            /** Body Complete */
            body_complete: boolean;
            /** Source Base64 */
            source_base64: string;
        };
        /** ModeledBundle */
        ModeledBundle: {
            /**
             * Version
             * @default modeled-inputs-v1
             * @constant
             */
            version: "modeled-inputs-v1";
            /** Analysis Date */
            analysis_date: string;
            /** Candidate Security Ids */
            candidate_security_ids: string[];
            /** Securities */
            securities: components["schemas"]["SecurityInput"][];
            /** Marks */
            marks: components["schemas"]["MarkInput"][];
            /** Taxonomy Name */
            taxonomy_name: string;
            /** Taxonomy Version */
            taxonomy_version: string;
            /** Classifications */
            classifications: components["schemas"]["ClassificationInput"][];
            history: components["schemas"]["HistoryRequest"];
            profile: components["schemas"]["InputProfile"];
            /** Investor Controls */
            investor_controls: components["schemas"]["InvestorControl"][];
        };
        /** ModeledDiagnostic */
        ModeledDiagnostic: {
            bundle: components["schemas"]["ModeledBundle"];
            /** Sources */
            sources: components["schemas"]["InputSource"][];
            /** Run Id */
            run_id: string;
            /** Expected Revision */
            expected_revision: number;
            /** As Of */
            as_of: string;
        };
        /** ModeledResult */
        ModeledResult: {
            /**
             * Kind
             * @default modeled-inputs-v1
             * @constant
             */
            kind: "modeled-inputs-v1";
            /** Input Revision */
            input_revision: number;
            /** Members */
            members: components["schemas"]["Member"][];
            /** Security Ids */
            security_ids: string[];
            /** Sessions */
            sessions: string[];
            /** Return Cell Count */
            return_cell_count: number;
            /** Unavailable Return Count */
            unavailable_return_count: number;
            /** Exclusions */
            exclusions: components["schemas"]["Finding"][];
            /** Issues */
            issues: components["schemas"]["InputIssue"][];
            /** Required Sources */
            required_sources: components["schemas"]["Digest"][];
            /** Software Inputs Complete */
            software_inputs_complete: boolean;
            /** Innovation Inputs Available */
            innovation_inputs_available: boolean;
            /**
             * Risk Available
             * @default false
             * @constant
             */
            risk_available: false;
            /**
             * Financial Use Authorized
             * @default false
             * @constant
             */
            financial_use_authorized: false;
            /**
             * Warnings
             * @default [
             *       "Unqualified supplied-input diagnostics; no provider, investor profile or financial acceptance",
             *       "Complete input coverage does not establish calibrated risk or validated suggestions",
             *       "Excluded holdings and untouched account cash are outside the modeled sleeve"
             *     ]
             */
            warnings: string[];
        };
        /** ModeledUpload */
        ModeledUpload: {
            bundle: components["schemas"]["ModeledBundle"];
            /** Sources */
            sources: components["schemas"]["InputSource"][];
        };
        /** OptionalLimit */
        OptionalLimit: {
            /** Enabled */
            enabled: boolean;
            /** Value */
            value: string | null;
        };
        /** Orders */
        Orders: {
            /** Sales */
            sales: components["schemas"]["SaleOrder"][];
            /** Buys */
            buys: components["schemas"]["BuyOrder"][];
        };
        /** Policy */
        Policy: {
            /** Values */
            values: components["schemas"]["ValueField"][];
            /** Decisions */
            decisions: components["schemas"]["Decision"][];
            /**
             * Version
             * @default equity-benchmark-v1
             */
            version: string;
        };
        /** Position */
        Position: {
            /** Id */
            id: string;
            /** Account Id */
            account_id: string;
            /** Security Id */
            security_id: string;
            /** Source Ref */
            source_ref: string;
            quantity: components["schemas"]["DecimalFact"];
            /**
             * @default {
             *       "reason": "Reported value not supplied"
             *     }
             */
            reported_value: components["schemas"]["DecimalFact"];
        };
        /** PrepareRequest */
        PrepareRequest: {
            /** Observation Id */
            observation_id: string;
            metadata_response?: components["schemas"]["MetadataImport"] | null;
        };
        /** PreparedMapping */
        PreparedMapping: {
            /**
             * Method
             * @default dated-issuer-ivv-v1
             * @constant
             */
            method: "dated-issuer-ivv-v1";
            /** Rows */
            rows: components["schemas"]["PreparedRow"][];
            /** Included Count */
            included_count: number;
            /** Excluded Count */
            excluded_count: number;
            /** Source Value Usd */
            source_value_usd: number | null;
            /** Retained Known Value Usd */
            retained_known_value_usd: number;
            /** Excluded Known Value Usd */
            excluded_known_value_usd: number;
            /** Unknown Value Rows */
            unknown_value_rows: number[];
            /** Aggregate Excluded Bps */
            aggregate_excluded_bps: number | null;
            /** Aggregate Highlight */
            aggregate_highlight: boolean | null;
            /** Highlighted Rows */
            highlighted_rows: number[];
            /** Coverage Unknown Reasons */
            coverage_unknown_reasons: string[];
            /**
             * History Status
             * @default not_assessed
             * @constant
             */
            history_status: "not_assessed";
            /**
             * Tax Status
             * @default not_assessed
             * @constant
             */
            tax_status: "not_assessed";
        };
        /** PreparedRow */
        PreparedRow: {
            /** Section */
            section: string;
            /** Index */
            index: number;
            row_sha256: components["schemas"]["Digest"];
            source_key: components["schemas"]["Digest"];
            /** Source Ref */
            source_ref: string | null;
            /** Ticker */
            ticker: string | null;
            /** Name */
            name: string | null;
            /** Source Type */
            source_type: string | null;
            /** Asset Class */
            asset_class: string | null;
            /** Location */
            location: string | null;
            /** Currency */
            currency: string | null;
            /** Market Currency */
            market_currency: string | null;
            /** Exchange */
            exchange: string | null;
            /** Raw Market Value */
            raw_market_value: string | null;
            /** Value Usd */
            value_usd: number | null;
            /** Security Id */
            security_id: string | null;
            /**
             * Action
             * @enum {string}
             */
            action: "include" | "exclude";
            /** Reason */
            reason: string;
            /** Excluded Bps */
            excluded_bps: number | null;
            /** Highlight */
            highlight: boolean | null;
        };
        /** PreviewResponse */
        PreviewResponse: {
            id: components["schemas"]["Digest"];
            snapshot: components["schemas"]["ImportSnapshot"];
            /**
             * Cash Holdings
             * @default []
             */
            cash_holdings: components["schemas"]["CashHolding"][];
        };
        /** Profile */
        Profile: {
            /** Identity */
            identity: string;
            /** F */
            f: string;
            /** A3 */
            a3: string;
            /** Kappa */
            kappa: string;
        };
        /** ProjectionDiagnostic */
        ProjectionDiagnostic: {
            /** Horizon */
            horizon: number;
            /** Approximation */
            approximation: string;
            /** Units */
            units: string;
            /** Annualization */
            annualization: number;
            input_sha256: components["schemas"]["Digest"];
            identity_sha256: components["schemas"]["Digest"];
            annual_covariance_sha256: components["schemas"]["Digest"];
        };
        /** RejectRequest */
        RejectRequest: {
            snapshot_id: components["schemas"]["Digest"];
        };
        /** Relationship */
        Relationship: {
            /** Left */
            left: string;
            /** Right */
            right: string;
            /**
             * Status
             * @enum {string}
             */
            status: "conflict" | "distinct" | "unknown";
            /** Valid From */
            valid_from: string;
            /** Valid Through */
            valid_through: string;
            evidence: components["schemas"]["prosper__lot_records__Evidence"];
            /** Rationale */
            rationale: string;
        };
        /** Restriction */
        Restriction: {
            /** Name */
            name: string;
            identity: components["schemas"]["Fact_str_"];
            /** Start */
            start?: string | null;
            /** End */
            end?: string | null;
            /**
             * Side
             * @default both
             * @enum {string}
             */
            side: "both" | "sell" | "buy";
            /** Source Ref */
            source_ref: string;
        };
        /** ReviewContextRequest */
        ReviewContextRequest: {
            /** Observation Id */
            observation_id: string;
        };
        /** ReviewRow */
        ReviewRow: {
            /** Section */
            section: string;
            /** Index */
            index: number;
            row_sha256: components["schemas"]["Digest"];
            /** Source Name */
            source_name: string | null;
            /** Source Ticker */
            source_ticker: string | null;
        };
        /** ReviewSection */
        ReviewSection: {
            /** Section */
            section: string;
            /** Row Count */
            row_count: number | null;
            /** Fields */
            fields: string[];
        };
        Revision: number;
        /** RiskInput */
        RiskInput: {
            /** Security Ids */
            security_ids: string[];
            /** Benchmark Ids */
            benchmark_ids: string[];
            /** Benchmark Weights */
            benchmark_weights: number[];
            /** Annual Covariance */
            annual_covariance: number[][];
            /**
             * Units
             * @constant
             */
            units: "annualized-simple-return-covariance";
            /** Annualization Sessions */
            annualization_sessions: number;
            /** As Of */
            as_of: string;
            /** Max Age Days */
            max_age_days: number;
            /** Reference */
            reference: string;
        };
        /** RowRule */
        RowRule: {
            locator: components["schemas"]["Locator"];
            /** Row Sha256 */
            row_sha256: string;
            security: components["schemas"]["prosper__basket__Security"] | null;
            target: components["schemas"]["Locator"] | null;
            evidence: components["schemas"]["prosper__basket__Evidence"];
        };
        /** RuntimeInfo */
        RuntimeInfo: {
            /**
             * Purpose
             * @default exploratory
             * @constant
             */
            purpose: "exploratory";
            /**
             * Financial Use Authorized
             * @default false
             * @constant
             */
            financial_use_authorized: false;
        };
        /** SaleOrder */
        SaleOrder: {
            /** Lot Id */
            lot_id: string;
            /** Shares */
            shares: number;
        };
        /** ScalarDiagnostic */
        ScalarDiagnostic: {
            /** Status */
            status: string;
            /** Issues */
            issues: string[];
            /** Version */
            version: string;
            configuration_sha256: components["schemas"]["Digest"];
            input_sha256: components["schemas"]["Digest"];
            output_sha256: components["schemas"]["Digest"];
            identity_sha256: components["schemas"]["Digest"];
            /** Starts */
            starts: components["schemas"]["StartDiagnostic"][];
            /** Selected Start */
            selected_start: number | null;
            /** Objective Range */
            objective_range: [
                number,
                number
            ] | null;
            /** Parameter Ranges */
            parameter_ranges: [
                number,
                number
            ][];
            /** Security Id */
            security_id: string;
            innovation_identity_sha256: components["schemas"]["Digest"];
            /** Parameters */
            parameters: [
                number,
                number,
                number
            ] | null;
            /** Second Moment */
            second_moment: number | null;
            /** Seed */
            seed: number | null;
            /** Omega */
            omega: number | null;
            /** Terminal Variance */
            terminal_variance: number | null;
            /** Forecast */
            forecast: number[];
        };
        /** ScreeningFacts */
        ScreeningFacts: {
            /**
             * Activities
             * @default []
             */
            activities: components["schemas"]["Activity"][];
            /**
             * Relationships
             * @default []
             */
            relationships: components["schemas"]["Relationship"][];
            /**
             * Restrictions
             * @default []
             */
            restrictions: components["schemas"]["Restriction"][];
            /**
             * Basis Disputes
             * @default []
             */
            basis_disputes: string[];
            unbounded_event: components["schemas"]["Fact_bool_"];
        };
        /** SectionRule */
        SectionRule: {
            /** Section */
            section: string;
            /**
             * Role
             * @enum {string}
             */
            role: "primary" | "alternate" | "subset" | "empty" | "unresolved";
            /** Weight Field */
            weight_field: string;
            /** Unit */
            unit: string;
            evidence: components["schemas"]["prosper__basket__Evidence"];
        };
        /** SecurityInput */
        SecurityInput: {
            /** Security Id */
            security_id: string;
            identity: components["schemas"]["Fact_str_"];
            classification: components["schemas"]["Fact_str_"];
            /** Currency */
            currency: string;
            evidence: components["schemas"]["SourceFact"];
        };
        /** SecurityMapping */
        SecurityMapping: {
            /** Source Account */
            source_account: string;
            /** Symbol */
            symbol: string;
            security: components["schemas"]["prosper__advisory_records__Security"];
            evidence: components["schemas"]["prosper__lot_records__Evidence"];
        };
        /** SelectRequest */
        SelectRequest: {
            snapshot_id: components["schemas"]["Digest"];
            /** Command Key */
            command_key: string;
            expected_revision: components["schemas"]["Revision"];
        };
        /** SeriesContext */
        SeriesContext: {
            /** Security Id */
            security_id: string;
            /** Provider */
            provider: string;
            /** Dataset */
            dataset: string;
            /** Permission Scope */
            permission_scope: string;
            /** Provider Symbol */
            provider_symbol: string;
            /** Mapping Start */
            mapping_start: string;
            /** Mapping End */
            mapping_end: string;
            /** Currency */
            currency: string;
            /** Calendar */
            calendar: string;
            /** Timezone */
            timezone: string;
            /** Interval */
            interval: string;
            /** Adjustment */
            adjustment: string;
            /** Action Convention */
            action_convention: string;
            /** Repair */
            repair: string;
            /** Source Schema */
            source_schema: string;
            /** Transform Version */
            transform_version: string;
            /** Return Convention */
            return_convention: string;
            /** Vintage */
            vintage: string;
            /**
             * Coherence
             * @enum {string}
             */
            coherence: "immutable-vintage" | "unverified";
            /** Coherence Evidence */
            coherence_evidence: string;
        };
        /** SessionGrid */
        SessionGrid: {
            /** Count */
            count: number;
            /** Data */
            data: string;
        };
        /** SettingsRequest */
        SettingsRequest: {
            /** Settings */
            settings: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Command Key */
            command_key: string;
            expected_revision: components["schemas"]["Revision"];
        };
        /** SnapshotEntry */
        SnapshotEntry: {
            id: components["schemas"]["Digest"];
            /** Imported At */
            imported_at: string;
            /**
             * State
             * @enum {string}
             */
            state: "staged" | "selected" | "rejected";
        };
        /** SourceCell */
        SourceCell: {
            /** Name */
            name: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "string" | "number" | "null" | "boolean" | "object" | "array";
            /** Value */
            value: string;
            /**
             * Origin
             * @default source
             * @enum {string}
             */
            origin: "source" | "adapter";
        };
        /** SourceFact */
        SourceFact: {
            source_sha256: components["schemas"]["Digest"];
            /** Source Ref */
            source_ref: string;
            /** Provider */
            provider: string;
            /** Dataset */
            dataset: string;
            /** Permission Scope */
            permission_scope: string;
            /** Effective */
            effective: string;
            /** Valid Through */
            valid_through: string;
            /** Recorded At */
            recorded_at: string;
        };
        /** SourceIssue */
        SourceIssue: {
            /** Code */
            code: string;
            /** Record */
            record: number | null;
            /** Column */
            column: string | null;
        };
        /** SourceIssueGroup */
        SourceIssueGroup: {
            /** Code */
            code: string;
            /** Occurrences */
            occurrences: number;
            /** Affected Rows */
            affected_rows: number;
            /** Details */
            details: string[];
        };
        /** SourceRow */
        SourceRow: {
            /** Section */
            section: string;
            /** Index */
            index: number;
            /** Source Ref */
            source_ref: string | null;
            /** Cells */
            cells: components["schemas"]["SourceCell"][];
            /** Issues */
            issues: string[];
        };
        /** StartDiagnostic */
        StartDiagnostic: {
            /** Index */
            index: number;
            /** Initial */
            initial: number[];
            /** Status */
            status: string;
            /** Optimizer Success */
            optimizer_success: boolean | null;
            /** Optimizer Status */
            optimizer_status: number | null;
            /** Message */
            message: string;
            /** Objective Callbacks */
            objective_callbacks: number;
            /** Gradient Callbacks */
            gradient_callbacks: number;
            /** Iterations */
            iterations: number;
            /** Parameters */
            parameters: number[] | null;
            /** Reported Objective */
            reported_objective: number | null;
            /** Objective */
            objective: number | null;
            /** Feasibility Residual */
            feasibility_residual: number | null;
            /** Projected Gradient Residual */
            projected_gradient_residual: number | null;
            /** Boundary */
            boundary: string[];
            /** Last Evaluated Parameters */
            last_evaluated_parameters: number[] | null;
            /** Last Evaluated Objective */
            last_evaluated_objective: number | null;
        };
        /** Stipulation */
        Stipulation: {
            /** Raw Sha256 */
            raw_sha256: string;
            fund: components["schemas"]["Fund"];
            /** Requested Date */
            requested_date: string | null;
            /** Effective Date */
            effective_date: string;
            /** Collected At */
            collected_at: string;
            fund_assertion: components["schemas"]["prosper__basket__Evidence"];
            /** Sections */
            sections: components["schemas"]["SectionRule"][];
            /** Rows */
            rows: components["schemas"]["RowRule"][];
            benchmark_cash: components["schemas"]["Fact"];
            /** Benchmark Cash Unit */
            benchmark_cash_unit: string;
        };
        /** TaxScenario */
        TaxScenario: {
            /** Usable Loss Fraction */
            usable_loss_fraction: string;
            /** Offset Rate */
            offset_rate: string;
            /** Reference */
            reference: string;
        };
        /** Upload */
        Upload: {
            /**
             * Version
             * @constant
             */
            version: "advisory-upload-v1";
            snapshot: components["schemas"]["ImportSnapshot"];
            /** Source Base64 */
            source_base64: string;
        };
        /** ValueField */
        ValueField: {
            /** Section */
            section: string;
            /** Field */
            field: string;
            /** Currency */
            currency: string;
        };
        /** Worksheet */
        Worksheet: {
            /**
             * Kind
             * @default manual-worksheet-v1
             * @constant
             */
            kind: "manual-worksheet-v1";
            command: components["schemas"]["WorksheetSave"];
            /** Saved At */
            saved_at: string;
            snapshot_id: components["schemas"]["Digest"];
            /** Source As Of */
            source_as_of: string;
            /** Analysis Date */
            analysis_date: string;
            /** Risk As Of */
            risk_as_of: string;
            /** Risk Horizon */
            risk_horizon: number;
            /** Annualization Sessions */
            annualization_sessions: number;
            scope: components["schemas"]["WorksheetScope"];
            /** Group Weights */
            group_weights: components["schemas"]["GroupWeight"][];
            baseline: components["schemas"]["CandidateCheck"];
            check: components["schemas"]["CandidateCheck"];
            /** Lines */
            lines: components["schemas"]["WorksheetLine"][];
            limits: components["schemas"]["CandidateLimits"];
            /** Cash To Invest */
            cash_to_invest: string;
            /** Assumptions */
            assumptions: string[];
            /** Warnings */
            warnings: string[];
            /** Exclusions */
            exclusions: components["schemas"]["Finding"][];
            /** Findings */
            findings: components["schemas"]["Finding"][];
            /**
             * Validation Outcome
             * @enum {string}
             */
            validation_outcome: "checked-estimate" | "baseline-diagnostic";
            /**
             * Financial Use Authorized
             * @default false
             * @constant
             */
            financial_use_authorized: false;
        };
        /** WorksheetCheck */
        WorksheetCheck: {
            /** Run Id */
            run_id: string;
            expected_revision: components["schemas"]["Revision"];
            orders: components["schemas"]["Orders"];
        };
        /** WorksheetLine */
        WorksheetLine: {
            /**
             * Side
             * @enum {string}
             */
            side: "sell" | "buy";
            /** Account Id */
            account_id: string;
            /** Account Alias */
            account_alias: string;
            /** Security Id */
            security_id: string;
            /** Ticker */
            ticker: string;
            /** Identity */
            identity: string;
            /** Lot Id */
            lot_id: string | null;
            /** Source Ref */
            source_ref: string;
            /** Shares */
            shares: number;
            /** Reference Price */
            reference_price: string;
            /** Price Date */
            price_date: string;
            /** Indicative Price */
            indicative_price: number;
        };
        /** WorksheetPreview */
        WorksheetPreview: {
            /** Run Id */
            run_id: string;
            baseline: components["schemas"]["CandidateCheck"];
            check: components["schemas"]["CandidateCheck"];
            /** Lines */
            lines: components["schemas"]["WorksheetLine"][];
            /** Save Allowed */
            save_allowed: boolean;
        };
        /** WorksheetSave */
        WorksheetSave: {
            /** Run Id */
            run_id: string;
            expected_revision: components["schemas"]["Revision"];
            orders: components["schemas"]["Orders"];
            /** Id */
            id: string;
            /** Parent Id */
            parent_id: string | null;
            /** As Of */
            as_of: string;
            /**
             * No External Changes
             * @constant
             */
            no_external_changes: true;
        };
        /** WorksheetScope */
        WorksheetScope: {
            /** Security Ids */
            security_ids: string[];
            /** Risk Reference */
            risk_reference: string;
            /** Lookback Sessions */
            lookback_sessions: number;
            /**
             * Search Method
             * @enum {string}
             */
            search_method: "complete-cartesian-whole-share-reference" | "deterministic-loss-prefix-repair-v1";
            /** Search Outcome */
            search_outcome: string;
            /** Stopping */
            stopping: string;
            /** Max States */
            max_states: number;
            /** Evaluated States */
            evaluated_states: number;
            /** Domain States */
            domain_states: number | null;
            /** Max Candidates */
            max_candidates: number;
        };
        /** Security */
        prosper__advisory_records__Security: {
            /** Id */
            id: string;
            /** Source Ref */
            source_ref: string;
            /** Ticker */
            ticker: string;
            identity: components["schemas"]["Fact_str_"];
            classification: components["schemas"]["Fact_str_"];
            /**
             * Currency
             * @default USD
             * @constant
             */
            currency: "USD";
            /**
             * @default {
             *       "reason": "Reported name not supplied"
             *     }
             */
            name: components["schemas"]["Fact_str_"];
        };
        /** Evidence */
        prosper__basket__Evidence: {
            /** Source Sha256 */
            source_sha256: string;
            /** Reference */
            reference: string;
            /** Effective */
            effective: string | null;
            /** Recorded */
            recorded: string | null;
            /** Valid Through */
            valid_through: string | null;
            /**
             * Unknown Reasons
             * @default []
             */
            unknown_reasons: string[];
        };
        /** Security */
        prosper__basket__Security: {
            /** Security Id */
            security_id: string | null;
            /** Currency */
            currency: string | null;
            /** Asset Type */
            asset_type: string;
            evidence: components["schemas"]["prosper__basket__Evidence"];
            /**
             * Unknown Reasons
             * @default []
             */
            unknown_reasons: string[];
        };
        /** Row */
        prosper__equity_benchmark__Row: {
            locator: components["schemas"]["Locator"];
            /** Row Sha256 */
            row_sha256: string;
            /** Role */
            role: string;
            /** Disposition */
            disposition: string;
            /** Reason */
            reason: string | null;
            /** Security Id */
            security_id: string | null;
            target: components["schemas"]["Locator"] | null;
            /** Raw Value */
            raw_value: string | null;
            /** Value Token Kind */
            value_token_kind: string;
            /** Value */
            value: string | null;
            /** Value Currency */
            value_currency: string;
            /** Raw Percentage */
            raw_percentage: string | null;
            /** Percentage Token Kind */
            percentage_token_kind: string;
            /** Published Weight */
            published_weight: string | null;
            /** Derived Weight */
            derived_weight: string | null;
            /** Issues */
            issues: string[];
        };
        /** Row */
        prosper__lot_opportunities__Row: {
            /** Lot Id */
            lot_id: string;
            /** Security Id */
            security_id: string;
            /** Source Ref */
            source_ref: string;
            quantity: components["schemas"]["DecimalFact"];
            term: components["schemas"]["Fact_str_"];
            /** Proposed Whole Shares */
            proposed_whole_shares: number | null;
            /** Remaining Quantity */
            remaining_quantity: string | null;
            allocated_basis: components["schemas"]["Fact_float_"];
            reference_value: components["schemas"]["Fact_float_"];
            price_basis_loss: components["schemas"]["Fact_float_"];
            indicative_net_proceeds: components["schemas"]["Fact_float_"];
            indicative_tax_pnl: components["schemas"]["Fact_float_"];
            modeled_cost: components["schemas"]["Fact_float_"];
            /**
             * Status
             * @enum {string}
             */
            status: "conditional-loss" | "blocked" | "no-price-loss" | "cash-treatment" | "excluded";
            /** Blockers */
            blockers: string[];
            /** Warnings */
            warnings: string[];
        };
        /** Evidence */
        prosper__lot_records__Evidence: {
            /** Actor */
            actor: string;
            /** Reference */
            reference: string;
            /** Effective At */
            effective_at: string;
            /** Recorded At */
            recorded_at: string;
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
    runtime_info_runtime_get: {
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
                    "application/json": components["schemas"]["RuntimeInfo"];
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
    stage_api_v1_previews_post: {
        parameters: {
            query?: never;
            header?: never;
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
    treat_cash_api_v1_holdings_cash_treatment_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CashTreatmentRequest"];
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
    prepare_holdings_api_v1_holdings_mapping_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HoldingsMappingRequest"];
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
    start_candidate_api_v1_candidates_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CandidateStart"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
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
    check_worksheet_api_v1_worksheets_check_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorksheetCheck"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorksheetPreview"];
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
    save_worksheet_api_v1_worksheets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorksheetSave"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Worksheet"];
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
    read_worksheet_api_v1_worksheets__identity__get: {
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
                    "application/json": components["schemas"]["Worksheet"];
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
    export_worksheet_api_v1_worksheets__identity__export_get: {
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
                content?: never;
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
    cancel_candidate_api_v1_candidates_cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CandidateIdentity"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
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
    candidate_result_api_v1_candidates_results__identity__get: {
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
                    "application/json": components["schemas"]["CandidateOutput"];
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
    fetch_benchmark_api_v1_benchmarks_fetch_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BenchmarkFetch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkObservation"];
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
    preview_inputs_api_v1_inputs_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModeledUpload"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModeledResult"];
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
    diagnose_inputs_api_v1_inputs_diagnostics_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModeledDiagnostic"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
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
    import_benchmark_api_v1_benchmarks_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BenchmarkImport"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkObservation"];
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
    benchmark_observation_api_v1_benchmarks_observations__identity__get: {
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
                    "application/json": components["schemas"]["BenchmarkObservation"];
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
    benchmark_source_api_v1_benchmarks_observations__identity__source_get: {
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
                content?: never;
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
    benchmark_source_rows_api_v1_benchmarks_rows_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BenchmarkRowsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkSourcePage"];
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
    benchmark_review_context_api_v1_benchmarks_review_context_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewContextRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkReviewContext"];
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
    prepare_benchmark_api_v1_benchmarks_prepare_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PrepareRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkReview"];
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
    preview_benchmark_api_v1_benchmarks_review_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BenchmarkReview"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkResult"];
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
    benchmark_diagnostic_api_v1_benchmarks_diagnostics_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BenchmarkDiagnostic"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
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
    select_benchmark_api_v1_benchmarks_select_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BenchmarkSelect"];
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
    stage_fidelity_api_v1_fidelity_previews_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FidelityUpload"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FidelityPreviewResponse"];
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
    open_fidelity_api_v1_fidelity_opening_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FidelityOpening"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FidelityPreviewResponse"];
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
    configure_lots_api_v1_lots_settings_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LotSettingsRequest"];
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
    lot_diagnostic_api_v1_lots_diagnostics_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LotDiagnosticRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
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
    preview_lot_settings_api_v1_lots_settings_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LotSettingsInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LotSettings"];
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
    lot_result_api_v1_lots_results__identity__get: {
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
                    "application/json": components["schemas"]["LotResult"];
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
    preview_api_v1_previews__identity__get: {
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
    catalog_api_v1_catalog_get: {
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
                    "application/json": components["schemas"]["CatalogResponse"];
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
    select_api_v1_select_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SelectRequest"];
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
    settings_api_v1_settings_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsRequest"];
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
    diagnose_api_v1_diagnostics_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DiagnosticRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
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
    run_api_v1_runs__identity__get: {
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
                    "application/json": components["schemas"]["AnalysisRun"];
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
    input_record_api_v1_input_records__identity__get: {
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
                    "application/json": components["schemas"]["Alignment"];
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
    history_rows_api_v1_history_rows_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HistoryRowsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HistoryRowsPage"];
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
    refresh_history_api_v1_history_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HistoryManifest"];
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
    preview_history_api_v1_history_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HistoryManifest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HistoryManifest"];
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
    stage_history_part_api_v1_history_parts_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HistoryPart"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HistoryPartReceipt"];
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
    discard_history_parts_api_v1_history_discard_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HistoryManifest"];
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
    plan_history_api_v1_history_plan_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HistoryPlanRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Alignment"];
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
    history_diagnostic_api_v1_history_diagnostics_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HistoryDiagnosticRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
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
    clear_history_api_v1_history_clear_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClearHistoryRequest"];
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
    download_backup_api_v1_backup_get: {
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
                    "application/octet-stream": Uint8Array<ArrayBuffer>;
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
    upload_backup_api_v1_restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
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
}

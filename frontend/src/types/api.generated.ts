// Generated from http://127.0.0.1:8000/openapi.json. Do not edit by hand.
export interface paths {
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** API liveness */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/signup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register an unverified account and send a verification email */
        post: operations["signup_api_v1_auth_signup_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/verify-email": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify an email with a one-time token */
        post: operations["verify_email_route_api_v1_auth_verify_email_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/resend-verification": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Send a replacement verification email when eligible */
        post: operations["resend_verification_api_v1_auth_resend_verification_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/forgot-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Send a password reset email when eligible */
        post: operations["forgot_password_api_v1_auth_forgot_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/reset-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Replace a password with a one-time token */
        post: operations["reset_password_route_api_v1_auth_reset_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sign in with a persisted account */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read the current authenticated user */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revoke the current session */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List active user accounts */
        get: operations["list_users_api_v1_auth_users_get"];
        put?: never;
        /** Create an account and assign its role */
        post: operations["add_user_api_v1_auth_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/admin-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List administrator access requests */
        get: operations["list_admin_requests_api_v1_auth_admin_requests_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/admin-requests/{user_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve verified administrator access */
        post: operations["approve_admin_request_api_v1_auth_admin_requests__user_id__approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/admin-requests/{user_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject administrator access while retaining auditor access */
        post: operations["reject_admin_request_api_v1_auth_admin_requests__user_id__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/upload": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload a real PDF or image */
        post: operations["upload_document_api_v1_documents_upload_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List uploaded documents */
        get: operations["list_documents_api_v1_documents_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get uploaded document and evidence */
        get: operations["get_document_api_v1_documents__document_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/{document_id}/process": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start or retry real document processing */
        post: operations["process_document_api_v1_documents__document_id__process_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/{document_id}/processing-status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Poll actual processing stage */
        get: operations["processing_status_api_v1_documents__document_id__processing_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/{document_id}/pages/{page_number}/image": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** View rendered document page */
        get: operations["page_image_api_v1_documents__document_id__pages__page_number__image_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search and filter active human reviews */
        get: operations["review_queue_api_v1_reviews_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Inspect AI evidence and officer review state */
        get: operations["review_detail_api_v1_reviews__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start human review */
        post: operations["start_api_v1_reviews__record_id__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}/fields/{field_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Accept, correct, or reject one AI field */
        post: operations["field_action_api_v1_reviews__record_id__fields__field_name__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}/accept-clear-fields": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Explicitly accept all clear AI fields */
        post: operations["accept_clear_api_v1_reviews__record_id__accept_clear_fields_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}/issues/{issue_code}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Record a human resolution for one validation issue */
        post: operations["issue_resolution_api_v1_reviews__record_id__issues__issue_code__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}/recommendation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Record a verifier recommendation without final decision */
        post: operations["recommendation_api_v1_reviews__record_id__recommendation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}/assign": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Assign or claim officer work */
        post: operations["assign_api_v1_reviews__record_id__assign_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reviews/{record_id}/decision": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve, reject, or send a record back */
        post: operations["decision_api_v1_reviews__record_id__decision_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audit/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Browse immutable audit events */
        get: operations["list_audit_events_api_v1_audit_events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List processed land records */
        get: operations["list_records_api_v1_records_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/records/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Inspect a record with review and audit evidence */
        get: operations["get_record_api_v1_records__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gis/parcels": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search processed parcel metadata and sourced boundaries */
        get: operations["list_parcels_api_v1_gis_parcels_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gis/parcels/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Inspect a processed parcel and any sourced boundary */
        get: operations["get_parcel_api_v1_gis_parcels__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gis/parcels/{record_id}/geometry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Attach officer-sourced parcel GeoJSON */
        post: operations["import_parcel_geometry_api_v1_gis_parcels__record_id__geometry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Show meaningful workflow notifications */
        get: operations["list_notifications_api_v1_notifications_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/{event_id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark one visible notification as read */
        post: operations["mark_notification_read_api_v1_notifications__event_id__read_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Operational metrics from persisted prototype data */
        get: operations["analytics_summary_api_v1_analytics_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Categorized record, document, and survey search */
        get: operations["search_api_v1_search_get"];
        put?: never;
        post?: never;
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
        /** ActionTokenRequest */
        ActionTokenRequest: {
            /** Token */
            token: string;
        };
        /** AdminRoleRequest */
        AdminRoleRequest: {
            user: components["schemas"]["AuthenticatedUser"];
            /** Emailverified */
            emailVerified: boolean;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Reviewedby */
            reviewedBy?: string | null;
            /** Reviewedat */
            reviewedAt?: string | null;
        };
        /** AssignRequest */
        AssignRequest: {
            /** Officerid */
            officerId: string;
        };
        /** AuthMessageResponse */
        AuthMessageResponse: {
            /** Message */
            message: string;
        };
        /** AuthenticatedUser */
        AuthenticatedUser: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Username */
            username: string;
            /** Email */
            email: string;
            role: components["schemas"]["Role"];
            requestedRole?: components["schemas"]["Role"] | null;
            roleApprovalStatus?: components["schemas"]["RoleApprovalStatus"] | null;
        };
        /** Body_import_parcel_geometry_api_v1_gis_parcels__record_id__geometry_post */
        Body_import_parcel_geometry_api_v1_gis_parcels__record_id__geometry_post: {
            /** File */
            file: string;
            /** Sourcereference */
            sourceReference: string;
        };
        /** Body_upload_document_api_v1_documents_upload_post */
        Body_upload_document_api_v1_documents_upload_post: {
            /** File */
            file: string;
            /**
             * Dataset
             * @default operational
             * @enum {string}
             */
            dataset: "operational" | "sample";
        };
        /** CreateUserRequest */
        CreateUserRequest: {
            /** Email */
            email: string;
            /** Name */
            name: string;
            /** Password */
            password: string;
            role: components["schemas"]["Role"];
        };
        /** DecisionRequest */
        DecisionRequest: {
            decision: components["schemas"]["ReviewDecision"];
            /** Reason */
            reason?: string | null;
        };
        /** DocumentDetail */
        DocumentDetail: {
            /** Id */
            id: string;
            /** Filename */
            fileName: string;
            /** Mimetype */
            mimeType: string;
            /** Filesize */
            fileSize: number;
            /** Pagecount */
            pageCount: number;
            /** Language */
            language?: string | null;
            /**
             * Uploadedat
             * Format: date-time
             */
            uploadedAt: string;
            status: components["schemas"]["DocumentStatus"];
            /** Stage */
            stage: string;
            /** Provider */
            provider?: string | null;
            /**
             * Issynthetic
             * @default false
             */
            isSynthetic: boolean;
            /**
             * Datasetscope
             * @default operational
             * @enum {string}
             */
            datasetScope: "operational" | "sample";
            /** Datasetreason */
            datasetReason?: string | null;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Processedat */
            processedAt?: string | null;
            /**
             * Attempts
             * @default 0
             */
            attempts: number;
            /** Pages */
            pages?: components["schemas"]["DocumentPage"][];
            /** Stages */
            stages?: components["schemas"]["StageProgress"][];
            /** Processingmetadata */
            processingMetadata?: {
                [key: string]: unknown;
            };
            /** Ocrpages */
            ocrPages?: components["schemas"]["OCRPage"][];
            /** Extraction */
            extraction?: {
                [key: string]: unknown;
            } | null;
            /** Fields */
            fields?: {
                [key: string]: unknown;
            }[];
            /** Validation */
            validation?: {
                [key: string]: unknown;
            } | null;
            /** Scorebreakdown */
            scoreBreakdown?: {
                [key: string]: unknown;
            } | null;
            /** Warnings */
            warnings?: string[];
            error?: components["schemas"]["DocumentError"] | null;
        };
        /** DocumentError */
        DocumentError: {
            /** Code */
            code: string;
            /** Message */
            message: string;
        };
        /** DocumentList */
        DocumentList: {
            /** Items */
            items: components["schemas"]["DocumentSummary"][];
            /** Total */
            total: number;
        };
        /** DocumentPage */
        DocumentPage: {
            /** Pagenumber */
            pageNumber: number;
            /** Imageurl */
            imageUrl: string;
            /** Width */
            width: number;
            /** Height */
            height: number;
        };
        /**
         * DocumentStatus
         * @enum {string}
         */
        DocumentStatus: "uploaded" | "processing" | "completed" | "failed";
        /** DocumentSummary */
        DocumentSummary: {
            /** Id */
            id: string;
            /** Filename */
            fileName: string;
            /** Mimetype */
            mimeType: string;
            /** Filesize */
            fileSize: number;
            /** Pagecount */
            pageCount: number;
            /** Language */
            language?: string | null;
            /**
             * Uploadedat
             * Format: date-time
             */
            uploadedAt: string;
            status: components["schemas"]["DocumentStatus"];
            /** Stage */
            stage: string;
            /** Provider */
            provider?: string | null;
            /**
             * Issynthetic
             * @default false
             */
            isSynthetic: boolean;
            /**
             * Datasetscope
             * @default operational
             * @enum {string}
             */
            datasetScope: "operational" | "sample";
            /** Datasetreason */
            datasetReason?: string | null;
        };
        /** EmailRequest */
        EmailRequest: {
            /** Email */
            email: string;
        };
        /** FieldReviewRequest */
        FieldReviewRequest: {
            action: components["schemas"]["ReviewFieldAction"];
            /** Reviewedvalue */
            reviewedValue?: unknown | null;
            /** Reason */
            reason?: string | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /** Status */
            status: string;
            /** Service */
            service: string;
            /** Version */
            version: string;
            /** Environment */
            environment: string;
            provider: components["schemas"]["ProviderHealth"];
            smtp: components["schemas"]["SmtpHealth"];
        };
        /** IssueResolutionRequest */
        IssueResolutionRequest: {
            /** Fieldname */
            fieldName?: string | null;
            resolution: components["schemas"]["IssueResolutionType"];
            /** Reason */
            reason: string;
        };
        /**
         * IssueResolutionType
         * @enum {string}
         */
        IssueResolutionType: "corrected" | "confirmed" | "not_applicable";
        /** LoginRequest */
        LoginRequest: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** LoginResponse */
        LoginResponse: {
            /** Accesstoken */
            accessToken: string;
            /**
             * Tokentype
             * @default bearer
             */
            tokenType: string;
            user: components["schemas"]["AuthenticatedUser"];
            /**
             * Expiresat
             * Format: date-time
             */
            expiresAt: string;
        };
        /** OCRPage */
        OCRPage: {
            /** Pagenumber */
            pageNumber: number;
            /** Text */
            text: string;
            /** Width */
            width: number;
            /** Height */
            height: number;
            /** Confidence */
            confidence?: number | null;
            /** Regions */
            regions?: components["schemas"]["OCRRegion"][];
            /** Language */
            language?: string | null;
        };
        /** OCRRegion */
        OCRRegion: {
            /** Text */
            text: string;
            /** Bbox */
            bbox: number[];
            /** Confidence */
            confidence?: number | null;
        };
        /** ProcessingStatus */
        ProcessingStatus: {
            /** Id */
            id: string;
            status: components["schemas"]["DocumentStatus"];
            /** Stage */
            stage: string;
            /** Attempts */
            attempts: number;
            /** Stages */
            stages: components["schemas"]["StageProgress"][];
            error?: components["schemas"]["DocumentError"] | null;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** ProviderHealth */
        ProviderHealth: {
            /** Provider */
            provider: string;
            /** Available */
            available: boolean;
            /**
             * Deterministic
             * @default true
             */
            deterministic: boolean;
            /** Message */
            message?: string | null;
            /** Pdftextavailable */
            pdfTextAvailable?: boolean | null;
            /** Ocravailable */
            ocrAvailable?: boolean | null;
            /** Installedlanguages */
            installedLanguages?: string[];
            /** Requestedlanguages */
            requestedLanguages?: string[];
            /** Unsupportedlanguages */
            unsupportedLanguages?: string[];
        };
        /** RecommendationRequest */
        RecommendationRequest: {
            recommendation: components["schemas"]["ReviewDecision"];
            /** Reason */
            reason: string;
        };
        /** ResetPasswordRequest */
        ResetPasswordRequest: {
            /** Token */
            token: string;
            /** Password */
            password: string;
            /** Confirmpassword */
            confirmPassword: string;
        };
        /** ReviewCaseDetail */
        ReviewCaseDetail: {
            /** Recordid */
            recordId: string;
            /** Recordnumber */
            recordNumber?: string | null;
            /** Documentid */
            documentId: string;
            /** Documentname */
            documentName: string;
            /** Ownername */
            ownerName?: string | null;
            /** Surveynumber */
            surveyNumber?: string | null;
            /** Qualityscore */
            qualityScore: number;
            /** Validationstatus */
            validationStatus: string;
            /** Primaryconflict */
            primaryConflict?: string | null;
            /**
             * Submittedat
             * Format: date-time
             */
            submittedAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            priority: components["schemas"]["ReviewPriority"];
            /** Priorityreasons */
            priorityReasons?: string[];
            assignedOfficer?: components["schemas"]["AuthenticatedUser"] | null;
            status: components["schemas"]["ReviewStatus"];
            /** Fields */
            fields: components["schemas"]["ReviewField"][];
            /** Originalrecord */
            originalRecord: {
                [key: string]: unknown;
            };
            /** Reviewedrecord */
            reviewedRecord: {
                [key: string]: unknown;
            };
            /** Validation */
            validation: {
                [key: string]: unknown;
            };
            /** Scorebreakdown */
            scoreBreakdown?: {
                [key: string]: unknown;
            } | null;
            /** Fieldreviews */
            fieldReviews?: {
                [key: string]: unknown;
            };
            /** Issueresolutions */
            issueResolutions?: {
                [key: string]: unknown;
            }[];
            /** Recommendation */
            recommendation?: {
                [key: string]: unknown;
            } | null;
            summary: components["schemas"]["ReviewSummary"];
            /** Startedat */
            startedAt?: string | null;
            /** Decidedat */
            decidedAt?: string | null;
            decidedBy?: components["schemas"]["AuthenticatedUser"] | null;
            /** Decisionreason */
            decisionReason?: string | null;
            /**
             * Gisindexed
             * @default false
             */
            gisIndexed: boolean;
            /** Gisparcelid */
            gisParcelId?: string | null;
        };
        /** ReviewCaseSummary */
        ReviewCaseSummary: {
            /** Recordid */
            recordId: string;
            /** Recordnumber */
            recordNumber?: string | null;
            /** Documentid */
            documentId: string;
            /** Documentname */
            documentName: string;
            /** Ownername */
            ownerName?: string | null;
            /** Surveynumber */
            surveyNumber?: string | null;
            /** Qualityscore */
            qualityScore: number;
            /** Validationstatus */
            validationStatus: string;
            /** Primaryconflict */
            primaryConflict?: string | null;
            /**
             * Submittedat
             * Format: date-time
             */
            submittedAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            priority: components["schemas"]["ReviewPriority"];
            /** Priorityreasons */
            priorityReasons?: string[];
            assignedOfficer?: components["schemas"]["AuthenticatedUser"] | null;
            status: components["schemas"]["ReviewStatus"];
        };
        /**
         * ReviewDecision
         * @enum {string}
         */
        ReviewDecision: "approve" | "reject" | "send_back";
        /** ReviewField */
        ReviewField: {
            /** Field */
            field: string;
            /** Originalvalue */
            originalValue?: unknown | null;
            /** Reviewedvalue */
            reviewedValue?: unknown | null;
            /** Confidence */
            confidence?: number | null;
            /** Source */
            source?: {
                [key: string]: unknown;
            } | null;
            /**
             * Validationstatus
             * @default clear
             */
            validationStatus: string;
            /**
             * Reviewstatus
             * @default unreviewed
             */
            reviewStatus: string;
            reviewer?: components["schemas"]["AuthenticatedUser"] | null;
            /** Reviewedat */
            reviewedAt?: string | null;
            /** Reason */
            reason?: string | null;
        };
        /**
         * ReviewFieldAction
         * @enum {string}
         */
        ReviewFieldAction: "accept" | "edit" | "reject";
        /** ReviewList */
        ReviewList: {
            /** Items */
            items: components["schemas"]["ReviewCaseSummary"][];
            /** Total */
            total: number;
        };
        /**
         * ReviewPriority
         * @enum {string}
         */
        ReviewPriority: "high" | "medium" | "low";
        /**
         * ReviewStatus
         * @enum {string}
         */
        ReviewStatus: "queued" | "in_progress" | "approved" | "rejected" | "sent_back";
        /** ReviewSummary */
        ReviewSummary: {
            /** Fieldsreviewed */
            fieldsReviewed: number;
            /** Fieldstotal */
            fieldsTotal: number;
            /** Warningsresolved */
            warningsResolved: number;
            /** Warningstotal */
            warningsTotal: number;
            /** Criticalconflicts */
            criticalConflicts: number;
            /** Canapprove */
            canApprove: boolean;
            /** Blockingreasons */
            blockingReasons?: string[];
        };
        /**
         * Role
         * @enum {string}
         */
        Role: "ADMIN" | "REVENUE_OFFICER" | "VERIFIER" | "AUDITOR";
        /**
         * RoleApprovalStatus
         * @enum {string}
         */
        RoleApprovalStatus: "PENDING" | "APPROVED" | "REJECTED";
        /** SignUpRequest */
        SignUpRequest: {
            /** Fullname */
            fullName: string;
            /** Username */
            username: string;
            /** Email */
            email: string;
            /** Password */
            password: string;
            /** Confirmpassword */
            confirmPassword: string;
            requestedRole: components["schemas"]["Role"];
        };
        /** SignUpResponse */
        SignUpResponse: {
            /** Message */
            message: string;
            role: components["schemas"]["Role"];
            requestedRole: components["schemas"]["Role"];
            roleApprovalStatus?: components["schemas"]["RoleApprovalStatus"] | null;
        };
        /** SmtpHealth */
        SmtpHealth: {
            /** Configured */
            configured: boolean;
            /** Connectionverified */
            connectionVerified: boolean | null;
            /** Checking */
            checking: boolean;
        };
        /** StageProgress */
        StageProgress: {
            /** Stage */
            stage: string;
            status: components["schemas"]["StageStatus"];
            /** Startedat */
            startedAt?: string | null;
            /** Completedat */
            completedAt?: string | null;
            /** Message */
            message?: string | null;
        };
        /**
         * StageStatus
         * @enum {string}
         */
        StageStatus: "pending" | "running" | "completed" | "failed";
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
    health_api_v1_health_get: {
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
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    signup_api_v1_auth_signup_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignUpRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SignUpResponse"];
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
    verify_email_route_api_v1_auth_verify_email_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActionTokenRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthMessageResponse"];
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
    resend_verification_api_v1_auth_resend_verification_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmailRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthMessageResponse"];
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
    forgot_password_api_v1_auth_forgot_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmailRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthMessageResponse"];
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
    reset_password_route_api_v1_auth_reset_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResetPasswordRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthMessageResponse"];
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
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoginResponse"];
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
    me_api_v1_auth_me_get: {
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
                    "application/json": components["schemas"]["AuthenticatedUser"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    list_users_api_v1_auth_users_get: {
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
                    "application/json": components["schemas"]["AuthenticatedUser"][];
                };
            };
        };
    };
    add_user_api_v1_auth_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateUserRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthenticatedUser"];
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
    list_admin_requests_api_v1_auth_admin_requests_get: {
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
                    "application/json": components["schemas"]["AdminRoleRequest"][];
                };
            };
        };
    };
    approve_admin_request_api_v1_auth_admin_requests__user_id__approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
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
                    "application/json": components["schemas"]["AuthenticatedUser"];
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
    reject_admin_request_api_v1_auth_admin_requests__user_id__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
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
                    "application/json": components["schemas"]["AuthenticatedUser"];
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
    upload_document_api_v1_documents_upload_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_document_api_v1_documents_upload_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentDetail"];
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
    list_documents_api_v1_documents_get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
                limit?: number;
                offset?: number;
            };
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
                    "application/json": components["schemas"]["DocumentList"];
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
    get_document_api_v1_documents__document_id__get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
            };
            header?: never;
            path: {
                document_id: string;
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
                    "application/json": components["schemas"]["DocumentDetail"];
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
    process_document_api_v1_documents__document_id__process_post: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
            };
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProcessingStatus"];
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
    processing_status_api_v1_documents__document_id__processing_status_get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
            };
            header?: never;
            path: {
                document_id: string;
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
                    "application/json": components["schemas"]["ProcessingStatus"];
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
    page_image_api_v1_documents__document_id__pages__page_number__image_get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
                original?: boolean;
            };
            header?: never;
            path: {
                document_id: string;
                page_number: number;
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
                    "application/json": unknown;
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
    review_queue_api_v1_reviews_get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
                filter?: string;
                search?: string;
                sort?: string;
                direction?: string;
                limit?: number;
                offset?: number;
            };
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
                    "application/json": components["schemas"]["ReviewList"];
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
    review_detail_api_v1_reviews__record_id__get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
            };
            header?: never;
            path: {
                record_id: string;
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
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    start_api_v1_reviews__record_id__start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
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
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    field_action_api_v1_reviews__record_id__fields__field_name__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
                field_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FieldReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    accept_clear_api_v1_reviews__record_id__accept_clear_fields_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
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
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    issue_resolution_api_v1_reviews__record_id__issues__issue_code__resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
                issue_code: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IssueResolutionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    recommendation_api_v1_reviews__record_id__recommendation_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecommendationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    assign_api_v1_reviews__record_id__assign_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AssignRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    decision_api_v1_reviews__record_id__decision_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DecisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewCaseDetail"];
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
    list_audit_events_api_v1_audit_events_get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
                recordId?: string | null;
                eventType?: string | null;
                limit?: number;
                offset?: number;
            };
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
                        [key: string]: unknown;
                    };
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
    list_records_api_v1_records_get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
                q?: string;
                limit?: number;
                offset?: number;
            };
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
                        [key: string]: unknown;
                    };
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
    get_record_api_v1_records__record_id__get: {
        parameters: {
            query?: {
                dataset?: "operational" | "sample";
            };
            header?: never;
            path: {
                record_id: string;
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
                    "application/json": {
                        [key: string]: unknown;
                    };
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
    list_parcels_api_v1_gis_parcels_get: {
        parameters: {
            query?: {
                state?: string | null;
                district?: string | null;
                village?: string | null;
                validationStatus?: string | null;
                recordStatus?: string | null;
                q?: string | null;
            };
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
                        [key: string]: unknown;
                    };
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
    get_parcel_api_v1_gis_parcels__record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
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
                    "application/json": {
                        [key: string]: unknown;
                    };
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
    import_parcel_geometry_api_v1_gis_parcels__record_id__geometry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_parcel_geometry_api_v1_gis_parcels__record_id__geometry_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
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
    list_notifications_api_v1_notifications_get: {
        parameters: {
            query?: {
                limit?: number;
            };
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
                        [key: string]: unknown;
                    };
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
    mark_notification_read_api_v1_notifications__event_id__read_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                event_id: string;
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
                    "application/json": {
                        [key: string]: unknown;
                    };
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
    analytics_summary_api_v1_analytics_summary_get: {
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
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    search_api_v1_search_get: {
        parameters: {
            query: {
                q: string;
            };
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
                        [key: string]: unknown;
                    };
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

CREATE TABLE admin_ai_request_log (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    staff_id INT NOT NULL,
    session_type NVARCHAR(64) NOT NULL,
    trace_id NVARCHAR(128) NOT NULL,
    provider NVARCHAR(64) NOT NULL DEFAULT N'reqai',
    operation NVARCHAR(32) NOT NULL,
    page_key NVARCHAR(255) NOT NULL,
    request_url NVARCHAR(1000) NOT NULL,
    request_payload NVARCHAR(MAX) NOT NULL,
    response_payload NVARCHAR(MAX) NULL,
    response_headers NVARCHAR(MAX) NULL,
    response_status_code INT NULL,
    model NVARCHAR(64) NULL,
    effort NVARCHAR(32) NULL,
    reqai_invocation_id NVARCHAR(128) NULL,
    usage NVARCHAR(MAX) NULL,
    error_message NVARCHAR(MAX) NULL,
    duration_ms INT NULL,
    success BIT NOT NULL DEFAULT 0,
    create_date DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    completed_date DATETIME2 NULL
);

CREATE INDEX IX_admin_ai_request_log_staff_create ON admin_ai_request_log(staff_id, create_date DESC);
CREATE INDEX IX_admin_ai_request_log_trace ON admin_ai_request_log(trace_id);
CREATE INDEX IX_admin_ai_request_log_reqai_invocation ON admin_ai_request_log(reqai_invocation_id);
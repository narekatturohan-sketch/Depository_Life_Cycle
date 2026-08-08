CREATE TABLE clients (
    client_id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pan_number          VARCHAR2(10) NOT NULL UNIQUE,
    full_name           VARCHAR2(150) NOT NULL,
    dob                 DATE,
    address_line1       VARCHAR2(200),
    address_line2       VARCHAR2(200),
    city                VARCHAR2(50),
    state               VARCHAR2(50),
    pincode             VARCHAR2(10),
    email               VARCHAR2(100),
    mobile              VARCHAR2(15),
    kyc_status          VARCHAR2(20) DEFAULT 'PENDING' CHECK (kyc_status IN ('PENDING','VERIFIED','REJECTED')),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP
);

CREATE TABLE demat_accounts (
    account_id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dp_id               VARCHAR2(8) NOT NULL,
    client_id           NUMBER NOT NULL REFERENCES clients(client_id),
    account_status      VARCHAR2(20) DEFAULT 'ACTIVE'
                        CHECK (account_status IN ('ACTIVE','MODIFICATION_PENDING','CLOSURE_PENDING','CLOSED')),
    nominee_name        VARCHAR2(150),
    bank_account_no     VARCHAR2(30),
    bank_ifsc           VARCHAR2(15),
    opened_date         DATE DEFAULT SYSDATE,
    closed_date         DATE,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP
);

CREATE TABLE account_requests (
    request_id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id          NUMBER REFERENCES demat_accounts(account_id),
    client_id           NUMBER REFERENCES clients(client_id),
    request_type        VARCHAR2(20) NOT NULL CHECK (request_type IN ('CREATE','MODIFY','CLOSE')),
    request_payload     CLOB,
    request_status      VARCHAR2(20) DEFAULT 'PENDING'
                        CHECK (request_status IN ('PENDING','APPROVED','REJECTED')),
    rejection_reason    VARCHAR2(500),
    requested_at        TIMESTAMP DEFAULT SYSTIMESTAMP,
    resolved_at         TIMESTAMP
);

CREATE TABLE account_history (
    history_id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id          NUMBER NOT NULL REFERENCES demat_accounts(account_id),
    request_id          NUMBER REFERENCES account_requests(request_id),
    field_changed        VARCHAR2(50),
    old_value            VARCHAR2(500),
    new_value            VARCHAR2(500),
    changed_at           TIMESTAMP DEFAULT SYSTIMESTAMP,
    changed_by            VARCHAR2(50) DEFAULT 'SYSTEM'
);

CREATE TABLE bulk_upload_batches (
    batch_id            NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_name             VARCHAR2(200),
    total_records          NUMBER,
    success_count          NUMBER DEFAULT 0,
    error_count            NUMBER DEFAULT 0,
    batch_status           VARCHAR2(20) DEFAULT 'PROCESSING'
                        CHECK (batch_status IN ('PROCESSING','COMPLETED','COMPLETED_WITH_ERRORS','FAILED')),
    started_at             TIMESTAMP DEFAULT SYSTIMESTAMP,
    completed_at           TIMESTAMP
);

CREATE TABLE bulk_upload_errors (
    error_id             NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id             NUMBER NOT NULL REFERENCES bulk_upload_batches(batch_id),
    row_number             NUMBER,
    raw_data               CLOB,
    error_message           VARCHAR2(500),
    logged_at              TIMESTAMP DEFAULT SYSTIMESTAMP
);

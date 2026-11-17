CREATE TABLE accounts (
    account_id INT NOT NULL AUTO_INCREMENT,
    full_name VARCHAR(160) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NULL,
    google_sub VARCHAR(255) NULL,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    session_version INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (account_id),
    UNIQUE KEY uq_accounts_email (email),
    UNIQUE KEY uq_accounts_google_sub (google_sub)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- NULL keeps existing console profiles unclaimed. The unique key allows only one
-- non-NULL profile per account while allowing any number of unclaimed profiles.
ALTER TABLE users
    ADD COLUMN account_id INT NULL,
    ADD COLUMN activity_level VARCHAR(20) NULL,
    ADD UNIQUE KEY uq_users_account_id (account_id),
    ADD CONSTRAINT fk_users_account FOREIGN KEY (account_id)
        REFERENCES accounts (account_id) ON DELETE RESTRICT;

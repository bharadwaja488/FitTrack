-- Legacy console rows have both values NULL. Account-owned profiles must have
-- an activity level, while preserving the old console profile representation.
ALTER TABLE users
    ADD CONSTRAINT chk_users_account_activity_level
    CHECK ((account_id IS NULL AND activity_level IS NULL)
        OR (account_id IS NOT NULL AND activity_level IS NOT NULL));

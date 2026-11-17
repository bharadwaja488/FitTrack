ALTER TABLE users
    ADD COLUMN daily_step_goal INT NULL,
    ADD CONSTRAINT chk_users_daily_step_goal
        CHECK (daily_step_goal IS NULL OR daily_step_goal BETWEEN 1 AND 100000);

ALTER TABLE fitness_records
    ADD COLUMN record_type VARCHAR(16) NULL,
    ADD COLUMN activity_type VARCHAR(16) NULL,
    ADD COLUMN workout_category VARCHAR(24) NULL,
    ADD COLUMN workout_name VARCHAR(120) NULL,
    ADD COLUMN notes VARCHAR(500) NULL,
    ADD KEY ix_fitness_records_user_date (user_id, record_date, record_id),
    ADD CONSTRAINT chk_fitness_records_type
        CHECK (record_type IS NULL OR record_type IN ('daily','cardio','workout')),
    ADD CONSTRAINT chk_fitness_records_activity_type
        CHECK (activity_type IS NULL OR activity_type IN ('walking','running','jogging','cycling')),
    ADD CONSTRAINT chk_fitness_records_workout_category
        CHECK (workout_category IS NULL OR workout_category IN ('strength_training','cardio','calisthenics','yoga','other'));

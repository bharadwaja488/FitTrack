-- FitTrack migration: add fitness goals and goal-based calorie targets.
-- Back up your database before running this migration.
-- Existing users are preserved and marked as maintenance until they choose a goal.

ALTER TABLE users
    ADD COLUMN goal VARCHAR(20) NOT NULL DEFAULT 'maintenance',
    ADD COLUMN target_calories DECIMAL(8,2) NULL;

UPDATE users
SET target_calories = daily_calories
WHERE target_calories IS NULL;

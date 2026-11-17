CREATE TABLE IF NOT EXISTS fitness_goals (
    goal_id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    goal_type VARCHAR(32) NOT NULL,
    starting_weight_kg DECIMAL(6,2) NOT NULL,
    target_weight_kg DECIMAL(6,2) NOT NULL,
    created_at DATETIME NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    calorie_adjustment DECIMAL(7,2) NULL,
    daily_calorie_target DECIMAL(7,2) NULL,
    PRIMARY KEY (goal_id),
    UNIQUE KEY uq_fitness_goals_user (user_id),
    CONSTRAINT fk_fitness_goals_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_fitness_goals_type CHECK (goal_type IN ('weight_loss','maintenance','weight_gain','muscle_building')),
    CONSTRAINT chk_fitness_goals_status CHECK (status IN ('active','paused','completed','cancelled')),
    CONSTRAINT chk_fitness_goals_start_weight CHECK (starting_weight_kg BETWEEN 1 AND 500),
    CONSTRAINT chk_fitness_goals_target_weight CHECK (target_weight_kg BETWEEN 1 AND 500),
    CONSTRAINT chk_fitness_goals_adjustment CHECK (calorie_adjustment IS NULL OR calorie_adjustment BETWEEN 0 AND 500),
    CONSTRAINT chk_fitness_goals_target_calories CHECK (daily_calorie_target IS NULL OR daily_calorie_target > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS weight_records (
    record_id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    weight_kg DECIMAL(6,2) NOT NULL,
    recorded_at DATETIME NOT NULL,
    PRIMARY KEY (record_id),
    KEY ix_weight_records_user_recorded (user_id, recorded_at, record_id),
    CONSTRAINT fk_weight_records_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_weight_records_weight CHECK (weight_kg BETWEEN 1 AND 500)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

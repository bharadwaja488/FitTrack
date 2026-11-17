CREATE TABLE IF NOT EXISTS users (
    user_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(10) NOT NULL,
    height FLOAT NOT NULL,
    weight FLOAT NOT NULL,
    bmi FLOAT DEFAULT NULL,
    daily_calories FLOAT DEFAULT NULL,
    goal VARCHAR(20) NOT NULL DEFAULT 'maintenance',
    target_calories FLOAT DEFAULT NULL,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS fitness_records (
    record_id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    record_date DATE NOT NULL,
    steps INT DEFAULT NULL,
    distance FLOAT DEFAULT NULL,
    workout_minutes INT DEFAULT NULL,
    calories_burned FLOAT DEFAULT NULL,
    PRIMARY KEY (record_id),
    CONSTRAINT fitness_records_ibfk_1
        FOREIGN KEY (user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

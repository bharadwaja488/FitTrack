ALTER TABLE nutrition_records
    ADD COLUMN data_source VARCHAR(40) NULL AFTER entry_date,
    ADD COLUMN source_id VARCHAR(128) NULL AFTER data_source,
    ADD COLUMN basis_unit VARCHAR(8) NULL AFTER source_id,
    ADD COLUMN serving_size_g DECIMAL(10,3) NULL AFTER basis_unit,
    ADD COLUMN serving_unit VARCHAR(32) NULL AFTER serving_size_g,
    ADD COLUMN calories_per_serving DECIMAL(10,4) NULL AFTER serving_unit,
    ADD COLUMN protein_per_serving_g DECIMAL(9,4) NULL AFTER calories_per_serving,
    ADD COLUMN carbohydrates_per_serving_g DECIMAL(9,4) NULL AFTER protein_per_serving_g,
    ADD COLUMN fat_per_serving_g DECIMAL(9,4) NULL AFTER carbohydrates_per_serving_g,
    ADD COLUMN calories_per_100 DECIMAL(10,4) NULL AFTER fat_per_serving_g,
    ADD COLUMN protein_per_100_g DECIMAL(9,4) NULL AFTER calories_per_100,
    ADD COLUMN carbohydrates_per_100_g DECIMAL(9,4) NULL AFTER protein_per_100_g,
    ADD COLUMN fat_per_100_g DECIMAL(9,4) NULL AFTER carbohydrates_per_100_g;

CREATE INDEX ix_nutrition_records_source ON nutrition_records (data_source, source_id);

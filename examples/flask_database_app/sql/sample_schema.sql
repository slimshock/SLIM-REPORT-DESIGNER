CREATE DATABASE IF NOT EXISTS slim_report_demo
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE slim_report_demo;

CREATE TABLE IF NOT EXISTS patients (
    patient_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    medical_record_number VARCHAR(32) NOT NULL UNIQUE,
    display_name VARCHAR(160) NOT NULL,
    birth_date DATE NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS test_catalog (
    test_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    test_code VARCHAR(24) NOT NULL UNIQUE,
    test_name VARCHAR(120) NOT NULL,
    unit VARCHAR(32) NULL,
    reference_range VARCHAR(80) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS laboratory_orders (
    order_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    order_number VARCHAR(32) NOT NULL UNIQUE,
    patient_id BIGINT UNSIGNED NOT NULL,
    ordered_at DATETIME NOT NULL,
    status VARCHAR(24) NOT NULL,
    CONSTRAINT fk_orders_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS laboratory_results (
    result_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    test_id BIGINT UNSIGNED NOT NULL,
    result_value DECIMAL(14,4) NULL,
    result_text VARCHAR(255) NULL,
    abnormal BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at DATETIME NULL,
    CONSTRAINT fk_results_order FOREIGN KEY (order_id) REFERENCES laboratory_orders(order_id),
    CONSTRAINT fk_results_test FOREIGN KEY (test_id) REFERENCES test_catalog(test_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

USE slim_report_demo;

INSERT INTO patients (patient_id, medical_record_number, display_name, birth_date, active) VALUES
    (1, 'MRN-10001', 'Alex Rivera', '1986-03-14', TRUE),
    (2, 'MRN-10002', 'Morgan Chen', '1992-11-02', TRUE),
    (3, 'MRN-10003', 'Taylor Singh', '1978-06-21', TRUE)
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), active = VALUES(active);

INSERT INTO test_catalog (test_id, test_code, test_name, unit, reference_range) VALUES
    (1, 'HGB', 'Hemoglobin', 'g/dL', '12.0-17.0'),
    (2, 'WBC', 'White Blood Cell Count', '10^9/L', '4.0-11.0'),
    (3, 'GLU', 'Glucose', 'mg/dL', '70-110')
ON DUPLICATE KEY UPDATE test_name = VALUES(test_name), unit = VALUES(unit);

INSERT INTO laboratory_orders (order_id, order_number, patient_id, ordered_at, status) VALUES
    (1, 'LAB-20260715-001', 1, '2026-07-15 08:15:00', 'verified'),
    (2, 'LAB-20260715-002', 2, '2026-07-15 09:30:00', 'verified'),
    (3, 'LAB-20260716-001', 3, '2026-07-16 10:00:00', 'pending')
ON DUPLICATE KEY UPDATE status = VALUES(status), ordered_at = VALUES(ordered_at);

INSERT INTO laboratory_results
    (result_id, order_id, test_id, result_value, result_text, abnormal, verified_at) VALUES
    (1, 1, 1, 13.8000, NULL, FALSE, '2026-07-15 10:20:00'),
    (2, 1, 2, 12.3000, NULL, TRUE, '2026-07-15 10:20:00'),
    (3, 2, 3, 98.0000, NULL, FALSE, '2026-07-15 11:10:00')
ON DUPLICATE KEY UPDATE result_value = VALUES(result_value), abnormal = VALUES(abnormal);

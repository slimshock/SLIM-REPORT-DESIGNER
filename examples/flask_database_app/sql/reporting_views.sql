USE slim_report_demo;

CREATE OR REPLACE VIEW report_laboratory_results AS
SELECT
    r.result_id,
    o.order_number,
    o.ordered_at,
    p.medical_record_number,
    p.display_name AS patient_name,
    c.test_code,
    c.test_name,
    r.result_value,
    r.result_text,
    c.unit,
    c.reference_range,
    r.abnormal,
    r.verified_at
FROM laboratory_results AS r
JOIN laboratory_orders AS o ON o.order_id = r.order_id
JOIN patients AS p ON p.patient_id = o.patient_id
JOIN test_catalog AS c ON c.test_id = r.test_id;

CREATE OR REPLACE VIEW report_daily_orders AS
SELECT
    o.order_id,
    o.order_number,
    o.ordered_at,
    DATE(o.ordered_at) AS order_date,
    o.status,
    p.medical_record_number,
    p.display_name AS patient_name
FROM laboratory_orders AS o
JOIN patients AS p ON p.patient_id = o.patient_id;

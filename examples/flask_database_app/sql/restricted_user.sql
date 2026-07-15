-- Run as a MySQL administrator after replacing the placeholder password.
CREATE USER IF NOT EXISTS 'slim_report_reader'@'localhost'
    IDENTIFIED BY 'replace-me-before-use';
ALTER USER 'slim_report_reader'@'localhost'
    IDENTIFIED BY 'replace-me-before-use';

GRANT SELECT ON slim_report_demo.report_laboratory_results
    TO 'slim_report_reader'@'localhost';
GRANT SELECT ON slim_report_demo.report_daily_orders
    TO 'slim_report_reader'@'localhost';

FLUSH PRIVILEGES;

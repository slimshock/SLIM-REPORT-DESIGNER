from __future__ import annotations

import socket
from dataclasses import FrozenInstanceError

import pytest

from slim_report_core import (
    EmptySQLError,
    InvalidSQLParameterError,
    InvalidSQLSyntaxError,
    MultipleStatementsError,
    MySQLDialect,
    QueryParameter,
    ReportDataset,
    SQLDialect,
    SQLValidationError,
    SQLValidationPolicy,
    SQLValidationResult,
    SQLValidator,
    UnsafeSQLConstructError,
    UnsupportedStatementError,
)


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator(dialect=MySQLDialect())


@pytest.mark.parametrize(
    "sql, root",
    [
        ("SELECT *", "SELECT"),
        ("SELECT * FROM patients", "SELECT"),
        ("SELECT * FROM patients WHERE id=:id", "SELECT"),
        ("WITH cte AS (SELECT 1) SELECT * FROM cte", "WITH"),
        ("SELECT * FROM a UNION ALL SELECT * FROM b", "SELECT"),
        ("SELECT 'DROP TABLE users'", "SELECT"),
        ("SELECT ';'", "SELECT"),
        ("SELECT `DROP` FROM `users`", "SELECT"),
    ],
)
def test_validator_accepts_supported_mysql_queries(
    validator: SQLValidator,
    sql: str,
    root: str,
) -> None:
    result = validator.validate(sql)

    assert result.root_statement == root
    assert result.normalized_sql == sql
    assert result.dialect == "mysql"


@pytest.mark.parametrize(
    "keyword",
    [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE",
        "REPLACE",
        "MERGE",
        "CALL",
        "EXECUTE",
        "LOAD",
        "GRANT",
        "REVOKE",
        "SET",
        "USE",
        "SHOW",
        "DESCRIBE",
        "EXPLAIN",
    ],
)
def test_validator_rejects_non_query_roots(
    validator: SQLValidator,
    keyword: str,
) -> None:
    with pytest.raises(UnsupportedStatementError, match="only SELECT and WITH"):
        validator.validate(keyword)


@pytest.mark.parametrize(
    "function",
    [
        "SLEEP(10)",
        "BENCHMARK(1, 1)",
        "LOAD_FILE('/etc/passwd')",
        "GET_LOCK('x', 10)",
        "RELEASE_LOCK('x')",
        "MASTER_POS_WAIT('log', 10)",
    ],
)
def test_validator_rejects_dangerous_functions_case_insensitively(
    validator: SQLValidator,
    function: str,
) -> None:
    with pytest.raises(UnsafeSQLConstructError, match="function is not allowed"):
        validator.validate(f"SELECT {function.lower()}")


@pytest.mark.parametrize(
    "sql, clause",
    [
        ("SELECT * FROM patients FOR UPDATE", "FOR UPDATE"),
        ("SELECT * FROM patients LOCK IN SHARE MODE", "LOCK IN SHARE MODE"),
        ("SELECT * INTO OUTFILE '/tmp/patients.csv' FROM patients", "INTO OUTFILE"),
        ("SELECT * INTO DUMPFILE '/tmp/patients.dat' FROM patients", "INTO DUMPFILE"),
        ("SELECT * INTO @result FROM patients", "INTO @"),
    ],
)
def test_validator_rejects_dangerous_mysql_clauses(
    validator: SQLValidator,
    sql: str,
    clause: str,
) -> None:
    with pytest.raises(UnsafeSQLConstructError, match=clause):
        validator.validate(sql.lower())


def test_clause_and_function_text_in_literals_comments_and_identifiers_is_safe(
    validator: SQLValidator,
) -> None:
    sql = """
    SELECT 'FOR UPDATE', 'SLEEP()', `DROP`
    FROM `SHOW`
    /* INTO OUTFILE */
    """

    assert validator.validate(sql).root_statement == "SELECT"


def test_mysql_executable_comments_are_rejected_but_literal_text_is_safe(
    validator: SQLValidator,
) -> None:
    with pytest.raises(UnsafeSQLConstructError, match="Executable SQL comments"):
        validator.validate("/*!50000 SET @attempt = 1 */ SELECT 1")
    with pytest.raises(UnsafeSQLConstructError, match="Executable SQL comments"):
        validator.validate("SELECT /*!50000 SLEEP(10), */ 1")

    assert validator.validate("SELECT '/*!50000 SLEEP(10) */'").root_statement == "SELECT"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT * FROM patients; DROP TABLE patients;",
        "SELECT 1;;",
    ],
)
def test_validator_rejects_multiple_or_extra_statements(
    validator: SQLValidator,
    sql: str,
) -> None:
    with pytest.raises(MultipleStatementsError, match="exactly one"):
        validator.validate(sql)


def test_semicolons_inside_strings_are_not_statement_separators(
    validator: SQLValidator,
) -> None:
    result = validator.validate("SELECT ';not a separator;'")

    assert result.normalized_sql == "SELECT ';not a separator;'"


@pytest.mark.parametrize(
    "sql, style",
    [
        ("SELECT ?", r"\?"),
        ("SELECT %s", "%s"),
        ("SELECT %(id)s", r"%\(name\)s"),
        ("SELECT ${id}", r"\$\{name\}"),
        ("SELECT {{id}}", r"\{\{name\}\}"),
    ],
)
def test_validator_rejects_unsupported_parameter_styles(
    validator: SQLValidator,
    sql: str,
    style: str,
) -> None:
    with pytest.raises(InvalidSQLParameterError, match=style):
        validator.validate(sql)


def test_named_parameters_are_unique_and_preserve_first_appearance(
    validator: SQLValidator,
) -> None:
    result = validator.validate(
        """
        SELECT * FROM orders
        WHERE orderdate BETWEEN :date_from AND :date_to
          AND client_id = :client_id
          AND created_at >= :date_from
          AND note = ':ignored'
        -- :also_ignored
        """
    )

    assert result.parameters == ("date_from", "date_to", "client_id")


def test_normalization_only_trims_and_removes_one_trailing_semicolon(
    validator: SQLValidator,
) -> None:
    sql = "  \nSELECT  MixedCase, 'Keep  spacing'\nFROM PatientTable; \n"

    result = validator.validate(sql)

    assert result.normalized_sql == "SELECT  MixedCase, 'Keep  spacing'\nFROM PatientTable"


def test_malformed_select_has_clear_syntax_error(validator: SQLValidator) -> None:
    with pytest.raises(InvalidSQLSyntaxError, match="mysql dialect"):
        validator.validate("SELECT FROM")


def test_empty_and_overlong_queries_are_rejected(validator: SQLValidator) -> None:
    with pytest.raises(EmptySQLError, match="must not be empty"):
        validator.validate(" \n ")

    limited = SQLValidator(MySQLDialect(), SQLValidationPolicy(max_query_length=8))
    with pytest.raises(SQLValidationError, match="maximum length"):
        limited.validate("SELECT 123")


def test_policy_can_disable_ctes_and_unions() -> None:
    policy = SQLValidationPolicy(allow_cte=False, allow_union=False)
    validator = SQLValidator(MySQLDialect(), policy)

    with pytest.raises(UnsupportedStatementError, match="expressions are disabled"):
        validator.validate("WITH cte AS (SELECT 1) SELECT * FROM cte")
    with pytest.raises(UnsupportedStatementError, match="UNION queries are disabled"):
        validator.validate("SELECT 1 UNION SELECT 2")


def test_parameter_limit_counts_unique_named_parameters() -> None:
    validator = SQLValidator(MySQLDialect(), SQLValidationPolicy(max_parameters=1))

    assert validator.validate("SELECT :id, :id").parameters == ("id",)
    with pytest.raises(InvalidSQLParameterError, match="maximum of 1"):
        validator.validate("SELECT :id, :other")


def test_dataset_validation_checks_declared_and_unused_parameters(
    validator: SQLValidator,
) -> None:
    dataset = ReportDataset(
        name="Patients",
        data_source_id="primary",
        source_type="query",
        query="SELECT * FROM patients WHERE id=:patient_id",
        parameters=[QueryParameter("patient_id"), QueryParameter("unused")],
    )

    result = validator.validate_dataset(dataset)

    assert result.parameters == ("patient_id",)
    assert result.warnings == (
        "Dataset parameter 'unused' is not referenced by the SQL query.",
    )


def test_dataset_validation_rejects_missing_parameter_declarations(
    validator: SQLValidator,
) -> None:
    dataset = ReportDataset(
        name="Patients",
        data_source_id="primary",
        source_type="query",
        query="SELECT * FROM patients WHERE id=:patient_id",
    )

    with pytest.raises(InvalidSQLParameterError, match=":patient_id"):
        validator.validate_dataset(dataset)


def test_dataset_validation_rejects_duplicates_even_after_model_mutation(
    validator: SQLValidator,
) -> None:
    dataset = ReportDataset(
        name="Patients",
        data_source_id="primary",
        source_type="query",
        query="SELECT :patient_id",
        parameters=[QueryParameter("patient_id")],
    )
    dataset.parameters.append(QueryParameter("PATIENT_ID"))

    with pytest.raises(InvalidSQLParameterError, match="duplicate parameter"):
        validator.validate_dataset(dataset)


def test_dataset_validation_requires_a_query(validator: SQLValidator) -> None:
    dataset = ReportDataset(
        name="Patient view",
        data_source_id="primary",
        source_type="view",
        view_name="patients",
    )

    with pytest.raises(EmptySQLError, match="Dataset query"):
        validator.validate_dataset(dataset)


def test_validation_never_opens_a_database_connection(
    validator: SQLValidator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("validation attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", fail_connection)

    assert validator.validate("SELECT :id").parameters == ("id",)


def test_dialect_contract_and_rule_collections_are_immutable() -> None:
    dialect: SQLDialect = MySQLDialect()

    assert dialect.name == "mysql"
    assert dialect.allowed_root_statements() == frozenset({"SELECT", "WITH"})
    assert isinstance(dialect.forbidden_keywords(), frozenset)
    assert isinstance(dialect.forbidden_functions(), frozenset)
    assert isinstance(dialect.forbidden_clauses(), frozenset)
    assert dialect.validate_identifier("reporting.patient_results")
    assert dialect.validate_identifier("`reporting`.`patient-results`")
    assert not dialect.validate_identifier("patient results")


def test_validation_result_and_policy_are_frozen(validator: SQLValidator) -> None:
    result = validator.validate("SELECT 1")

    assert isinstance(result, SQLValidationResult)
    with pytest.raises(FrozenInstanceError):
        result.dialect = "other"  # type: ignore[misc]
    with pytest.raises(ValueError, match="at least 1"):
        SQLValidationPolicy(max_query_length=0)
    with pytest.raises(ValueError, match="must not be negative"):
        SQLValidationPolicy(max_parameters=-1)

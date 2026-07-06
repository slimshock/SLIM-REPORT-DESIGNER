"""Minimal Flask demo for Slim Report Designer."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from flask import Flask, Response, redirect

REPO_ROOT = Path(__file__).resolve().parents[2]
for package_src in (
    REPO_ROOT / "packages" / "slim_report_core" / "src",
    REPO_ROOT / "packages" / "slim_report_designer_ui",
    REPO_ROOT / "packages" / "slim_report_flask" / "src",
):
    if str(package_src) not in sys.path:
        sys.path.insert(0, str(package_src))

from slim_report_core import Band, Report  # noqa: E402
from slim_report_core.serialization import JSONSerializer  # noqa: E402
from slim_report_flask import SlimReportDesigner  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(BASE_DIR / "sample_templates")

designer = SlimReportDesigner()
designer.init_app(app)


def demo_lab_results() -> list[dict[str, str]]:
    """Return enough realistic lab rows to exercise pagination demos."""
    return [
        {
            "test": "WBC",
            "result": "7.10",
            "value": "7.10",
            "unit": "10^9/L",
            "reference": "4.00 - 10.00",
            "flag": "N",
        },
        {
            "test": "RBC",
            "result": "5.02",
            "value": "5.02",
            "unit": "10^12/L",
            "reference": "4.50 - 5.90",
            "flag": "N",
        },
        {
            "test": "HGB",
            "result": "14.20",
            "value": "14.20",
            "unit": "g/dL",
            "reference": "13.00 - 17.00",
            "flag": "N",
        },
        {
            "test": "HCT",
            "result": "42.80",
            "value": "42.80",
            "unit": "%",
            "reference": "40.00 - 50.00",
            "flag": "N",
        },
        {
            "test": "MCV",
            "result": "85.30",
            "value": "85.30",
            "unit": "fL",
            "reference": "80.00 - 100.00",
            "flag": "N",
        },
        {
            "test": "MCH",
            "result": "28.30",
            "value": "28.30",
            "unit": "pg",
            "reference": "27.00 - 32.00",
            "flag": "N",
        },
        {
            "test": "MCHC",
            "result": "33.20",
            "value": "33.20",
            "unit": "g/dL",
            "reference": "32.00 - 36.00",
            "flag": "N",
        },
        {
            "test": "RDW-CV",
            "result": "13.10",
            "value": "13.10",
            "unit": "%",
            "reference": "11.50 - 14.50",
            "flag": "N",
        },
        {
            "test": "PLT",
            "result": "265",
            "value": "265",
            "unit": "10^9/L",
            "reference": "150 - 400",
            "flag": "N",
        },
        {
            "test": "MPV",
            "result": "9.40",
            "value": "9.40",
            "unit": "fL",
            "reference": "7.50 - 11.50",
            "flag": "N",
        },
        {
            "test": "Neutrophils",
            "result": "58",
            "value": "58",
            "unit": "%",
            "reference": "50 - 70",
            "flag": "N",
        },
        {
            "test": "Lymphocytes",
            "result": "32",
            "value": "32",
            "unit": "%",
            "reference": "20 - 40",
            "flag": "N",
        },
        {
            "test": "Monocytes",
            "result": "6",
            "value": "6",
            "unit": "%",
            "reference": "2 - 8",
            "flag": "N",
        },
        {
            "test": "Eosinophils",
            "result": "3",
            "value": "3",
            "unit": "%",
            "reference": "1 - 4",
            "flag": "N",
        },
        {
            "test": "Basophils",
            "result": "1",
            "value": "1",
            "unit": "%",
            "reference": "0 - 1",
            "flag": "N",
        },
        {
            "test": "Glucose",
            "result": "94",
            "value": "94",
            "unit": "mg/dL",
            "reference": "70 - 99",
            "flag": "N",
        },
        {
            "test": "BUN",
            "result": "14",
            "value": "14",
            "unit": "mg/dL",
            "reference": "7 - 20",
            "flag": "N",
        },
        {
            "test": "Creatinine",
            "result": "0.92",
            "value": "0.92",
            "unit": "mg/dL",
            "reference": "0.70 - 1.30",
            "flag": "N",
        },
        {
            "test": "Uric Acid",
            "result": "5.80",
            "value": "5.80",
            "unit": "mg/dL",
            "reference": "3.50 - 7.20",
            "flag": "N",
        },
        {
            "test": "Total Cholesterol",
            "result": "182",
            "value": "182",
            "unit": "mg/dL",
            "reference": "< 200",
            "flag": "N",
        },
        {
            "test": "Triglycerides",
            "result": "118",
            "value": "118",
            "unit": "mg/dL",
            "reference": "< 150",
            "flag": "N",
        },
        {
            "test": "HDL",
            "result": "48",
            "value": "48",
            "unit": "mg/dL",
            "reference": "> 40",
            "flag": "N",
        },
        {
            "test": "LDL",
            "result": "110",
            "value": "110",
            "unit": "mg/dL",
            "reference": "< 130",
            "flag": "N",
        },
        {
            "test": "AST",
            "result": "24",
            "value": "24",
            "unit": "U/L",
            "reference": "0 - 40",
            "flag": "N",
        },
        {
            "test": "ALT",
            "result": "29",
            "value": "29",
            "unit": "U/L",
            "reference": "0 - 41",
            "flag": "N",
        },
        {
            "test": "Sodium",
            "result": "139",
            "value": "139",
            "unit": "mmol/L",
            "reference": "135 - 145",
            "flag": "N",
        },
        {
            "test": "Potassium",
            "result": "4.20",
            "value": "4.20",
            "unit": "mmol/L",
            "reference": "3.50 - 5.10",
            "flag": "N",
        },
        {
            "test": "Chloride",
            "result": "102",
            "value": "102",
            "unit": "mmol/L",
            "reference": "98 - 107",
            "flag": "N",
        },
        {
            "test": "Urine Color",
            "result": "Yellow",
            "value": "Yellow",
            "unit": "",
            "reference": "Yellow",
            "flag": "N",
        },
        {
            "test": "Urine Clarity",
            "result": "Clear",
            "value": "Clear",
            "unit": "",
            "reference": "Clear",
            "flag": "N",
        },
        {
            "test": "Specific Gravity",
            "result": "1.020",
            "value": "1.020",
            "unit": "",
            "reference": "1.005 - 1.030",
            "flag": "N",
        },
        {
            "test": "Urine pH",
            "result": "6.0",
            "value": "6.0",
            "unit": "",
            "reference": "5.0 - 8.0",
            "flag": "N",
        },
        {
            "test": "Protein",
            "result": "Negative",
            "value": "Negative",
            "unit": "",
            "reference": "Negative",
            "flag": "N",
        },
        {
            "test": "Glucose Urine",
            "result": "Negative",
            "value": "Negative",
            "unit": "",
            "reference": "Negative",
            "flag": "N",
        },
        {
            "test": "Ketones",
            "result": "Negative",
            "value": "Negative",
            "unit": "",
            "reference": "Negative",
            "flag": "N",
        },
        {
            "test": "Nitrite",
            "result": "Negative",
            "value": "Negative",
            "unit": "",
            "reference": "Negative",
            "flag": "N",
        },
    ]


@designer.provider("lab_result")
def lab_result(record_id: str) -> dict[str, dict[str, str]]:
    return {
        "patient": {
            "name": "JUAN DELA CRUZ",
            "age": "35",
            "sex": "MALE",
        },
        "order": {
            "id": record_id,
            "date": "2026-07-05",
        },
        "result": {
            "HGB": "14.5",
            "WBC": "7.2",
            "PLT": "250",
        },
    }


@designer.provider("cerebro_cbc")
def cerebro_cbc(record_id: str) -> dict[str, dict[str, str]]:
    return {
        "patient": {
            "name": "dhab W. cabrera",
            "age": "1",
            "dob": "09/18/2024",
            "sex": "FEMALE",
            "physician": "",
            "clinical_diagnosis": "",
        },
        "order": {
            "id": record_id,
            "source": "OPD",
            "room_no": "",
            "received": "06/29/2026, 11:04:55 AM",
            "checked_in": "06/29/2026, 11:04:59 AM",
            "released": "06/29/2026, 11:05:43 AM",
            "printed": "07/05/2026, 06:45:49 PM",
        },
        "results": {
            "wbc": "50",
            "rbc": "5",
            "hgb": "5",
            "hct": "5",
            "mcv": "",
            "mch": "",
            "mchc": "",
            "rdw": "",
            "neutrophils": "",
            "lymphocytes": "",
            "monocytes": "",
            "basophils": "",
            "total": "",
            "platelet": "",
        },
    }


@designer.provider("repeating_lab_result")
def repeating_lab_result(record_id: str) -> dict[str, object]:
    return {
        "laboratory": {
            "name": "Cerebro Diagnostic System",
            "address": "Cagayan de Oro City, Philippines",
        },
        "patient": {
            "name": "JUAN DELA CRUZ",
            "patient_no": "P-00001234",
            "age": "34",
            "sex": "Male",
            "dob": "1992-04-18",
        },
        "order": {
            "id": record_id,
            "date": "2026-07-06",
            "physician": "Dr. Maria Santos",
            "section": "Hematology",
        },
        "results": demo_lab_results(),
    }


@designer.provider("table_lab_result")
def table_lab_result(record_id: str) -> dict[str, object]:
    return {
        "laboratory": {
            "name": "Cerebro Diagnostic System",
            "address": "Cagayan de Oro City, Philippines",
        },
        "patient": {
            "name": "JUAN DELA CRUZ",
            "patient_no": "P-00001234",
            "age": "34",
            "sex": "Male",
        },
        "order": {
            "id": record_id,
            "date": "2026-07-06",
            "physician": "Dr. Maria Santos",
        },
        "results": demo_lab_results(),
    }


@designer.provider("barcode_qr_lab_result")
def barcode_qr_lab_result(record_id: str) -> dict[str, object]:
    return {
        "laboratory": {
            "name": "Cerebro Diagnostic System",
            "address": "Cagayan de Oro City, Philippines",
        },
        "patient": {
            "name": "JUAN DELA CRUZ",
            "patient_no": "P-00001234",
            "age": "34",
            "sex": "Male",
        },
        "order": {
            "id": record_id,
            "date": "2026-07-06",
            "physician": "Dr. Maria Santos",
        },
        "result": {
            "HGB": "14.20",
            "WBC": "7.10",
            "PLT": "265",
        },
    }


@app.get("/")
def index():
    return redirect("/report-designer/templates/lab_result/preview/ORDER-1001")


@app.get("/direct-preview/<template_id>/<record_id>")
def direct_template_preview(template_id: str, record_id: str) -> Response:
    """Preview any demo template using Flask plus the core Report API directly."""
    report = designer.get_report(template_id)
    data = designer.resolve_data(template_id, record_id)
    return Response(report.render_html(data), mimetype="text/html")


@app.get("/direct-export/pdf/<template_id>/<record_id>")
def direct_template_export_pdf(template_id: str, record_id: str) -> Response:
    """Export any demo template using Flask plus the core Report API directly."""
    report = designer.get_report(template_id)
    data = designer.resolve_data(template_id, record_id)
    return Response(
        report.render_pdf(data),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{template_id}-{record_id}.pdf"',
        },
    )


def ensure_sample_templates() -> None:
    ensure_report_template("lab_result", create_lab_result_report)
    ensure_report_template("cerebro_cbc", create_cerebro_cbc_report)
    ensure_report_template("repeating_lab_result", create_repeating_lab_result_report)
    ensure_report_template("table_lab_result", create_table_lab_result_report)
    ensure_report_template("barcode_qr_lab_result", create_barcode_qr_lab_result_report)


def ensure_sample_template() -> None:
    """Compatibility wrapper for older local usage."""
    ensure_sample_templates()


def ensure_report_template(template_id: str, create_report: Callable[[], Report]) -> None:
    template_path = BASE_DIR / "sample_templates" / f"{template_id}.json"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    serializer = JSONSerializer()

    if template_path.exists():
        report = serializer.load(template_path)
    else:
        report = create_report()
        serializer.save(report, template_path)

    result = report.validate()
    if not result.is_valid:
        errors = "; ".join(f"{error.path}: {error.message}" for error in result.errors)
        raise RuntimeError(f"Invalid sample report template {template_id}: {errors}")


def create_lab_result_report() -> Report:
    """Create the sample template with the beginner-friendly Report API."""
    report = Report("Laboratory Result")
    report.metadata(
        description="Sample laboratory result report template.",
        author="Slim Report Designer",
        tags=["demo", "lab"],
        id="lab_result",
        provider="lab_result",
    )

    page = report.page()
    page.text(
        "LABORATORY RESULT", x=50, y=40, width=500, height=32, id="title", font_size=22, bold=True
    )
    page.field(
        "patient.name", x=50, y=90, width=360, height=22, id="patient_name", font_size=13, bold=True
    )
    page.field("patient.age", x=50, y=116, width=120, height=20, id="patient_age", font_size=12)
    page.field("patient.sex", x=190, y=116, width=120, height=20, id="patient_sex", font_size=12)
    page.field("order.id", x=50, y=142, width=260, height=20, id="order_id", font_size=12)
    page.line(x=50, y=176, width=500, id="separator", stroke_width=1)
    page.rectangle(x=50, y=200, width=500, height=130, id="result_box", border_width=1)
    page.text("HGB", x=75, y=226, width=80, height=20, id="hgb_label", font_size=12, bold=True)
    page.field("result.HGB", x=180, y=226, width=120, height=20, id="hgb_value", font_size=12)
    page.text("WBC", x=75, y=262, width=80, height=20, id="wbc_label", font_size=12, bold=True)
    page.field("result.WBC", x=180, y=262, width=120, height=20, id="wbc_value", font_size=12)
    page.text("PLT", x=75, y=298, width=80, height=20, id="plt_label", font_size=12, bold=True)
    page.field("result.PLT", x=180, y=298, width=120, height=20, id="plt_value", font_size=12)
    report.data = {"sample": lab_result("ORDER-1001")}
    return report


def create_cerebro_cbc_report() -> Report:
    """Create a compact CBC report inspired by the Cerebro sample."""
    report = Report("Cerebro CBC Result")
    report.metadata(
        description="Cerebro Diagnostic System CBC report demo.",
        author="Slim Report Designer",
        tags=["demo", "lab", "cbc", "cerebro"],
        id="cerebro_cbc",
        provider="cerebro_cbc",
    )
    page = report.page()
    page.width = 651
    page.height = 842
    page.unit = "px"

    page.text(
        "CEREBRO",
        x=16,
        y=26,
        width=150,
        height=30,
        id="cerebro_logo",
        font_size=27,
        color="#0B79C9",
    )
    page.text(
        "DIAGNOSTIC SYSTEM",
        x=18,
        y=56,
        width=150,
        height=16,
        id="cerebro_subtitle",
        font_size=10,
        color="#E53935",
    )
    page.text(
        "Cerebro Diagnostic System",
        x=170,
        y=4,
        width=360,
        height=30,
        id="clinic_name",
        font_size=26,
        bold=True,
    )
    page.text(
        "Alwana Business Park, Zone 4 Cugman, Cagayan de Oro City",
        x=171,
        y=35,
        width=390,
        height=12,
        id="clinic_address",
        font_size=10,
    )
    page.text(
        "Contact No.: +639 260 235 049, +639 222 979 774",
        x=171,
        y=61,
        width=360,
        height=12,
        id="clinic_contact",
        font_size=10,
    )
    page.text(
        "Email Address: cerebro.info@gmail.com",
        x=171,
        y=74,
        width=300,
        height=12,
        id="clinic_email",
        font_size=10,
    )
    page.line(x=14, y=90, width=624, id="header_rule", stroke_width=1)

    add_label_field(
        page, "Patient Name:", "patient.name", x=14, y=98, label_width=96, value_width=180
    )
    add_label_field(page, "Age:", "patient.age", x=14, y=111, label_width=96, value_width=180)
    add_label_field(page, "DOB:", "patient.dob", x=14, y=124, label_width=96, value_width=180)
    add_label_field(page, "Sex:", "patient.sex", x=14, y=137, label_width=96, value_width=180)
    add_label_field(page, "Order No.:", "order.id", x=330, y=98, label_width=98, value_width=185)
    add_label_field(page, "Source:", "order.source", x=330, y=111, label_width=98, value_width=185)
    add_label_field(
        page, "Date Received:", "order.received", x=330, y=137, label_width=98, value_width=185
    )
    add_label_field(
        page, "Date Printed:", "order.printed", x=330, y=176, label_width=98, value_width=185
    )
    page.text(
        "HEMATOLOGY",
        x=0,
        y=198,
        width=651,
        height=16,
        id="section",
        font_size=12,
        bold=True,
        color="#9AA0A6",
        align="center",
    )

    page.text(
        "TEST NAME", x=16, y=232, width=150, height=14, id="test_header", font_size=10, bold=True
    )
    page.text(
        "RESULT", x=226, y=232, width=54, height=14, id="result_header", font_size=10, bold=True
    )
    page.text("UNIT", x=315, y=232, width=58, height=14, id="unit_header", font_size=10, bold=True)
    page.text(
        "REFERENCE RANGE",
        x=378,
        y=232,
        width=130,
        height=14,
        id="range_header",
        font_size=10,
        bold=True,
    )
    page.text("FLAGS", x=570, y=232, width=54, height=14, id="flag_header", font_size=10, bold=True)
    add_result_row(
        page,
        0,
        248,
        "White Blood Cell Count",
        "results.wbc",
        "x10^9/L",
        "5-14.5",
        "HIGH",
        "#FF0000",
    )
    add_result_row(
        page, 1, 264, "Red Blood Cell Count", "results.rbc", "x10^12/L", "3.9 - 5.3", "", "#000000"
    )
    add_result_row(
        page, 2, 280, "Hemoglobin", "results.hgb", "g/dL", "11.5 - 13.5", "LOW", "#003BFF"
    )
    add_result_row(page, 3, 296, "Hematocrit", "results.hct", "%", "34 - 40", "LOW", "#003BFF")
    add_result_row(page, 4, 312, "MCV", "results.mcv", "c.u.", "75 - 87", "", "#000000")
    add_result_row(page, 5, 328, "MCH", "results.mch", "uug", "24 - 30", "", "#000000")
    add_result_row(page, 6, 344, "MCHC", "results.mchc", "g/dL", "31-37", "", "#000000")
    add_result_row(page, 7, 360, "RDW", "results.rdw", "%", "11 - 16", "", "#000000")
    add_result_row(page, 8, 376, "Differential Count", "", "", "", "", "#000000")
    add_result_row(
        page, 9, 392, "Neutrophils", "results.neutrophils", "%", "50 - 70", "", "#000000"
    )
    add_result_row(
        page, 10, 408, "Lymphocytes", "results.lymphocytes", "%", "20 - 40", "", "#000000"
    )
    add_result_row(page, 11, 424, "Monocytes", "results.monocytes", "%", "3 - 9", "", "#000000")
    add_result_row(page, 12, 440, "Basophils", "results.basophils", "%", "0 - 0.5", "", "#000000")
    add_result_row(page, 13, 456, "Total (%)", "results.total", "", "", "", "#000000")
    add_result_row(
        page, 14, 472, "Platelet Count", "results.platelet", "x10^9/L", "150 - 450", "", "#000000"
    )

    page.text(
        "Cerebro Diagnostic System",
        x=52,
        y=672,
        width=150,
        height=12,
        id="performed_name",
        font_size=7,
        bold=True,
        align="center",
    )
    page.line(x=14, y=693, width=193, id="performed_line", stroke_width=1)
    page.text(
        "Dummy LAB_ENCODER",
        x=276,
        y=672,
        width=130,
        height=12,
        id="validator",
        font_size=7,
        bold=True,
        align="center",
    )
    page.line(x=232, y=693, width=192, id="validated_line", stroke_width=1)
    page.text(
        "MARY ANN R. TORREGOSA, M.D.",
        x=473,
        y=672,
        width=150,
        height=12,
        id="pathologist",
        font_size=7,
        bold=True,
        align="center",
    )
    page.line(x=448, y=693, width=193, id="pathologist_line", stroke_width=1)
    page.text("1 of 1", x=614, y=738, width=30, height=11, id="page_count", font_size=9, bold=True)
    report.data = {"sample": cerebro_cbc("ORDER-1001")}
    return report


def create_repeating_lab_result_report() -> Report:
    report = Report("Repeating Laboratory Result")
    report.metadata(
        description="Laboratory result template with repeating detail rows.",
        author="Slim Report Designer",
        tags=["demo", "lab", "repeat"],
        id="repeating_lab_result",
        provider="repeating_lab_result",
    )
    page = report.page()
    page.width = 595
    page.height = 842
    page.unit = "px"
    report.bands = [
        Band.from_dict(
            {
                "id": "page_header",
                "type": "page_header",
                "name": "Page Header",
                "y": 0,
                "height": 120,
            }
        ),
        Band.from_dict(
            {
                "id": "detail",
                "type": "detail",
                "name": "Detail",
                "y": 120,
                "height": 660,
                "repeat": {
                    "enabled": True,
                    "data_path": "results",
                    "row_height": 24,
                    "preview_rows": 10,
                    "empty_message": "No results",
                },
            }
        ),
        Band.from_dict(
            {
                "id": "page_footer",
                "type": "page_footer",
                "name": "Page Footer",
                "y": 780,
                "height": 62,
            }
        ),
    ]
    page.text(
        "LABORATORY RESULT",
        x=40,
        y=30,
        width=280,
        height=28,
        id="title",
        font_size=20,
        bold=True,
        band="page_header",
    )
    page.field(
        "patient.name",
        x=40,
        y=72,
        width=220,
        height=18,
        id="patient_name",
        font_size=12,
        bold=True,
        band="page_header",
    )
    page.field(
        "order.id",
        x=360,
        y=72,
        width=160,
        height=18,
        id="order_id",
        font_size=12,
        band="page_header",
    )
    page.text(
        "TEST",
        x=42,
        y=126,
        width=160,
        height=18,
        id="test_header",
        font_size=11,
        bold=True,
        band="detail",
    )
    page.text(
        "VALUE",
        x=220,
        y=126,
        width=90,
        height=18,
        id="value_header",
        font_size=11,
        bold=True,
        band="detail",
    )
    page.text(
        "UNIT",
        x=330,
        y=126,
        width=90,
        height=18,
        id="unit_header",
        font_size=11,
        bold=True,
        band="detail",
    )
    page.text(
        "FLAG",
        x=450,
        y=126,
        width=70,
        height=18,
        id="flag_header",
        font_size=11,
        bold=True,
        band="detail",
    )
    page.field(
        "test", x=42, y=152, width=160, height=18, id="row_test", font_size=11, band="detail"
    )
    page.field(
        "value", x=220, y=152, width=90, height=18, id="row_value", font_size=11, band="detail"
    )
    page.field(
        "unit", x=330, y=152, width=90, height=18, id="row_unit", font_size=11, band="detail"
    )
    page.field(
        "flag", x=450, y=152, width=70, height=18, id="row_flag", font_size=11, band="detail"
    )
    page.line(x=40, y=174, width=480, id="row_rule", stroke_width=1, band="detail")
    page.text(
        "Generated by Slim Report Designer",
        x=40,
        y=802,
        width=240,
        height=16,
        id="footer",
        font_size=10,
        band="page_footer",
    )
    for obj in report.objects:
        if obj.id in {"title", "patient_name", "order_id"}:
            obj.band_id = "page_header"
            obj.properties["band"] = "page_header"
            obj.properties["band_id"] = "page_header"
        elif obj.id == "footer":
            obj.band_id = "page_footer"
            obj.properties["band"] = "page_footer"
            obj.properties["band_id"] = "page_footer"
        else:
            obj.band_id = "detail"
            obj.properties["band"] = "detail"
            obj.properties["band_id"] = "detail"
    report.data = {"sample": repeating_lab_result("ORDER-1001")}
    return report


def create_table_lab_result_report() -> Report:
    report = Report("Table Laboratory Result")
    report.metadata(
        description="Laboratory result template using the basic table object.",
        author="Slim Report Designer",
        tags=["demo", "lab", "table"],
        id="table_lab_result",
        provider="table_lab_result",
    )
    page = report.page()
    page.width = 595
    page.height = 842
    page.unit = "px"
    report.bands = [
        Band.from_dict(
            {
                "id": "page_header",
                "type": "page_header",
                "name": "Page Header",
                "y": 0,
                "height": 150,
            }
        ),
        Band.from_dict(
            {"id": "detail", "type": "detail", "name": "Detail", "y": 150, "height": 620}
        ),
        Band.from_dict(
            {
                "id": "page_footer",
                "type": "page_footer",
                "name": "Page Footer",
                "y": 770,
                "height": 72,
            }
        ),
    ]
    page.field(
        "laboratory.name",
        x=40,
        y=24,
        width=360,
        height=24,
        id="lab_name",
        font_size=18,
        bold=True,
        band="page_header",
    )
    page.text(
        "Laboratory Result",
        x=40,
        y=58,
        width=300,
        height=22,
        id="report_title",
        font_size=15,
        bold=True,
        color="#2563eb",
        band="page_header",
    )
    page.text(
        "Patient:",
        x=40,
        y=95,
        width=80,
        height=18,
        id="patient_label",
        font_size=11,
        bold=True,
        band="page_header",
    )
    page.field(
        "patient.name",
        x=120,
        y=95,
        width=250,
        height=18,
        id="patient_name",
        font_size=11,
        band="page_header",
    )
    page.text(
        "Order:",
        x=390,
        y=95,
        width=65,
        height=18,
        id="order_label",
        font_size=11,
        bold=True,
        band="page_header",
    )
    page.field(
        "order.id",
        x=455,
        y=95,
        width=110,
        height=18,
        id="order_id",
        font_size=11,
        band="page_header",
    )
    page.line(
        x=40,
        y=144,
        width=515,
        height=1,
        id="header_line",
        stroke_width=1,
        stroke_color="#111827",
        band="page_header",
    )
    page.table(
        id="results_table",
        x=40,
        y=180,
        width=515,
        height=260,
        data_path="results",
        columns=[
            {
                "id": "test",
                "label": "Test",
                "binding": "test",
                "width": 130,
                "align": "left",
                "source_path": "results[].test",
            },
            {
                "id": "result",
                "label": "Result",
                "binding": "result",
                "width": 90,
                "align": "center",
                "source_path": "results[].result",
            },
            {
                "id": "unit",
                "label": "Unit",
                "binding": "unit",
                "width": 80,
                "align": "left",
                "source_path": "results[].unit",
            },
            {
                "id": "reference",
                "label": "Reference",
                "binding": "reference",
                "width": 130,
                "align": "left",
                "source_path": "results[].reference",
            },
            {
                "id": "flag",
                "label": "Flag",
                "binding": "flag",
                "width": 45,
                "align": "center",
                "source_path": "results[].flag",
            },
        ],
        header={
            "visible": True,
            "height": 24,
            "background_color": "#e5e7eb",
            "color": "#111827",
            "font_size": 10,
            "bold": True,
        },
        row={
            "height": 24,
            "background_color": "#ffffff",
            "alternate_background_color": "#f9fafb",
            "color": "#111827",
            "font_size": 10,
        },
        border={"width": 1, "color": "#d1d5db"},
        background_color="#ffffff",
        border_radius=0,
        band="detail",
    )
    page.line(
        x=40,
        y=780,
        width=515,
        height=1,
        id="footer_line",
        stroke_width=1,
        stroke_color="#d1d5db",
        band="page_footer",
    )
    page.text(
        "Generated by Slim Report Designer",
        x=40,
        y=802,
        width=240,
        height=16,
        id="footer",
        font_size=10,
        band="page_footer",
    )
    for obj in report.objects:
        if obj.properties.get("band"):
            obj.band_id = obj.properties["band"]
            obj.properties["band_id"] = obj.band_id
    report.data = {
        "sample": table_lab_result("ORDER-1001"),
        "fields": [
            {
                "path": "laboratory.name",
                "label": "Laboratory Name",
                "type": "string",
                "sample": "Cerebro Diagnostic System",
            },
            {
                "path": "patient.name",
                "label": "Patient Name",
                "type": "string",
                "sample": "JUAN DELA CRUZ",
            },
            {"path": "order.id", "label": "Order ID", "type": "string", "sample": "ORDER-1001"},
            {"path": "results[]", "label": "Results", "type": "array", "sample": "36 rows"},
            {"path": "results[].test", "label": "Test", "type": "string", "sample": "WBC"},
            {"path": "results[].result", "label": "Result", "type": "string", "sample": "7.10"},
            {"path": "results[].unit", "label": "Unit", "type": "string", "sample": "10^9/L"},
            {
                "path": "results[].reference",
                "label": "Reference",
                "type": "string",
                "sample": "4.00 - 10.00",
            },
            {"path": "results[].flag", "label": "Flag", "type": "string", "sample": "N"},
        ],
    }
    return report


def create_barcode_qr_lab_result_report() -> Report:
    report = Report("Barcode QR Laboratory Result")
    report.metadata(
        description="Laboratory result template with barcode and QR code objects.",
        author="Slim Report Designer",
        tags=["demo", "lab", "barcode", "qr"],
        id="barcode_qr_lab_result",
        provider="barcode_qr_lab_result",
    )
    page = report.page()
    page.width = 595
    page.height = 842
    page.unit = "px"
    report.bands = [
        Band.from_dict(
            {
                "id": "page_header",
                "type": "page_header",
                "name": "Page Header",
                "y": 0,
                "height": 150,
            }
        ),
        Band.from_dict(
            {
                "id": "detail",
                "type": "detail",
                "name": "Detail",
                "y": 150,
                "height": 620,
            }
        ),
        Band.from_dict(
            {
                "id": "page_footer",
                "type": "page_footer",
                "name": "Page Footer",
                "y": 770,
                "height": 72,
            }
        ),
    ]
    page.field(
        "laboratory.name",
        x=40,
        y=24,
        width=320,
        height=24,
        id="lab_name",
        font_size=18,
        bold=True,
        band="page_header",
    )
    page.text(
        "Barcode and QR Result",
        x=40,
        y=58,
        width=260,
        height=22,
        id="report_title",
        font_size=15,
        bold=True,
        color="#2563eb",
        band="page_header",
    )
    barcode = page.barcode(
        "1234567890",
        x=380,
        y=32,
        width=160,
        height=48,
        id="barcode_order_id",
        symbology="code128",
        show_text=True,
        binding="order.id",
        foreground_color="#111827",
        background_color="#ffffff",
        font_size=8,
        band="page_header",
    )
    barcode.properties["format"] = "code128"
    qr = page.qrcode(
        "https://example.com",
        x=480,
        y=86,
        width=70,
        height=70,
        id="qr_order_id",
        binding="order.id",
        error_correction="M",
        foreground_color="#111827",
        background_color="#ffffff",
        band="page_header",
    )
    page.text(
        "Patient:",
        x=40,
        y=100,
        width=70,
        height=18,
        id="patient_label",
        font_size=11,
        bold=True,
        band="page_header",
    )
    page.field(
        "patient.name",
        x=112,
        y=100,
        width=220,
        height=18,
        id="patient_name",
        font_size=11,
        band="page_header",
    )
    page.text(
        "Order:",
        x=40,
        y=124,
        width=70,
        height=18,
        id="order_label",
        font_size=11,
        bold=True,
        band="page_header",
    )
    page.field(
        "order.id",
        x=112,
        y=124,
        width=180,
        height=18,
        id="order_id",
        font_size=11,
        band="page_header",
    )
    page.line(
        x=40,
        y=146,
        width=515,
        height=1,
        id="header_line",
        stroke_width=1,
        stroke_color="#111827",
        band="page_header",
    )
    page.rectangle(
        x=40,
        y=185,
        width=515,
        height=150,
        id="result_box",
        border_width=1,
        border_color="#d1d5db",
        background_color="#ffffff",
        band="detail",
    )
    page.text(
        "HGB",
        x=70,
        y=215,
        width=90,
        height=20,
        id="hgb_label",
        font_size=12,
        bold=True,
        band="detail",
    )
    page.field(
        "result.HGB",
        x=170,
        y=215,
        width=100,
        height=20,
        id="hgb_value",
        font_size=12,
        band="detail",
    )
    page.text(
        "WBC",
        x=70,
        y=250,
        width=90,
        height=20,
        id="wbc_label",
        font_size=12,
        bold=True,
        band="detail",
    )
    page.field(
        "result.WBC",
        x=170,
        y=250,
        width=100,
        height=20,
        id="wbc_value",
        font_size=12,
        band="detail",
    )
    page.text(
        "PLT",
        x=70,
        y=285,
        width=90,
        height=20,
        id="plt_label",
        font_size=12,
        bold=True,
        band="detail",
    )
    page.field(
        "result.PLT",
        x=170,
        y=285,
        width=100,
        height=20,
        id="plt_value",
        font_size=12,
        band="detail",
    )
    page.line(
        x=40,
        y=780,
        width=515,
        height=1,
        id="footer_line",
        stroke_width=1,
        stroke_color="#d1d5db",
        band="page_footer",
    )
    page.text(
        "Generated by Slim Report Designer",
        x=40,
        y=802,
        width=240,
        height=16,
        id="footer",
        font_size=10,
        band="page_footer",
    )
    for obj in report.objects:
        if obj.properties.get("band"):
            obj.band_id = obj.properties["band"]
            obj.properties["band_id"] = obj.band_id
    report.data = {
        "sample": barcode_qr_lab_result("ORDER-1001"),
        "fields": [
            {
                "path": "laboratory.name",
                "label": "Laboratory Name",
                "type": "string",
                "sample": "Cerebro Diagnostic System",
            },
            {
                "path": "patient.name",
                "label": "Patient Name",
                "type": "string",
                "sample": "JUAN DELA CRUZ",
            },
            {
                "path": "patient.patient_no",
                "label": "Patient No.",
                "type": "string",
                "sample": "P-00001234",
            },
            {"path": "order.id", "label": "Order ID", "type": "string", "sample": "ORDER-1001"},
            {"path": "result.HGB", "label": "HGB", "type": "string", "sample": "14.20"},
            {"path": "result.WBC", "label": "WBC", "type": "string", "sample": "7.10"},
            {"path": "result.PLT", "label": "PLT", "type": "string", "sample": "265"},
        ],
    }
    qr.properties["value"] = "https://example.com"
    return report


def add_label_field(
    page: object,
    label: str,
    binding: str,
    *,
    x: float,
    y: float,
    label_width: float,
    value_width: float,
) -> None:
    prefix = "".join(char.lower() if char.isalnum() else "_" for char in label).strip("_")
    page.text(label, x=x, y=y, width=label_width, height=12, id=f"{prefix}_label", font_size=10)
    page.field(
        binding,
        x=x + label_width,
        y=y,
        width=value_width,
        height=12,
        id=f"{prefix}_value",
        font_size=10,
        bold=True,
    )


def add_result_row(
    page: object,
    index: int,
    y: float,
    test_name: str,
    result_binding: str,
    unit: str,
    reference_range: str,
    flag: str,
    result_color: str,
) -> None:
    row_id = f"result_{index}"
    page.text(
        test_name,
        x=16,
        y=y,
        width=190,
        height=13,
        id=f"{row_id}_test",
        font_size=9,
        bold=not result_binding,
    )
    if result_binding:
        page.field(
            result_binding,
            x=226,
            y=y,
            width=54,
            height=13,
            id=f"{row_id}_value",
            font_size=9,
            color=result_color,
            align="center",
        )
    page.text(unit, x=312, y=y, width=58, height=13, id=f"{row_id}_unit", font_size=9)
    page.text(reference_range, x=378, y=y, width=120, height=13, id=f"{row_id}_range", font_size=9)
    page.text(
        flag,
        x=592,
        y=y,
        width=40,
        height=13,
        id=f"{row_id}_flag",
        font_size=9,
        color=result_color,
        bold=bool(flag),
    )


if __name__ == "__main__":
    ensure_sample_templates()
    app.run(debug=True, use_reloader=False)

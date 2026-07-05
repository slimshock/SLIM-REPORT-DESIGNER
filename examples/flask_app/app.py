"""Minimal Flask demo for Slim Report Designer."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from flask import Flask, Response, redirect

REPO_ROOT = Path(__file__).resolve().parents[2]
for package_src in (
    REPO_ROOT / "packages" / "slim_report_core" / "src",
    REPO_ROOT / "packages" / "slim_report_flask" / "src",
):
    if str(package_src) not in sys.path:
        sys.path.insert(0, str(package_src))

from slim_report_core import Report  # noqa: E402
from slim_report_core.serialization import JSONSerializer  # noqa: E402
from slim_report_flask import SlimReportDesigner  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(BASE_DIR / "sample_templates")

designer = SlimReportDesigner()
designer.init_app(app)


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


@app.get("/")
def index():
    return redirect("/report-designer/templates/lab_result/preview/ORDER-1001")


@app.get("/direct-preview/<record_id>")
def direct_preview(record_id: str) -> Response:
    """Preview using Flask plus the core Report API directly."""
    report = designer.get_report("lab_result")
    data = lab_result(record_id)
    return Response(report.render_html(data), mimetype="text/html")


@app.get("/direct-export/pdf/<record_id>")
def direct_export_pdf(record_id: str) -> Response:
    """Export PDF using Flask plus the core Report API directly."""
    report = designer.get_report("lab_result")
    data = lab_result(record_id)
    return Response(
        report.render_pdf(data),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="lab_result-{record_id}.pdf"',
        },
    )


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
        "LABORATORY RESULT",
        x=50,
        y=40,
        width=500,
        height=32,
        id="title",
        font_size=22,
        bold=True,
    )
    page.field(
        "patient.name",
        x=50,
        y=90,
        width=360,
        height=22,
        id="patient_name",
        font_size=13,
        bold=True,
    )
    page.field(
        "patient.age",
        x=50,
        y=116,
        width=120,
        height=20,
        id="patient_age",
        font_size=12,
    )
    page.field(
        "patient.sex",
        x=190,
        y=116,
        width=120,
        height=20,
        id="patient_sex",
        font_size=12,
    )
    page.field("order.id", x=50, y=142, width=260, height=20, id="order_id", font_size=12)
    page.line(x=50, y=176, width=500, id="separator", stroke_width=1)
    page.rectangle(x=50, y=200, width=500, height=130, id="result_box", border_width=1)

    page.text(
        "HGB",
        x=75,
        y=226,
        width=80,
        height=20,
        id="hgb_label",
        font_size=12,
        bold=True,
    )
    page.field(
        "result.HGB",
        x=180,
        y=226,
        width=120,
        height=20,
        id="hgb_value",
        font_size=12,
    )
    page.text(
        "WBC",
        x=75,
        y=262,
        width=80,
        height=20,
        id="wbc_label",
        font_size=12,
        bold=True,
    )
    page.field(
        "result.WBC",
        x=180,
        y=262,
        width=120,
        height=20,
        id="wbc_value",
        font_size=12,
    )
    page.text(
        "PLT",
        x=75,
        y=298,
        width=80,
        height=20,
        id="plt_label",
        font_size=12,
        bold=True,
    )
    page.field(
        "result.PLT",
        x=180,
        y=298,
        width=120,
        height=20,
        id="plt_value",
        font_size=12,
    )

    return report


def create_cerebro_cbc_report() -> Report:
    """Create a CBC report inspired by the Cerebro Diagnostic System sample."""
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
    page.orientation = "portrait"

    add_cerebro_header(page)
    add_cerebro_patient_block(page)
    add_cerebro_results_table(page)
    add_cerebro_footer(page)
    return report


def add_cerebro_header(page: object) -> None:
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
        id="cerebro_logo_subtitle",
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
        id="clinic_address_1",
        font_size=10,
    )
    page.text(
        "Misamis Oriental 9000",
        x=171,
        y=48,
        width=250,
        height=12,
        id="clinic_address_2",
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


def add_cerebro_patient_block(page: object) -> None:
    left_rows = [
        ("Patient Name:", "patient.name"),
        ("Age:", "patient.age"),
        ("DOB:", "patient.dob"),
        ("Sex:", "patient.sex"),
        ("Physician:", "patient.physician"),
        ("Clinical Diagnosis:", "patient.clinical_diagnosis"),
    ]
    right_rows = [
        ("Order No.:", "order.id"),
        ("Source:", "order.source"),
        ("Room No.:", "order.room_no"),
        ("Date Received:", "order.received"),
        ("Date Checked-In:", "order.checked_in"),
        ("Date Released:", "order.released"),
        ("Date Printed:", "order.printed"),
    ]

    y = 98
    for label, binding in left_rows:
        add_label_field(page, label, binding, x=14, y=y, label_width=96, value_width=180)
        y += 13

    y = 98
    for label, binding in right_rows:
        add_label_field(page, label, binding, x=330, y=y, label_width=98, value_width=185)
        y += 13

    page.text(
        "HEMATOLOGY",
        x=0,
        y=198,
        width=651,
        height=16,
        id="section_hematology",
        font_size=12,
        bold=True,
        color="#9AA0A6",
        align="center",
    )


def add_cerebro_results_table(page: object) -> None:
    page.text(
        "TEST NAME",
        x=16,
        y=232,
        width=150,
        height=14,
        id="test_name_header",
        font_size=10,
        bold=True,
    )
    page.text(
        "RESULT",
        x=226,
        y=232,
        width=54,
        height=14,
        id="result_header",
        font_size=10,
        bold=True,
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
    page.text(
        "FLAGS",
        x=570,
        y=232,
        width=54,
        height=14,
        id="flags_header",
        font_size=10,
        bold=True,
    )

    rows = [
        ("White Blood Cell Count", "results.wbc", "x10^9/L", "5-14.5", "HIGH", "#FF0000"),
        ("Red Blood Cell Count", "results.rbc", "x10^12/L", "3.9 - 5.3", "", "#000000"),
        ("Hemoglobin", "results.hgb", "g/dL", "11.5 - 13.5", "LOW", "#003BFF"),
        ("Hematocrit", "results.hct", "%", "34 - 40", "LOW", "#003BFF"),
        ("MCV", "results.mcv", "c.u.", "75 - 87", "", "#000000"),
        ("MCH", "results.mch", "uug", "24 - 30", "", "#000000"),
        ("MCHC", "results.mchc", "g/dL", "31-37", "", "#000000"),
        ("RDW", "results.rdw", "%", "11 - 16", "", "#000000"),
        ("Differential Count", "", "", "", "", "#000000"),
        ("Neutrophils", "results.neutrophils", "%", "50 - 70", "", "#000000"),
        ("Lymphocytes", "results.lymphocytes", "%", "20 - 40", "", "#000000"),
        ("Monocytes", "results.monocytes", "%", "3 - 9", "", "#000000"),
        ("Basophils", "results.basophils", "%", "0 - 0.5", "", "#000000"),
        ("Total (%)", "results.total", "", "", "", "#000000"),
        ("Platelet Count", "results.platelet", "x10^9/L", "150 - 450", "", "#000000"),
    ]

    y = 248
    for index, row in enumerate(rows):
        add_result_row(page, index, y, *row)
        y += 16


def add_cerebro_footer(page: object) -> None:
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
    page.text(
        "License No.: 0000",
        x=52,
        y=681,
        width=150,
        height=10,
        id="performed_license",
        font_size=7,
        align="center",
    )
    page.line(x=14, y=693, width=193, id="performed_line", stroke_width=1)
    page.text(
        "Performed By",
        x=72,
        y=698,
        width=92,
        height=10,
        id="performed_by",
        font_size=7,
        align="center",
    )

    page.text(
        "Dummy LAB_ENCODER",
        x=276,
        y=672,
        width=130,
        height=12,
        id="validated_name",
        font_size=7,
        bold=True,
        align="center",
    )
    page.text(
        "License No.: DMYROLE2",
        x=276,
        y=681,
        width=130,
        height=10,
        id="validated_license",
        font_size=7,
        align="center",
    )
    page.line(x=232, y=693, width=192, id="validated_line", stroke_width=1)
    page.text(
        "Validated By",
        x=282,
        y=698,
        width=90,
        height=10,
        id="validated_by",
        font_size=7,
        align="center",
    )

    page.text(
        "M. Torregosa",
        x=482,
        y=646,
        width=130,
        height=26,
        id="pathologist_signature",
        font_size=18,
    )
    page.text(
        "MARY ANN R. TORREGOSA, M.D.",
        x=473,
        y=672,
        width=150,
        height=12,
        id="pathologist_name",
        font_size=7,
        bold=True,
        align="center",
    )
    page.text(
        "License No.: 0057674",
        x=473,
        y=681,
        width=150,
        height=10,
        id="pathologist_license",
        font_size=7,
        align="center",
    )
    page.line(x=448, y=693, width=193, id="pathologist_line", stroke_width=1)
    page.text(
        "Pathologist",
        x=502,
        y=698,
        width=90,
        height=10,
        id="pathologist_role",
        font_size=7,
        align="center",
    )

    page.text(
        '"Please consult your doctors for clinical & interpretation of the result"',
        x=192,
        y=718,
        width=270,
        height=11,
        id="consult_note",
        font_size=7,
        color="#004CFF",
        align="center",
    )
    page.text(
        "**Results Electronically Signed**",
        x=244,
        y=728,
        width=160,
        height=11,
        id="signed_note",
        font_size=7,
        color="#004CFF",
        align="center",
    )
    page.text("1 of 1", x=614, y=738, width=30, height=11, id="page_count", font_size=9, bold=True)


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
    prefix = safe_id(label)
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
    is_group = not result_binding
    page.text(
        test_name,
        x=16,
        y=y,
        width=190,
        height=13,
        id=f"{row_id}_test",
        font_size=9,
        bold=is_group,
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


def safe_id(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


if __name__ == "__main__":
    ensure_sample_templates()
    app.run(debug=True)

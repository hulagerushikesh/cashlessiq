"""Render generic two-page pre-authorisation PDFs from case dictionaries."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_case(case: dict, target: Path) -> None:
    """Render one fictional request; no real insurer form or patient data is copied."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    story = [
        Paragraph("CASHLESS PRE-AUTHORISATION REQUEST", styles["Title"]),
        Paragraph("Synthetic hackathon demonstration - not a real claim form", styles["Italic"]),
        Spacer(1, 6 * mm),
    ]
    fields = [
        ("Request", case["request_id"]),
        ("Policy", case["policy_id"]),
        ("Hospital", case["hospital_name"]),
        ("Patient", case["patient_name"]),
        ("Admission", case["admission_date"]),
        ("Emergency", str(case["is_emergency"])),
        ("Diagnosis", case.get("diagnosis") or "Not supplied"),
        ("Procedure", case.get("procedure") or "Not supplied"),
        ("Room", case["room_category"]),
        ("Room rent/day", f"INR {case['room_rent_per_day_inr']:,}"),
        ("Planned stay", f"{case['planned_los_days']} days"),
    ]
    details = Table(fields, colWidths=[38 * mm, 52 * mm, 38 * mm, 52 * mm])
    details.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F1F8")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8F1F8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ]
        )
    )
    story.extend(
        [details, Spacer(1, 7 * mm), Paragraph("Estimated cost break-up", styles["Heading2"])]
    )
    costs = [["Item", "Amount (INR)"]]
    costs.extend([[row["item"], f"{row['claimed_inr']:,}"] for row in case.get("cost_breakup", [])])
    costs.append(["Estimated total", f"{case['estimated_total_inr']:,}"])
    cost_table = Table(costs, colWidths=[120 * mm, 50 * mm])
    cost_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173A5E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]
        )
    )
    story.extend(
        [cost_table, PageBreak(), Paragraph("CLINICAL NOTE", styles["Title"]), Spacer(1, 8 * mm)]
    )
    story.append(Paragraph(case["clinical_note"], styles["BodyText"]))
    story.extend(
        [
        Spacer(1, 15 * mm),
        Paragraph("Declaration", styles["Heading2"]),
        Paragraph(
            "The details above are fictional and were generated solely to test document "
            "extraction and decision-support software. Human review is required for every "
            "recommendation.",
            styles["BodyText"],
        ),
        ]
    )
    doc.build(story)

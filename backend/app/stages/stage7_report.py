import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from backend.app.models.models import Scan, ExtractedField, RuleCheck
from backend.app.core.config import settings

def save_scan_results_to_db(
    db: Session,
    scan_id: str,
    input_type: str,
    image_path: Optional[str],
    authenticity_score: float,
    object_classification: str,
    extracted_fields: Dict[str, Any],
    check_results: List[Dict[str, Any]]
) -> Scan:
    """
    Saves the entire scan pipeline results to PostgreSQL.
    """
    # 1. Create or update Scan
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        scan = Scan(
            id=scan_id,
            input_type=input_type,
            image_path=image_path,
            authenticity_score=authenticity_score,
            object_classification=object_classification
        )
        db.add(scan)
    else:
        scan.authenticity_score = authenticity_score
        scan.object_classification = object_classification
        db.query(ExtractedField).filter(ExtractedField.scan_id == scan_id).delete()
        db.query(RuleCheck).filter(RuleCheck.scan_id == scan_id).delete()
        
    db.commit()
    
    # 2. Save Extracted Fields
    for key, val in extracted_fields.items():
        if key in ["listing_fields", "is_imported"]:
            continue
            
        confidence = 0.95
        if key == "mrp":
            confidence = extracted_fields.get("mrp_confidence", 0.95)
        elif key == "net_quantity":
            confidence = extracted_fields.get("net_quantity_confidence", 0.95)
        elif key == "mfg_date":
            confidence = extracted_fields.get("mfg_date_confidence", 0.95)
            
        field_entry = ExtractedField(
            scan_id=scan.id,
            field_name=key,
            field_value=str(val) if val is not None else None,
            ocr_confidence=confidence
        )
        db.add(field_entry)
        
    # 3. Save Rule Checks
    for check in check_results:
        check_entry = RuleCheck(
            scan_id=scan.id,
            rule_id=check.get("rule_id", "check_unknown"),
            status=check.get("status", "unverifiable"),
            explanation=check.get("explanation", "")
        )
        db.add(check_entry)
        
    db.commit()
    db.refresh(scan)
    return scan

def generate_pdf_report(scan: Scan, check_results: List[Dict[str, Any]]) -> str:
    """
    Generates a formal PDF Audit Report using ReportLab.
    Returns the absolute path to the generated PDF.
    """
    pdf_filename = f"{scan.id}_report.pdf"
    target_path = os.path.join(settings.REPORT_DIR, pdf_filename)
    
    doc = SimpleDocTemplate(target_path, pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    
    styles = getSampleStyleSheet()
    
    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'ReportSub',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=20
    )
    
    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=15,
        spaceAfter=8
    )
    
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=11
    )
    
    cell_bold_style = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11
    )
    
    story = []
    
    # 1. Header Title
    story.append(Paragraph("GOVERNMENT OF INDIA", ParagraphStyle('Gov', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', leading=9, alignment=1, spaceAfter=2)))
    story.append(Paragraph("MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION", ParagraphStyle('Ministry', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', leading=10, alignment=1, spaceAfter=2)))
    story.append(Paragraph("DEPARTMENT OF LEGAL METROLOGY", ParagraphStyle('Dept', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', leading=11, alignment=1, spaceAfter=15)))
    
    story.append(Paragraph("Legal Metrology (Packaged Commodities) Audit Report", title_style))
    story.append(Paragraph(f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Scan Reference ID: {scan.id}", subtitle_style))
    
    # 2. Overall Status Panel
    overall_status = "PASS"
    fail_count = sum(1 for c in check_results if c.get("status") == "fail")
    exempt_count = sum(1 for c in check_results if c.get("status") == "exempt")
    unverifiable_count = sum(1 for c in check_results if c.get("status") == "unverifiable")
    
    if fail_count > 0:
        overall_status = "NON-COMPLIANT (FAIL)"
        status_color = colors.HexColor('#EF4444')
    elif unverifiable_count > 0:
        overall_status = "WARNING (UNVERIFIABLE CHECKS)"
        status_color = colors.HexColor('#F59E0B')
    else:
        overall_status = "COMPLIANT (PASS)"
        status_color = colors.HexColor('#10B981')
        
    summary_data = [
        [Paragraph("<b>Audit Status:</b>", cell_bold_style), Paragraph(f"<font color='{status_color}'><b>{overall_status}</b></font>", cell_bold_style)],
        [Paragraph("<b>Input Type:</b>", cell_bold_style), Paragraph(scan.input_type.upper(), cell_style)],
        [Paragraph("<b>Authenticity Confidence:</b>", cell_bold_style), Paragraph(f"{scan.authenticity_score}%", cell_style)],
        [Paragraph("<b>Object Classification:</b>", cell_bold_style), Paragraph(scan.object_classification, cell_style)]
    ]
    
    summary_table = Table(summary_data, colWidths=[150, 380])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 15))
    
    # 3. Extracted Declarations
    story.append(Paragraph("Extracted Label Declarations", section_style))
    confidence_col_title = "Extraction Confidence" if scan.input_type == "url" else "OCR Confidence"
    fields_data = [
        [Paragraph("<b>Declaration Field</b>", cell_bold_style), Paragraph("<b>Extracted Value</b>", cell_bold_style), Paragraph(f"<b>{confidence_col_title}</b>", cell_bold_style)]
    ]
    
    # Gather fields
    for field in (scan.fields or []):
        fields_data.append([
            Paragraph((field.field_name or "").replace("_", " ").title(), cell_bold_style),
            Paragraph(field.field_value or "<i>[Not Detected]</i>", cell_style),
            Paragraph(f"{(field.ocr_confidence or 0.0) * 100:.1f}%", cell_style)
        ])
        
    fields_table = Table(fields_data, colWidths=[160, 270, 100])
    fields_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(fields_table)
    story.append(Spacer(1, 15))
    
    # 4. Rules Checklist
    story.append(Paragraph("Statutory Rule Check List", section_style))
    rules_data = [
        [Paragraph("<b>Citation</b>", cell_bold_style), Paragraph("<b>Rule Description</b>", cell_bold_style), Paragraph("<b>Result</b>", cell_bold_style), Paragraph("<b>Audit Explanation</b>", cell_bold_style)]
    ]
    
    for check in check_results:
        st = check.get("status", "unverifiable")
        if st == "pass":
            color_hex = "#10B981"
        elif st == "fail":
            color_hex = "#EF4444"
        elif st == "exempt":
            color_hex = "#64748B"
        else:
            color_hex = "#F59E0B"
            
        citation = check.get("rule_citation", check.get("rule_id", "Rule Check"))
        desc = check.get("description", "")
        explanation = check.get("explanation", "")
        
        rules_data.append([
            Paragraph(citation, cell_bold_style),
            Paragraph(desc, cell_style),
            Paragraph(f"<font color='{color_hex}'><b>{st.upper()}</b></font>", cell_bold_style),
            Paragraph(explanation, cell_style)
        ])
        
    rules_table = Table(rules_data, colWidths=[100, 150, 70, 210])
    rules_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(rules_table)
    story.append(Spacer(1, 40))
    
    # 5. Signature Footer
    sig_data = [
        [Paragraph("Audit Officer Inspector: ________________________", cell_bold_style),
         Paragraph("Signature / Stamp: ________________________", cell_bold_style)]
    ]
    sig_table = Table(sig_data, colWidths=[270, 260])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_table)
    
    doc.build(story)
    return target_path

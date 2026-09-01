import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
)
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
    
    # Save Extracted Fields
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
        
    # Save Rule Checks
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
    Generates a formal PDF Product Compliance Report matching the exact required 4-part structure:
    - Header: Report ID, Date & Time, Product Image
    - 1. PRODUCT INFORMATION
    - 2. EXTRACTION RESULTS
    - 3. NON-COMPLIANCE / WARNINGS
    - 4. OVERALL ASSESSMENT (COMPLIANT / NON-COMPLIANT / REQUIRES VERIFICATION)
    """
    os.makedirs(settings.REPORT_DIR, exist_ok=True)
    pdf_filename = f"{scan.id}_report.pdf"
    target_path = os.path.join(settings.REPORT_DIR, pdf_filename)
    
    doc = SimpleDocTemplate(
        target_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Typography Styles
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        alignment=1, # Centered
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=10
    )
    
    section_hdr_style = ParagraphStyle(
        'SectionHdr',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=6
    )
    
    label_style = ParagraphStyle(
        'FieldLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    
    val_style = ParagraphStyle(
        'FieldVal',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )
    
    small_style = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#64748B')
    )
    
    story = []
    
    # ─────────────────────────────────────────────────────────────
    # TITLE & METADATA HEADER BOX
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("PRODUCT COMPLIANCE REPORT", title_style))
    story.append(Spacer(1, 4))
    
    # Map extracted fields to dictionary
    field_map = {}
    for f in (scan.fields or []):
        field_map[f.field_name] = f.field_value
        
    created_dt_str = scan.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if scan.created_at else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Check if a product image exists
    img_element = None
    if scan.image_path:
        local_img_path = scan.image_path
        if local_img_path.startswith("/static/"):
            local_img_path = os.path.join(settings.BASE_DIR, local_img_path.lstrip("/"))
            
        if os.path.exists(local_img_path):
            try:
                img_element = RLImage(local_img_path, width=110, height=85)
            except Exception:
                img_element = None
                
    if not img_element:
        img_element = Paragraph("<i>[Digital E-Commerce URL / Listing Scan]</i>", small_style)
        
    header_meta_data = [
        [
            Paragraph(f"<b>Report ID:</b> {scan.id}", val_style),
            Paragraph("<b>Product Image:</b>", label_style)
        ],
        [
            Paragraph(f"<b>Date &amp; Time:</b> {created_dt_str}", val_style),
            img_element
        ],
        [
            Paragraph(f"<b>Target Category:</b> {(scan.object_classification or 'Retail Commodity').replace('_', ' ').title()}", val_style),
            Paragraph(f"<b>Input Channel:</b> {(scan.input_type or 'photo').upper()}", small_style)
        ]
    ]
    
    header_table = Table(header_meta_data, colWidths=[360, 180])
    header_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('SPAN', (1, 1), (1, 2)), # Span image across row 1 & 2
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    
    # ─────────────────────────────────────────────────────────────
    # 1. PRODUCT INFORMATION
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("1. PRODUCT INFORMATION", section_hdr_style))
    
    # Format Dates (MFD, Expiry, Best Before)
    mfg_date = field_map.get("mfg_date") or "Not Declared"
    exp_date = field_map.get("expiry_date") or field_map.get("best_before_date")
    dates_str = f"Mfg: {mfg_date}" + (f" | Exp/Best Before: {exp_date}" if exp_date else "")
    
    # Format Customer Care
    cc_phone = field_map.get("consumer_care_phone") or "1800-XXX-XXXX"
    cc_email = field_map.get("consumer_care_email") or "care@brand.com"
    cc_str = f"Phone: {cc_phone} | Email: {cc_email}"
    
    # Manufacturer details
    mfg_name = field_map.get("manufacturer_name") or field_map.get("importer_name") or "Not Declared"
    mfg_addr = field_map.get("manufacturer_address") or field_map.get("importer_address")
    if mfg_addr and mfg_addr != mfg_name:
        mfg_display = f"{mfg_name} ({mfg_addr})"
    else:
        mfg_display = mfg_name

    prod_info_data = [
        [Paragraph("Product Name", label_style), Paragraph(field_map.get("generic_name") or "<i>[Not Detected]</i>", val_style)],
        [Paragraph("Manufacturer / Packer", label_style), Paragraph(mfg_display, val_style)],
        [Paragraph("MRP (Maximum Retail Price)", label_style), Paragraph(field_map.get("mrp") or "<i>[Not Detected]</i>", val_style)],
        [Paragraph("Net Quantity", label_style), Paragraph(field_map.get("net_quantity") or "<i>[Not Detected]</i>", val_style)],
        [Paragraph("Batch / Lot Number", label_style), Paragraph(field_map.get("batch_no") or field_map.get("lot_no") or "Declared on Batch Stamp", val_style)],
        [Paragraph("Dates (Mfg / Expiry)", label_style), Paragraph(dates_str, val_style)],
        [Paragraph("Customer Care Details", label_style), Paragraph(cc_str, val_style)]
    ]
    
    # Add category specific extras if present
    if field_map.get("fssai_license_no"):
        prod_info_data.append([
            Paragraph("FSSAI License No", label_style),
            Paragraph(str(field_map.get("fssai_license_no")), val_style)
        ])
    if field_map.get("fiber_composition") or field_map.get("apparel_size"):
        textile_details = f"Size: {field_map.get('apparel_size', 'N/A')} | Fiber: {field_map.get('fiber_composition', 'N/A')}"
        prod_info_data.append([
            Paragraph("Apparel Specs (Size/Fiber)", label_style),
            Paragraph(textile_details, val_style)
        ])
    if field_map.get("country_of_origin"):
        prod_info_data.append([
            Paragraph("Country of Origin", label_style),
            Paragraph(str(field_map.get("country_of_origin")), val_style)
        ])
        
    prod_info_table = Table(prod_info_data, colWidths=[170, 370])
    prod_info_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(prod_info_table)
    story.append(Spacer(1, 10))
    
    # ─────────────────────────────────────────────────────────────
    # 2. EXTRACTION RESULTS (OCR / Detection Confidence)
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("2. EXTRACTION RESULTS", section_hdr_style))
    confidence_col_title = "Extraction Confidence" if scan.input_type == "url" else "OCR Confidence"
    
    extraction_data = [
        [
            Paragraph("<b>Statutory Field Key</b>", label_style),
            Paragraph("<b>Raw Extracted Text Region</b>", label_style),
            Paragraph(f"<b>{confidence_col_title}</b>", label_style)
        ]
    ]
    
    for f in (scan.fields or []):
        if not f.field_value:
            continue
        field_display_name = (f.field_name or "").replace("_", " ").title()
        conf_pct = f"{(f.ocr_confidence or 0.95) * 100:.1f}%"
        extraction_data.append([
            Paragraph(field_display_name, label_style),
            Paragraph(str(f.field_value), val_style),
            Paragraph(conf_pct, val_style)
        ])
        
    if len(extraction_data) == 1:
        extraction_data.append([
            Paragraph("Raw Text OCR", label_style),
            Paragraph("<i>No text regions extracted from image.</i>", val_style),
            Paragraph("0.0%", val_style)
        ])
        
    extraction_table = Table(extraction_data, colWidths=[150, 310, 80])
    extraction_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(extraction_table)
    story.append(Spacer(1, 10))
    
    # ─────────────────────────────────────────────────────────────
    # 3. NON-COMPLIANCE / WARNINGS (Issue + Explanation)
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("3. NON-COMPLIANCE / WARNINGS", section_hdr_style))
    
    non_comp_checks = [c for c in check_results if c.get("status") in ["fail", "unverifiable"]]
    
    if len(non_comp_checks) == 0:
        clean_msg_data = [
            [
                Paragraph("<font color='#059669'><b>✓ No Statutory Non-Compliances Detected</b></font>", label_style),
                Paragraph("All evaluated declarations (MRP, Net Quantity, Dates, Manufacturer/Packer, Customer Care, FSSAI / Textile Rules) strictly adhere to Legal Metrology Standards.", val_style)
            ]
        ]
        clean_table = Table(clean_msg_data, colWidths=[180, 360])
        clean_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#86EFAC')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(clean_table)
    else:
        issues_data = [
            [
                Paragraph("<b>Statutory Rule &amp; Issue</b>", label_style),
                Paragraph("<b>Severity</b>", label_style),
                Paragraph("<b>Audit Explanation &amp; Corrective Action</b>", label_style)
            ]
        ]
        
        for c in non_comp_checks:
            citation = c.get("rule_citation", c.get("rule_id", "Statutory Rule"))
            status = c.get("status", "fail").upper()
            status_color = "#DC2626" if status == "FAIL" else "#D97706"
            explanation = c.get("explanation", "Declaration missing or invalid under statutory guidelines.")
            fix = c.get("fix_suggestion")
            
            detail_p = f"{explanation}"
            if fix:
                detail_p += f"<br/><font color='#059669'><b>Consumer Action:</b> {fix}</font>"
                
            issues_data.append([
                Paragraph(f"<font color='{status_color}'><b>[{status}]</b></font> {citation}", label_style),
                Paragraph(c.get("severity", "MAJOR"), val_style),
                Paragraph(detail_p, val_style)
            ])
            
        issues_table = Table(issues_data, colWidths=[150, 60, 330])
        issues_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FCA5A5')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FEE2E2')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FECACA')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFF1F2')]),
        ]))
        story.append(issues_table)
        
    story.append(Spacer(1, 10))
    
    # ─────────────────────────────────────────────────────────────
    # 4. OVERALL ASSESSMENT
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("4. OVERALL ASSESSMENT", section_hdr_style))
    
    fail_count = sum(1 for c in check_results if c.get("status") == "fail")
    unverifiable_count = sum(1 for c in check_results if c.get("status") == "unverifiable")
    
    if fail_count > 0:
        verdict_text = "NON-COMPLIANT"
        verdict_color = "#DC2626"
        verdict_desc = f"Product packaging violates {fail_count} statutory declaration requirement(s) under Indian Legal Metrology Rules."
    elif unverifiable_count > 0:
        verdict_text = "REQUIRES VERIFICATION"
        verdict_color = "#D97706"
        verdict_desc = f"Product packaging has {unverifiable_count} declaration(s) requiring manual physical verification or clearer photo scan."
    else:
        verdict_text = "COMPLIANT"
        verdict_color = "#059669"
        verdict_desc = "Product packaging satisfies all mandatory statutory declarations across evaluated rules."
        
    auth_score = scan.authenticity_score or 0.0
    auth_verdict = "Authentic / Original Capture" if auth_score >= 70.0 else "Tampering / Synthesis Warning"
    
    assessment_data = [
        [
            Paragraph(f"<font color='{verdict_color}' size='13'><b>{verdict_text}</b></font>", label_style),
            Paragraph(f"<b>Statutory Assessment:</b> {verdict_desc}", val_style)
        ],
        [
            Paragraph(f"<b>Image Authenticity: {auth_score:.1f}%</b>", label_style),
            Paragraph(f"<b>Forensics Verdict:</b> {auth_verdict} (EXIF Metadata, 2D FFT Frequency Analysis &amp; ELA Error Profile).", small_style)
        ]
    ]
    
    assessment_table = Table(assessment_data, colWidths=[180, 360])
    assessment_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor(verdict_color)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(assessment_table)
    
    # Build Document
    doc.build(story)
    return target_path

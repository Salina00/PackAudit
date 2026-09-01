import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.database import SessionLocal
from backend.app.models.models import RuleDefinition, ManufacturerCache

def export_db_to_sql():
    os.makedirs("database", exist_ok=True)
    db = SessionLocal()
    sql_lines = [
        "-- ========================================================",
        "-- PACKAUDIT STATUTORY DATABASE SCHEMA & SEED DATA",
        "-- Legal Metrology Rules 2011, FSSAI 2020, & Textile 2011",
        "-- ========================================================\n",
        "CREATE TABLE IF NOT EXISTS rule_definitions (",
        "    rule_id VARCHAR(50) PRIMARY KEY,",
        "    rule_citation VARCHAR(255) NOT NULL,",
        "    description TEXT NOT NULL,",
        "    check_type VARCHAR(50) NOT NULL,",
        "    severity VARCHAR(20) DEFAULT 'MAJOR',",
        "    fix_suggestion TEXT,",
        "    validation_logic JSONB DEFAULT '{}'::jsonb",
        ");\n",
        "CREATE TABLE IF NOT EXISTS manufacturer_cache (",
        "    id SERIAL PRIMARY KEY,",
        "    company_name VARCHAR(255) NOT NULL,",
        "    aliases JSONB DEFAULT '[]'::jsonb,",
        "    registered_pincodes JSONB DEFAULT '[]'::jsonb,",
        "    verified_addresses JSONB DEFAULT '[]'::jsonb",
        ");\n",
        "CREATE TABLE IF NOT EXISTS scans (",
        "    id VARCHAR(36) PRIMARY KEY,",
        "    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,",
        "    input_type VARCHAR(20) NOT NULL,",
        "    image_path VARCHAR(255),",
        "    authenticity_score FLOAT DEFAULT 100.0,",
        "    object_classification VARCHAR(50) DEFAULT 'packaged_commodity',",
        "    extracted_text TEXT",
        ");\n",
        "CREATE TABLE IF NOT EXISTS extracted_fields (",
        "    id SERIAL PRIMARY KEY,",
        "    scan_id VARCHAR(36) REFERENCES scans(id) ON DELETE CASCADE,",
        "    field_name VARCHAR(50) NOT NULL,",
        "    field_value TEXT,",
        "    ocr_confidence FLOAT DEFAULT 1.0,",
        "    bounding_box JSONB",
        ");\n",
        "CREATE TABLE IF NOT EXISTS rule_checks (",
        "    id SERIAL PRIMARY KEY,",
        "    scan_id VARCHAR(36) REFERENCES scans(id) ON DELETE CASCADE,",
        "    rule_id VARCHAR(50) REFERENCES rule_definitions(rule_id),",
        "    status VARCHAR(20) NOT NULL,",
        "    explanation TEXT NOT NULL",
        ");\n"
    ]
    
    # Export Rule Definitions
    rules = db.query(RuleDefinition).all()
    sql_lines.append(f"-- SEEDING {len(rules)} STATUTORY RULE DEFINITIONS")
    for r in rules:
        val_logic = json.dumps(r.validation_logic or {}).replace("'", "''")
        fix_sug = (r.fix_suggestion or "").replace("'", "''")
        desc = r.description.replace("'", "''")
        cit = r.rule_citation.replace("'", "''")
        sql_lines.append(
            f"INSERT INTO rule_definitions (rule_id, rule_citation, description, check_type, severity, fix_suggestion, validation_logic) "
            f"VALUES ('{r.rule_id}', '{cit}', '{desc}', '{r.check_type}', '{r.severity}', '{fix_sug}', '{val_logic}'::jsonb) "
            f"ON CONFLICT (rule_id) DO UPDATE SET rule_citation = EXCLUDED.rule_citation, description = EXCLUDED.description, "
            f"severity = EXCLUDED.severity, fix_suggestion = EXCLUDED.fix_suggestion, validation_logic = EXCLUDED.validation_logic;"
        )
        
    # Export Manufacturer Caches
    mfgs = db.query(ManufacturerCache).all()
    sql_lines.append(f"\n-- SEEDING {len(mfgs)} VERIFIED MANUFACTURER CACHES")
    for m in mfgs:
        aliases = json.dumps(m.aliases or []).replace("'", "''")
        pins = json.dumps(m.registered_pincodes or []).replace("'", "''")
        addrs = json.dumps(m.verified_addresses or []).replace("'", "''")
        cname = m.company_name.replace("'", "''")
        sql_lines.append(
            f"INSERT INTO manufacturer_cache (company_name, aliases, registered_pincodes, verified_addresses) "
            f"VALUES ('{cname}', '{aliases}'::jsonb, '{pins}'::jsonb, '{addrs}'::jsonb);"
        )
        
    output_path = os.path.join("database", "packaudit_init.sql")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines) + "\n")
        
    print(f"Exported {len(rules)} rules and {len(mfgs)} manufacturer caches to {output_path}")
    db.close()

if __name__ == "__main__":
    export_db_to_sql()

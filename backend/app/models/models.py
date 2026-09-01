from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from backend.app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="consumer") # "consumer", "citizen", "officer"
    created_at = Column(DateTime, default=datetime.utcnow)

class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(String, unique=True, index=True, nullable=False)  # e.g., "check_2"
    rule_citation = Column(String, nullable=False)                      # e.g., "Rule 6(1)(a)"
    description = Column(String, nullable=False)
    check_type = Column(String, nullable=False)                         # "presence", "regex", "measurement", "exemption"
    validation_logic = Column(JSON, nullable=True)                      # flexible validation rules
    severity = Column(String, default="MAJOR")                          # "CRITICAL", "MAJOR", "MINOR"
    fix_suggestion = Column(String, nullable=True)                      # static guidance fix template
    
    checks = relationship("RuleCheck", back_populates="definition")

class Scan(Base):
    __tablename__ = "scans"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    image_path = Column(String, nullable=True)
    input_type = Column(String, nullable=False)                         # "photo" or "url"
    authenticity_score = Column(Float, default=0.0)
    object_classification = Column(String, default="unknown")           # e.g. "retail_package", "exempt_food"
    
    fields = relationship("ExtractedField", back_populates="scan", cascade="all, delete-orphan")
    checks = relationship("RuleCheck", back_populates="scan", cascade="all, delete-orphan")

class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String, nullable=False)                         # e.g., "mrp", "net_quantity"
    field_value = Column(String, nullable=True)
    ocr_confidence = Column(Float, default=0.0)
    
    scan = relationship("Scan", back_populates="fields")

class RuleCheck(Base):
    __tablename__ = "rule_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    rule_id = Column(String, ForeignKey("rule_definitions.rule_id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False)                             # "pass", "fail", "exempt", "unverifiable"
    explanation = Column(String, nullable=True)
    
    scan = relationship("Scan", back_populates="checks")
    definition = relationship("RuleDefinition", back_populates="checks")
    rule = relationship("RuleDefinition", viewonly=True)

class ManufacturerCache(Base):
    __tablename__ = "manufacturer_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, unique=True, index=True, nullable=False)
    aliases = Column(JSON, nullable=True)                               # list of names/brands (JSON array)
    registered_pincodes = Column(JSON, nullable=True)                   # list of valid pincodes (JSON array)
    verified_addresses = Column(JSON, nullable=True)                    # list of official addresses (JSON array)

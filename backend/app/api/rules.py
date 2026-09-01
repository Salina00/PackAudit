from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.core.database import get_db
from backend.app.models.models import RuleDefinition
from backend.app.schemas.schemas import RuleDefinitionResponse

router = APIRouter(
    prefix="/api/rules",
    tags=["Rules"]
)

@router.get("", response_model=List[RuleDefinitionResponse])
def read_rules(db: Session = Depends(get_db)):
    """
    Returns the list of all defined Legal Metrology compliance checks.
    """
    rules = db.query(RuleDefinition).order_by(RuleDefinition.rule_id).all()
    return rules

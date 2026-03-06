from typing import List, Optional
from pydantic import Field, BaseModel
from .base_model import BaseEntity
from datetime import datetime

class CaseDocument(BaseModel):
    url: str
    fileName: str
    type: str
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)

class HearingEntry(BaseModel):
    hearingDate: datetime
    note: str
    updatedBy: str
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)

class Note(BaseModel):
    description: str
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)

class Case(BaseEntity):
    id: Optional[str]
    clientId: str
    advocateId: str
    caseTitle: str
    caseDetail: str
    caseNumber: str
    hearingDate: datetime
    courtLocation: str
    caseParentId: Optional[str] = None
    filingDate: datetime = Field(default_factory=datetime.utcnow)
    caseStatus: str = "Open"
    opponant: str
    oppositeAdvocate: str
    caseRemark: str  
    caseDocuments: Optional[List[CaseDocument]] = []
    hearingHistory: Optional[List[HearingEntry]] = []
    notes: Optional[List[Note]] = []



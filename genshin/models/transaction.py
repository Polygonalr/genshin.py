from typing import Literal
from pydantic import BaseModel, Field
from datetime import datetime


class Transaction(BaseModel):
    kind: Literal["primogem", "crystal", "resin"]
    
    id: int
    uid: int
    time: datetime
    amount: int = Field(alias="add_num")
    reason_id: int = Field(alias="reason")
    reason: str  = Field('', alias="reason_str")

class ItemTransaction(Transaction):
    kind: Literal["artifact", "weapon"]
    
    name: str
    rarity: int = Field(alias="rank")
from pydantic import BaseModel, Field
from typing import Optional, Literal


class SpecimenInput(BaseModel):
    specimen_key: str = Field(min_length=1, max_length=100)
    reading: float = Field(allow_inf_nan=False)
    rejudgement: Optional[Literal['leak', 'sealed']] = None

from pydantic import BaseModel, Field


class RollInput(BaseModel):
    roll_code: str = Field(min_length=1, max_length=100)
    material: str = Field(default='', max_length=120)
    note: str = Field(default='', max_length=500)

from pydantic import BaseModel, Field


class RoundInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    note: str = Field(default='', max_length=2000)
    calibration_roll_ids: list[int] = Field(default_factory=list)
    blind_roll_ids: list[int] = Field(default_factory=list)

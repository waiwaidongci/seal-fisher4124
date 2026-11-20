from pydantic import BaseModel, Field


class RoundRollsInput(BaseModel):
    calibration_roll_ids: list[int] = Field(default_factory=list)
    blind_roll_ids: list[int] = Field(default_factory=list)

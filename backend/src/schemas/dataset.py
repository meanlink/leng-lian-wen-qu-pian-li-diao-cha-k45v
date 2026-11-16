from pydantic import BaseModel, Field
class DatasetInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source: str = Field(default='manual.json', max_length=200)
    records: list[dict] = Field(min_length=5, max_length=5000)
class DoorEventInput(BaseModel):
    route: str = Field(min_length=1, max_length=120)
    start_minute: float | None = None
    end_minute: float | None = None
    label: str = Field(default='', max_length=160)
class SupplementInput(BaseModel):
    request_id: str = Field(min_length=8, max_length=64)
    events: list[DoorEventInput] = Field(min_length=1, max_length=50)
class ResolveInput(BaseModel):
    action: str = Field(min_length=2, max_length=20)
    start_minute: float | None = None
    end_minute: float | None = None

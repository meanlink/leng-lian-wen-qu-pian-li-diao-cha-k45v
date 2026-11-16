from sqlalchemy import String, JSON, Double, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    source: Mapped[str] = mapped_column(String(200), default='manual.json')
    records: Mapped[list] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Double)
class DoorEvent(Base):
    __tablename__ = 'door_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    route: Mapped[str] = mapped_column(String(120))
    start_minute: Mapped[float | None] = mapped_column(Double, nullable=True)
    end_minute: Mapped[float | None] = mapped_column(Double, nullable=True)
    label: Mapped[str] = mapped_column(String(160), default='')
    status: Mapped[str] = mapped_column(String(20), default='pending')
    reason: Mapped[str] = mapped_column(String(200), default='')
    request_id: Mapped[str] = mapped_column(String(64))
    seq: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(String(160), default='')
    created_at: Mapped[float] = mapped_column(Double)
    __table_args__ = (UniqueConstraint('dataset_id', 'request_id', 'seq', name='uq_door_events_request'),)
class DatasetVersion(Base):
    __tablename__ = 'dataset_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    version_no: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default='draft')
    events: Mapped[list] = mapped_column(JSON, default=list)
    affected: Mapped[dict] = mapped_column(JSON, default=dict)
    checksum: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(String(400), default='')
    created_by: Mapped[str] = mapped_column(String(160), default='')
    created_at: Mapped[float] = mapped_column(Double)
    published_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    __table_args__ = (UniqueConstraint('dataset_id', 'version_no', name='uq_versions_no'), UniqueConstraint('dataset_id', 'checksum', name='uq_versions_checksum'))

from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class EventStatus(str, Enum):
    applied = 'applied'
    pending = 'pending'
    dismissed = 'dismissed'
class VersionStatus(str, Enum):
    draft = 'draft'
    published = 'published'
    superseded = 'superseded'

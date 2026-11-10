from enum import Enum


class UserRole(str, Enum):
    FAMILY = "FAMILY"
    ELDERLY = "ELDERLY"


class FamilyElderlyLinkStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


class ReminderRecurrence(str, Enum):
    ONCE = "ONCE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class ReminderStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AUDIO_READY = "AUDIO_READY"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReminderEventType(str, Enum):
    CREATED = "CREATED"
    TRIGGERED = "TRIGGERED"
    AUDIO_GENERATED = "AUDIO_GENERATED"
    DELIVERED = "DELIVERED"
    PLAYED = "PLAYED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
from enum import StrEnum


class CapabilityClass(StrEnum):
    C0_INFORMATIONAL = "C0"
    C1_READ_ONLY = "C1"
    C2_DIAGNOSTIC = "C2"
    C3_CONTROLLED_CHANGE = "C3"
    C4_SERVICE_IMPACTING = "C4"
    C5_DESTRUCTIVE = "C5"


FOUNDATION_CAPABILITY_CLASSES = frozenset(
    {CapabilityClass.C0_INFORMATIONAL, CapabilityClass.C1_READ_ONLY}
)

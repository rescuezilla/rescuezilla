from enum import Enum


class EncryptionState(Enum):
    ENCRYPTED_AND_LOCKED = 1
    ENCRYPTED_AND_UNLOCKED = 2
    NOT_ENCRYPTED = 3

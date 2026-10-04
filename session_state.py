"""Observable adapter lifecycle; PREPARING never forwards gameplay input."""

from enum import Enum


class SessionState(Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    CLOSED = "closed"

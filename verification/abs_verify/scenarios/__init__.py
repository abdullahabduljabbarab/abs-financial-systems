"""System verification scenarios (SYS-V-*)."""

from .base import Scenario, World
from .sys_v_001 import SysV001

# Registry keyed by the lowercase, hyphenated scenario id the runner accepts.
REGISTRY: dict[str, type[Scenario]] = {
    SysV001.id: SysV001,
}

__all__ = ["Scenario", "World", "SysV001", "REGISTRY"]

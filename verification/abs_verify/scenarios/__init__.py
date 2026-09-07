"""System verification scenarios (SYS-V-*)."""

from .base import Scenario, World
from .sys_v_001 import SysV001
from .sys_v_002 import SysV002
from .sys_v_003 import SysV003
from .sys_v_004 import SysV004
from .sys_v_005 import SysV005
from .sys_v_006 import SysV006
from .sys_v_010 import SysV010
from .sys_v_012 import SysV012

# Registry keyed by the lowercase, hyphenated scenario id the runner accepts.
REGISTRY: dict[str, type[Scenario]] = {
    SysV001.id: SysV001,
    SysV002.id: SysV002,
    SysV003.id: SysV003,
    SysV004.id: SysV004,
    SysV005.id: SysV005,
    SysV006.id: SysV006,
    SysV010.id: SysV010,
    SysV012.id: SysV012,
}

__all__ = [
    "Scenario",
    "World",
    "SysV001",
    "SysV002",
    "SysV003",
    "SysV004",
    "SysV005",
    "SysV006",
    "SysV010",
    "SysV012",
    "REGISTRY",
]

"""Black-box system verification harness for ABS Financial Systems.

The harness drives the five live services only through their public HTTP
surface (see ../docs/SERVICE_CATALOGUE.md) and asserts on their responses and on the
events observed through consumers' read APIs. It never reaches inside a service.
"""

__all__ = ["config", "clients", "evidence", "scenarios"]

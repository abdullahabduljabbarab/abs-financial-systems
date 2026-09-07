"""ABS engineering portal, backend-for-frontend.

A read-only aggregation layer over the live ecosystem. It holds no database and is
not a financial service: it calls the services' public HTTP surface, composes the
answers a read-only engineering and operations view needs (system health, a payment
trace, the verification matrix, and service reads), and serves the frontend.
"""

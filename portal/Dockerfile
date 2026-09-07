# abs-portal: one image, both halves. The frontend is built with Node, then served
# as static files by the FastAPI BFF, so the whole portal is a single Cloud Run
# service on one origin.

# --- build the frontend -------------------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- runtime: the BFF serving /api and the built frontend --------------------
FROM python:3.12-slim
WORKDIR /app

COPY bff/requirements.txt ./bff/requirements.txt
RUN pip install --no-cache-dir -r bff/requirements.txt

COPY bff/ ./bff/
# The BFF serves frontend/dist relative to itself (app/../../frontend/dist).
COPY --from=frontend /build/dist/ ./frontend/dist/

ENV PORT=8080
WORKDIR /app/bff
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}

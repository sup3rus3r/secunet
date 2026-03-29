# SecuNet Agent Base Image — documentation only.
# Agents are NOT built from this image. Each agent uses python:3.12-slim
# and copies agents/base/ as a shared library layer.
#
# All offensive tool execution happens via cc_client.execute() which runs
# commands on the Command Center Kali container — agents are thin reasoners.
FROM python:3.12-slim

WORKDIR /agent/base

COPY agents/base/ /agent/base/

RUN pip install --no-cache-dir \
    httpx pydantic python-dotenv \
    anthropic "openai>=1.50.0" redis

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/agent:/agent/base

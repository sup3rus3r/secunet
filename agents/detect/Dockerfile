FROM python:3.12-slim

WORKDIR /agent

COPY agents/base/ /agent/base/
COPY agents/detect/ /agent/

RUN pip install --no-cache-dir \
    httpx \
    pydantic \
    python-dotenv \
    anthropic \
    "openai>=1.50.0" \
    redis \
    pyyaml

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/agent:/agent/base:/agent/siem

CMD ["python", "main.py"]

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev 2>/dev/null || \
    pip install --no-cache-dir fastapi[standard] motor bcrypt pydantic python-dotenv "python-jose[cryptography]" pycryptodome slowapi sqlalchemy uvicorn
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

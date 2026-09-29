FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY customer_service ./customer_service
COPY tests ./tests
COPY docs ./docs
USER 65532:65532
EXPOSE 8000
CMD ["python", "-m", "customer_service.server", "--host", "0.0.0.0", "--port", "8000"]

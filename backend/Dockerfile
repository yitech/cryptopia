FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sdk /sdk
RUN pip install --no-cache-dir /sdk && \
    python -m ipykernel install --sys-prefix

ENV JUPYTER_DATA_DIR=/usr/local/share/jupyter

COPY backend/. .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

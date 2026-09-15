FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --default-timeout=180 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY run.py ./run.py

EXPOSE 8200

CMD ["python", "run.py"]

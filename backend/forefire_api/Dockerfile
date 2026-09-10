FROM ubuntu:22.04 AS forefire-builder

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g; s|http://security.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    cmake \
    g++ \
    git \
    make \
    libboost-dev \
    libboost-program-options-dev \
    libnetcdf-dev \
    libnetcdf-c++4-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN git clone --depth 1 https://github.com/forefireAPI/firefront.git firefront || \
    git clone --depth 1 https://github.com/forefireAPI/forefire.git firefront

WORKDIR /opt/firefront

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --parallel && \
    candidate="$(find /opt/firefront/bin /opt/firefront/build -type f \( -name forefire -o -name ForeFire \) | head -n 1)" && \
    test -n "$candidate" && \
    cp "$candidate" /opt/forefire


FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g; s|http://security.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-pip \
    libnetcdf-dev \
    libnetcdf-c++4-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=forefire-builder /opt/forefire /usr/local/bin/forefire
COPY --from=forefire-builder /opt/firefront/lib/libforefireL.so /usr/local/lib/libforefireL.so
ENV LD_LIBRARY_PATH=/usr/local/lib
RUN chmod +x /usr/local/bin/forefire

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY app ./app

ENV ENVIRONMENT_DIR=/app/environment
ENV FOREFIRE_OUTPUT_DIR=/app/output
ENV FOREFIRE_CMD="forefire -i {case_file}"
EXPOSE 8080

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.13-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends cmake g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
EXPOSE 8000
ENV MEDVIEW_CORE_LIBRARY=/app/build/libmedview_core.so
CMD ["medview", "--host", "0.0.0.0", "--port", "8000", "--no-browser"]


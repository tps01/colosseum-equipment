FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libtk8.6 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace/colosseum-equipment
COPY colosseum-core /workspace/colosseum-core
COPY colosseum-equipment /workspace/colosseum-equipment
RUN python -m pip install --no-cache-dir /workspace/colosseum-core \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check
ENTRYPOINT ["python", "tests/fixtures/fuzz/run.py"]

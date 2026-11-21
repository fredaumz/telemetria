FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio==1.66.2 grpcio-tools==1.66.2
COPY *.proto ./
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. telemetry.proto mdt_dialout.proto
COPY sim.py ./
CMD ["python", "-u", "sim.py"]

ARG image="python:3.11.9-slim"

FROM ${image}

WORKDIR /app

COPY requirements.txt .

RUN \
    # Cache dependencies
    --mount=type=cache,target=/root/.cache/pip \
    # Install dependencies
    pip install -r requirements.txt --target dependencies \
    # Cleanup
    && rm requirements.txt

# Use SIGINT to gracefully shutdown python applications
STOPSIGNAL SIGINT

# Expand search path for Python
ENV PYTHONPATH="/app/dependencies"

COPY src/ service/

ENTRYPOINT ["python3", "-O", "-m", "service"]

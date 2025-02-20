#!/bin/sh
docker run --rm \
    -t \
    --security-opt seccomp=seccomp.json \
    --memory 32m \
    --cpus 0.1 \
    gcr.io/distroless/python3-debian12 \
    -c "print('Hello, World')"
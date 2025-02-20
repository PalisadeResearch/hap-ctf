#!/bin/sh
docker run --rm \
    -t \
    --security-opt seccomp=seccomp.json \
    --memory 32m \
    --cpus 1 \
    -v "$(pwd)/user_submission.py:/app/user_submission.py:ro" \
    --env-file .env \
    hap-ctf \
    user_submission.py
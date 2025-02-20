#!/bin/sh
systemd-run --user --scope \
  --property=CPUQuota=100% \
  -- \
  timeout 1s \
  prlimit --as=67108864 --data=67108864 --stack=8388608 \
  bwrap --ro-bind /usr /usr \
        --ro-bind /lib /lib \
        --ro-bind /lib64 /lib64 \
        --ro-bind /etc/ssl /etc/ssl \
        --ro-bind /etc/resolv.conf /etc/resolv.conf \
        --proc /proc \
        --dev /dev \
        --unshare-all \
        --share-net \
        --die-with-parent \
        --new-session \
        --ro-bind . /app \
        --seccomp 3 3<build/seccomp.bpf \
        python3 /app/user_submission.py
#!/bin/sh
bwrap --ro-bind /usr /usr \
      --ro-bind /lib /lib \
      --ro-bind /lib64 /lib64 \
      --proc /proc \
      --dev /dev \
      --unshare-all \
      --die-with-parent \
      --new-session \
      --ro-bind . /app \
      --seccomp 3 3<build/seccomp.bpf \
      python3 /app/user_submission.py
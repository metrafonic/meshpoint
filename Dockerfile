# syntax=docker/dockerfile:1
#
# Target: Raspberry Pi 4, 64-bit OS (linux/arm64).
# Build on the Pi itself or via `docker buildx` with --platform linux/arm64.
#
# The HAL build stage clones the Semtech SX1302 sources, applies the
# Meshpoint patches (TX sync word + temperature sensor tolerance), and
# compiles libloragw.so.  The runtime stage copies that library and
# installs the Python application.

# ── Stage 1: Build the Semtech SX1302 HAL ─────────────────────────────────────
FROM python:3.12-slim AS hal-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/Lora-net/sx1302_hal.git /opt/sx1302_hal

COPY scripts/patch_hal.py /tmp/patch_hal.py
RUN python3 /tmp/patch_hal.py \
        /opt/sx1302_hal/libloragw/src/loragw_sx1302.c \
        /opt/sx1302_hal/libloragw/src/loragw_hal.c

RUN set -eux; \
    cd /opt/sx1302_hal; \
    mkdir -p pic_obj; \
    for src in libtools/src/*.c; do \
        gcc -c -O2 -fPIC -Wall -Wextra -std=c99 \
            -Ilibtools/inc -Ilibtools \
            "$src" -o "pic_obj/$(basename "${src%.c}.o")"; \
    done; \
    for src in libloragw/src/*.c; do \
        gcc -c -O2 -fPIC -Wall -Wextra -std=c99 \
            -Ilibloragw/inc -Ilibloragw -Ilibtools/inc \
            "$src" -o "pic_obj/$(basename "${src%.c}.o")"; \
    done; \
    gcc -shared -o libloragw/libloragw.so pic_obj/*.o -lrt -lm -lpthread

# ── Stage 2: Runtime image ─────────────────────────────────────────────────────
FROM python:3.12-slim

# gpiod provides gpioset/gpioget for the concentrator reset script.
# build-essential is needed to compile C extensions in the Python packages
# (pycryptodome, bcrypt).  i2c-tools is useful for diagnostics.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gpiod \
        i2c-tools \
    && rm -rf /var/lib/apt/lists/*

COPY --from=hal-builder /opt/sx1302_hal/libloragw/libloragw.so /usr/local/lib/libloragw.so
RUN ldconfig

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyserial

COPY . .

RUN mkdir -p data && chmod +x docker-entrypoint.sh scripts/reset_concentrator.sh

EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]

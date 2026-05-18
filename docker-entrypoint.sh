#!/usr/bin/env sh
set -e

# Reset the SX1302 concentrator via GPIO before the HAL is opened.
# Skip gracefully if the SPI device isn't present (serial/USB-only setups).
if [ -e /dev/spidev0.0 ]; then
    scripts/reset_concentrator.sh 2>/dev/null \
        || echo "WARNING: concentrator reset failed — continuing anyway"
fi

exec python -m uvicorn src.api.server:create_app \
    --factory \
    --host 0.0.0.0 \
    --port "${MESHPOINT_PORT:-8080}"

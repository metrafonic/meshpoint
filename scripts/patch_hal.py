#!/usr/bin/env python3
"""Apply Meshpoint HAL patches to the Semtech SX1302 source tree.

Usage:
    python3 scripts/patch_hal.py <path/to/loragw_sx1302.c> <path/to/loragw_hal.c>

Idempotent — safe to run multiple times. Patches:
  loragw_sx1302.c  TX sync word: makes TX use the configured RX sync word
                   (e.g. 0x2B for Meshtastic) instead of the hardcoded
                   LoRaWAN values, so transmitted packets are heard by mesh nodes.
  loragw_hal.c     Temperature sensor: demotes missing I2C sensor from a fatal
                   error to a warning and falls back to 25 C.
"""

import sys
from pathlib import Path


def _rd(p):
    f = Path(p)
    if not f.is_file():
        print("FAIL: " + p)
        sys.exit(1)
    return f, f.read_text().replace("\r\n", "\n")


f1, s1 = _rd(sys.argv[1])
f2, s2 = _rd(sys.argv[2])

# ── loragw_sx1302.c patches ───────────────────────────────────────────────────

_A = """\
    int err = LGW_REG_SUCCESS;

    /* Multi-SF modem configuration */
    DEBUG_MSG("INFO: configuring LoRa (Multi-SF) SF5->SF6 with syncword PRIVATE (0x12)\\n");
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF5_PEAK1_POS_SF5, 2);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH1_SF5_PEAK2_POS_SF5, 4);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF6_PEAK1_POS_SF6, 2);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH1_SF6_PEAK2_POS_SF6, 4);
    if (public == true) {
        DEBUG_MSG("INFO: configuring LoRa (Multi-SF) SF7->SF12 with syncword PUBLIC (0x34)\\n");
        err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF7TO12_PEAK1_POS_SF7TO12, 6);
        err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH1_SF7TO12_PEAK2_POS_SF7TO12, 8);
    } else {
        DEBUG_MSG("INFO: configuring LoRa (Multi-SF) SF7->SF12 with syncword PRIVATE (0x12)\\n");
        err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF7TO12_PEAK1_POS_SF7TO12, 2);
        err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH1_SF7TO12_PEAK2_POS_SF7TO12, 4);
    }

    /* LoRa Service modem configuration */
    if ((public == false) || (lora_service_sf == DR_LORA_SF5) || (lora_service_sf == DR_LORA_SF6)) {
        DEBUG_PRINTF("INFO: configuring LoRa (Service) SF%u with syncword PRIVATE (0x12)\\n", lora_service_sf);
        err |= lgw_reg_w(SX1302_REG_RX_TOP_LORA_SERVICE_FSK_FRAME_SYNCH0_PEAK1_POS, 2);
        err |= lgw_reg_w(SX1302_REG_RX_TOP_LORA_SERVICE_FSK_FRAME_SYNCH1_PEAK2_POS, 4);
    } else {
        DEBUG_PRINTF("INFO: configuring LoRa (Service) SF%u with syncword PUBLIC (0x34)\\n", lora_service_sf);
        err |= lgw_reg_w(SX1302_REG_RX_TOP_LORA_SERVICE_FSK_FRAME_SYNCH0_PEAK1_POS, 6);
        err |= lgw_reg_w(SX1302_REG_RX_TOP_LORA_SERVICE_FSK_FRAME_SYNCH1_PEAK2_POS, 8);
    }

    return err;"""

_B = """\
    int err = LGW_REG_SUCCESS;

    uint8_t sw_reg1, sw_reg2;
    if (public == true) {
        sw_reg1 = 6;
        sw_reg2 = 8;
    } else if (lora_service_sf > 12) {
        sw_reg1 = ((lora_service_sf >> 4) & 0x0F) * 2;
        sw_reg2 = (lora_service_sf & 0x0F) * 2;
        DEBUG_PRINTF("INFO: sync cfg 0x%02X -> %u, %u\\n", lora_service_sf, sw_reg1, sw_reg2);
    } else {
        sw_reg1 = 2;
        sw_reg2 = 4;
    }

    sx1302_tx_sw_peak1 = sw_reg1;
    sx1302_tx_sw_peak2 = sw_reg2;

    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF5_PEAK1_POS_SF5, sw_reg1);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH1_SF5_PEAK2_POS_SF5, sw_reg2);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF6_PEAK1_POS_SF6, sw_reg1);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH1_SF6_PEAK2_POS_SF6, sw_reg2);

    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF7TO12_PEAK1_POS_SF7TO12, sw_reg1);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH1_SF7TO12_PEAK2_POS_SF7TO12, sw_reg2);

    err |= lgw_reg_w(SX1302_REG_RX_TOP_LORA_SERVICE_FSK_FRAME_SYNCH0_PEAK1_POS, sw_reg1);
    err |= lgw_reg_w(SX1302_REG_RX_TOP_LORA_SERVICE_FSK_FRAME_SYNCH1_PEAK2_POS, sw_reg2);

    return err;"""

if "sw_reg1" in s1:
    pass
elif _A in s1:
    s1 = s1.replace(_A, _B, 1)
else:
    print("FAIL: source mismatch in " + str(f1))
    sys.exit(1)

_TX_A = """\
    /* Syncword */
    if ((lwan_public == false) || (pkt_data->datarate == DR_LORA_SF5) || (pkt_data->datarate == DR_LORA_SF6)) {
        DEBUG_MSG("Setting LoRa syncword 0x12\\n");
        err = lgw_reg_w(SX1302_REG_TX_TOP_FRAME_SYNCH_0_PEAK1_POS(pkt_data->rf_chain), 2);
        CHECK_ERR(err);
        err = lgw_reg_w(SX1302_REG_TX_TOP_FRAME_SYNCH_1_PEAK2_POS(pkt_data->rf_chain), 4);
        CHECK_ERR(err);
    } else {
        DEBUG_MSG("Setting LoRa syncword 0x34\\n");
        err = lgw_reg_w(SX1302_REG_TX_TOP_FRAME_SYNCH_0_PEAK1_POS(pkt_data->rf_chain), 6);
        CHECK_ERR(err);
        err = lgw_reg_w(SX1302_REG_TX_TOP_FRAME_SYNCH_1_PEAK2_POS(pkt_data->rf_chain), 8);
        CHECK_ERR(err);
    }"""

_TX_B = """\
    /* Syncword */
    err = lgw_reg_w(SX1302_REG_TX_TOP_FRAME_SYNCH_0_PEAK1_POS(pkt_data->rf_chain), sx1302_tx_sw_peak1);
    CHECK_ERR(err);
    err = lgw_reg_w(SX1302_REG_TX_TOP_FRAME_SYNCH_1_PEAK2_POS(pkt_data->rf_chain), sx1302_tx_sw_peak2);
    CHECK_ERR(err);"""

if "static uint8_t sx1302_tx_sw_peak1" not in s1:
    s1 = s1.replace(
        "int sx1302_lora_syncword(",
        "static uint8_t sx1302_tx_sw_peak1 = 2;\n"
        "static uint8_t sx1302_tx_sw_peak2 = 4;\n\n"
        "int sx1302_lora_syncword(",
        1,
    )

if "sx1302_tx_sw_peak1 = sw_reg1" not in s1:
    s1 = s1.replace(
        "    sw_reg2 = 4;\n    }\n\n    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF5_PEAK1_POS_SF5",
        "    sw_reg2 = 4;\n    }\n\n"
        "    sx1302_tx_sw_peak1 = sw_reg1;\n"
        "    sx1302_tx_sw_peak2 = sw_reg2;\n\n"
        "    err |= lgw_reg_w(SX1302_REG_RX_TOP_FRAME_SYNCH0_SF5_PEAK1_POS_SF5",
        1,
    )

if _TX_A in s1:
    s1 = s1.replace(_TX_A, _TX_B, 1)

f1.write_text(s1, newline="\n")
print("OK: loragw_sx1302.c patched")

# ── loragw_hal.c patches ──────────────────────────────────────────────────────

_C = [
    (
        """\
        /* Find the temperature sensor on the known supported ports */
        for (i = 0; i < (int)(sizeof I2C_PORT_TEMP_SENSOR); i++) {
            ts_addr = I2C_PORT_TEMP_SENSOR[i];
            err = i2c_linuxdev_open(I2C_DEVICE, ts_addr, &ts_fd);
            if (err != LGW_I2C_SUCCESS) {
                printf("ERROR: failed to open I2C for temperature sensor on port 0x%02X\\n", ts_addr);
                return LGW_HAL_ERROR;
            }

            err = stts751_configure(ts_fd, ts_addr);
            if (err != LGW_I2C_SUCCESS) {
                printf("INFO: no temperature sensor found on port 0x%02X\\n", ts_addr);
                i2c_linuxdev_close(ts_fd);
                ts_fd = -1;
            } else {
                printf("INFO: found temperature sensor on port 0x%02X\\n", ts_addr);
                break;
            }
        }
        if (i == sizeof I2C_PORT_TEMP_SENSOR) {
            printf("ERROR: no temperature sensor found.\\n");
            return LGW_HAL_ERROR;
        }""",
        """\
        /* Find the temperature sensor on the known supported ports */
        for (i = 0; i < (int)(sizeof I2C_PORT_TEMP_SENSOR); i++) {
            ts_addr = I2C_PORT_TEMP_SENSOR[i];
            err = i2c_linuxdev_open(I2C_DEVICE, ts_addr, &ts_fd);
            if (err != LGW_I2C_SUCCESS) {
                printf("WARNING: could not open I2C on port 0x%02X\\n", ts_addr);
                ts_fd = -1;
                continue;
            }

            err = stts751_configure(ts_fd, ts_addr);
            if (err != LGW_I2C_SUCCESS) {
                printf("INFO: no temperature sensor found on port 0x%02X\\n", ts_addr);
                i2c_linuxdev_close(ts_fd);
                ts_fd = -1;
            } else {
                printf("INFO: found temperature sensor on port 0x%02X\\n", ts_addr);
                break;
            }
        }
        if (ts_fd < 0) {
            printf("WARNING: sensor not available, using default\\n");
        }""",
    ),
    (
        """\
        case LGW_COM_SPI:
            err = stts751_get_temperature(ts_fd, ts_addr, temperature);
            break;""",
        """\
        case LGW_COM_SPI:
            if (ts_fd > 0) {
                err = stts751_get_temperature(ts_fd, ts_addr, temperature);
            } else {
                *temperature = 25.0;
                err = LGW_HAL_SUCCESS;
            }
            break;""",
    ),
    (
        """\
        DEBUG_MSG("INFO: Closing I2C for temperature sensor\\n");
        x = i2c_linuxdev_close(ts_fd);
        if (x != 0) {
            printf("ERROR: failed to close I2C temperature sensor device (err=%i)\\n", x);
            err = LGW_HAL_ERROR;
        }""",
        """\
        if (ts_fd > 0) {
            DEBUG_MSG("INFO: Closing I2C for temperature sensor\\n");
            x = i2c_linuxdev_close(ts_fd);
            if (x != 0) {
                printf("ERROR: failed to close I2C temperature sensor device (err=%i)\\n", x);
                err = LGW_HAL_ERROR;
            }
        }""",
    ),
]

ok = True
for o, n in _C:
    if n in s2:
        continue
    if o not in s2:
        ok = False
        break
    s2 = s2.replace(o, n, 1)

if ok:
    f2.write_text(s2, newline="\n")
    print("OK: loragw_hal.c patched")
else:
    print("FAIL: source mismatch in " + str(f2))
    sys.exit(1)

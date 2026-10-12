#!/usr/bin/env python3
"""Inspect the three extracted SPI, I2C, and UART calibration captures."""

import bisect
import csv
import struct
import zlib
from pathlib import Path


DATA = Path(__file__).resolve().parent / "extracted"


def dewhiten(data: bytes, page_index: int) -> bytes:
    state = (0x9E3779B9 ^ page_index) & 0xFFFFFFFF
    result = bytearray()
    for byte in data:
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        result.append(byte ^ (state & 0xFF))
    return bytes(result)


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def inspect_spi() -> None:
    raw = (DATA / "controller-spi.raw").read_bytes()
    if len(raw) != 4096 * 272:
        raise ValueError("unexpected SPI dump size")

    print("SPI: committed, CRC-valid records for board revision 0x53190002")
    for index in range(4096):
        page = raw[index * 272:(index + 1) * 272]
        decoded = dewhiten(page[:256], index)
        spare = page[256:]
        magic, kind, flags, generation, length, revision, crc = struct.unpack(
            "<2sBBHHII", spare
        )
        valid = zlib.crc32(spare[:12] + decoded) & 0xFFFFFFFF == crc
        if valid and flags & 1 and revision == 0x53190002 and kind in (0x31, 0x32):
            print(f"  page={index:4} gen={generation:04x} kind={kind:02x} "
                  f"data={decoded[:length].hex()}")


def inspect_i2c() -> None:
    with (DATA / "capture-01.csv").open(newline="") as stream:
        rows = [tuple(map(int, (row["time_ns"], row["scl"], row["sda"])))
                for row in csv.DictReader(stream)]

    print("I2C: transactions (a '+' suffix means ACK)")
    active = False
    bits: list[int] = []
    received: list[tuple[int, int]] = []
    for previous, current in zip(rows, rows[1:]):
        _, old_scl, old_sda = previous
        _, scl, sda = current
        if scl == 1 and old_sda == 1 and sda == 0:  # START / repeated START
            if received:
                print("  " + " ".join(f"{value:02x}{'+' if ack == 0 else '-'}"
                                      for value, ack in received))
            active, bits, received = True, [], []
        elif scl == 1 and old_sda == 0 and sda == 1:  # STOP
            if received:
                print("  " + " ".join(f"{value:02x}{'+' if ack == 0 else '-'}"
                                      for value, ack in received))
            active, bits, received = False, [], []
        elif active and old_scl == 0 and scl == 1:
            bits.append(sda)
            if len(bits) == 9:
                value = sum(bits[i] << (7 - i) for i in range(8))
                received.append((value, bits[8]))
                bits = []


def inspect_uart() -> None:
    with (DATA / "capture-02.csv").open(newline="") as stream:
        rows = [(int(row["time_ns"]), int(row["ch0"]))
                for row in csv.DictReader(stream)]
    times = [time for time, _ in rows]

    def level(time: float) -> int:
        index = max(0, bisect.bisect_right(times, time) - 1)
        return 1 - rows[index][1]  # transistor inverts channel 0

    bit_time = 1_000_000_000 / 57_600
    decoded = bytearray()
    skip_until = 0.0
    for time in sorted(set(times)):
        if time < skip_until or level(time - 0.1) != 1 or level(time + 0.1) != 0:
            continue
        bits = [level(time + (1.5 + i) * bit_time) for i in range(8)]
        if level(time + 9.5 * bit_time) == 1:
            decoded.append(sum(bit << i for i, bit in enumerate(bits)))
            skip_until = time + 9.7 * bit_time

    print("UART: inverted channel 0, 57600 8N1")
    for offset in range(0, len(decoded), 39):
        packet = decoded[offset:offset + 39]
        if len(packet) != 39 or packet[:2] != b"\x55\xaa" or packet[4] != 32:
            print(f"  unparsed bytes: {packet.hex()}")
            continue
        revision = int.from_bytes(packet[2:4], "little")
        valid = crc16_modbus(packet[:-2]) == int.from_bytes(packet[-2:], "little")
        print(f"  rev={revision} crc={'valid' if valid else 'INVALID'} "
              f"component={packet[5:37].hex()}")


if __name__ == "__main__":
    inspect_spi()
    inspect_i2c()
    inspect_uart()

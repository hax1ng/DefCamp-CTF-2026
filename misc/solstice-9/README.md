# solstice-9

## Challenge

- **Category:** Misc / hardware forensics

- **Goal:** Retrieve the service receipt from an undocumented maintenance backdoor.
- **Flag format:** `DCTF{sha256}`

We are given a roughly 4 GB Raspberry Pi firmware image and access to a TCP service that behaves like an industrial RTU controller.

The short version is that the disk contains three old hardware captures. Those captures let us reconstruct a 96-byte factory calibration fixture. A diagnostic program turns that fixture into an Ed25519 private key. We can then use that key to authenticate to a hidden Modbus-like maintenance command and ask the live service for its receipt.

That sounds like a lot, but each part leaves fairly friendly documentation behind.

---

## 1. Initial analysis: looking through the firmware image

First, I checked the image layout:

```console
$ file solstice9-firmware.img
solstice9-firmware.img: DOS/MBR boot sector ...

$ fdisk -l solstice9-firmware.img
Device                       Start     End Sectors  Size Id Type
solstice9-firmware.img1       8192 1056767 1048576  512M  c W95 FAT32
solstice9-firmware.img2    1056768 8241151 7184384  3.4G 83 Linux
```

Partition 2 is an ext4 root filesystem beginning at sector `1056768`. I did not need to mount it; Sleuth Kit can list and extract files directly:

```bash
fls -r -p -o 1056768 solstice9-firmware.img > fs_listing.txt
grep -Ei 'solstice|powerd|board|capture|bench|archive' fs_listing.txt
```

The interesting additions were:

```text
/usr/sbin/powerd
/usr/libexec/boarddiag
/usr/share/board/storage.txt
/usr/share/board/fixture.txt
/var/lib/powerd/archive/controller-spi.raw
/var/lib/powerd/archive/capture-01.csv
/var/lib/powerd/archive/capture-02.csv
/var/lib/powerd/archive/bench.txt
```

`/usr/share/doc/solstice9/base-image.txt` even confirms that these are the challenge-specific files.

With the inode numbers shown by `fls`, a file can be extracted using `icat`. For example:

```bash
icat -o 1056768 solstice9-firmware.img 48820 > powerd
icat -o 1056768 solstice9-firmware.img 48821 > boarddiag
```

I did the same for the notes and three captures.

---

## 2. What the notes tell us

The bench note identifies the board as marking `5319`, revision `0002`, and describes the captures:

* `controller-spi.raw` is a flash dump;
* `capture-01.csv` is an I2C capture of an eight-pin EEPROM;
* `capture-02.csv` is a UART capture from a supervisor header;
* a transistor in the UART path inverts the signal.

`fixture.txt` says the final calibration fixture is 96 bytes in this order:

1. 32 bytes from the controller journal;
2. 32 bytes from the EEPROM;
3. 32 bytes from the supervisor.

It also says that `boarddiag` converts that fixture into the controller's public identity.

So the immediate job is to recover one 32-byte component from each capture.

---

## 3. Recovering the controller journal

`storage.txt` documents the flash format almost completely:

* 4096 pages;
* 256 data bytes and 16 spare bytes per page;
* data is whitened independently on each page with a xorshift32 stream;
* the spare area contains the record type, flags, generation, length, board revision, and CRC32;
* record kinds `0x31` and `0x32` form the two 16-byte halves of the controller component;
* flag bit 0 means that a record is committed;
* the two halves need matching board revision and generation;
* generations are wrapping 16-bit counters.

The spare structure is:

```text
magic[2], kind:u8, flags:u8, generation:u16,
length:u16, board_revision:u32, crc32:u32
```

The important part of my parser was:

```python
import struct
import zlib

def dewhiten(data, page_index):
    x = (0x9e3779b9 ^ page_index) & 0xffffffff
    out = bytearray()
    for b in data:
        x ^= (x << 13) & 0xffffffff
        x ^= x >> 17
        x ^= (x << 5) & 0xffffffff
        x &= 0xffffffff
        out.append(b ^ (x & 0xff))
    return bytes(out)

raw = open("controller-spi.raw", "rb").read()

for page_index in range(4096):
    page = raw[page_index * 272:(page_index + 1) * 272]
    data = dewhiten(page[:256], page_index)
    spare = page[256:]

    magic, kind, flags, generation, length, revision, saved_crc = \
        struct.unpack("<2sBBHHII", spare)
    calculated_crc = zlib.crc32(spare[:12] + data) & 0xffffffff

    if calculated_crc == saved_crc:
        print(page_index, magic, kind, flags, generation,
              length, hex(revision), data[:length].hex())
```

There are several valid old records, including generations near the `0xffff -> 0x0000` wrap. Generation `0x0004` is newer-looking but uncommitted, so it must be ignored. The newest complete, committed pair is generation `0x0002`.

For board revision `0x53190002`, its two halves are:

```text
kind 0x31: f07fb429318b400792c47765179ff564
kind 0x32: 02ad956f22989e77868b65099f095d66
```

Therefore the controller component is:

```text
f07fb429318b400792c47765179ff56402ad956f22989e77868b65099f095d66
```

---

## 4. Decoding the I2C EEPROM capture

`capture-01.csv` has three columns:

```text
time_ns,scl,sda
```

This is ordinary I2C. The useful rules are:

* SDA falling while SCL is high is a START;
* SDA rising while SCL is high is a STOP;
* sample SDA on each rising edge of SCL;
* every byte has eight data bits followed by one ACK bit.

Decoding the capture shows reads from device address `0x50`. The firmware first writes an EEPROM offset and then uses a repeated START to read from it. The note says revision 2 calibration starts at offset `0x40` and is 32 bytes long.

The capture reads the first half at `0x40` and the second half at `0x50`:

```text
offset 0x40: 3f ef c0 49 a8 9a 61 2a 35 42 d3 0e cc 39 52 c4
offset 0x50: b4 17 1f e1 4e 33 a9 8c 0d ba d4 23 01 52 95 30
```

So the EEPROM component is:

```text
3fefc049a89a612a3542d30ecc3952c4b4171fe14e33a98c0dbad42301529530
```

---

## 5. Decoding the supervisor UART capture

`capture-02.csv` contains two digital channels and timestamps in nanoseconds. Looking at the transition spacing gives a UART bit time of about `17.361 us`, or **57600 baud**.

The transistor mentioned in the note is the small trap here: the useful serial signal is inverted. Treating channel 0 as inverted UART with 8 data bits, no parity, and one stop bit produces clean packets.

The packet format from `fixture.txt` is:

```text
55 aa | revision LE16 | length U8 | component | CRC16/Modbus LE16
```

The decoded stream contains three 39-byte packets:

```text
55aa010020 34679a886887d3dd5628a9a006a76555e879a4667afc158bfbe282800f8850ab 8e9a
55aa020020 6c8737ba4c7a107a4c01f44dc0f42df58a36735d3aca1bcaba67191ffea05225 6ccc
55aa020020 0a835185173ff000ba3f1959f11cbba0566876b183911918ea8cfabe43d865c0 19da
```

The first packet is valid, but belongs to revision 1. The second packet is for revision 2 and has a valid Modbus CRC. The last packet may look newer because it was seen last, but its CRC is invalid. That agrees with the warning in the note: use a **valid** packet for the board revision, not merely the final packet.

The supervisor component is therefore:

```text
6c8737ba4c7a107a4c01f44dc0f42df58a36735d3aca1bcaba67191ffea05225
```

---

## 6. Rebuilding the 96-byte fixture

Concatenating the components in the documented order gives:

```text
f07fb429318b400792c47765179ff56402ad956f22989e77868b65099f095d66
3fefc049a89a612a3542d30ecc3952c4b4171fe14e33a98c0dbad42301529530
6c8737ba4c7a107a4c01f44dc0f42df58a36735d3aca1bcaba67191ffea05225
```

That is exactly 96 bytes.

`boarddiag` is a small stripped AArch64 binary. Reversing its main loop shows that it routes bytes from the three 32-byte lanes and produces a 32-byte Ed25519 private seed. In Python, its transformation is:

```python
fixture = controller + eeprom + supervisor
seed = bytearray(32)

for i in range(32):
    rotation = i & 7
    middle = fixture[32 + i]
    rotated = ((middle << rotation) |
               (middle >> ((-rotation) & 7))) & 0xff

    seed[i] = (
        fixture[(7 + 13 * i) & 31] ^
        fixture[95 - i] ^
        rotated
    )
```

The 32-byte seed is derived by [`reconstruct.py`](reconstruct.py) and kept as a local generated file, not committed.

Its Ed25519 public key is:

```text
8bc22f9dad276d4302d75f5bf0dc6ab30a50ff102d9d7b96de69fec36048ed4c
```

This is an important sanity check: that exact public key is embedded in `powerd`. It proves that all three captures were decoded correctly.

---

## 7. Finding the undocumented maintenance commands

Connecting to the service only advertises normal FC03 telemetry:

```text
Solstice 9 RTU bridge / HELP for transport
XFER <hex RTU frame>; CRC16/Modbus low byte first; unit 17 hex; FC03 telemetry
```

The wire format is simple: send the ASCII word `XFER`, followed by a hex-encoded RTU frame. The binary frame itself ends with a little-endian Modbus CRC16.

Reversing `powerd` reveals two commands that HELP does not mention:

* function `0x41` starts maintenance authentication and returns a random 32-byte challenge;
* function `0x42` accepts a 64-byte Ed25519 signature and returns the service receipt.

The challenge request PDU is:

```text
17 41 53 39 00 02
```

Here `0x17` is the RTU unit, `0x41` is the hidden function, and the remaining bytes are its board/revision magic. After adding the Modbus CRC, the complete request is:

```text
1741533900027fbb
```

The successful response has this form:

```text
17 41 20 <32-byte nonce> <CRC16>
```

To answer it, sign the following 56 bytes with the recovered Ed25519 private seed:

```text
"SOLSTICE9/maintenance/v1" || nonce
```

The signature goes into an FC42 frame:

```text
17 42 <64-byte Ed25519 signature> <CRC16>
```

The challenge is time-limited, so both requests should be sent over the same connection without waiting around.

---

## 8. Final solver

Use the accompanying [`reconstruct.py`](reconstruct.py) to derive `seed.bin` from the documented capture components, then run [`solve.py`](solve.py) against a team-confirmed instance:

```bash
python3 reconstruct.py
python3 solve.py <team-host> <team-port>
```

The live endpoint used during the event is intentionally not published. The script requires a host and port explicitly; it never probes for instances.

The service returns:

```text
DCTF{c7da32e39bd5727769742639fb9855971cb88cb952573182913b9155d7b1b286}
```

---

## Flag

`DCTF{c7da32e39bd5727769742639fb9855971cb88cb952573182913b9155d7b1b286}`


## Included files and key takeaways

`extracted/` contains the small files recovered from the firmware image: controller and diagnostic executables, documentation, and three hardware captures. The multi-gigabyte source image and generated filesystem listing are omitted. `decode.py` inspects the captures; `reconstruct.py` derives the fixture and key locally; `solve.py` implements the authenticated RTU exchange. The challenge rewards verifying integrity metadata (CRC, commit state, revision), correctly handling generation wraparound and inverted UART, and recognizing undocumented maintenance functions in firmware.

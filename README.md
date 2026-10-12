# DefCamp Capture the Flag 2026 Qualifiers

Selected solutions from the **DCTF26 Qualifiers**, held September 18–20, 2026.

- **Repository:** [31337hax0r (@hax1ng)](https://github.com/hax1ng)
- **Documented solves:** 3

| Category | Challenge | Core idea |
|---|---|---|
| Misc | [Flag of Clairvoyance](misc/flag-of-clairvoyance/README.md) | Capture canvas draw calls before a wall hides the text |
| Misc | [Flag of Yore](misc/flag-of-yore/README.md) | Recover a forgotten development asset from an old release |
| Misc | [solstice-9](misc/solstice-9/README.md) | Reconstruct hardware calibration data and authenticate to a hidden RTU command |

The first two solves explore different weaknesses in a browser-based pirate game: client-side rendering reveals supposedly hidden text, while a production screenshot discloses the identifier of an older release. The third reconstructs a controller identity from SPI, I²C, and UART captures recovered from a firmware image.

Only challenges with documented `DCTF{...}` flags are included. Large source images, transient logs, team-instance addresses, generated keys, and unrelated experiments are intentionally omitted. Each challenge directory contains its writeup and the small scripts or evidence needed to follow the solve. Run any network-facing script **only** against an instance assigned to your team.

Python helpers use the standard library plus `Pillow` and `cryptography`; install the optional dependencies with `python3 -m pip install -r requirements.txt`.

# Brother QL-1100 native macOS driver

An independent **ARM64 CUPS driver** for Brother QL-1100/QL-1100c label printers connected by USB. It uses macOS's existing PDF rasterizer, CUPS library and USB backend. The filter runs natively on Apple Silicon, without Rosetta, Homebrew libraries, Python at print time, or Brother's Intel driver.

This project is not affiliated with or supported by Brother. Source and locally built packages are unsigned and not notarized. Build from source you trust; this project does not require disabling SIP or Gatekeeper.

## Support and test status

Version **0.2.0** covers the Intel driver's **67 named media choices**: 17 die-cut formats (including three round labels), eight continuous roll widths, 24 banners printed as two to four strips, and 18 convenience presets. Two old native size names remain for compatibility. Custom lengths are available for recognized continuous-roll and banner widths. See [the full media table and discrepancies](docs/MEDIA.md).

- **Hardware tested by the owner:** QL-1100c, 103 × 164 mm stock; calibration, ordinary application printing, two copies and automatic cutting reported passing on the original 0.1.0 build. The 0.2.0 default geometry is retained and regression-tested; recheck one label after upgrading.
- **Other formats/new controls:** offline protocol and Apple PDF conversion tests, not physical certification of every roll. Banner strips must be assembled by the user. Round media use a square bounding box; keep artwork within the actual label shape, including any hole.
- **Platform:** Apple Silicon only. The build has an explicit macOS 11.0 deployment target; development and execution were tested on macOS 27.2.1 with SDK 27.2. A lower deployment target does not establish older-system compatibility. Future macOS 28 CUPS/PPD availability is unverified.
- **Raster input:** uncompressed CUPS v1/v3, 300 dpi, single-channel 1/8-bit grayscale. Compressed v2, PWG and URF are rejected. The tested Apple PDF rasterizer supplies supported v3 input.

## Build and install

Install Apple's Xcode Command Line Tools if you do not already have them (`xcode-select --install`). Then:

```sh
git clone https://github.com/yuxhuang/brother-ql1100-macos.git
cd brother-ql1100-macos
make
make test PYTHON=python3
bash scripts/package.sh
bash scripts/install.sh
```

The tests use Python 3's standard library and system libcups; no Python package installation is required. If Python is elsewhere, set `PYTHON` to its path. Compiling and testing do not print or install anything. `install.sh` requests administrator authentication and installs the locally built `build/QL1100Native-0.2.0.pkg`.

**Existing 0.1.0 installation:** run that version's `scripts/uninstall.sh` from your original checkout first. For a 0.2.x replacement, finish/cancel native jobs and run this checkout's uninstaller first. This release deliberately refuses existing driver destinations rather than overwriting an active installation.

## Add the printer

Connect and power on one QL-1100/QL-1100c by USB, then:

```sh
bash scripts/add-queue.sh
```

This discovers the connected USB device and creates **QL1100_Native**. It does not require the official Brother driver, does not change your default printer and prints nothing. If several matching printers are connected, it refuses to choose one. You can instead pass an existing queue name or an exact matching USB URI from `lpinfo -v`:

```sh
bash scripts/add-queue.sh Brother_QL_1100
```

Keep any existing queue for rollback, but avoid concurrent jobs through two queues sharing the same physical printer. In application print dialogs, select **Brother QL-1100 Native ARM64** and the matching loaded media.

## First label

With **103 × 164 mm die-cut stock** loaded:

```sh
lp -d QL1100_Native -n 1 -o PageSize=DC103_164 \
  -o AutoCut=True examples/calibration-103x164.pdf
```

Check orientation, all four borders, the 50 mm ruler, barcode scan and cut. Then test your normal label application at actual size. Do not use this calibration PDF on another stock without choosing a suitable page layout.

Options include `AutoCut=True/False`, `CutEvery=1..255`, `CutAtEnd=True/False`, `PrintQuality=Speed/Quality`, and `Collate=True/False`. Quality priority is a printer-mode choice at **300 dpi**, not 600 dpi. AutoCut=False disables automatic cut modes. See [implementation details](docs/IMPLEMENTATION.md) for defaults and limits.

For continuous custom sizes, use the exact width and units described in [MEDIA.md](docs/MEDIA.md); arbitrary physical roll widths are rejected. Names containing x2/x3/x4 are composite artwork split into separate strips, not wider physical rolls.

## Troubleshooting and removal

```sh
lpstat -p QL1100_Native -l
lpstat -o QL1100_Native
```

Cancel a failed job using its exact ID, e.g. `cancel QL1100_Native-123`. Avoid repeatedly resubmitting a stopped job. The filter confirms transfer to the CUPS backend; it cannot confirm the loaded roll or physical print completion. It has no printer-status backchannel.

Finish/cancel native jobs and stop submitting new ones during removal:

```sh
sudo bash scripts/uninstall.sh
```

This removes the native queue and only these driver files/receipt, refusing uncertain CUPS state or other queues using the filter:

- `/Library/Printers/QL1100Native/rastertoql1100`
- `/Library/Printers/PPDs/Contents/Resources/Brother-QL1100-Native.ppd.gz`
- Receipt: `io.github.yuxhuang.brother-ql1100`

Other queues and drivers are preserved.

## Development and provenance

The C filter and PPD generator are authored here under the [GNU General Public License version 3 only (GPL-3.0-only)](LICENSE). Media identifiers and dimensions were compared with the user's official Intel driver 4.0.7 and Brother's public [raster command reference](https://download.brother.com/welcome/docp100366/cv_ql1100_eng_raster_100.pdf). No proprietary Brother binaries, original PPD, lookup tables, icons or private UI plug-ins are distributed. See [IMPLEMENTATION.md](docs/IMPLEMENTATION.md), [MEDIA.md](docs/MEDIA.md), and [VALIDATION.md](docs/VALIDATION.md).

Reports should include macOS version, printer model, label size/option, command used and non-sensitive error output. Do not upload shipping addresses, printer serial numbers or credentials. Physical reports for additional media are welcome.

## License

Copyright (c) 2026 yuxhuang and contributors. This project is licensed under GPL-3.0-only; see [LICENSE](LICENSE) for the full terms.

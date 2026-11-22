# Validation and limitations

## Hardware evidence

The owner reports successful calibration, application printing and two-copy/cutting checks on a QL-1100c with 103 × 164 mm stock using the 0.1.0 prototype. The 0.2.0 default media geometry is unchanged; recheck a calibration label after replacing the driver. No claim is made that every added stock, banner mode or control has been physically tested.

The driver is compiled for ARM64 and dynamically links only macOS system libcups and libSystem. Development system: macOS 27.2.1, SDK 27.2. The explicit deployment target is 11.0; earlier-system execution has not been tested. macOS 28 compatibility is unknown because the implementation depends on legacy CUPS/PPD integration.

## Evidence from the official driver

The official 4.0.7 PPD exposes 67 PageSize choices, and its printer resource has 49 underlying media entries. Integer geometry and protocol facts were extracted and compared with Brother's public manual; discrepancies and normalizations are recorded in MEDIA.md. These facts informed newly authored source. Vendor files themselves are excluded from this repository.

An offline reference run of the Intel filter with DC16 selected in its PPD emitted type 11, width 102, **length 153**, and 1660 raster rows. This resolved the disagreement with the public manual's length 152 entry. No printer was connected to the reference filter's output; stdout was captured as a file.

Separate all-black round-label reference runs emitted square raster content on DC05 and DC12, including the CD-label center. The native implementation therefore does not infer circular or center-hole clipping from the private PPD's mask metadata. Use artwork appropriate to the actual label shape. Private UI behavior was not reproduced.

## Offline acceptance

The test suite includes an independent raster fixture generator and Brother command decoder. It checks the original job validation cases plus every named media choice, aliases, custom lengths, pin placement, full/printable crop equivalence, banner strip ordering and copies, physical impression bounds, feed and cut/quality commands, unsupported input and malformed jobs. Apple cupsfilter converts generated PDFs through the authored PPD for each unique geometry. Release-script tests use temporary files and mocked administrative commands and do not install printers or drivers.

Final 0.2.0 validation on 2026-11-22: **55 tests passed** in the lead's final run (40.729 seconds). The independent test engineer's run also passed all 55 (29.178 seconds); AddressSanitizer and UndefinedBehaviorSanitizer passed all 55 (39.640 seconds), without sanitizer findings. LeakSanitizer is unsupported on this macOS and was disabled; this is not a leak-check result. No test was skipped. Tests are reproducible with `make test PYTHON=python3`.

The suite exercises 53 distinct named-media PDF geometries and both custom-length endpoints through Apple's actual rasterizer. An additional three-page Intel reference job with cut interval two emitted that interval command on all three pages, supporting the native filter's repeated per-page command placement. This does not establish physical cutter behavior.

Independent code, security, release and factual reviews passed with the documented operational limits. Review/tests found and fixed uncollated banner copy ordering and payload-directory permissions inherited from the build shell. Staging under both permissive `umask 000` and restrictive `umask 077` now yields directories/filter 0755 and PPD 0644.

The final unsigned package was expanded: filter, decompressed PPD and preinstall bytes matched their inputs; BOM ownership was root (0/0), directories/filter 0755, PPD 0644. The filter's ad-hoc signature verified. Local package SHA256: `26140b565f3943079ecfe0beb700f628319fcb51c684db472b8855858fc2d0a2`. Rebuilding packages may produce a different archive hash; no prebuilt package is committed to this source repository.

## Operational limits

- Physical printer errors, wrong-roll handling, no-cut behavior, all new controls and arbitrary banner assembly need further device testing.
- The filter has no status backchannel. Successful byte transfer is not proof that a label physically printed.
- Continuous margins are normalized as documented in MEDIA.md; this is not a pixel-for-pixel clone of every vendor setting.
- Brightness/contrast LUTs, vendor halftoning, private print-dialog extensions, automatic trailing-blank trimming, status utility and disabled 600 dpi mode are not implemented.
- All input is validated/spooled before any printer bytes. Already-transferred bytes cannot be recalled after cancellation.
- First-install-only packaging requires removal before replacement. Do not submit new jobs during removal.
- Packages are unsigned local builds. Source availability and a checksum do not provide publisher authentication.

## GPL licensing revision

The public repository was recreated under GPL-3.0-only. This revision changes license text, notices and documentation only; no filter behavior was changed. The generator consistency check and native build passed again, and the local package was rebuilt with the GPL notices.

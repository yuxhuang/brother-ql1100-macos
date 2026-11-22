# Changelog

## 0.2.0

- Public source distribution is licensed under GPL-3.0-only.

- Reproduces all 67 media names exposed by the official 4.0.7 PPD, with factual dimensions and independently authored configuration.
- Adds continuous custom lengths and two-, three- and four-strip banner output; preserves the original two native size aliases.
- Adds cut-every-N, cut-at-end and 300 dpi speed/quality-priority controls.
- Corrects 102 × 152 wire length to 153, confirmed by offline execution of the official filter; the marketed size name stays unchanged.
- Adds standalone USB discovery so the official driver is not a setup dependency.
- Uses a public project package identifier, source-only distribution, and an explicit deployment target.
- Retains bounded whole-job validation, compressed-input rejection and cancellation handling. New formats and controls have offline coverage; broad hardware validation remains open.

## 0.1.0 (local prototype)

- Initial native ARM64 filter for 103 × 164 and 102 × 152 die-cut labels.
- Owner confirmed physical printing, calibration and two-copy checks with 103 × 164 stock.

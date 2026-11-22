# Media coverage

The authored catalog in `src/media.json` is the source of truth for 67 named Intel-driver media choices, plus the backward-compatible `w103h164` and `w102h152` names. Run `make generate` after editing it; `make check-generated` verifies that the C table and PPD match. The catalog contains 17 die-cut sizes (including three circular labels), eight continuous widths, 24 two-, three- and four-strip banners, and 18 descriptive aliases, including binder spines and postage sizes. These are format compatibility facts, not a claim of complete vendor-driver feature parity.

Dimensions are printer dots at 300 dpi. Advertised millimeters often differ from the actual sheet dimensions; use the PPD's dimensions rather than converting the marketed name. `width` and `height` describe the logical full sheet, `printable_width` describes one physical strip, `printable_height` describes the transmitted rows, `x`/`y` describe the full-sheet crop, `right` locates the strip on the 1296-pin print head, and `strips` is 1 through 4. `code` and `length` are the media-identification bytes.

The numeric dimensions and names were compared against the installed Intel driver's PPD and media XML during development. Neither proprietary file is distributed. Printer geometry, pin alignment and wire commands were checked against Brother's [Raster Command Reference 1.00](https://download.brother.com/welcome/docp100366/cv_ql1100_eng_raster_100.pdf), printed pages 13–20 and 23–29. Where the XML differs from the manual, 54 mm tape uses a 638-dot sheet and 24-dot left crop (manual: 636/23), and the 60 x 86 mm label uses a 1027-dot sheet and 957 printable rows (manual: 1024/954). These retain the Intel driver's layout. The 102 x 152 mm label uses media-length byte 153, confirmed by capturing the Intel filter's stdout offline. This corrects version 0.1's manual-based byte 152, including for the `w102h152` alias. The 103 x 164 mm geometry remains 1224 x 1941 dots, with a 1200 x 1822 printable rectangle at 12,59.

Continuous media deliberately uses consistent 35-dot leading/trailing feed margins. At the default 1181-dot sheet length it transmits 1111 raster rows. This normalizes the inconsistent Intel PPD's vertical imageable rectangles, particularly for 103 mm tape. Die-cut labels have zero commanded feed; their catalog crop determines the raster rows. Circular labels accept the documented square printable bounding box without a software circular mask; artwork must fit the physical label shape.

Banners divide the logical printable width into two, three or four equal strips, from left to right. Their sheet width is `strips * printable_width + left border + right border`. No scale, overlap or seam marks are added. Each strip is a physical impression and is cut separately with the default `AutoCut=True, CutEvery=1`; larger cut intervals group physical strips. Collated copies repeat the complete strip sequence; uncollated copies repeat the logical page's complete strip sequence before advancing to the next logical page. Physical strips count toward the 1000-impression limit.

Custom sizes use CUPS `Custom.<width>x<height>` in points, with optional `mm` or `in` suffixes applying to both dimensions. Only a width matching a catalog continuous or virtual-banner sheet width is accepted (within 1.01 printer dots). The length must be 25.4–3000 mm and is rounded upward to printer dots, clamped to the protocol's 301–35434-dot physical-length range. If the rasterizer supplies one fewer row because it rounded the nominal length down, the filter appends one white printable row; its input boundary accounting still uses the actual input bytes. For example, `Custom.175.68x288` uses the 732-dot-wide 62 mm roll and a 1200-dot length. The broad custom-size controls in a PPD cannot express discrete supported widths, so the filter rejects other widths before sending printer output. A nominal `103mm` width is not the actual 1224-dot sheet width; use 293.76 points for that roll.

Both full-sheet raster input and exact printable-area raster input are supported. The PPD's custom imageable area is the full sheet, and the filter crops it to the supported roll's printable width and 35-dot end margins. For named media, the PPD supplies the catalog's imageable rectangle. A job can select aliases interchangeably when their dimensions and wire identity agree.

The expanded formats are covered by offline raster/protocol and PPD integration tests. No expanded format or banner is claimed to have been physically printed; hardware validation remains necessary for alignment, media sensing and cutter behavior on each stock.

The PPD also exposes automatic cutting, selected cut intervals, cutting at job end and speed/quality priority. `CutEvery` accepts any integer 1–255 in CUPS options; the PPD offers common intervals. `CutAtEnd` defaults true and is effective only with `AutoCut=True`. `PrintQuality=Speed` is the default; `Quality` sets the printer protocol's quality-priority flag. These commands are covered by offline byte-stream tests, with physical speed and cutter behavior still unverified.

## Named media choices

| CUPS name | Print-dialog label | Full sheet (dots) | Strips |
|---|---|---:|---:|
| `DC01` | 17 mm x 54 mm | 201 x 636 | 1 |
| `DC02` | 17 mm x 87 mm | 201 x 1026 | 1 |
| `DC20` | 23 mm x 23 mm | 272 x 272 | 1 |
| `DC08` | 29 mm x 42 mm | 342 x 495 | 1 |
| `DC03` | 29 mm x 90 mm | 342 x 1061 | 1 |
| `DC04` | 38 mm x 90 mm | 449 x 1061 | 1 |
| `DC17` | 39 mm x 48 mm | 461 x 565 | 1 |
| `DC24` | 52 mm x 29 mm | 614 x 341 | 1 |
| `DCNB` | 60 mm x 86 mm | 708 x 1027 | 1 |
| `DC06` | 62 mm x 29 mm | 732 x 341 | 1 |
| `DC07` | 62 mm x 100 mm | 732 x 1179 | 1 |
| `DC15` | 102 mm x 51 mm | 1200 x 596 | 1 |
| `DC16` | 102 mm x 152 mm | 1200 x 1804 | 1 |
| `DC103_164` | 103 mm x 164 mm | 1224 x 1941 | 1 |
| `DC12` | 12 mm Dia | 142 x 142 | 1 |
| `DC13` | 24 mm Dia | 284 x 284 | 1 |
| `DC05` | 58 mm Dia | 688 x 688 | 1 |
| `12mm` | 12 mm | 142 x 1181 | 1 |
| `29mm` | 29 mm | 342 x 1181 | 1 |
| `38mm` | 38 mm | 449 x 1181 | 1 |
| `50mm` | 50 mm | 590 x 1181 | 1 |
| `54mm` | 54 mm | 638 x 1181 | 1 |
| `62mm` | 62 mm | 732 x 1181 | 1 |
| `102mm` | 102 mm | 1200 x 1181 | 1 |
| `103mm` | 103 mm | 1224 x 1181 | 1 |
| `12mmx2` | 12 mm x2 | 248 x 1181 | 2 |
| `29mmx2` | 29 mm x2 | 648 x 1181 | 2 |
| `38mmx2` | 38 mm x2 | 862 x 1181 | 2 |
| `50mmx2` | 50 mm x2 | 1144 x 1181 | 2 |
| `54mmx2` | 54 mm x2 | 1228 x 1181 | 2 |
| `62mmx2` | 62 mm x2 | 1428 x 1181 | 2 |
| `102mmx2` | 102 mm x2 | 2364 x 1181 | 2 |
| `103mmx2` | 103 mm x2 | 2424 x 1181 | 2 |
| `12mmx3` | 12 mm x3 | 354 x 1181 | 3 |
| `29mmx3` | 29 mm x3 | 954 x 1181 | 3 |
| `38mmx3` | 38 mm x3 | 1275 x 1181 | 3 |
| `50mmx3` | 50 mm x3 | 1698 x 1181 | 3 |
| `54mmx3` | 54 mm x3 | 1818 x 1181 | 3 |
| `62mmx3` | 62 mm x3 | 2124 x 1181 | 3 |
| `102mmx3` | 102 mm x3 | 3528 x 1181 | 3 |
| `103mmx3` | 103 mm x3 | 3624 x 1181 | 3 |
| `12mmx4` | 12 mm x4 | 460 x 1181 | 4 |
| `29mmx4` | 29 mm x4 | 1260 x 1181 | 4 |
| `38mmx4` | 38 mm x4 | 1688 x 1181 | 4 |
| `50mmx4` | 50 mm x4 | 2252 x 1181 | 4 |
| `54mmx4` | 54 mm x4 | 2408 x 1181 | 4 |
| `62mmx4` | 62 mm x4 | 2820 x 1181 | 4 |
| `102mmx4` | 102 mm x4 | 4692 x 1181 | 4 |
| `103mmx4` | 103 mm x4 | 4824 x 1181 | 4 |
| `C_DC03_01` | Standard Address Label | 342 x 1061 | 1 |
| `C_DC04_02` | Large Address Label | 449 x 1061 | 1 |
| `C_DC06_03` | Small Address Label | 732 x 341 | 1 |
| `C_DC01_04` | Return Address Label | 201 x 636 | 1 |
| `C_DC07_05` | Shipping Label | 732 x 1179 | 1 |
| `C_DC07_06` | Visitor Name Badge Label | 732 x 1179 | 1 |
| `C_DC02_07` | File Folder Label | 201 x 1026 | 1 |
| `C_DC01_08` | Hanging File Folder Label | 201 x 636 | 1 |
| `C_29mm_09` | Binder 3 cm - Spine | 342 x 2468 | 1 |
| `C_62mm_10` | Binder 5 cm - Spine | 732 x 2468 | 1 |
| `C_DC05_11` | CD/DVD Label | 688 x 688 | 1 |
| `C_DC12_12` | 12 mm Round Label | 142 x 142 | 1 |
| `C_DC13_13` | 24 mm Round Label | 284 x 284 | 1 |
| `C_DC20_14` | 23 mm x 23 mm Square Label | 272 x 272 | 1 |
| `C_62mm_15` | 62 mm x 184 mm Postage Label | 732 x 2172 | 1 |
| `C_62mm_16` | 62 mm x 209 mm Postage Label | 732 x 2472 | 1 |
| `C_DC15_15` | Label | 1200 x 596 | 1 |
| `C_DC103_164_18` | Large Shipping Label | 1224 x 1941 | 1 |
| `w103h164` | 103 mm x 164 mm | 1224 x 1941 | 1 |
| `w102h152` | 102 mm x 152 mm | 1200 x 1804 | 1 |

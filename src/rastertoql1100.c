/* SPDX-License-Identifier: GPL-3.0-only */
#define _DARWIN_C_SOURCE
#include <cups/cups.h>
#include <cups/raster.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stddef.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

#define LIMIT (64u * 1024u * 1024u)
#define MAX_PAGES 100u
#define MAX_IMPRESSIONS 1000u
#define ROW_BYTES 162u
#define VERSION "0.2.0"

typedef struct {
    const char *name;
    unsigned width, height, printable_width, printable_height, x, y, right, code, length, strips, continuous;
} media_t;
#include "media.h"
typedef struct { off_t offset; media_t media; } page_t;
static volatile sig_atomic_t cancelled;
static void cancel_job(int sig) { (void)sig; cancelled = 1; }
static int fail(const char *message) { fprintf(stderr, "ERROR: %s\n", message); return 1; }
static int wait_ready(int fd, short events) {
    struct pollfd descriptor = {fd, events, 0};
    while (!cancelled) {
        int n = poll(&descriptor, 1, 250);
        if (n < 0 && errno != EINTR) return 0;
        if (n > 0) return !cancelled && !(descriptor.revents & POLLNVAL);
    }
    return 0;
}
static ssize_t raster_read(void *context, unsigned char *buffer, size_t bytes) {
    FILE *input = context;
    if (cancelled) return -1;
    size_t n = fread(buffer, 1, bytes, input);
    return ferror(input) ? -1 : (ssize_t)n;
}
static int write_all(const void *data, size_t length) {
    const unsigned char *p = data;
    while (length && !cancelled) {
        ssize_t n = write(STDOUT_FILENO, p, length);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            if (!wait_ready(STDOUT_FILENO, POLLOUT)) return 0;
            continue;
        }
        if (n <= 0) return 0;
        p += n; length -= (size_t)n;
    }
    return !cancelled;
}
static int boolean(const char *value, int *result) {
    if (!strcasecmp(value, "true") || !strcmp(value, "1") || !strcasecmp(value, "on")) *result = 1;
    else if (!strcasecmp(value, "false") || !strcmp(value, "0") || !strcasecmp(value, "off")) *result = 0;
    else return 0;
    return 1;
}
static int near_dots(double points, unsigned dots) {
    return isfinite(points) && fabs(points * 300.0 / 72.0 - dots) <= 1.01;
}
static int same_size(const media_t *a, const media_t *b) {
    return a->width == b->width && a->height == b->height && a->code == b->code &&
        a->length == b->length && a->strips == b->strips && a->continuous == b->continuous;
}
static int custom_media(double width, double height, media_t *result) {
    if (!isfinite(width) || !isfinite(height) || height < 72.0 - 0.001 || height > 3000.0 * 72.0 / 25.4 + 0.001) return 0;
    for (size_t i = 0; i < sizeof(media) / sizeof(media[0]); i++) {
        if (!media[i].continuous || !near_dots(width, media[i].width)) continue;
        *result = media[i];
        result->name = "Custom";
        result->height = (unsigned)ceil(height / 0.24 - 0.00001);
        if (result->height < 301) result->height = 301;
        result->y = 35;
        result->printable_height = result->height - 70;
        return 1;
    }
    return 0;
}
static int parse_media(const char *value, media_t *result) {
    for (size_t i = 0; i < sizeof(media) / sizeof(media[0]); i++) {
        if (!strcmp(value, media[i].name)) { *result = media[i]; return 1; }
    }
    if (strncmp(value, "Custom.", 7)) return 0;
    char *end;
    errno = 0;
    double width = strtod(value + 7, &end);
    if (errno || end == value + 7 || *end != 'x') return 0;
    const char *start = end + 1;
    double height = strtod(start, &end);
    if (errno || end == start) return 0;
    double scale = !strcmp(end, "mm") ? 72.0 / 25.4 : !strcmp(end, "in") ? 72.0 : !*end ? 1.0 : 0.0;
    return scale && custom_media(width * scale, height * scale, result);
}
static int validate_header(const cups_page_header2_t *h, const media_t *selected, int *full, media_t *result) {
    if (h->HWResolution[0] != 300 || h->HWResolution[1] != 300 || h->Duplex || h->Tumble ||
        h->cupsColorOrder != CUPS_ORDER_CHUNKED || h->cupsNumColors != 1 ||
        (h->cupsColorSpace != CUPS_CSPACE_K && h->cupsColorSpace != CUPS_CSPACE_W && h->cupsColorSpace != CUPS_CSPACE_SW) ||
        (h->cupsBitsPerPixel != 1 && h->cupsBitsPerPixel != 8) ||
        h->cupsBitsPerColor != h->cupsBitsPerPixel || h->NumCopies > 1 ||
        h->cupsBytesPerLine != (h->cupsWidth * (uint64_t)h->cupsBitsPerPixel + 7) / 8)
        return 0;
    double width = h->cupsPageSize[0] ? h->cupsPageSize[0] : h->PageSize[0];
    double height = h->cupsPageSize[1] ? h->cupsPageSize[1] : h->PageSize[1];
    media_t custom;
    size_t count = selected ? 1 : sizeof(media) / sizeof(media[0]);
    for (size_t i = 0; i <= count; i++) {
        const media_t *m;
        if (i < count) m = selected ? selected : &media[i];
        else {
            if (selected || !custom_media(width, height, &custom)) break;
            m = &custom;
        }
        /* Legacy integer PageSize rounds points, not printer dots. */
        int size_ok = h->cupsPageSize[0] && h->cupsPageSize[1] ?
            near_dots(width, m->width) && near_dots(height, m->height) :
            fabs(width - m->width * 0.24) <= 0.51 && fabs(height - m->height * 0.24) <= 0.51;
        if (!size_ok) continue;
        int is_custom = !strcmp(m->name, "Custom");
        *full = h->cupsWidth == m->width && (h->cupsHeight == m->height ||
            (is_custom && h->cupsHeight + 1 == m->height));
        if (*full || (h->cupsWidth == m->printable_width * m->strips &&
            (h->cupsHeight == m->printable_height || (is_custom && h->cupsHeight + 1 == m->printable_height)))) {
            *result = *m; return 1;
        }
    }
    return 0;
}
static unsigned preflight(FILE *raw, size_t total, const media_t *selected, unsigned long copies) {
    uint32_t magic;
    if (fread(&magic, 1, sizeof(magic), raw) != sizeof(magic)) return 0;
    int v1 = magic == CUPS_RASTER_SYNCv1 || magic == CUPS_RASTER_REVSYNCv1;
    int v3 = magic == CUPS_RASTER_SYNC || magic == CUPS_RASTER_REVSYNC;
    if (!v1 && !v3) return 0;
    int swap = magic == CUPS_RASTER_REVSYNCv1 || magic == CUPS_RASTER_REVSYNC;
    size_t header_size = v1 ? sizeof(cups_page_header_t) : sizeof(cups_page_header2_t);
    size_t position = sizeof(magic);
    unsigned pages = 0, impressions = 0;
    while (position < total && !cancelled) {
        cups_page_header2_t h;
        memset(&h, 0, sizeof(h));
        if (header_size > total - position || fread(&h, 1, header_size, raw) != header_size) return 0;
        if (swap) {
            unsigned char *bytes = (unsigned char *)&h;
            size_t end = v1 ? header_size : offsetof(cups_page_header2_t, cupsString);
            for (size_t i = offsetof(cups_page_header2_t, AdvanceDistance); i < end; i += 4) {
                unsigned char a = bytes[i], b = bytes[i + 1];
                bytes[i] = bytes[i + 3]; bytes[i + 1] = bytes[i + 2];
                bytes[i + 2] = b; bytes[i + 3] = a;
            }
        }
        if (v1) h.cupsNumColors = 1;
        int full;
        media_t m;
        if (!validate_header(&h, selected, &full, &m)) return 0;
        position += header_size;
        size_t pixels = (size_t)h.cupsBytesPerLine * h.cupsHeight;
        if (pixels > total - position || ++pages > MAX_PAGES || (impressions += m.strips) * copies > MAX_IMPRESSIONS) return 0;
        position += pixels;
        if (fseeko(raw, (off_t)position, SEEK_SET)) return 0;
    }
    if (cancelled || fseeko(raw, 0, SEEK_SET)) return 0;
    return pages;
}
static int emit_page(FILE *spool, const page_t *page, int first, int last, int cut, int cut_every, int cut_at_end, int quality) {
    const media_t *m = &page->media;
    unsigned rows = m->printable_height;
    unsigned char commands[] = {
        0x1b, 'i', 'z', (m->continuous ? 0x86 : 0x8e) | (quality ? 0x40 : 0), m->continuous ? 0x0a : 0x0b, (unsigned char)m->code, (unsigned char)m->length,
        rows & 255, (rows >> 8) & 255, 0, 0, first ? 0 : 1, 0,
        0x1b, 'i', 'M', cut ? 0x40 : 0,
        0x1b, 'i', 'A', (unsigned char)cut_every,
        0x1b, 'i', 'K', cut && cut_at_end ? 0x08 : 0,
        0x1b, 'i', 'd', m->continuous ? 35 : 0, 0, 'M', 0
    };
    if (fseeko(spool, page->offset, SEEK_SET) || !write_all(commands, sizeof(commands))) return 0;
    unsigned char row[ROW_BYTES + 3] = {'g', 0, ROW_BYTES};
    for (unsigned y = 0; y < rows; y++) {
        if (fread(row + 3, 1, ROW_BYTES, spool) != ROW_BYTES || !write_all(row, sizeof(row))) return 0;
    }
    unsigned char end = last ? 0x1a : 0x0c;
    return write_all(&end, 1);
}
int main(int argc, char **argv) {
    if (argc == 2 && (!strcmp(argv[1], "--help") || !strcmp(argv[1], "--version"))) {
        if (!strcmp(argv[1], "--version")) puts("rastertoql1100 " VERSION);
        else puts("Usage: rastertoql1100 job-id user title copies options [raster-file]");
        return 0;
    }
    if (argc != 6 && argc != 7) return fail("Expected CUPS filter arguments; use --help");
    char *end;
    errno = 0;
    unsigned long copies = strtoul(argv[4], &end, 10);
    if (errno || !*argv[4] || *end || copies < 1 || copies > 100) return fail("Copies must be 1 through 100");
    int cut = 1, collate = 1, cut_every = 1, cut_at_end = 1, quality = 0;
    media_t selection;
    const media_t *selected = NULL;
    cups_option_t *options = NULL;
    int count = cupsParseOptions(argv[5], 0, &options);
    int valid = 1;
    for (int i = 0; i < count; i++) {
        const char *key = options[i].name, *value = options[i].value;
        if (!strcasecmp(key, "PageSize") || !strcasecmp(key, "PageRegion") || !strcasecmp(key, "media")) {
            media_t found;
            if (!parse_media(value, &found) || (selected && !same_size(selected, &found))) valid = 0;
            else { selection = found; selected = &selection; }
        } else if (!strcasecmp(key, "AutoCut")) valid &= boolean(value, &cut);
        else if (!strcasecmp(key, "CutAtEnd")) valid &= boolean(value, &cut_at_end);
        else if (!strcasecmp(key, "CutEvery")) {
            char *last;
            errno = 0;
            unsigned long number = strtoul(value, &last, 10);
            if (errno || !*value || *last || number < 1 || number > 255) valid = 0;
            else cut_every = (int)number;
        } else if (!strcasecmp(key, "PrintQuality")) {
            if (!strcmp(value, "Speed")) quality = 0;
            else if (!strcmp(value, "Quality")) quality = 1;
            else valid = 0;
        }
        else if (!strcasecmp(key, "Collate")) valid &= boolean(value, &collate);
        else if (!strcasecmp(key, "CutMedia")) {
            if (!strcmp(value, "0")) cut = 0;
            else if (!strcmp(value, "4")) cut = 1;
            else valid = 0;
        } else if (!strcasecmp(key, "Resolution")) valid &= !strcmp(value, "300dpi") || !strcmp(value, "300x300dpi");
        else if (!strcasecmp(key, "ColorModel")) valid &= !strcmp(value, "Gray") || !strcmp(value, "Black");
        else if (!strcasecmp(key, "sides")) valid &= !strcmp(value, "one-sided");
        else if (!strcasecmp(key, "MirrorPrint")) { int mirror = 0; valid &= boolean(value, &mirror) && !mirror; }
    }
    cupsFreeOptions(count, options);
    if (!valid) return fail("Unsupported or conflicting print options");
    struct sigaction action;
    memset(&action, 0, sizeof(action)); action.sa_handler = cancel_job; sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL); sigaction(SIGINT, &action, NULL);
    signal(SIGPIPE, SIG_IGN);
    int fd = argc == 7 ? open(argv[6], O_RDONLY | O_CLOEXEC | O_NONBLOCK) : STDIN_FILENO;
    if (fd < 0) return fail("Cannot open raster input");
    FILE *raw = tmpfile(), *spool = tmpfile();
    cups_raster_t *raster = NULL;
    int result = 1;
    int input_flags = fcntl(fd, F_GETFL), output_flags = fcntl(STDOUT_FILENO, F_GETFL);
    if (input_flags < 0 || output_flags < 0 || fcntl(fd, F_SETFL, input_flags | O_NONBLOCK) ||
        fcntl(STDOUT_FILENO, F_SETFL, output_flags | O_NONBLOCK)) { fail("Cannot configure cancellable job I/O"); goto done; }
    if (!raw || !spool) { fail("Cannot create private job spool"); goto done; }
    unsigned char buffer[8192];
    size_t total = 0;
    for (;;) {
        if (!wait_ready(fd, POLLIN)) { fail("Job cancelled or input unavailable"); goto done; }
        ssize_t n = read(fd, buffer, sizeof(buffer));
        if (cancelled) { fail("Job cancelled"); goto done; }
        if (n < 0 && errno == EINTR) continue;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) continue;
        if (n < 0) { fail("Cannot read raster input"); goto done; }
        if (!n) break;
        if ((size_t)n > LIMIT - total) { fail("Raster input exceeds 64 MiB limit"); goto done; }
        total += (size_t)n;
        if (fwrite(buffer, 1, (size_t)n, raw) != (size_t)n) { fail("Cannot spool raster input"); goto done; }
    }
    if (fflush(raw) || fseeko(raw, 0, SEEK_SET)) { fail("Cannot rewind raster input"); goto done; }
    unsigned expected_pages = preflight(raw, total, selected, copies);
    if (!expected_pages) { fail("Require complete supported uncompressed CUPS v1/v3 raster pages within job limits"); goto done; }
    raster = cupsRasterOpenIO(raster_read, raw, CUPS_RASTER_READ);
    if (!raster) { fail("Invalid CUPS raster stream"); goto done; }
    page_t pages[MAX_IMPRESSIONS];
    unsigned page_count = 0, logical_count = 0;
    unsigned starts[MAX_PAGES], strip_counts[MAX_PAGES];
    size_t spool_size = 0;
    for (;;) {
        if (logical_count == expected_pages) break;
        cups_page_header2_t h;
        if (!cupsRasterReadHeader2(raster, &h)) {
            fail("Cannot decode validated raster page header"); goto done;
        }
        int full = 0;
        media_t resolved;
        const media_t *m = &resolved;
        if (!validate_header(&h, selected, &full, &resolved)) { fail("Unsupported raster header: require supported media, 300dpi, single-channel 1/8-bit grayscale"); goto done; }
        size_t page_bytes = (size_t)m->printable_height * ROW_BYTES;
        if (logical_count == MAX_PAGES || (page_count + m->strips) * copies > MAX_IMPRESSIONS ||
            page_bytes * m->strips > LIMIT - spool_size) { fail("Job exceeds page, impression or spool limit"); goto done; }
        starts[logical_count] = page_count; strip_counts[logical_count] = m->strips;
        off_t base = ftello(spool);
        if (base < 0) { fail("Cannot locate page spool"); goto done; }
        for (unsigned strip = 0; strip < m->strips; strip++) {
            pages[page_count + strip].offset = base + (off_t)(page_bytes * strip);
            pages[page_count + strip].media = *m;
        }
        unsigned char source[4800 + 48], target[ROW_BYTES];
        unsigned x_offset = full ? m->x : 0, y_offset = full ? m->y : 0;
        for (unsigned y = 0; y < h.cupsHeight; y++) {
            if (cancelled) { fail("Job cancelled"); goto done; }
            if (cupsRasterReadPixels(raster, source, h.cupsBytesPerLine) != h.cupsBytesPerLine) { fail("Truncated raster pixels"); goto done; }
            if (y < y_offset || y >= h.cupsHeight - (full ? m->height - m->y - m->printable_height : 0)) continue;
            for (unsigned strip = 0; strip < m->strips; strip++) {
                memset(target, 0, sizeof(target));
                for (unsigned x = 0; x < m->printable_width; x++) {
                    unsigned sx = x + x_offset + strip * m->printable_width;
                    unsigned value = h.cupsBitsPerPixel == 1 ? ((source[sx / 8] >> (7 - sx % 8)) & 1) * 255 : source[sx];
                    int black = h.cupsColorSpace == CUPS_CSPACE_K ? value >= 128 : value < 128;
                    if (black) {
                        unsigned bit = m->right + m->printable_width - 1 - x;
                        target[bit / 8] |= (unsigned char)(0x80 >> (bit % 8));
                    }
                }
                off_t offset = pages[page_count + strip].offset + (off_t)((y - y_offset) * ROW_BYTES);
                if (fseeko(spool, offset, SEEK_SET) || fwrite(target, 1, sizeof(target), spool) != sizeof(target)) { fail("Cannot write page spool"); goto done; }
            }
        }
        unsigned input_rows = full ? h.cupsHeight - y_offset - (m->height - m->y - m->printable_height) : h.cupsHeight;
        if (input_rows < m->printable_height) {
            memset(target, 0, sizeof(target));
            for (unsigned strip = 0; strip < m->strips; strip++) {
                off_t offset = pages[page_count + strip].offset + (off_t)(input_rows * ROW_BYTES);
                if (fseeko(spool, offset, SEEK_SET) || fwrite(target, 1, sizeof(target), spool) != sizeof(target)) { fail("Cannot pad custom page spool"); goto done; }
            }
        }
        spool_size += page_bytes * m->strips;
        if (fseeko(spool, (off_t)spool_size, SEEK_SET)) { fail("Cannot locate spool end"); goto done; }
        page_count += m->strips;
        logical_count++;
    }
    if (!page_count) { fail("No raster pages"); goto done; }
    if (fflush(spool) || cancelled) { fail("Cannot complete job spool or job cancelled"); goto done; }
    unsigned char invalidate[350] = {0};
    const unsigned char init[] = {0x1b, '@', 0x1b, 'i', 'a', 1, 0x1b, 'i', '!', 1};
    if (!write_all(invalidate, sizeof(invalidate)) || !write_all(init, sizeof(init))) { fail("Cannot write printer initialization"); goto done; }
    unsigned impression = 0;
    for (unsigned outer = 0; outer < (collate ? copies : logical_count); outer++) {
        for (unsigned inner = 0; inner < (collate ? logical_count : copies); inner++) {
            unsigned logical = collate ? inner : outer;
            for (unsigned strip = 0; strip < strip_counts[logical]; strip++) {
                unsigned p = starts[logical] + strip;
                fprintf(stderr, "PAGE: %u 1\n", logical + 1);
                if (!emit_page(spool, &pages[p], impression == 0, impression + 1 == page_count * copies, cut, cut_every, cut_at_end, quality)) { fail("Printer output failed or job cancelled"); goto done; }
                impression++;
            }
        }
    }
    fprintf(stderr, "INFO: Sent %u label(s) to CUPS backend\n", impression);
    result = 0;
done:
    if (input_flags >= 0) fcntl(fd, F_SETFL, input_flags);
    if (output_flags >= 0) fcntl(STDOUT_FILENO, F_SETFL, output_flags);
    if (raster) cupsRasterClose(raster);
    if (raw) fclose(raw);
    if (spool) fclose(spool);
    if (argc == 7 && fd >= 0) close(fd);
    return result;
}

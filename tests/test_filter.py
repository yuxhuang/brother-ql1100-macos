"""Offline behavior tests. Protocol oracle: Brother manual pp5,19-20,31-37.

The generator uses system libcups; the decoder does not import driver code.
Run: python -m unittest discover -s tests -v (from module root).
"""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILTER = Path(os.environ.get('QL1100_FILTER', ROOT / 'build/rastertoql1100'))


def unpackbits(payload):
    out = bytearray()
    i = 0
    while i < len(payload):
        n = payload[i]
        i += 1
        if n < 128:
            count = n + 1
            if i + count > len(payload):
                raise AssertionError('truncated PackBits literal')
            out.extend(payload[i:i + count]); i += count
        elif n > 128:
            if i == len(payload):
                raise AssertionError('truncated PackBits repeat')
            out.extend(payload[i:i + 1] * (257 - n)); i += 1
    return bytes(out)


def decode(data):
    """Parse every byte, including command-shaped bytes inside raster payloads."""
    assert data[:350] == bytes(350), 'missing 350-byte invalidate prefix'
    assert data[350:352] == b'\x1b@', 'missing initialize'
    i = 352
    pages = []
    current = None
    compression = 0
    settings = {}
    while i < len(data):
        if data[i:i+3] == b'\x1biz':
            args = data[i+3:i+13]
            assert len(args) == 10
            current = dict(settings, flags=args[0], media=tuple(args[1:4]),
                           count=int.from_bytes(args[4:8], 'little'),
                           subsequent=args[8], reserved=args[9], rows=[])
            pages.append(current); i += 13
        elif data[i:i+3] in (b'\x1bia', b'\x1bi!', b'\x1biM', b'\x1biA', b'\x1biK'):
            command = data[i:i+3]
            key = {b'\x1bia':'mode', b'\x1bi!':'status', b'\x1biM':'cut', b'\x1biA':'cut_every', b'\x1biK':'expanded'}[command]
            settings[key] = data[i+3]
            if current is not None: current[key] = data[i+3]
            i += 4
        elif data[i:i+3] == b'\x1bid':
            settings['margin'] = int.from_bytes(data[i+3:i+5], 'little')
            if current is not None: current['margin'] = settings['margin']
            i += 5
        elif data[i] == 77:
            compression = data[i+1]; assert compression in (0, 2); i += 2
        elif data[i] == 103:
            assert current is not None
            assert data[i+1] == 0
            size = data[i+2]
            raw = data[i+3:i+3+size]
            assert len(raw) == size
            row = unpackbits(raw) if compression == 2 else raw
            assert len(row) == 162, f'raster width {len(row)}'
            current['rows'].append(row); i += 3 + size
        elif data[i] == 90:
            assert current is not None
            current['rows'].append(bytes(162)); i += 1
        elif data[i] in (12, 26):
            assert current is not None
            current['end'] = data[i]; current = None; i += 1
        else:
            raise AssertionError(f'unknown command at {i}: {data[i:i+12].hex()}')
    assert pages and current is None, 'missing final print command'
    for index, page in enumerate(pages):
        assert len(page['rows']) == page['count']
        assert page['end'] == (26 if index == len(pages)-1 else 12)
        assert page['subsequent'] == (0 if index == 0 else 1)
    return pages


def black_bits(row):
    return {i for i in range(1296) if row[i // 8] & (128 >> (i % 8))}


class FilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ql1100-tests-')
        cls.generator = Path(cls.tmp.name) / 'raster_fixture'
        subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', str(ROOT/'tests/raster_fixture.c'), '-lcups', '-o', str(cls.generator)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fixture(self, roll=103, depth=1, space='K', pages=1, pattern='edges', full=False, field='none', value=0, rows=-1, encoding='rawv3'):
        return subprocess.check_output([str(self.generator), *map(str, (roll,depth,space,pages,pattern,int(full),field,value,rows,encoding))])

    def run_filter(self, data, copies='1', options=''):
        return subprocess.run([str(FILTER), '1', 'tester', 'fixture', str(copies), options], input=data, capture_output=True, timeout=30)

    def success(self, data, **kwargs):
        result = self.run_filter(data, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return decode(result.stdout)

    def reject(self, data, **kwargs):
        result = self.run_filter(data, **kwargs)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'', 'invalid job sent printer commands')

    def test_raw_v1_and_v3_both_byte_orders(self):
        # libcups emits native little-endian v3. CUPS raster headers contain
        # 256 initial string bytes followed by 32-bit numeric fields; v1 ends
        # at420, v3 numeric fields end at580. Pixel bytes remain unchanged.
        data=self.fixture()
        self.assertEqual(data[:4],b'3SaR')
        header=data[4:1800]
        pixels=data[1800:]
        expected=self.success(data)[0]['rows']
        for version,size,numeric_end in [(1,420,420),(3,1796,580)]:
            for endian in ('little','big'):
                with self.subTest(version=version,endian=endian):
                    h=bytearray(header[:size])
                    if endian=='big':
                        for i in range(256,numeric_end,4): h[i:i+4]=h[i:i+4][::-1]
                    magic={(1,'little'):b'tSaR',(1,'big'):b'RaSt',(3,'little'):b'3SaR',(3,'big'):b'RaS3'}[version,endian]
                    self.assertEqual(self.success(magic+h+pixels)[0]['rows'],expected)

    def test_cancel_waiting_for_fifo_file_argument_exits_promptly(self):
        path=Path(self.tmp.name)/'empty-input.fifo'
        os.mkfifo(path)
        p=subprocess.Popen([str(FILTER),'1','tester','fixture','1','',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            time.sleep(0.05)
            p.send_signal(signal.SIGTERM)
            out,_=p.communicate(timeout=3)
            self.assertNotEqual(p.returncode,0)
            self.assertEqual(out,b'')
        finally:
            if p.poll() is None: p.kill(); p.communicate()

    def test_default_103_media_and_protocol(self):
        p = self.success(self.fixture())[0]
        self.assertEqual((p['media'],p['count'],p['flags'] & 14,p['reserved'],p['mode'],p['status'],p['margin'],p['cut'] & 64,p['expanded'] & 8,p['cut_every']), ((11,104,164),1822,14,0,1,1,0,64,8,1))

    def test_exact_1296_bit_geometry_and_orientation(self):
        for roll, width, height, right in [(103,1200,1822,38),(102,1164,1660,56)]:
            with self.subTest(roll=roll):
                p = self.success(self.fixture(roll=roll))[0]
                self.assertEqual(black_bits(p['rows'][0]), {right,right+width-1})
                self.assertEqual(black_bits(p['rows'][1]), {right+width-2})
                self.assertEqual(black_bits(p['rows'][-1]), {right+width-8})
                self.assertEqual(len(p['rows']),height)
                self.assertEqual(p['media'], (11,104,164) if roll==103 else (11,102,153))

    def test_full_physical_page_crops_to_identical_printable_content(self):
        for roll in (103,102):
            with self.subTest(roll=roll):
                self.assertEqual(self.success(self.fixture(roll=roll,full=True))[0]['rows'], self.success(self.fixture(roll=roll))[0]['rows'])

    def test_white_black_and_gray_polarity(self):
        for depth in (1,8):
            for space in ('W','K'):
                with self.subTest(depth=depth,space=space):
                    white = self.success(self.fixture(depth=depth,space=space,pattern='white'))[0]
                    self.assertTrue(all(row==bytes(162) for row in white['rows']))
                    black = self.success(self.fixture(depth=depth,space=space,pattern='black'))[0]
                    self.assertEqual(black_bits(black['rows'][0]),set(range(38,1238)))

    def test_asymmetric_bits_across_byte_boundary(self):
        p=self.success(self.fixture(pattern='asymmetric'))[0]
        self.assertEqual(black_bits(p['rows'][0]), {1237-x for x in (0,2,7,8,119)})

    def test_8bit_white_threshold(self):
        p=self.success(self.fixture(depth=8,space='W',pattern='threshold'))[0]
        self.assertEqual(black_bits(p['rows'][0]), {1237,1236})

    def test_full_page_unprintable_borders_are_discarded(self):
        for roll in (103,102):
            with self.subTest(roll=roll):
                p=self.success(self.fixture(roll=roll,full=True,pattern='cropmarks'))[0]
                self.assertTrue(all(row==bytes(162) for row in p['rows']))

    def test_collated_and_uncollated_copy_order(self):
        data=self.fixture(pages=2,pattern='pageid')
        for options,expected in [('Collate=True',[1237,1236,1237,1236]),('Collate=False',[1237,1237,1236,1236])]:
            with self.subTest(options=options):
                pages=self.success(data,copies=2,options=options)
                self.assertEqual([black_bits(p['rows'][0]) for p in pages],[{x} for x in expected])

    def test_page_count_and_impression_limits(self):
        self.reject(self.fixture(pages=101,pattern='white'))
        self.reject(self.fixture(pages=11,pattern='white'),copies=100)

    def test_cutmedia_options(self):
        for option,expected in [('CutMedia=0',0),('CutMedia=4',64)]:
            with self.subTest(option=option):
                p=self.success(self.fixture(),options=option)[0]
                self.assertEqual(p['cut'] & 64,expected)

    def test_late_bad_header_sends_no_output(self):
        valid=self.fixture()
        bad=self.fixture(field='dpi',value=600)
        # CUPS raw v3 starts with four magic bytes; subsequent headers omit magic.
        self.reject(valid+bad[4:])

    def test_raster_file_argument(self):
        path=Path(self.tmp.name)/'input.raster'
        path.write_bytes(self.fixture())
        result=subprocess.run([str(FILTER),'1','tester','fixture','1','',str(path)],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        self.assertEqual(decode(result.stdout)[0]['media'],(11,104,164))

    def test_copies_and_multipage_have_single_final_feed(self):
        pages=self.success(self.fixture(pages=2),copies=2)
        self.assertEqual(len(pages),4)

    def test_auto_cut_false_disables_both_cut_flags(self):
        p=self.success(self.fixture(),options='AutoCut=False')[0]
        self.assertEqual((p['cut'] & 64,p['expanded'] & 8), (0,0))

    def test_invalid_input_is_rejected_without_any_output(self):
        for data in (b'', b'not cups', self.fixture(rows=1), self.fixture()[:-1]):
            with self.subTest(length=len(data)): self.reject(data)

    def test_compressed_cups_input_is_explicitly_rejected(self):
        # v2 compression permits libcups read-ahead to hide partial trailing
        # headers. The filter deliberately accepts bounded raw v1/v3 only.
        for depth in (1,8):
            with self.subTest(depth=depth):
                self.reject(self.fixture(depth=depth,encoding='compressed'))

    def test_partial_trailing_headers_and_junk_emit_nothing(self):
        for encoding in ('rawv3','compressed'):
            data=self.fixture(encoding=encoding)
            header=self.fixture(field='dpi',value=600,encoding=encoding)[4:]
            for suffix in (b'x',bytes(4),header[:100],header[:-1]):
                with self.subTest(encoding=encoding,suffix_length=len(suffix)):
                    self.reject(data+suffix)

    def test_late_truncated_page_emits_nothing(self):
        for encoding in ('rawv3','compressed'):
            with self.subTest(encoding=encoding):
                data=self.fixture(pages=2,encoding=encoding)
                self.reject(data[:-100])

    def test_bogus_oversize_and_unsupported_headers(self):
        for field,value in [('width',0),('width',0xffffffff),('height',0xffffffff),('bpl',0xffffffff),('dpi',600),('colors',3),('order',2),('space',1),('pagewidth',1000),('duplex',1),('copies',2)]:
            with self.subTest(field=field,value=value): self.reject(self.fixture(field=field,value=value))
        self.reject(self.fixture(depth=4))

    def test_invalid_copies_and_media_options(self):
        data=self.fixture()
        for copies in ('0','-1','101','999999999999999999999','1junk'):
            with self.subTest(copies=copies): self.reject(data,copies=copies)
        for options in ('PageSize=Letter','PageSize=w102h152','AutoCut=maybe','CutMedia=2'):
            with self.subTest(options=options): self.reject(data,options=options)

    def test_raw_input_limit_fails_without_printer_output(self):
        result=self.run_filter(bytes(64*1024*1024+1))
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,b'')
        self.assertIn(b'64 MiB',result.stderr)

    def test_cancel_during_blocked_printer_output_exits_promptly(self):
        path=Path(self.tmp.name)/'cancel.raster'
        path.write_bytes(self.fixture())
        p=subprocess.Popen([str(FILTER),'1','tester','fixture','1','',str(path)], stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(p.stdout.read(350),bytes(350))
            p.send_signal(signal.SIGTERM)
            _,err=p.communicate(timeout=3)
            self.assertNotEqual(p.returncode,0,err)
        finally:
            if p.poll() is None: p.kill(); p.communicate()

    def test_broken_output_fails_promptly(self):
        data=self.fixture()
        read,write=os.pipe(); os.close(read)
        try:
            p=subprocess.Popen([str(FILTER),'1','tester','fixture','1',''], stdin=subprocess.PIPE, stdout=write, stderr=subprocess.PIPE)
            _,err=p.communicate(data,timeout=5)
            self.assertNotEqual(p.returncode,0,err)
        finally: os.close(write)

    def test_cancel_while_waiting_for_input_exits_promptly_without_output(self):
        p=subprocess.Popen([str(FILTER),'1','tester','fixture','1',''],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        time.sleep(0.05)
        p.send_signal(signal.SIGTERM)
        out,_=p.communicate(timeout=3)
        self.assertNotEqual(p.returncode,0)
        self.assertEqual(out,b'')


if __name__ == '__main__':
    unittest.main()

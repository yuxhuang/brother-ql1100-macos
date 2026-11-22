"""Independent facts from Brother raster reference pp13-20,25 and media metadata.

No driver catalog is imported: a wrong catalog must fail these tests.
"""
import re
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from test_filter import ROOT, FILTER, decode, black_bits

# name, physical width/height, printable width/height, crop x/y, right pins,
# protocol width/length. Values are dots, not rounded marketed millimeters.
DIE = [
 ('DC01',201,636,165,566,18,35,44,17,54),
 ('DC02',201,1026,165,956,18,35,44,17,87),
 ('DC20',272,272,236,202,18,35,84,23,23),
 ('DC08',342,495,306,425,18,35,50,29,42),
 ('DC03',342,1061,306,991,18,35,50,29,90),
 ('DC04',449,1061,413,991,18,35,56,38,90),
 ('DC17',461,565,425,495,18,35,50,39,48),
 ('DC24',614,341,578,271,18,35,44,52,29),
 ('DCNB',708,1027,672,957,18,35,68,60,87),
 ('DC06',732,341,696,271,18,35,56,62,29),
 ('DC07',732,1179,696,1109,18,35,56,62,100),
 ('DC15',1200,596,1164,526,18,35,56,102,51),
 ('DC16',1200,1804,1164,1660,18,72,56,102,153),
 ('DC103_164',1224,1941,1200,1822,12,59,38,104,164),
 ('DC12',142,142,94,94,24,24,156,12,12),
 ('DC13',284,284,236,236,24,24,85,24,24),
 ('DC05',688,688,618,618,35,35,94,58,58),
]
# nominal width, physical dots, printable dots, crop, right pins, wire width.
ROLLS = [(12,142,106,18,74,12),(29,342,306,18,50,29),
 (38,449,413,18,56,38),(50,590,554,18,56,50),
 (54,638,590,24,44,54),(62,732,696,18,44,62),
 (102,1200,1164,18,56,102),(103,1224,1200,12,38,104)]
ALIASES = {
 'C_DC03_01':'DC03','C_DC04_02':'DC04','C_DC06_03':'DC06',
 'C_DC01_04':'DC01','C_DC07_05':'DC07','C_DC07_06':'DC07',
 'C_DC02_07':'DC02','C_DC01_08':'DC01','C_DC05_11':'DC05',
 'C_DC12_12':'DC12','C_DC13_13':'DC13','C_DC20_14':'DC20',
 'C_DC15_15':'DC15','C_DC103_164_18':'DC103_164',
 'w103h164':'DC103_164','w102h152':'DC16'}


def facts():
    result={r[0]:(*r[1:],1,False) for r in DIE}
    for nominal,pw,w,x,right,code in ROLLS:
        for strips in range(1,5):
            name=f'{nominal}mm'+(f'x{strips}' if strips>1 else '')
            result[name]=(pw+(strips-1)*w,1181,w,1111,x,35,right,code,0,strips,True)
    for alias,target in ALIASES.items(): result[alias]=result[target]
    for alias,nominal,ph in [('C_29mm_09',29,2468),('C_62mm_10',62,2468),('C_62mm_15',62,2172),('C_62mm_16',62,2472)]:
        r=list(result[f'{nominal}mm']); r[1]=ph; r[3]=ph-70; result[alias]=tuple(r)
    return result

MEDIA=facts()


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='ql-media-')
        cls.generator=Path(cls.tmp.name)/'fixture'
        subprocess.run(['clang','-Wall','-Wextra','-Werror',str(ROOT/'tests/media_fixture.c'),'-lcups','-o',str(cls.generator)],check=True)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def fixture(self,name,pattern='edges',full=False,pages=1,depth=1,space='K',geometry=None):
        pw,ph,w,h,x,y,right,code,length,strips,continuous=geometry or MEDIA[name]
        return subprocess.check_output([str(self.generator),name,*map(str,(pw,ph,w,h,x,y,strips)),pattern,str(int(full)),str(pages),str(depth),space])

    def run_filter(self,data,options='',copies=1):
        return subprocess.run([str(FILTER),'1','tester','media',str(copies),options],input=data,capture_output=True,timeout=20)

    def success(self,data,**kw):
        r=self.run_filter(data,**kw)
        self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'))
        return decode(r.stdout)

    def reject(self,data,**kw):
        r=self.run_filter(data,**kw)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(r.stdout,b'','rejected input produced printer output')

    def test_all_69_choices_have_expected_wire_geometry_and_pin_alignment(self):
        self.assertEqual(len(MEDIA),69)
        for name,g in MEDIA.items():
            with self.subTest(media=name):
                pw,ph,w,h,x,y,right,code,length,strips,continuous=g
                pages=self.success(self.fixture(name),options='PageSize='+name)
                self.assertEqual(len(pages),strips)
                for p in pages:
                    self.assertEqual((p['media'],p['count'],p['margin'],p['flags']&14),((10 if continuous else 11,code,length),h,35 if continuous else 0,6 if continuous else 14))
                    self.assertEqual(black_bits(p['rows'][0]),{right,right+w-1})
                    self.assertEqual((p['cut']&64,p['expanded']&8,p['cut_every']),(64,8,1))

    def test_full_physical_page_crop_matches_printable_for_every_geometry(self):
        seen=set()
        for name,g in MEDIA.items():
            if g in seen: continue
            seen.add(g)
            with self.subTest(media=name):
                expected=self.success(self.fixture(name),options='PageSize='+name)
                actual=self.success(self.fixture(name,full=True),options='PageSize='+name)
                self.assertEqual([p['rows'] for p in actual],[p['rows'] for p in expected])
                cropped=self.success(self.fixture(name,full=True,pattern='cropmarks'),options='PageSize='+name)
                self.assertTrue(all(row==bytes(162) for p in cropped for row in p['rows']))

    def test_banner_strips_preserve_content_page_order_and_copy_order(self):
        for name,g in MEDIA.items():
            strips=g[-2]
            if strips==1: continue
            right,w=g[6],g[2]
            for collate in (True,False):
                with self.subTest(media=name,collate=collate):
                    pages=self.success(self.fixture(name,pattern='stripid',pages=2),options=f'PageSize={name} Collate={collate}',copies=2)
                    one=list(range(strips)); two=list(range(strips,2*strips))
                    ids=(one+two)*2 if collate else one*2+two*2
                    self.assertEqual([black_bits(p['rows'][0]) for p in pages],[{right+w-1-i} for i in ids])

    def test_continuous_8bit_white_and_no_cut(self):
        for nominal,*_ in ROLLS:
            name=f'{nominal}mm'
            with self.subTest(media=name):
                p=self.success(self.fixture(name,depth=8,space='W'),options=f'PageSize={name} AutoCut=False')[0]
                self.assertEqual(black_bits(p['rows'][0]),{MEDIA[name][6],MEDIA[name][6]+MEDIA[name][2]-1})
                self.assertEqual((p['cut']&64,p['expanded']&8),(0,0))

    def test_widest_banner_8bit_full_raster_preserves_all_four_strips(self):
        pages=self.success(self.fixture('103mmx4',pattern='stripid',full=True,depth=8,space='W'),options='PageSize=103mmx4')
        self.assertEqual([black_bits(p['rows'][0]) for p in pages],[{1237-i} for i in range(4)])

    def test_custom_unrecognized_roll_widths_emit_nothing(self):
        for width in (13,28,39,51,61,90,104,500):
            with self.subTest(width=width):
                pw=round(width*300/25.4)
                name=f'Custom.{width}x100mm'
                g=(pw,1182,max(pw-36,1),1112,18,35,56,width,0,1,True)
                self.reject(self.fixture(name,geometry=g),options='PageSize='+name)

    def test_banner_impression_limit_counts_strips_and_rejects_before_output(self):
        self.reject(self.fixture('12mmx4',pattern='white',pages=3),options='PageSize=12mmx4',copies=100)

    def test_cut_interval_quality_and_end_cut_wire_controls(self):
        for options,expected in [('CutEvery=255 CutAtEnd=False PrintQuality=Quality',(255,0,64)),('CutEvery=1 CutAtEnd=True PrintQuality=Speed',(1,8,0)),('AutoCut=False CutAtEnd=True',(1,0,0))]:
            with self.subTest(options=options):
                p=self.success(self.fixture('DC01'),options='PageSize=DC01 '+options)[0]
                self.assertEqual((p['cut_every'],p['expanded']&8,p['flags']&64),expected)

    def test_invalid_cut_and_quality_controls_emit_nothing(self):
        for options in ('CutEvery=0','CutEvery=256','CutEvery=-1','CutEvery=1junk','CutAtEnd=maybe','PrintQuality=invalid'):
            with self.subTest(options=options): self.reject(self.fixture('DC01'),options=options)

    def test_custom_height_boundaries_and_widths(self):
        for nominal,pw,w,x,right,code in ROLLS:
            for mm,ph in ((25.4,301),(3000,35434)):
                name=f'Custom.{pw*.24:.2f}x{mm*72/25.4:.8f}'
                g=(pw,ph,w,ph-70,x,35,right,code,0,1,True)
                with self.subTest(width=nominal,height=mm):
                    p=self.success(self.fixture(name,geometry=g),options='PageSize='+name)[0]
                    self.assertEqual((p['media'],p['count'],p['margin']),((10,code,0),ph-70,35))

    def test_malformed_custom_dimensions_rejected_without_output(self):
        data=self.fixture('62mm')
        for value in ('Custom.62x25.3999mm','Custom.62x3000.0001mm','Custom.175.68x0','Custom.175.68x71.9','Custom.175.68x8504','Custom.180x283.44','Custom.nanx283.44','Custom.175.68xinf','Custom.175.68x283.44junk','Custom.-175.68x283.44','Custom.175.68x283.44x2'):
            with self.subTest(value=value): self.reject(data,options='PageSize='+value)

    def test_media_selection_conflicts_rejected_before_output(self):
        for options in ('PageSize=DC01 PageRegion=DC02','PageSize=62mm media=29mm','PageSize=DC01'):
            with self.subTest(options=options): self.reject(self.fixture('62mm'),options=options)

    def test_custom_big_endian_and_malformed_float_headers(self):
        name='Custom.175.68x283.44'; g=MEDIA['62mm']; data=self.fixture(name,geometry=g)
        h=bytearray(data[4:1800])
        for i in range(256,580,4): h[i:i+4]=h[i:i+4][::-1]
        expected=self.success(data,options='PageSize='+name)
        self.assertEqual(self.success(b'RaS3'+h+data[1800:],options='PageSize='+name),expected)
        # cupsPageSize starts at byte428 of cups_page_header2_t.
        for value in (float('nan'),float('inf'),-1.0,0.01):
            for endian,magic,header in (('<',b'3SaR',bytearray(data[4:1800])),('>',b'RaS3',h.copy())):
                with self.subTest(value=value,endian=endian):
                    struct.pack_into(endian+'f',header,428,value)
                    self.reject(magic+header+data[1800:],options='PageSize='+name)



def pdf_page(width,height):
    """Small self-contained PDF, deliberately independent of PDF packages."""
    stream=f'0 g 0 0 {width} {height} re f\n'.encode('ascii')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
      b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
      f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << >> /Contents 4 0 R >>'.encode('ascii'),
      b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'endstream']
    out=bytearray(b'%PDF-1.4\n'); offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(out)); out.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    start=len(out); out.extend(b'xref\n0 5\n0000000000 65535 f \n')
    for offset in offsets[1:]: out.extend(f'{offset:010} 00000 n \n'.encode())
    out.extend(f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return out


@unittest.skipUnless(Path('/usr/sbin/cupsfilter').exists(),'Apple CUPS PDF rasterizer unavailable')
class ApplePPDIntegrationTests(unittest.TestCase):
    def test_ppd_has_all_choices_and_matching_physical_and_imageable_geometry(self):
        ppds=list((ROOT/'ppd').glob('*.ppd'))
        self.assertEqual(len(ppds),1)
        text=ppds[0].read_text()
        sizes=dict(re.findall(r'^\*PaperDimension ([^/:]+)[^:]*:\s*"([^"\n]+)"',text,re.M))
        areas=dict(re.findall(r'^\*ImageableArea ([^/:]+)[^:]*:\s*"([^"\n]+)"',text,re.M))
        choices=set(re.findall(r'^\*PageSize ([^/:]+)[^:]*:',text,re.M))
        self.assertEqual(choices,set(MEDIA))
        self.assertEqual(set(sizes),set(MEDIA))
        self.assertEqual(set(areas),set(MEDIA))
        for name,g in MEDIA.items():
            with self.subTest(media=name):
                pw,ph,w,h,x,y,right,code,length,strips,continuous=g
                actual=tuple(map(float,sizes[name].split()))
                self.assertEqual(tuple(round(v/.24) for v in actual),(pw,ph))
                box=tuple(map(float,areas[name].split()))
                self.assertEqual(tuple(round(v/.24) for v in box),(x,ph-y-h,x+w*strips,ph-y))

    def test_actual_ppd_custom_height_endpoints(self):
        ppd=next((ROOT/'ppd').glob('*.ppd'))
        with tempfile.TemporaryDirectory(prefix='ql-custom-pdf-') as td:
            path=Path(td)/'page.pdf'
            for points,expected_rows in ((72,231),(3000*72/25.4,35364)):
                with self.subTest(height=points):
                    name=f'Custom.175.68x{points:.9f}'
                    path.write_bytes(pdf_page(175.68,points))
                    raster=subprocess.run(['/usr/sbin/cupsfilter','-p',str(ppd),'-i','application/pdf','-m','application/vnd.cups-raster','-o','PageSize='+name,str(path)],capture_output=True,timeout=30)
                    self.assertEqual(raster.returncode,0,raster.stderr.decode(errors='replace'))
                    output=subprocess.run([str(FILTER),'1','tester','custom PDF','1','PageSize='+name],input=raster.stdout,capture_output=True,timeout=20)
                    self.assertEqual(output.returncode,0,output.stderr.decode(errors='replace'))
                    p=decode(output.stdout)[0]
                    self.assertEqual((p['media'],p['count'],p['margin']),((10,62,0),expected_rows,35))
                    self.assertTrue(any(any(row) for row in p['rows']))

    def test_actual_ppd_pdf_conversion_for_every_unique_geometry(self):
        ppds=list((ROOT/'ppd').glob('*.ppd'))
        self.assertEqual(len(ppds),1)
        seen=set()
        with tempfile.TemporaryDirectory(prefix='ql-pdf-') as td:
            path=Path(td)/'page.pdf'
            for name,g in MEDIA.items():
                if g in seen: continue
                seen.add(g)
                with self.subTest(media=name):
                    pw,ph,w,h,x,y,right,code,length,strips,continuous=g
                    path.write_bytes(pdf_page(pw*.24,ph*.24))
                    raster=subprocess.run(['/usr/sbin/cupsfilter','-p',str(ppds[0]),'-i','application/pdf','-m','application/vnd.cups-raster','-o','PageSize='+name,str(path)],capture_output=True,timeout=30)
                    self.assertEqual(raster.returncode,0,raster.stderr.decode(errors='replace'))
                    output=subprocess.run([str(FILTER),'1','tester','PDF integration','1','PageSize='+name],input=raster.stdout,capture_output=True,timeout=20)
                    self.assertEqual(output.returncode,0,output.stderr.decode(errors='replace'))
                    pages=decode(output.stdout)
                    self.assertEqual([(p['media'],p['count']) for p in pages],[((10 if continuous else 11,code,length),h)]*strips)
                    for p in pages:
                        self.assertEqual(black_bits(p['rows'][h//2]),set(range(right,right+w)))

if __name__=='__main__': unittest.main()

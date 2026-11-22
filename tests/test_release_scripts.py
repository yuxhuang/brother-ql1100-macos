"""Isolated release safety tests: every destination and system mutation mocked."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ql1100-release-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.library = self.base/'Library'
        self.cups = self.base/'etc/cups'
        self.bin = self.base/'mocks'
        self.bin.mkdir()
        self.log = self.base/'calls'
        self.filter = self.library/'Printers/QL1100Native/rastertoql1100'
        self.ppd = self.library/'Printers/PPDs/Contents/Resources/Brother-QL1100-Native.ppd.gz'
        self.queue = self.cups/'ppd/QL1100_Native.ppd'
        for path in (self.filter,self.ppd,self.queue):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('QL1100Native/rastertoql1100\n')
        self.vendor = self.library/'Printers/vendor-original'
        self.vendor.write_text('preserve')
        mocks = {
            'id': 'echo 0\n',
            'lpstat': 'if [ "$1" = "$QLTEST_FAIL" ]; then exit 1; fi\nif [ "$1" = -v ]; then printf "%s\\n" "$QLTEST_SOURCE"; elif [ "$1" = -a ]; then printf "%s\\n" "$QLTEST_ACCEPTING"; elif [ "$1" = -p ]; then printf "%s\\n" "$QLTEST_PRINTERS"; else printf "%s\\n" "$QLTEST_JOBS"; fi\n',
            'lpinfo': 'if [ -n "$QLTEST_INFO_FAIL" ]; then exit 1; fi\nprintf "%s\\n" "$QLTEST_DEVICES"\n',
            'sudo': 'exec "$@"\n',
            'pkgutil': 'echo "pkgutil $*" >> "$QLTEST_LOG"\nexit 0\n',
            'lpadmin': 'echo "lpadmin $*" >> "$QLTEST_LOG"\nexit 0\n',
        }
        for name,body in mocks.items():
            path=self.bin/name
            path.write_text('#!/bin/bash\nset -eu\n'+body)
            path.chmod(0o700)
        self.env=dict(os.environ,PATH=str(self.bin)+':/usr/bin:/bin', QLTEST_INFO_FAIL='', QLTEST_DEVICES='', QLTEST_ACCEPTING='', QLTEST_SOURCE='', QLTEST_FAIL='', QLTEST_PRINTERS='',QLTEST_JOBS='',QLTEST_LOG=str(self.log))

    def run_script(self,name,args=(),**env):
        text=(ROOT/'scripts'/name).read_text()
        # Full source copies only; never source or execute the originals.
        text=text.replace('/Library',str(self.library)).replace('/etc/cups',str(self.cups))
        for absolute in ('/usr/bin/lpstat','/usr/sbin/lpadmin','/usr/sbin/pkgutil','/usr/sbin/lpinfo','/usr/bin/sudo'):
            text=text.replace(absolute,str(self.bin/Path(absolute).name))
        self.assertNotIn('/Library/',text.replace(str(self.library),''))
        self.assertNotIn('/etc/cups/',text.replace(str(self.cups),''))
        script=self.base/('isolated-'+name)
        script.write_text(text)
        return subprocess.run(['/bin/bash',str(script),*args],env=dict(self.env,**env),capture_output=True,timeout=5)

    def assert_native_preserved(self):
        self.assertTrue(self.filter.exists())
        self.assertTrue(self.ppd.exists())
        self.assertEqual(self.vendor.read_text(),'preserve')
        if self.log.exists(): self.assertNotIn('lpadmin',self.log.read_text())

    def test_uninstall_printer_query_failure_preserves_files(self):
        self.assertNotEqual(self.run_script('uninstall.sh',QLTEST_FAIL='-p').returncode,0)
        self.assert_native_preserved()

    def test_uninstall_job_query_failure_preserves_files(self):
        self.assertNotEqual(self.run_script('uninstall.sh',QLTEST_FAIL='-o').returncode,0)
        self.assert_native_preserved()

    def test_uninstall_pending_native_jobs_preserves_files(self):
        r=self.run_script('uninstall.sh',QLTEST_PRINTERS='printer QL1100_Native is idle.',QLTEST_JOBS='QL1100_Native-42 user 100')
        self.assertNotEqual(r.returncode,0)
        self.assert_native_preserved()

    def test_uninstall_other_queue_reference_preserves_files(self):
        (self.queue.parent/'other.ppd').write_text('QL1100Native/rastertoql1100')
        self.assertNotEqual(self.run_script('uninstall.sh').returncode,0)
        self.assert_native_preserved()

    def test_clean_uninstall_only_deletes_native_files(self):
        r=self.run_script('uninstall.sh',QLTEST_PRINTERS='printer QL1100_Native is idle.')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse(self.filter.exists())
        self.assertFalse(self.ppd.exists())
        self.assertEqual(self.vendor.read_text(),'preserve')
        self.assertIn('lpadmin -x QL1100_Native',self.log.read_text())

    def test_preinstall_regular_collision_preserves_files(self):
        self.assertNotEqual(self.run_script('pkg-preinstall').returncode,0)
        self.assert_native_preserved()

    def test_preinstall_symlink_collision_preserves_target(self):
        self.filter.unlink()
        self.filter.symlink_to(self.vendor)
        self.assertNotEqual(self.run_script('pkg-preinstall').returncode,0)
        self.assertEqual(self.vendor.read_text(),'preserve')
        self.assertTrue(self.filter.is_symlink())


    def test_queue_usb_discovery_creates_one_matching_device_without_printing(self):
        uri='usb://Brother/QL-1100?serial=TEST-FIXTURE'
        r=self.run_script('add-queue.sh',QLTEST_DEVICES='network ipp://other/printer\ndirect '+uri)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('lpadmin -p QL1100_Native -E -v '+uri,self.log.read_text())
        self.assertNotIn('lp ',self.log.read_text())

    def test_queue_usb_discovery_zero_or_multiple_devices_does_not_create_queue(self):
        for devices in ('','direct usb://Other/Printer?serial=TEST','direct usb://Brother/QL-1100?serial=TEST-A\ndirect usb://Brother/QL-1100c?serial=TEST-B'):
            with self.subTest(devices=devices):
                self.assertNotEqual(self.run_script('add-queue.sh',QLTEST_DEVICES=devices).returncode,0)
                self.assertFalse(self.log.exists())

    def test_queue_status_or_discovery_query_failure_does_not_create_queue(self):
        for env in ({'QLTEST_FAIL':'-a'},{'QLTEST_INFO_FAIL':'1'}):
            with self.subTest(env=env):
                self.assertNotEqual(self.run_script('add-queue.sh',**env).returncode,0)
                self.assertFalse(self.log.exists())

    def test_queue_existing_native_queue_is_never_overwritten(self):
        r=self.run_script('add-queue.sh',QLTEST_ACCEPTING='QL1100_Native accepting requests since today')
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(self.log.exists())

    def test_queue_explicit_or_existing_queue_uses_exact_supported_usb_uri(self):
        uri='usb://Brother/QL-1100c?serial=TEST-FIXTURE'
        for args,env in [((uri,),{}),(('VendorQueue',),{'QLTEST_SOURCE':'device for VendorQueue: '+uri})]:
            with self.subTest(args=args):
                if self.log.exists(): self.log.unlink()
                r=self.run_script('add-queue.sh',args=args,**env)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn('-v '+uri,self.log.read_text())

    def test_queue_invalid_uri_or_failed_existing_queue_lookup_creates_nothing(self):
        cases=[(('usb://Brother/QL-1100?serial=TEST\nother',),{}),
               (('usb://Brother/QL-1100?serial=TEST\rother',),{}),
               (('usb://Other/Printer?serial=TEST',),{}),
               (('VendorQueue',),{'QLTEST_FAIL':'-v'}),
               (('VendorQueue',),{'QLTEST_SOURCE':'device for WrongQueue: usb://Brother/QL-1100?serial=TEST'}),
               (('VendorQueue',),{'QLTEST_SOURCE':'device for VendorQueue: ipp://remote/printer'})]
        for args,env in cases:
            with self.subTest(args=args,env=env):
                self.assertNotEqual(self.run_script('add-queue.sh',args=args,**env).returncode,0)
                self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()

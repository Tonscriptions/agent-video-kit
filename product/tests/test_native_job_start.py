from __future__ import annotations
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from ai_ad_editor.browser_process import BrowserProcessJob
from ai_ad_editor.errors import AppError


@unittest.skipUnless(os.name=='nt','requires native Windows Job Objects')
class NativeJobStartTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='native-job-start-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.job=BrowserProcessJob(30);self.addCleanup(self.job.close)

    def command(self,source):return [sys.executable,'-I','-S','-B','-c',source]

    def start(self,source):
        return self.job.start(self.command(source),cwd=self.root,env=dict(os.environ),
                              stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def test_real_child_stays_suspended_until_job_assignment(self):
        marker=self.root/'ran';real=subprocess.Popen;observed=[]
        def delayed(*args,**kwargs):
            child=real(*args,**kwargs);time.sleep(.15)
            observed.append((child.poll(),marker.exists()))
            return child
        with mock.patch('ai_ad_editor.browser_process.subprocess.Popen',side_effect=delayed):
            child=self.start('from pathlib import Path;Path('+repr(str(marker))+').write_text("ran")')
        self.assertEqual(observed,[(None,False)])
        self.assertEqual(child.wait(timeout=5),0);self.assertEqual(marker.read_text(),'ran')
        receipt=self.job.close();self.assertEqual(receipt['start_policy'],'create_suspended_assign_job_resume_primary_thread')
        self.assertEqual(len(receipt['resumed_primary_threads']),1);self.assertTrue(receipt['all_children_reaped'])

    def test_twenty_actual_fast_children_cannot_exit_before_assignment(self):
        for _ in range(20):self.assertEqual(self.start('pass').wait(timeout=5),0)
        receipt=self.job.close();self.assertTrue(receipt['all_children_reaped'])
        self.assertEqual(len(receipt['resumed_primary_threads']),20)

    def test_assignment_failure_never_runs_child_and_reaps_it(self):
        marker=self.root/'must-not-exist'
        def reject(*args):ctypes.set_last_error(5);return False
        with mock.patch.object(self.job.api,'AssignProcessToJobObject',side_effect=reject):
            with self.assertRaises(AppError) as caught:
                self.start('from pathlib import Path;Path('+repr(str(marker))+').write_text("escaped")')
        self.assertEqual(caught.exception.code,'HTML_JOB_UNAVAILABLE')
        self.assertFalse(marker.exists());self.assertTrue(self.job.close()['all_children_reaped'])
        self.assertEqual(self.job.receipt['resumed_primary_threads'],[])

    def test_actual_descendant_inherits_job_and_is_reaped(self):
        marker=self.root/'child-pid'
        child_code='import time;time.sleep(60)'
        parent_code=('import subprocess,sys,time;from pathlib import Path;'
                     'p=subprocess.Popen([sys.executable,"-I","-S","-B","-c",'+repr(child_code)+'],creationflags=subprocess.CREATE_NO_WINDOW);'
                     'Path('+repr(str(marker))+').write_text(str(p.pid));time.sleep(60)')
        parent=self.start(parent_code);deadline=time.monotonic()+5
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(marker.exists());descendant=int(marker.read_text())
        self.assertIn(descendant,self.job.pids());self.assertIn(parent.pid,self.job.pids())
        receipt=self.job.close();self.assertTrue(receipt['all_children_reaped'])
        self.assertEqual(receipt['active_after_cleanup'],[]);self.assertIn(descendant,receipt['seen_pids'])


if __name__=='__main__':unittest.main()

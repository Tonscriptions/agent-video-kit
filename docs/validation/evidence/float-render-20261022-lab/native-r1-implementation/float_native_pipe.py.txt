"""Bounded native decoder/probe stdout with cancellation and owned cleanup."""
from collections import deque
import math,queue,subprocess,threading,time
from .errors import AppError
from .native_audio_clock import cancel

CHUNK_BYTES=65536
QUEUE_CHUNKS=4

def error(code,message,**details):return AppError('FLOAT_NATIVE_PIPE_'+code,message,exit_code=6,diagnostics=details or None)

class NativePipe:
    def __init__(self,command,*,cwd,cancel_file=None,timeout=300):
        if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0<timeout<=3600:
            raise error('BUDGET','原生读取超时须在0..3600秒范围')
        cancel(cancel_file);self.marker=cancel_file;self.deadline=time.monotonic()+timeout
        self.queue=queue.Queue(maxsize=QUEUE_CHUNKS);self.tail=deque(maxlen=2);self.stop=threading.Event()
        self.closed=False;self.eof=False;self.pending=b'';self.offset=0;self.maximum_queued_chunks=0;self.bytes_read=0
        self.process=subprocess.Popen(list(map(str,command)),cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,bufsize=0,creationflags=subprocess.CREATE_NO_WINDOW)
        def put(value):
            while not self.stop.is_set():
                try:
                    self.queue.put(value,timeout=.1);self.maximum_queued_chunks=max(self.maximum_queued_chunks,self.queue.qsize());return
                except queue.Full:pass
        def output():
            try:
                while not self.stop.is_set():
                    block=self.process.stdout.read(CHUNK_BYTES)
                    if not block:break
                    put(block)
            except BaseException as exc:put(exc)
            finally:put(None)
        def diagnostics():
            try:
                while block:=self.process.stderr.read(CHUNK_BYTES):self.tail.append(block)
            except OSError:pass
        self.threads=[threading.Thread(target=output,name='float-native-stdout',daemon=True),
            threading.Thread(target=diagnostics,name='float-native-stderr',daemon=True)]
        try:
            for thread in self.threads:thread.start()
        except BaseException:
            self.close();raise

    def stderr(self):return b''.join(self.tail).decode('utf8','replace')[-6000:]

    def check(self):
        if self.closed:raise error('STATE','原生读取管道已经关闭')
        cancel(self.marker)
        if time.monotonic()>self.deadline:raise error('TIMEOUT','原生读取超过时间预算')

    def pull(self):
        if self.eof:return None
        while True:
            self.check()
            try:value=self.queue.get(timeout=.1)
            except queue.Empty:continue
            if isinstance(value,BaseException):raise error('READ','原生stdout读取失败',cause=repr(value),stderr=self.stderr())
            if value is None:self.eof=True
            return value

    def chunks(self):
        if self.pending:raise error('STATE','分块迭代不能插入尚未消费的帧读取')
        while (value:=self.pull()) is not None:self.bytes_read+=len(value);yield value

    def read(self,count):
        if type(count) is not int or not 0<=count<=512*1024**2:raise error('BUDGET','单次原生读取超过512MiB预算')
        output=bytearray(count);view=memoryview(output);used=0
        while used<count:
            self.check()
            if self.offset==len(self.pending):
                self.pending=self.pull() or b'';self.offset=0
                if not self.pending:break
            size=min(count-used,len(self.pending)-self.offset)
            view[used:used+size]=memoryview(self.pending)[self.offset:self.offset+size];used+=size;self.offset+=size
        view.release()
        if used<count:del output[used:]
        self.bytes_read+=used;return output

    def finish(self):
        if not self.eof:raise error('STATE','必须消费原生EOF后才能确认执行完成')
        while self.process.poll() is None:
            self.check()
            try:self.process.wait(timeout=.1)
            except subprocess.TimeoutExpired:pass
        for thread in self.threads:thread.join(timeout=5)
        self.check()
        if any(thread.is_alive() for thread in self.threads):raise error('LIFECYCLE','原生读取线程未退出')
        if self.process.returncode:raise error('PROCESS','原生进程执行失败',exit_code=self.process.returncode,stderr=self.stderr())

    def close(self):
        if self.closed:return
        self.closed=True;self.stop.set()
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        for thread in self.threads:
            if thread.ident is not None:thread.join(timeout=5)
        for stream in (self.process.stdout,self.process.stderr):
            try:stream.close()
            except OSError:pass
        self.pending=b'';self.offset=0
        while True:
            try:self.queue.get_nowait()
            except queue.Empty:break
        if any(thread.is_alive() for thread in self.threads):raise error('LIFECYCLE','自有原生进程回收后仍有读取线程存活')

    def __enter__(self):return self
    def __exit__(self,*_):self.close()

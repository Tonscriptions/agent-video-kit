"""Actual native codec boundaries and independent fixed-code RGB/alpha checks."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_pixels import decode_frame,frame_bytes,layout
from ai_ad_editor.media import ffmpeg_path

NATIVE_CALLS=[]

class FloatPixelTests(unittest.TestCase):
    def test_all_65536_native_RGBA16_codes_survive_and_alpha_stays_independent(self):
        grid=np.arange(65536,dtype=np.uint32).reshape(64,1024)
        red=((grid*41+3)%65536).astype('<u2');green=((grid*17+117)%65536).astype('<u2')
        blue=((grid*31+71)%65536).astype('<u2');alpha=grid.astype('<u2')
        raw=np.stack((green,blue,red,alpha)).tobytes()
        actual,meta=decode_frame(raw,'gbrap16le',1024,64)
        recovered=np.rint(actual.astype(np.float64)*65535).astype(np.uint16)
        np.testing.assert_array_equal(recovered,np.stack((red,green,blue,alpha),axis=-1))
        self.assertEqual(np.unique(actual[...,3]).size,65536)
        self.assertEqual(np.unique(actual[...,0]).size,65536)
        self.assertEqual(meta['colour_transform'],'none;source-numeric-values-only')

    def test_packed_eight_bit_orders_and_padding_match_fixed_binary_examples(self):
        examples={'rgb24':bytes([17,31,255]),'bgr24':bytes([255,31,17]),'rgba':bytes([17,31,255,102]),
            'bgra':bytes([255,31,17,102]),'argb':bytes([102,17,31,255]),'abgr':bytes([102,255,31,17]),
            'rgb0':bytes([17,31,255,57]),'bgr0':bytes([255,31,17,57]),
            '0rgb':bytes([57,17,31,255]),'0bgr':bytes([57,255,31,17])}
        for fmt,raw in examples.items():
            with self.subTest(pixel_format=fmt):
                actual,meta=decode_frame(raw,fmt,1,1)
                expected=np.array([17/255,31/255,1,102/255 if meta['source_has_alpha'] else 1],dtype=np.float32)
                np.testing.assert_array_equal(actual[0,0],expected)

    def test_planar_integer_depths_endianness_and_all_native_ten_bit_levels(self):
        for bits in (9,10,12,14,16):
            maximum=(1<<bits)-1;values=np.arange(maximum+1,dtype=np.uint32)
            for endian in ('le','be'):
                with self.subTest(bits=bits,endian=endian):
                    dtype='<u2' if endian=='le' else '>u2'
                    planes=np.stack((values,maximum-values,values//2)).astype(dtype)
                    actual,_=decode_frame(planes.tobytes(),'gbrp'+str(bits)+endian,len(values),1) if len(values)<=16384 else decode_frame(planes.reshape(3,64,1024).tobytes(),'gbrp'+str(bits)+endian,1024,64)
                    recovered=np.rint(actual[...,:3].astype(np.float64)*maximum).astype(np.uint32).reshape(-1,3)
                    np.testing.assert_array_equal(recovered,np.stack((values//2,values,maximum-values),axis=-1))
                    self.assertTrue(np.all(actual[...,3]==1))

    def test_native_msb_aligned_ten_and_twelve_bit_codes_ignore_padding_bits(self):
        for bits in (10,12):
            maximum=(1<<bits)-1;shift=16-bits
            for endian in ('le','be'):
                with self.subTest(bits=bits,endian=endian):
                    values=np.array([0,1,maximum//2,maximum],dtype=np.uint16)
                    raw=np.stack([((values<<shift)|3)]*3).astype('<u2' if endian=='le' else '>u2').tobytes()
                    actual,_=decode_frame(raw,'gbrp'+str(bits)+'msb'+endian,4,1)
                    np.testing.assert_array_equal(np.rint(actual[0,:,0]*maximum).astype(np.uint16),values)

    def test_float_native_formats_keep_negative_high_and_noninteger_channels(self):
        for bits in (16,32):
            for endian in ('le','be'):
                for fmt in ('gbrapf','rgbaf'):
                    with self.subTest(bits=bits,endian=endian,fmt=fmt):
                        dtype=('<' if endian=='le' else '>')+'f'+str(bits//8)
                        expected=np.array([[-.125,5.5,.1234567,.375],[2.125,-1.25,12.75,1]],dtype=dtype)
                        stored=expected[:,[1,2,0,3]].T if fmt=='gbrapf' else expected
                        actual,meta=decode_frame(stored.tobytes(),fmt+str(bits)+endian,2,1)
                        np.testing.assert_array_equal(actual[0],expected.astype(np.float32))
                        self.assertFalse(meta['HDR_accepted']);self.assertFalse(meta['editor_integrated'])

    def test_gray_and_gray_alpha_have_explicit_luminance_and_coverage(self):
        examples=[('gray',bytes([51]),51/255,1),('ya8',bytes([51,102]),51/255,102/255),
            ('gray16be',struct.pack('>H',25700),25700/65535,1),
            ('ya16le',struct.pack('<HH',25700,12345),25700/65535,12345/65535),
            ('grayf32be',struct.pack('>f',-.25),-.25,1),
            ('yaf32le',struct.pack('<ff',2.5,.375),2.5,.375)]
        for fmt,raw,y,a in examples:
            with self.subTest(pixel_format=fmt):
                actual,_=decode_frame(raw,fmt,1,1)
                np.testing.assert_array_equal(actual[0,0],np.array([y,y,y,a],dtype=np.float32))

    def test_packed_sixteen_bit_rgb_alpha_and_big_endian_codes(self):
        for prefix,values in [('rgb48',(117,65535,12345)),('bgr48',(12345,65535,117)),
            ('rgba64',(117,65535,12345,23456)),('bgra64',(12345,65535,117,23456))]:
            for endian in ('le','be'):
                with self.subTest(pixel_format=prefix+endian):
                    raw=struct.pack(('<' if endian=='le' else '>')+'H'*len(values),*values)
                    actual,_=decode_frame(raw,prefix+endian,1,1)
                    np.testing.assert_array_equal(np.rint(actual[0,0].astype(np.float64)*65535).astype(np.uint16),
                        [117,65535,12345,23456 if len(values)==4 else 65535])

    def test_explicit_premultiplied_source_unassociates_and_zero_alpha_is_canonical(self):
        original=np.array([[[.125,-.25,2,.5],[.25,.75,.5,0]]],dtype='<f4');raw=original.tobytes()
        straight,_=decode_frame(raw,'rgbaf32le',2,1)
        actual,_=decode_frame(raw,'rgbaf32le',2,1,alpha_association='premultiplied')
        np.testing.assert_array_equal(straight,original)
        np.testing.assert_array_equal(actual[0],[[.25,-.5,4,.5],[0,0,0,0]])
        self.assertEqual(raw,original.tobytes())

    def test_actual_native_FFV1_RGBA16_decode_matches_all_original_codes(self):
        import hashlib
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='float-pixels-',dir=base) as temp:
            folder=Path(temp);w,h=128,64;grid=np.arange(w*h,dtype=np.uint32).reshape(h,w)
            source=np.stack([((grid*17+117)%65536),((grid*31+71)%65536),((grid*41+3)%65536),((grid*13)%65536)]).astype('<u2')
            path=folder/'source.gbrap16le';path.write_bytes(source.tobytes());movie=folder/'source.mkv'
            commands=[([ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','gbrap16le','-video_size',f'{w}x{h}',
                '-framerate','1','-i',str(path),'-c:v','ffv1','-level','3',str(movie)],False),
                ([ffmpeg_path(),'-v','verbose','-i',str(movie),'-map','0:v:0','-an','-pix_fmt','gbrap16le',
                '-fps_mode','passthrough','-f','rawvideo','pipe:1'],True)]
            for command,decode in commands:
                p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
                NATIVE_CALLS.append({'test':self.id(),'command':command,'exit_code':p.returncode,
                    'output_bytes':len(p.stdout),'output_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),
                    'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest()})
                self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace')[-1500:])
                if decode:
                    self.assertEqual(p.stdout,source.tobytes())
                    actual,_=decode_frame(p.stdout,'gbrap16le',w,h)
                    np.testing.assert_array_equal(np.rint(actual.astype(np.float64)*65535).astype(np.uint16),
                        np.moveaxis(source[[2,0,1,3]],0,-1))

    def test_invalid_formats_dimensions_bytes_values_and_budgets_are_rejected(self):
        for bad in ('yuv420p10le','rgb565le','gbrp32le','gray32le','gbrpf12le',None):
            with self.subTest(format=bad),self.assertRaises(AppError):layout(bad)
        for dimensions in ((0,1),(True,2),(16385,1),(8192,8192)):
            with self.subTest(dimensions=dimensions),self.assertRaises(AppError):frame_bytes('rgba',*dimensions)
        for raw in (b'',b'123',b'12345','1234',memoryview(b'12345678')[::2]):
            with self.subTest(raw=str(raw)),self.assertRaises(AppError):decode_frame(raw,'rgba',1,1)
        with self.assertRaises(AppError):decode_frame(b'1234','rgba',1,1,max_working_bytes=1)
        with self.assertRaises(AppError):decode_frame(b'1234','rgba',1,1,alpha_association='auto')
        with self.assertRaises(AppError):decode_frame(struct.pack('<HHH',1024,0,0),'gbrp10le',1,1)
        for channels in ([float('nan'),0,0,1],[float('inf'),0,0,1],[0,0,0,-.01],[0,0,0,1.01],[1,1,1,1e-44]):
            with self.subTest(channels=channels),self.assertRaises(AppError):
                decode_frame(np.array(channels,dtype='<f4').tobytes(),'rgbaf32le',1,1,alpha_association='premultiplied')

    def test_result_owns_memory_and_never_changes_callers_bytearray(self):
        raw=bytearray([17,31,255,102]);actual,_=decode_frame(raw,'rgba',1,1)
        self.assertEqual(raw,bytearray([17,31,255,102]));raw[0]=255
        self.assertAlmostEqual(float(actual[0,0,0]),17/255)
        actual[0,0,0]=0;self.assertEqual(raw[0],255)

    def test_cancellation_is_polled_during_frame_conversion(self):
        raw=bytes([17,31,255,102])*(1024*128);calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==3:raise AppError('CANCELLED','native-pixel cancellation',exit_code=8)
        with self.assertRaises(AppError) as caught:decode_frame(raw,'rgba',1024,128,cancel=cancel)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertEqual(calls,3)

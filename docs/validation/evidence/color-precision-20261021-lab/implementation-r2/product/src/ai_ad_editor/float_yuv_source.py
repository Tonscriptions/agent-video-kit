"""Original-clock native YUV reader with explicit progressive colour boundary."""
from pathlib import Path
from .errors import AppError
from .float_video_source import NativeRGBSource,cancelled
from .float_yuv import YUVSpec,decode_frame,frame_bytes,layout

class NativeYUVSource(NativeRGBSource):
    def __init__(self,*args,spec,scan=None,**kwargs):
        if not isinstance(spec,YUVSpec):raise AppError('FLOAT_YUV_COLOR','原生YCbCr读取须提供明确矩阵/量程/采样位置',exit_code=2)
        if scan!='progressive':raise AppError('FLOAT_YUV_SCAN','须明确声明逐行色度语义；隔行源需要专用适配',exit_code=2)
        self.spec=spec;super().__init__(*args,**kwargs)
        self.metadata.update(protocol='native-YCbCr-float32-frame-source-v1',
            colour_transform='explicit-YCbCr-to-RGB;source-transfer-and-primaries')

    def _additional_artifacts(self):
        return [('yuv_source_implementation',__file__),('yuv_pixels_implementation',Path(__file__).with_name('float_yuv.py'))]

    def _prepare_pixels(self,pixel_format):
        info=layout(pixel_format)
        if self.stream.get('field_order') not in (None,'unknown','progressive'):
            raise AppError('FLOAT_YUV_INTERLACED','场色度位置尚需专用适配，不能当作逐行图像',exit_code=2)
        self.bytes_per_frame=frame_bytes(pixel_format,self.width,self.height)
        return {'source_has_alpha':info.alpha,'source_color_spec':{
            'matrix':self.spec.matrix,'range':self.spec.range,'chroma_location':self.spec.chroma_location},
            'source_color_spec_overrides_tags':True,'working_transfer':'source-transfer-unmodified',
            'working_primaries':'source-primaries-unmodified','progressive_only':True,
            'scan_assumption':'caller-declared-progressive','scan_automatically_verified':False}

    def _decode_pixels(self,raw):
        return decode_frame(raw,self.pixel_format,self.width,self.height,spec=self.spec,
            alpha_association=self.alpha_association,cancel=lambda:cancelled(self.marker))

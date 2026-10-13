"""远程媒体 URL 直写模式（USE_REMOTE_MEDIA_URL）单元测试。

覆盖：
1. 开关开启时，add_videos / add_images / add_audios 草稿 path 为原始 URL，且不触发 download；
2. 开关关闭时（默认），仍走本地下载逻辑；
3. 底层 VideoMaterial / AudioMaterial 对远程 URL 的元数据支持；
4. schema 层对非 http(s) URL 的拒绝。
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.service.add_audios import (
    add_audio_to_draft,
    _prepare_audios_local_files,
    get_audio_actual_duration,
)
from src.service.add_images import add_image_to_draft, _prepare_images_local_files
from src.service.add_videos import add_video_to_draft, _prepare_videos_local_files
from src.service.easy_create_material import (
    add_video_material,
    add_image_material,
    add_audio_material,
)
from src.pyJianYingDraft.local_materials import VideoMaterial, AudioMaterial, _is_remote_path
from src.schemas.add_images import AddImagesRequest
from src.schemas.add_videos import AddVideosRequest
from src.schemas.add_audios import AddAudiosRequest
from src.schemas.easy_create_material import EasyCreateMaterialRequest
from src.utils.media import use_remote_media_url


@pytest.fixture
def draft_ctx():
    """构造测试用草稿上下文。"""
    script = MagicMock()
    script.width = 1920
    script.height = 1080
    return {
        "draft_id": "draft-test-001",
        "draft_url": "http://localhost/v1/get_draft?draft_id=draft-test-001",
        "script": script,
    }


@pytest.fixture
def enable_remote_url(monkeypatch):
    """开启远程 URL 直写模式（通过环境变量注入）。"""
    monkeypatch.setenv("USE_REMOTE_MEDIA_URL", "true")


@pytest.fixture
def disable_remote_url(monkeypatch):
    """关闭远程 URL 直写模式（默认本地下载）。"""
    monkeypatch.setenv("USE_REMOTE_MEDIA_URL", "false")


# ---------- 底层素材类 ----------


def test_is_remote_path_detects_http_urls():
    """_is_remote_path 应正确识别 http(s) URL。"""
    assert _is_remote_path("https://assets.jcaigc.cn/demo1.mp4") is True
    assert _is_remote_path("http://example.com/a.png") is True
    assert _is_remote_path("/tmp/demo1.mp4") is False
    assert _is_remote_path("C:/temp/demo1.mp4") is False
    assert _is_remote_path("file:///tmp/demo1.mp4") is False


def test_video_material_supports_remote_url_metadata():
    """底层 VideoMaterial 应支持 URL + 元数据直写。"""
    material = VideoMaterial(
        "https://assets.jcaigc.cn/demo1.mp4",
        duration=3_000_000,
        width=1280,
        height=720,
        material_type="video",
    )
    assert material.path == "https://assets.jcaigc.cn/demo1.mp4"
    assert material.duration == 3_000_000
    assert material.width == 1280
    assert material.height == 720
    assert material.material_type == "video"


def test_audio_material_supports_remote_url_duration():
    """底层 AudioMaterial 应支持 URL + duration 直写。"""
    material = AudioMaterial("https://assets.jcaigc.cn/demo1.mp3", duration=2_500_000)
    assert material.path == "https://assets.jcaigc.cn/demo1.mp3"
    assert material.duration == 2_500_000


def test_audio_material_remote_url_requires_positive_duration():
    """URL 音频缺少正数 duration 时应抛出 ValueError。"""
    with pytest.raises(ValueError, match="duration"):
        AudioMaterial("https://assets.jcaigc.cn/demo1.mp3", duration=0)


# ---------- URL 直写模式：add_*_to_draft ----------


def test_add_image_to_draft_uses_url_when_flag_on(draft_ctx, enable_remote_url):
    """开启开关时，图片素材 path 应为原始 URL，且不调用 download。"""
    segment = MagicMock()
    segment.segment_id = "seg-image-1"
    segment.material_instance.material_id = "img-mat-1"
    with patch("src.service.add_images.download") as mock_download, \
            patch("src.service.add_images.draft.VideoSegment", return_value=segment) as mock_segment:
        add_image_to_draft(
            script=draft_ctx["script"],
            track_name="image_track_1",
            draft_image_dir="/tmp/unused",
            image={
                "image_url": "https://assets.jcaigc.cn/demo1.png",
                "width": 1024,
                "height": 1024,
                "start": 0,
                "end": 1_000_000,
            },
        )
    mock_download.assert_not_called()
    material = mock_segment.call_args.kwargs["material"]
    assert material.path == "https://assets.jcaigc.cn/demo1.png"
    assert material.material_type == "photo"


def test_add_video_to_draft_uses_url_when_flag_on(draft_ctx, enable_remote_url):
    """开启开关时，VideoMaterial 入参应为用户原始 URL，且不调用 download。"""
    video_material = MagicMock(duration=2_000_000)
    segment = MagicMock(segment_id="seg-video-1")
    with patch("src.service.add_videos.download") as mock_download, \
            patch("src.service.add_videos.draft.VideoMaterial", return_value=video_material) as mock_material, \
            patch("src.service.add_videos.draft.VideoSegment", return_value=segment):
        segment_id, segment_info, actual_duration = add_video_to_draft(
            script=draft_ctx["script"],
            track_name="video_track_1",
            draft_video_dir="/tmp/unused",
            video={
                "video_url": "https://assets.jcaigc.cn/demo1.mp4",
                "start": 0,
                "end": 1_000_000,
                "duration": 1_000_000,
                "volume": 1.0,
            },
        )
    mock_download.assert_not_called()
    assert mock_material.call_args.args[0] == "https://assets.jcaigc.cn/demo1.mp4"
    assert segment_id == "seg-video-1"
    assert segment_info.id == "seg-video-1"
    assert segment_info.start == 0
    assert segment_info.end == 1_000_000
    assert actual_duration == 1_000_000


def test_add_audio_to_draft_uses_url_when_flag_on(draft_ctx, enable_remote_url):
    """开启开关时，音频素材 path 应为原始 URL，且不调用 download。"""
    segment = MagicMock()
    segment.material_instance.material_id = "audio-mat-1"
    with patch("src.service.add_audios.download") as mock_download, \
            patch("src.service.add_audios.get_audio_actual_duration", return_value=1_000_000), \
            patch("src.service.add_audios.draft.AudioSegment", return_value=segment) as mock_segment:
        add_audio_to_draft(
            script=draft_ctx["script"],
            track_name="audio_track_1",
            draft_audio_dir="/tmp/unused",
            audio={
                "audio_url": "https://assets.jcaigc.cn/demo1.mp3",
                "start": 0,
                "end": 1_000_000,
                "volume": 1.0,
            },
        )
    mock_download.assert_not_called()
    material = mock_segment.call_args.kwargs["material"]
    assert material.path == "https://assets.jcaigc.cn/demo1.mp3"


# ---------- 本地下载模式（默认）：仍走 download ----------


def test_add_video_to_draft_downloads_when_flag_off(draft_ctx, disable_remote_url):
    """关闭开关时，无 local_video_path 应触发 download，并用本地路径创建素材。"""
    video_material = MagicMock(duration=2_000_000)
    segment = MagicMock(segment_id="seg-video-1")
    with patch("src.service.add_videos.download", return_value="/tmp/local.mp4") as mock_download, \
            patch("src.service.add_videos.draft.VideoMaterial", return_value=video_material) as mock_material, \
            patch("src.service.add_videos.draft.VideoSegment", return_value=segment):
        add_video_to_draft(
            script=draft_ctx["script"],
            track_name="video_track_1",
            draft_video_dir="/tmp/videos",
            video={
                "video_url": "https://assets.jcaigc.cn/demo1.mp4",
                "start": 0,
                "end": 1_000_000,
                "duration": 1_000_000,
                "volume": 1.0,
            },
        )
    mock_download.assert_called_once_with(url="https://assets.jcaigc.cn/demo1.mp4", save_dir="/tmp/videos")
    assert mock_material.call_args.args[0] == "/tmp/local.mp4"


def test_add_image_to_draft_downloads_when_flag_off(draft_ctx, disable_remote_url):
    """关闭开关时，无 local_image_path 应触发 download。"""
    segment = MagicMock()
    segment.segment_id = "seg-image-1"
    segment.material_instance.material_id = "img-mat-1"
    with patch("src.service.add_images.download", return_value="/tmp/local.png") as mock_download, \
            patch("src.service.add_images.draft.VideoSegment", return_value=segment) as mock_segment:
        add_image_to_draft(
            script=draft_ctx["script"],
            track_name="image_track_1",
            draft_image_dir="/tmp/images",
            image={
                "image_url": "https://assets.jcaigc.cn/demo1.png",
                "width": 1024,
                "height": 1024,
                "start": 0,
                "end": 1_000_000,
            },
        )
    mock_download.assert_called_once()
    assert mock_segment.call_args.kwargs["material"] == "/tmp/local.png"


def test_add_audio_to_draft_downloads_when_flag_off(draft_ctx, disable_remote_url):
    """关闭开关时，无 local_audio_path 应触发 download。"""
    segment = MagicMock()
    segment.material_instance.material_id = "audio-mat-1"
    with patch("src.service.add_audios.download_audio_file", return_value="/tmp/local.mp3") as mock_download, \
            patch("src.service.add_audios.get_audio_actual_duration", return_value=1_000_000), \
            patch("src.service.add_audios.draft.AudioSegment", return_value=segment) as mock_segment:
        add_audio_to_draft(
            script=draft_ctx["script"],
            track_name="audio_track_1",
            draft_audio_dir="/tmp/audios",
            audio={
                "audio_url": "https://assets.jcaigc.cn/demo1.mp3",
                "start": 0,
                "end": 1_000_000,
                "volume": 1.0,
            },
        )
    mock_download.assert_called_once()
    assert mock_segment.call_args.kwargs["material"] == "/tmp/local.mp3"


# ---------- 预处理函数 ----------


def test_prepare_videos_skips_download_when_flag_on(enable_remote_url):
    """开启开关时，预处理不应调用 download。"""
    video_infos = json.dumps([{
        "video_url": "https://assets.jcaigc.cn/demo1.mp4",
        "start": 0,
        "end": 1_000_000,
    }])
    with patch("src.service.add_videos.DRAFT_CACHE", {"draft-test-001": MagicMock()}), \
            patch("src.service.add_videos.download") as mock_download:
        videos = _prepare_videos_local_files(
            "http://localhost/v1/get_draft?draft_id=draft-test-001",
            video_infos,
        )
    mock_download.assert_not_called()
    assert len(videos) == 1
    assert "local_video_path" not in videos[0]
    assert videos[0]["video_url"] == "https://assets.jcaigc.cn/demo1.mp4"


def test_prepare_images_skips_download_when_flag_on(enable_remote_url):
    """开启开关时，图片预处理不应调用 download。"""
    image_infos = json.dumps([{
        "image_url": "https://assets.jcaigc.cn/demo1.png",
        "width": 100,
        "height": 100,
        "start": 0,
        "end": 1_000_000,
    }])
    with patch("src.service.add_images.DRAFT_CACHE", {"draft-test-001": MagicMock()}), \
            patch("src.service.add_images.download") as mock_download:
        images = _prepare_images_local_files(
            "http://localhost/v1/get_draft?draft_id=draft-test-001",
            image_infos,
        )
    mock_download.assert_not_called()
    assert len(images) == 1
    assert "local_image_path" not in images[0]


def test_prepare_audios_skips_download_when_flag_on(enable_remote_url):
    """开启开关时，音频预处理不应调用 download。"""
    audio_infos = json.dumps([{
        "audio_url": "https://assets.jcaigc.cn/demo1.mp3",
        "start": 0,
        "end": 1_000_000,
        "volume": 1.0,
    }])
    with patch("src.service.add_audios.DRAFT_CACHE", {"draft-test-001": MagicMock()}), \
            patch("src.service.add_audios.download_audio_file") as mock_download:
        audios = _prepare_audios_local_files(
            "http://localhost/v1/get_draft?draft_id=draft-test-001",
            audio_infos,
        )
    mock_download.assert_not_called()
    assert len(audios) == 1
    assert "local_audio_path" not in audios[0]


def test_get_audio_actual_duration_uses_fallback_when_flag_on(enable_remote_url):
    """开启开关时，音频时长应使用 fallback，不探测本地文件。"""
    duration = get_audio_actual_duration(fallback_duration=2_000_000)
    assert duration == 2_000_000


# ---------- easy_create_material ----------


def test_easy_create_video_material_uses_url_mode(draft_ctx, enable_remote_url):
    """easy_create_material 视频分支在 URL 模式下应调用 add_video_to_draft，且不创建依赖下载。"""
    with patch("src.service.add_videos.add_video_to_draft") as mock_add, \
            patch.object(draft_ctx["script"], "add_track_ordered"):
        ok = add_video_material(draft_ctx["script"], draft_ctx["draft_id"], "https://assets.jcaigc.cn/demo1.mp4")
    assert ok is True
    mock_add.assert_called_once()
    # URL 模式下 draft_video_dir 为空字符串
    assert mock_add.call_args.args[2] == ""


def test_easy_create_image_material_uses_url_mode(draft_ctx, enable_remote_url):
    """easy_create_material 图片分支在 URL 模式下 draft_image_dir 为空。"""
    with patch("src.service.add_images.add_image_to_draft") as mock_add, \
            patch.object(draft_ctx["script"], "add_track_ordered"):
        ok = add_image_material(draft_ctx["script"], draft_ctx["draft_id"], "https://assets.jcaigc.cn/demo1.png")
    assert ok is True
    mock_add.assert_called_once()
    assert mock_add.call_args.args[2] == ""


def test_easy_create_audio_material_uses_url_mode(draft_ctx, enable_remote_url):
    """easy_create_material 音频分支在 URL 模式下 draft_audio_dir 为空。"""
    with patch("src.service.add_audios.add_audio_to_draft") as mock_add, \
            patch.object(draft_ctx["script"], "add_track"):
        ok = add_audio_material(draft_ctx["script"], draft_ctx["draft_id"], "https://assets.jcaigc.cn/demo1.mp3")
    assert ok is True
    mock_add.assert_called_once()
    assert mock_add.call_args.args[2] == ""


# ---------- Schema 校验 ----------


def test_schema_rejects_non_http_image_url():
    """图片 URL 非 http/https 时，应在 schema 阶段失败。"""
    with pytest.raises(Exception):
        AddImagesRequest(
            draft_url="http://localhost/v1/get_draft?draft_id=draft-1",
            image_infos=json.dumps([{
                "image_url": "file:///tmp/demo1.png",
                "width": 100,
                "height": 100,
                "start": 0,
                "end": 1000,
            }]),
        )


def test_schema_rejects_non_http_video_url():
    """视频 URL 非 http/https 时，应在 schema 阶段失败。"""
    with pytest.raises(Exception):
        AddVideosRequest(
            draft_url="http://localhost/v1/get_draft?draft_id=draft-1",
            video_infos=json.dumps([{
                "video_url": "C:/temp/demo1.mp4",
                "start": 0,
                "end": 1000,
            }]),
        )


def test_schema_rejects_non_http_audio_url():
    """音频 URL 非 http/https 时，应在 schema 阶段失败。"""
    with pytest.raises(Exception):
        AddAudiosRequest(
            draft_url="http://localhost/v1/get_draft?draft_id=draft-1",
            audio_infos=json.dumps([{
                "audio_url": "ftp://example.com/demo1.mp3",
                "start": 0,
                "end": 1000,
            }]),
        )


def test_easy_create_material_schema_rejects_non_http_audio_url():
    """easy_create_material 的 audio_url 应在 schema 阶段校验。"""
    with pytest.raises(Exception):
        EasyCreateMaterialRequest(
            draft_url="http://localhost/v1/get_draft?draft_id=draft-1",
            audio_url="file:///tmp/demo1.mp3",
        )


def test_easy_create_material_schema_rejects_non_http_optional_media_url():
    """easy_create_material 的 img_url/video_url 如有值必须为 http/https。"""
    with pytest.raises(Exception):
        EasyCreateMaterialRequest(
            draft_url="http://localhost/v1/get_draft?draft_id=draft-1",
            audio_url="https://assets.jcaigc.cn/test1.mp3",
            img_url="ftp://example.com/demo1.png",
        )


def test_use_remote_media_url_default_is_false(monkeypatch):
    """未设置环境变量时，开关默认关闭，保持与现有 main 行为一致。"""
    monkeypatch.delenv("USE_REMOTE_MEDIA_URL", raising=False)
    assert use_remote_media_url() is False


def test_use_remote_media_url_reads_env_case_insensitively(monkeypatch):
    """环境变量大小写不敏感，true/TRUE/True 均视为开启。"""
    monkeypatch.setenv("USE_REMOTE_MEDIA_URL", "TRUE")
    assert use_remote_media_url() is True
    monkeypatch.setenv("USE_REMOTE_MEDIA_URL", "false")
    assert use_remote_media_url() is False

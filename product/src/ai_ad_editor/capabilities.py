from __future__ import annotations

from typing import Any

from . import ENGINE_ID, VERSION
from .effects import EFFECT_CATALOG_VERSION, effect_catalog
from .media import ffmpeg_version


def build_capability_manifest() -> dict[str, Any]:
    """Return the local, test-backed capability contract for Agent planning.

    This manifest intentionally reports limits alongside supported features so an
    Agent can choose an explicit degradation or reject a plan before rendering.
    """
    local_effects = effect_catalog()
    local_effect_ids = [item["id"] for item in local_effects["effects"]]
    return {
        "manifest_version": "0.1.0",
        "engine": {"id": ENGINE_ID, "version": VERSION, "runtime": "python+ffmpeg-local", "network": "disabled"},
        "ffmpeg": {"version": ffmpeg_version()},
        "capabilities": {
            "media": {
                "status": "implemented",
                "features": ["probe", "local_ingest", "image_loop", "proxy", "thumbnail", "waveform", "scene_change", "silence", "beat_anchors", "relink_by_hash", "relink_by_unique_name", "local_template_tracking"],
                "tracking_contract": "local_template_matching_emits_confidence_and_transform_keyframes",
                "limits": ["tracking_can_drift_on_occlusion_scale_change_or_scene_cut", "tracking_requires_local_pillow_and_numpy"],
            },
            "library": {
                "status": "implemented",
                "features": ["local_index", "deterministic_token_search", "subtitle_sidecar_search", "media_facets", "duration_filter", "dimension_filter", "audio_presence_filter", "sha256_duplicate_groups", "incremental_stat_refresh", "ffmpeg_average_hash_candidates"],
                "catalog_version": "0.3.0",
                "semantic_index_version": "0.2.0",
                "search_source": "deterministic-local",
                "vector_index": False,
                "visual_similarity_contract": "optional_ffmpeg_ahash_v1_samples_with_hamming_distance_candidate_groups",
                "limits": ["no_vlm_embeddings", "no_content_understanding_without_local_model", "duplicate_detection_is_exact_hash_only", "visual_similarity_is_a_review_candidate_not_content_understanding", "incremental_refresh_trusts_file_stat_and_sidecar_signatures", "subtitle_sidecar_requires_matching_relative_stem"],
            },
            "project": {
                "status": "implemented",
                "features": ["init", "inspect", "migrate", "atomic_save", "native_process_write_lock", "snapshot", "restore", "before_mutation_snapshot"],
                "snapshot_contract": "self_contained_project_rights_lock_json",
                "migration_contract": "project_migrate_creates_before_migrate_snapshot_and_validates_candidate",
                "write_lock_contract": "operations/project-write.lock_serializes_cooperating_cli_read_modify_write_operations_and_returns_retryable_PROJECT_WRITE_LOCKED",
                "limits": ["cross_file_transaction_recovery_after_power_loss_pending", "direct_external_json_editors_do_not_join_cli_lock", "cross_version_snapshot_migration_is_limited_to_known_legacy_shapes"],
            },
            "timeline": {
                "status": "implemented",
                "features": ["multi_track", "append", "update", "remove", "split", "ripple_insert", "ripple_delete", "slip", "slide", "speed", "speed_curve", "speed_curve_reverse_reflection", "reverse", "freeze_frame", "crop", "crop_position_keyframes", "crop_size_keyframes", "nested_sequences", "nested_reverse", "nested_reverse_parent_bezier_keyframes", "nested_parent_keyframe_layers", "markers"],
                "limits": ["dynamic_crop_uses_fixed_canvas_inverse_sampling", "dynamic_crop_inverse_sampler_is_cpu_geq", "nested_static_transform_effects_blend_are_flattened", "nested_multiple_masks_use_sequential_alpha_with_coordinate_approximation", "nested_reverse_static_clips_preserve_temporal_order", "nested_reverse_leaf_keyframes_under_nonlinear_speed_are_piecewise_approximate", "nested_speed_curve_uses_analytic_boundary_mapping_and_leaf_average_speed", "audio_speed_curve_uses_piecewise_atempo_and_can_have_segment_boundaries"],
            },
            "keyframes": {
                "status": "implemented",
                "properties": ["transform.position.x", "transform.position.y", "transform.scale", "transform.rotation", "transform.opacity", "blend.opacity", "audio.volume", "audio.pan", "crop.x", "crop.y", "crop.width", "crop.height", "mask.x", "mask.y", "mask.width", "mask.height", "mask.cx", "mask.cy", "mask.radius", "mask.rx", "mask.ry", "mask.feather", "mask.points.<index>.x", "mask.points.<index>.y"],
                "interpolation": ["hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"],
                "bezier_control_points": {"forms": [["y1", "y2"], ["x1", "y1", "x2", "y2"]], "x_range": [0, 1], "execution": "normalized cubic easing sampled into a frame-evaluable FFmpeg expression"},
            },
            "effects": {
                "status": "implemented",
                "features": ["grayscale", "sepia", "blur", "boxblur", "sharpen", "brightness", "contrast", "saturation", "hue", "gamma", "color_temperature", "color_balance", "vignette", "noise", "invert", "posterize", "edgedetect", "deband", "deshake", "histeq", "gradfun", "chroma_key", "hflip", "vflip", "exposure", "color_levels", "curves", "hqdn3d", "smartblur", "avgblur", "tmix", "tblend", "lens_correction", "draw_box", "color_contrast", "solarize", "threshold", "deflicker", "dctdnoiz", "effect_catalog_cli", "effect_parameter_keyframes", "sequence_adjustments", "interval_adjustments", "lut3d_project_local"],
                "catalog_version": EFFECT_CATALOG_VERSION,
                "catalog_features": local_effect_ids,
                "catalog_source": local_effects["source"],
                "catalog_contract": "effects.list_and_effects.inspect_return_local_ffmpeg_backend_parameter_limits_and_keyframe_contract",
                "unknown_effect_policy": "RENDER_FEATURE_UNSUPPORTED",
                "effect_keyframe_contract": "brightness_contrast_saturation_hue_gamma_vignette_use_local_eq_hue_vignette_eval_frame",
                "adjustment_contract": "settings.adjustments_are_applied_after_track_compositing_in_declared_order; start_tick_and_duration_tick_define_optional_sequence_clock_intervals",
                "limits": ["unsupported_effect_parameters_use_static_value_with_warning", "new_native_filters_are_static_only_and_warn_on_parameter_keyframes", "curves_accept_one_whitelist_validated_all_master_curve", "interval_adjustments_are_video_only_and_reassembled_with_trim_concat", "lut_intensity_and_lut_library_management_pending"],
            },
            "compositing": {
                "status": "implemented",
                "masks": ["rectangle", "circle", "ellipse", "path", "polygon"],
                "blend_modes": ["normal", "multiply", "screen", "overlay", "difference", "addition", "softlight", "hardlight"],
                "features": ["mask_invert", "dynamic_feather_simple_shapes", "dynamic_feather_path_polygon", "path_cubic_segments", "blend_opacity_keyframes", "rgb_blend_math"],
                "limits": ["dynamic_path_uses_point_coordinate_keyframes", "path_point_count_is_fixed_per_clip", "path_cubic_segments_are_static_sampled_polygons", "path_polygon_feather_uses_inner_edge_distance_approximation", "blend_requires_same_canvas_inputs"],
            },
            "transitions": {
                "status": "implemented",
                "features": ["fade", "crossfade", "dissolve", "wipe", "slide", "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite", "radial", "smooth", "circleopen", "circleclose", "pixelize", "zoomin", "cover", "reveal", "diagonal", "slice", "wind", "blur", "fadegrays", "squeeze"],
                "xfade_catalog": "local_ffmpeg_xfade",
                "condition": "overlap transitions require adjacent clips with matching overlap handles; otherwise the CLI returns an explicit unsupported warning",
            },
            "subtitles": {
                "status": "implemented",
                "formats": ["srt", "vtt", "ass", "ssa"],
                "features": ["validate", "normalize_srt", "inline_drawtext", "independent_text_track", "drawtext_line_spacing", "drawtext_border_and_shadow", "drawtext_alignment", "drawtext_text_shaping", "subtitle_width_wrap_font_metrics", "local_font_advance_metrics", "fade_text_animation", "slide_text_animation", "typewriter_text_animation", "pop_text_animation", "bounce_text_animation", "independent_rotate_text_layer", "independent_text_transform_keyframes", "independent_text_masks", "independent_text_blend", "mixed_video_text_track_order", "independent_text_fade_transitions", "independent_text_spatial_transitions", "word_timing_highlight", "word_timing_source_matching"],
                "limits": ["embedded_rotate_text_is_approximated", "independent_text_complex_transition_handles_pending", "advanced_text_layout_exact_metrics_pending", "subtitle_width_wrap_falls_back_to_average_glyph_width_without_local_font", "word_timing_multiline_line_mapping_pending", "complex_bidi_layout_pending"],
            },
            "audio": {
                "status": "implemented",
                "features": ["multi_track_mix", "volume_automation", "pan_automation", "stereo_preserving_numeric_pan", "fade", "denoise", "compressor", "equalizer", "highpass", "lowpass", "dialogue_enhance", "pitch_shift", "reverb", "loudnorm", "ducking", "pan", "beat_anchors", "freeze_audio_silence_at_timeline_position"],
                "limits": ["freeze_audio_continue_uses_tail_padding", "audio_speed_curve_uses_piecewise_atempo"],
            },
            "render": {
                "status": "implemented",
                "features": ["ffmpeg_local", "output_profiles", "jsonl_progress", "cancel_file", "safe_resume"],
                "resume_contract": "rebuild_from_validated_plan_when_project_and_input_hashes_match",
                "limits": ["resume_is_not_partial_frame_checkpoint", "changed_inputs_are_rejected", "other_long_tasks_progress_pending"],
            },
            "queue": {
                "status": "implemented",
                "features": ["enqueue", "list", "inspect", "sequential_run", "explicit_retry", "cancel_pending", "cancel_running", "cancel_ack_while_project_lock_held"],
                "state_file": "operations/render-queue.json",
                "execution": "single_process_sequential_local_ffmpeg",
                "cancel_contract": "pending_cancel_confirms_when_queue_lock_is_free; running_or_lock_contended_cancel_acknowledges_marker_then_queue_run_confirms_terminal_state",
                "limits": ["distributed_workers_pending", "priority_and_fairness_pending", "cross_machine_artifacts_pending", "running_cancel_confirmation_is_eventual"],
            },
            "quality": {
                "status": "implemented",
                "features": ["stream_presence", "canvas", "duration", "av_duration_delta", "blackdetect_optional", "ebur128_optional", "target_lufs_gate", "true_peak_gate", "fail_on_black", "waveform_scope", "vectorscope", "histogram_scope", "golden_manifest_capture", "golden_manifest_verify", "golden_hash_and_metric_drift_report"],
                "scope_engine": "ffmpeg-local",
                "scope_artifacts": ["png", "json_report"],
                "defaults": {"max_av_sync_ms": 80.0, "lufs_tolerance": 2.0},
                "limits": ["true_peak_gate_requires_expensive_scan_and_ffmpeg_ebur128", "scope_images_are_review_artifacts_not_automatic_color_judgement", "golden_is_exact_for_the_captured_local_artifact_and_requires_the_same_local_media_and_settings", "cross_device_visual_thresholds_pending"],
            },
            "output": {
                "status": "implemented",
                "profiles": ["vertical", "square", "landscape", "vertical_720", "landscape_720", "custom"],
                "containers": ["mp4", "webm", "mkv"],
                "video_codecs": ["libx264", "libx265", "libvpx-vp9", "libvpx", "libaom-av1"],
                "pixel_formats": ["yuv420p", "yuv422p", "yuv444p", "yuv420p10le", "yuv422p10le", "yuv444p10le", "yuva420p"],
                "audio_codecs": ["aac", "libopus", "opus", "pcm_s16le"],
                "defaults": {"container": "mp4", "video_codec": "libx264", "audio_codec": "aac"},
                "color_metadata_contract": "settings.color_is_forwarded_as_ffmpeg_primaries_transfer_matrix_range; optional_hdr_tone_map_uses_local_zscale_float_tonemap_to_bt709",
                "tone_mapping": ["linear", "gamma", "clip", "reinhard", "hable", "mobius"],
                "alpha_contract": "yuva420p_preserves_transparent_canvas_for_webm_vpx_outputs_and_sets_alpha_mode_metadata",
                "limits": ["codec availability still depends on the local FFmpeg build", "10_bit_requires_encoder_and_container_support", "transparent_output_requires_webm_vpx_and_yuva420p", "webm requires VPX/AV1 video plus Opus audio"],
            },
            "interoperability": {
                "status": "degraded",
                "formats": ["agent-json", "otio", "kdenlive-xml"],
                "features": ["agent_json_exact_roundtrip", "otio_stack_track_gap_clip", "otio_tick_rational_time", "otio_metadata_clip_recovery", "kdenlive_profile_frame_rate", "kdenlive_blank_gap_mapping", "kdenlive_entry_frame_mapping", "local_reference_only"],
                "report_states": ["Exact", "Mapped", "Approximate", "Baked", "Unsupported", "Failed"],
                "limits": ["complex_effects_and_advanced_animation_require_explicit_mapping_report", "otio_sequential_track_cannot_represent_overlapping_clips_without_metadata", "kdenlive_effect_filters_and_text_generators_require_explicit_mapping_or_bake", "foreign_relative_references_are_resolved_against_interchange_file"],
            },
            "ai": {
                "status": "local_adapter_only",
                "features": ["offline_transformers_asr_gate", "local_flite_tts", "heuristic_highlights", "local_ad_plan", "local_template_tracking"],
                "network": "disabled",
                "tts_contract": "tts.synthesize_uses_ffmpeg_flite_and_writes_project_local_wav_without_network_or_model_download",
                "limits": ["model_weights_must_be_provided_locally", "flite_voice_inventory_depends_on_local_ffmpeg_build", "flite_adapter_is_ascii_english_only", "multilingual_model_tts_adapter_pending"],
            },
            "rights": {
                "status": "implemented",
                "schema_version": "0.2.0",
                "features": ["local_ledger", "immutable_revisions", "status_transitions", "takedown_and_dispute_gate", "channel_gate", "expiry_gate", "audit_history", "template_dependency_closure", "derived_asset_closure", "hash_snapshot_gate", "atomic_batch_update", "release_manifest", "historical_impact_report", "historical_disposition_decisions", "disposition_approval_and_cancellation_chain", "replacement_dependency_gate", "approved_replace_delete_release_block", "local_disposition_apply_with_snapshot"],
                "commands": ["rights.check", "rights.list", "rights.history", "rights.update", "rights.batch-update", "rights.impact", "rights.retract", "rights.decide", "rights.apply", "rights.export"],
                "limits": ["disposition_apply_updates_current_project_references_and_preserves_historical_media_files", "license_policy_is_field_and_status_based_without_external_network_verification"],
            },
            "policy": {
                "status": "implemented",
                "network": "disabled",
                "features": ["local_reference_validation", "project_json_remote_reference_audit", "provider_marker_detection", "remote_media_rejection"],
                "limits": ["research_and_documentation_urls_are_not_runtime_inputs", "local_models_must_be_registered_by_path_and_hash"],
            },
        },
        "policies": {
            "closed_services_enabled": False,
            "jianying_runtime_enabled": False,
            "docker_or_wsl_started": False,
            "rights_required_for_publish": True,
        },
    }

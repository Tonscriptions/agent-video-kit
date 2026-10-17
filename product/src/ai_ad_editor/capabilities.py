from __future__ import annotations

from typing import Any

from . import ENGINE_ID, VERSION
from .effects import EFFECT_CATALOG_VERSION, effect_catalog
from .media import ffmpeg_version
from .motion_presets import MOTION_PRESET_CATALOG_VERSION, motion_preset_catalog


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
                "features": ["probe", "local_ingest", "image_loop", "proxy", "thumbnail", "waveform", "scene_change", "silence", "beat_anchors", "heuristic_highlights", "highlight_rough_cut_apply", "beat_cut_timeline", "multicam_audio_sync", "multicam_switch_plan", "relink_by_hash", "relink_by_unique_name", "local_template_tracking", "local_visual_model_tracking_adapter", "local_multi_object_tracking", "native_yolov10_onnx_cpu", "native_motion_association", "tracking_clip_model_rights_dependencies", "visual_adapter_registry", "local_tracking_bind_to_visual_clip", "local_auto_reframe", "smart_cut_silence", "smart_cut_transcript_phrases", "smart_cut_linked_audio", "stabilize_vidstab_two_pass"],
                "tracking_contract": "local_template_matching_emits_confidence_and_transform_keyframes",
                "mask_tracking": {
                    "status": "implemented_with_limits",
                    "engine": "local-mask-bbox-tracking-v1",
                    "commands": ["media.track", "media.track-bind", "media.reframe"],
                    "features": ["registered_encoded_alpha_or_explicit_luma_mask", "source_clock_offset", "bounded_mask_review", "explicit_checkpoint_gate", "nonempty_dense_range_gate", "scene_cut_gate", "boundary_interpolation", "terminal_hold", "source_clip_canvas_binding", "mask_and_source_rights_closure", "failed_report_survives_metadata_rollback"],
                    "limits": ["caller_selects_mask_identity_and_extent", "bbox_is_not_pose_or_reidentification", "confidence_means_nonempty_not_model_score", "geometry_follows_supplied_mask_errors", "display_aspect_must_match", "persistent_canvas_binding_requires_existing_square_pixel_zero_rotation_CFR_source_contract", "reframe_apply_rejects_intrinsic_geometry_that_changes_display_dimensions", "interpolation_and_sampling_are_explicit_approximations", "decode_storage_budget_excludes_total_ram_and_ffmpeg", "semantic_segmentation_and_broad_natural_video_quality_unaccepted"],
                },
                "alpha_fit_padding_contract": "declared_alpha_rasters_and_transparent_output_use_RGBA_transparent_letterbox_padding_before_layer_transform_and_compositing;_ordinary_opaque_fit_keeps_black_letterbox",
                "visual_adapter_contract": "media_adapter_registers_hash_verified_local_command_json_tracking_runner;v1_validates_single_object_frames_and_v2_validates_unique_object_trajectories_before_keyframes",
                "tracking_bind_contract": "legacy_source_normalized_bake_or_explicit_source_clip_timeline_canvas_binding_with_source_hash_observations_and_render_time_recompilation",
                "canvas_tracking_binding": {
                    "status": "implemented_with_limits",
                    "version": "timeline-canvas-v1",
                    "features": ["source_clip_reference", "source_sha256_gate", "source_clock_observations", "crop_fit_fill_stretch", "animated_crop", "position_scale_anchor_rotation", "hflip_vflip", "trim_speed_reverse_speed_curve", "display_frame_freeze", "source_opacity", "output_canvas_recompile", "crop_visibility", "optional_roi_scale", "optional_source_rotation", "cycle_rejection", "detach_preserves_preview_keys", "external_export_baking"],
                    "max_display_frames": 20000,
                    "limits": ["direct_cfr_square_pixel_zero_rotation_zero_start_pts_sources", "positive_uniform_scale", "nested_parent_coordinates_require_review", "source_masks_and_occlusion_visibility_require_review", "nonlinear_geometry_effects_rejected", "observations_are_interpolated_not_new_detections", "pixel_and_performance_acceptance_is_fixture_specific"],
                },
                "reframe_contract": "local_template_or_hash_verified_command_json_track_to_normalized_target_aspect_crop_keyframes_with_confidence_and_clipping_warnings",
                "smart_cut_contract": "ffmpeg_local_silencedetect_plus_explicit_local_caption_phrase_ranges_generates_source_clock_ranges_and_can_apply_to_direct_video_and_linked_audio_clips",
                "stabilize_contract": "media_stabilize_runs_local_vidstabdetect_then_vidstabtransform_and_registers_a_project_derived_asset_with_parent_rights",
                "beat_cut_contract": "media_beat_cut_uses_local_ffmpeg_energy_anchors_to_generate_auditable_source_bounded_video_clips_and_can_apply_them_with_snapshot_validation_and_operation_record",
                "highlights_contract": "media_highlights_uses_local_scene_silence_and_optional_beat_evidence_to_write_hash_linked_candidates_and_can_apply_them_to_a_registered_video_track_with_before_snapshot_overlap_gate_validation_and_review_warning",
                "limits": ["multicam_requires_two_or_more_local_video_assets_with_audio", "multicam_uses_bounded_audio_envelope_cross_correlation_and_does_not_claim_visual_or_speaker_understanding", "multicam_low_confidence_offsets_require_waveform_review", "multicam_switch_plan_is_fixed_or_explicit_and_does_not_auto_direct_shots", "highlights_use_scene_silence_and_optional_beat_heuristics_not_semantic_or_visual_director_understanding", "highlights_apply_requires_a_registered_local_video_asset_and_explicit_target_track", "highlights_apply_rejects_existing_track_overlap_unless_replace_track_is_explicit", "highlights_apply_requires_review_for_semantics_continuity_audio_sync_and_transitions", "native_yolo_requires_explicit_python_onnx_coco80_and_local_evidence", "native_yolo_is_cpu_only_and_has_no_appearance_reid", "native_yolo_rejects_external_onnx_data_and_nonstandard_operator_domains", "native_yolo_sampling_is_ffmpeg_fps_resampled_and_budgeted_without_silent_truncation", "tracking_can_drift_on_occlusion_scale_change_or_scene_cut", "tracking_requires_local_pillow_and_numpy_when_template_engine_is_used", "visual_command_json_v1_accepts_only_normalized_single_object_bbox_frames", "visual_command_json_v2_validates_unique_object_id_trajectories", "multi_object_tracking_apply_requires_explicit_object_selection", "multi_object_tracking_all_objects_is_report_only", "multi_object_identity_requires_quality_golden_review", "visual_command_json_requires_hash_verified_local_model_and_argv_only_runner", "visual_command_json_rejects_shell_wrappers_and_network_is_disabled", "visual_runner_results_require_quality_golden_review_and_do_not_claim_model_quality", "legacy_bind_without_source_clip_references_uses_source_normalized_duration_mapping", "tracking_bind_rejects_audio_and_nested_sequence_targets", "auto_reframe_requires_direct_constant_speed_forward_clip", "auto_reframe_reports_subject_clipping_when_target_aspect_cannot_fit_bbox", "smart_cut_rejects_nested_speed_curve_and_freeze_clips", "smart_cut_transcript_matching_is_explicit_lexical_cue_granularity_and_does_not_claim_semantic_or_word_level_understanding", "smart_cut_removes_silence_only_without_transcript_phrases", "beat_cut_uses_energy_peaks_not_musical_semantic_understanding", "beat_cut_reuses_or_slows_source_clips_when_interval_exceeds_source_duration", "beat_cut_requires_registered_local_video_assets_for_timeline_apply", "stabilize_requires_ffmpeg_libvidstab", "stabilize_creates_derived_asset_and_does_not_rewrite_timeline", "stabilize_quality_depends_on_motion_and_crop_policy"],
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
            "lut_library": {
                "status": "implemented",
                "features": ["project_local_registration", "sha256_identity", "cube_metadata", "list", "inspect", "rights_ledger_registration", "lut_id_effect_reference", "hash_mismatch_gate", "cube_static_intensity_blend", "deterministic_intensity_cache"],
                "library_version": "0.1.0",
                "path": "assets/lut-library.json",
                "extensions": [".cube", ".3dl", ".csp", ".dat"],
                "limits": ["non_cube_metadata_is_extension_only", "non_cube_intensity_unsupported", "dynamic_intensity_uses_static_value", "snapshot_restore_does_not_delete_newly_copied_asset_files"],
            },
            "project": {
                "status": "implemented",
                "features": ["init", "inspect", "migrate", "recover", "atomic_save", "native_process_write_lock", "snapshot", "restore", "before_mutation_snapshot", "metadata_transaction_journal", "automatic_preflight_recovery"],
                "snapshot_contract": "self_contained_project_rights_lock_json",
                "migration_contract": "project_migrate_creates_before_migrate_snapshot_and_validates_candidate",
                "write_lock_contract": "operations/project-write.lock_serializes_cooperating_cli_read_modify_write_operations_and_returns_retryable_PROJECT_WRITE_LOCKED",
                "transaction_contract": "operations/project-transaction.json_journals_project_rights_lock_and_metadata_records_before_cooperating_cli_mutations;_prepared_journal_is_rolled_back_on_next_start_or_project_recover",
                "failure_diagnostic_contract": "normal_exception_rollback_preserves_explicitly_referenced_versioned_failed_validation_JSON_and_failed_cancelled_partial_operation_records;_crash_recovery_does_not_infer_exception_diagnostics",
                "transaction_scope": ["project.json", "rights-ledger.json", "project.lock.json", "operations_metadata", "history_metadata", "validation_metadata", "exports_metadata"],
                "limits": ["media_and_render_side_effect_files_are_reported_but_not_copied_or_deleted_by_recovery", "direct_external_json_editors_do_not_join_cli_lock_or_transaction", "cross_version_snapshot_migration_is_limited_to_known_legacy_shapes"],
            },
            "timeline": {
                "status": "implemented",
                "features": ["multi_track", "append", "update", "remove", "split", "ripple_insert", "ripple_delete", "slip", "slide", "speed", "speed_curve", "speed_curve_reverse_reflection", "speed_curve_easing", "speed_curve_bezier_handles", "bounded_speed_clock_compilation", "reverse", "freeze_frame", "crop", "crop_position_keyframes", "crop_size_keyframes", "transform_anchor", "motion_preset_keyframes", "motion_preset_apply", "nested_sequences", "isolated_sequence_compositing", "sequence_parent_canvas_transform", "sequence_parent_canvas_crop_mask", "sequence_parent_opacity_after_overlap", "sequence_group_track_z_order", "alpha_preserving_isolated_blend", "sequence_group_fade", "nested_reverse", "nested_reverse_parent_bezier_keyframes", "nested_parent_keyframe_layers", "nested_analytic_video_clock", "nested_covering_source_frame_intervals", "nested_subframe_source_trim", "nested_mapped_video_eof", "nested_global_half_open_output_frames", "nested_authored_keyframe_clock", "nested_integrated_audio_windows", "markers"],
                "limits": ["dynamic_crop_uses_fixed_canvas_inverse_sampling", "dynamic_crop_inverse_sampler_is_cpu_geq", "nested_reverse_static_clips_preserve_temporal_order", "nested_video_nonlinear_mapping_normalizes_source_display_clock_to_registered_cfr", "speed_easing_compilation_has_250_microsecond_source_clock_bound_and_1024_segment_limit", "speed_bezier_requires_finite_handles_normalized_x_and_positive_interior_speed", "source_speed_endpoint_floor_remains_0_01", "deep_animated_clock_expressions_have_explicit_4mib_limit", "nested_freeze_clock_keeps_explicit_approximation_boundaries", "isolated_sequence_canvases_use_root_canvas_dimensions", "sequence_spatial_order_is_child_composite_crop_transform_opacity_effects_mask_fade", "group_crop_and_affine_are_cpu_inverse_sampling", "isolated_compositing_is_8bit_encoded_rgb_not_linear_light_or_hdr_acceptance", "named_audio_send_return_and_group_nested_freeze_are_not_accepted", "group_slide_wipe_transitions_are_not_accepted", "nested_audio_tempo_windows_are_limited_to_16384_and_at_least_one_48khz_sample", "audio_speed_curve_uses_piecewise_atempo_and_can_have_segment_boundaries"],
            },
            "motion": {
                "status": "implemented",
                "catalog_version": MOTION_PRESET_CATALOG_VERSION,
                "source": "local-catalog",
                "engine": "timeline-keyframes",
                "features": ["list", "inspect", "apply", "aliases", "bounded_parameters", "partial_clip_range", "snapshot_before_apply", "operation_record"],
                "presets": motion_preset_catalog()["presets"],
                "limits": ["presets_write_transform_keyframes_and_do_not_generate_new_media", "fixed_catalog_does_not_claim_gui_motion_template_equivalence", "keyframe_motion_is_rendered_by_local_ffmpeg_backend"],
            },
            "templates": {
                "status": "implemented",
                "features": ["local_json_template", "typed_variables", "enum_variables", "numeric_and_string_constraints", "default_values", "exact_placeholder_type_preservation", "inline_string_placeholders", "template_snapshot", "batch_variant_input", "append_clip", "update_clip", "replace_clip", "remove_clip", "add_track", "update_track", "remove_track", "add_marker", "remove_marker"],
                "variable_types": ["any", "string", "number", "integer", "boolean", "asset", "color", "enum"],
                "limits": ["asset_type_only_validates_string_shape_before_project_asset_and_rights_checks", "complex_slot_graphs_and_conditional_operations_pending", "expression_evaluation_disabled"],
            },
            "keyframes": {
                "status": "implemented",
                "properties": ["transform.position.x", "transform.position.y", "transform.anchor.x", "transform.anchor.y", "transform.scale", "transform.rotation", "transform.opacity", "blend.opacity", "audio.volume", "audio.pan", "crop.x", "crop.y", "crop.width", "crop.height", "mask.x", "mask.y", "mask.width", "mask.height", "mask.cx", "mask.cy", "mask.radius", "mask.rx", "mask.ry", "mask.feather", "mask.points.<index>.x", "mask.points.<index>.y", "mask.segments.<index>.<from|control1|control2|to>.x", "mask.segments.<index>.<from|control1|control2|to>.y"],
                "interpolation": ["hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"],
                "bezier_control_points": {"forms": [["y1", "y2"], ["x1", "y1", "x2", "y2"]], "x_range": [0, 1], "execution": "normalized cubic easing sampled into a frame-evaluable FFmpeg expression"},
            },
            "effects": {
                "status": "implemented",
                "features": ["grayscale", "sepia", "blur", "boxblur", "sharpen", "brightness", "contrast", "saturation", "hue", "hsl", "gamma", "color_temperature", "color_balance", "color_wheel", "rgb_curves", "vignette", "noise", "invert", "posterize", "edgedetect", "deband", "deshake", "histeq", "gradfun", "chroma_key", "hflip", "vflip", "exposure", "color_levels", "curves", "hqdn3d", "smartblur", "avgblur", "tmix", "tblend", "lens_correction", "draw_box", "color_contrast", "solarize", "threshold", "deflicker", "dctdnoiz", "frame_interpolation", "effect_catalog_cli", "effect_parameter_keyframes", "sequence_adjustments", "interval_adjustments", "lut3d_project_local", "lut3d_static_intensity"],
                "catalog_version": EFFECT_CATALOG_VERSION,
                "catalog_features": local_effect_ids,
                "catalog_source": local_effects["source"],
                "catalog_contract": "effects.list_and_effects.inspect_return_local_ffmpeg_backend_parameter_limits_and_keyframe_contract",
                "unknown_effect_policy": "RENDER_FEATURE_UNSUPPORTED",
                "effect_keyframe_contract": "brightness_contrast_saturation_hue_hsl_gamma_vignette_use_local_eq_eval_frame_and_hue_frame_expressions",
                "adjustment_contract": "settings.adjustments_are_applied_after_track_compositing_in_declared_order; start_tick_and_duration_tick_define_optional_sequence_clock_intervals",
                "limits": ["unsupported_effect_parameters_use_static_value_with_warning", "new_native_filters_are_static_only_and_warn_on_parameter_keyframes", "hsl_lightness_maps_to_ffmpeg_hue_brightness", "rgb_curves_are_static_and_channel_whitelist_validated", "color_wheel_maps_to_ffmpeg_colorbalance_three_way_wheel", "curves_accept_one_whitelist_validated_all_master_curve", "interval_adjustments_are_video_only_and_reassembled_with_trim_concat", "lut_intensity_requires_project_local_cube_for_partial_strength", "frame_interpolation_uses_local_minterpolate_and_can_be_cpu_expensive", "frame_interpolation_scene_change_detection_is_heuristic"],
            },
            "compositing": {
                "status": "implemented",
                "masks": ["rectangle", "circle", "ellipse", "path", "polygon"],
                "blend_modes": ["normal", "multiply", "screen", "overlay", "difference", "addition", "softlight", "hardlight"],
                "features": ["mask_invert", "dynamic_feather_simple_shapes", "dynamic_feather_path_polygon", "path_cubic_segments", "path_curve_control_point_keyframes", "blend_opacity_keyframes", "rgb_blend_math"],
                "limits": ["dynamic_path_uses_fixed_sample_count", "path_point_count_is_fixed_per_clip", "path_cubic_segments_are_sampled_polygons", "path_polygon_feather_uses_inner_edge_distance_approximation", "ffmpeg_expression_register_limit_falls_back_to_expanded_expression_with_warning", "blend_requires_same_canvas_inputs"],
            },
            "transitions": {
                "status": "implemented",
                "features": ["fade", "crossfade", "dissolve", "wipe", "slide", "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite", "radial", "smooth", "circleopen", "circleclose", "pixelize", "zoomin", "cover", "reveal", "diagonal", "slice", "wind", "blur", "fadegrays", "squeeze", "auto_handle_contiguous_clips"],
                "xfade_catalog": "local_ffmpeg_xfade",
                "condition": "manual transitions require adjacent clips with matching overlap handles; auto_handle=true or handle_policy=auto enables contiguous clips and preserves their authored timeline length with an explicit tail-padding approximation warning",
            },
            "subtitles": {
                "status": "implemented",
                "formats": ["srt", "vtt", "ass", "ssa", "ttml"],
                "features": ["validate", "normalize_srt", "ttml_clock_parser", "inline_drawtext", "independent_text_track", "nested_authored_subtitle_clock", "nested_reverse_caption_boundaries", "external_caption_time_base", "external_caption_local_font", "nested_text_animation_and_transition_clock", "drawtext_line_spacing", "drawtext_border_and_shadow", "drawtext_alignment", "drawtext_text_shaping", "subtitle_width_wrap_font_metrics", "local_font_advance_metrics", "fade_text_animation", "slide_text_animation", "typewriter_text_animation", "native_whole_prefix_typewriter", "fixed_paragraph_typewriter_anchor", "native_typewriter_multiline_baselines", "cfr_authored_clock_typewriter_commands", "word_highlight_native_animation_composition", "pop_text_animation", "bounce_text_animation", "independent_rotate_text_layer", "independent_text_transform_keyframes", "independent_text_masks", "independent_text_blend", "mixed_video_text_track_order", "independent_text_fade_transitions", "independent_text_spatial_transitions", "word_timing_highlight", "word_timing_source_matching", "whole_paragraph_word_color_selection", "native_ffmpeg_text_metrics", "word_timing_multiline_source_mapping", "word_timing_no_double_paint", "native_multiline_paragraph_baselines", "literal_newline_without_extra_glyph", "straight_text_color_alpha", "ordered_box_shadow_border_fill_coverage", "local_ffmpeg_color_parser", "color_alpha_times_animation_and_layer_opacity", "local_asr_to_srt", "registered_native_whisper_asr", "local_font_ingest", "subtitle_cer_evaluation", "ffmpeg_whisper_cpp_asr", "subtitle_asset_registration", "subtitle_track_apply_with_snapshot"],
                "limits": ["embedded_rotate_text_is_approximated", "dynamic_raster_inline_animation_alpha_keeps_explicit_approximation", "word_highlight_native_engine_metrics_required", "word_highlight_dynamic_inline_raster_suppressed_with_warning", "word_highlight_bidi_and_internal_shaping_clusters_rejected", "word_highlight_position_stateful_expressions_rejected", "word_highlight_negative_line_spacing_requires_review", "dynamic_raster_inline_color_keeps_explicit_approximation", "text_color_8bit_encoded_rgb_not_linear_light", "random_text_colors_rejected", "external_ass_color_semantics_require_separate_acceptance", "word_highlight_measurement_budget_128_ranges_512_queries", "caption_freeze_clock_keeps_explicit_approximation", "subtitle_asset_animation_keeps_explicit_approximation", "external_caption_sequence_clock_is_default", "drawtext_frame_counter_remains_final_frame_counter", "independent_text_complex_transition_handles_pending", "advanced_text_layout_exact_metrics_pending", "subtitle_width_wrap_falls_back_to_average_glyph_width_without_local_font", "word_timing_general_overlapping_lines_pending", "multiline_box_smaller_than_paragraph_rejected", "dynamic_inline_typewriter_layout_keeps_explicit_approximation", "native_typewriter_requires_runtime_text_commands", "native_typewriter_512_graphemes_128_lines_16384_commands_4MiB", "native_typewriter_bidi_and_stateful_position_rejected", "typewriter_general_VFR_and_freeze_pending", "complex_bidi_layout_pending", "ffmpeg_whisper_requires_an_explicit_local_model_file_and_whisper_enabled_ffmpeg_build", "automatic_subtitle_apply_requires_a_registered_source_asset_for_rights_inheritance"],
            },
            "audio": {
                "status": "implemented",
                "features": ["multi_track_mix", "track_mute", "track_solo", "track_volume", "track_pan", "track_role", "volume_automation", "pan_automation", "stereo_preserving_numeric_pan", "fade", "denoise", "compressor", "equalizer", "highpass", "lowpass", "dialogue_enhance", "pitch_shift", "reverb", "loudnorm", "ducking", "pan", "beat_anchors", "freeze_audio_silence_at_timeline_position", "sequence_duration_audio_padding", "extract_audio_asset", "derived_audio_rights_inheritance", "audio_track_apply", "mid_side_separation_approximation", "separation_asset_pair", "selected_stem_audio_track_apply", "offline_adapter_registry", "adapter_hash_verification", "adapter_rights_registration", "command_json_audio_runner", "native_offline_hdemucs_vocals_accompaniment", "explicit_separation_cpu_cuda", "disk_backed_overlap_add", "float_pcm_mixture_consistency", "derived_stem_model_rights_dependency", "separation_failure_output_cleanup", "explicit_local_rubberband_r3_offline", "whole_clip_audio_time_map", "pinned_audio_stretcher_artifacts", "float32_audio_stretch_intermediate", "pcm_24_32_float_mkv_output", "unity_tempo_bypasses_buffered_stretch", "explicit_r3_together_apart_channel_mode", "channel_mode_in_immutable_audio_cache_key", "hierarchical_sequence_audio_buses", "track_effects_after_clip_sum", "container_effects_after_sequence_sum", "float_sum_without_input_normalization", "sample_grid_audio_placement", "sample_evaluated_gain_envelopes", "container_authored_audio_clock", "sequence_local_audio_solo", "audio_mute_preserves_video", "scope_local_multi_input_ducking", "audio_bus_manifest_nodes"],
                "native_separation_engine": "torchaudio-hdemucs-local-v1",
                "limits": ["extract_audio_uses_first_local_audio_stream", "extract_audio_outputs_lossless_pcm_wav", "mid_side_separation_is_phase_based_and_approximate", "true_vocal_background_separation_requires_a_registered_offline_model_adapter", "native_hdemucs_requires_existing_compatible_pt_pth_weights_native_python_torch_torchaudio_numpy_and_evidence", "native_hdemucs_is_stereo_44100_model_with_explicit_device_no_download_or_fallback", "native_hdemucs_max_7200_seconds_and_segment_1_to_20_seconds", "native_hdemucs_accompaniment_is_original_minus_model_vocals_not_independent_four_stem_export", "native_hdemucs_float_wav_can_exceed_unit_peak_and_requires_listening_license_and_broad_music_review", "legacy_demucs_uvr_openunmix_onnx_engines_without_dedicated_runner_remain_metadata_only", "unknown_audio_adapter_never_falls_back_to_mid_side", "command_json_runner_accepts_one_local_json_request_and_requires_exact_center_side_wav_outputs", "command_json_runner_rejects_cmd_and_bat_shell_wrappers", "command_json_runner_quality_and_model_license_require_project_golden_and_rights_review", "freeze_audio_continue_uses_tail_padding", "unconfigured_audio_speed_curve_uses_piecewise_atempo", "offline_r3_requires_explicit_local_executable_dependency_and_license_hashes", "offline_r3_time_map_is_not_sample_exact_local_content_alignment", "offline_r3_ultra_short_pitch_and_listening_unaccepted", "offline_r3_together_default_preserves_v26_centre_focus", "offline_r3_apart_can_degrade_mono_compatibility", "offline_r3_channel_mode_does_not_solve_ultra_short_pitch", "offline_r3_pcm_buffers_are_bounded_to_512mib_each_and_8_channels", "float_sum_can_exceed_unit_peak_without_automatic_limiter", "legacy_multitrack_mix_level_changes_when_input_normalization_is_removed", "bus_effects_except_volume_and_pan_are_static", "track_fades_require_clip_authored_envelopes_and_are_rejected", "duck_detector_is_sequence_local_and_pre_current_track_processing", "named_send_return_feedback_and_spatial_buses_are_not_implemented", "windowed_atempo_nonlinear_dc_amplitude_and_silent_gaps_remain_unaccepted"],
            },
            "render": {
                "status": "implemented",
                "features": ["ffmpeg_local", "output_profiles", "jsonl_progress", "cancel_file", "safe_resume", "float_premultiplied_alpha_media_resize", "float_premultiplied_alpha_text_resize", "float_premultiplied_alpha_affine_sampling", "float_premultiplied_alpha_dynamic_crop", "straight_alpha_independent_text_raster"],
                "resume_contract": "rebuild_from_validated_plan_when_project_and_input_hashes_match",
                "limits": ["resume_is_not_partial_frame_checkpoint", "changed_inputs_are_rejected", "other_long_tasks_progress_pending", "other_effect_warps_require_separate_alpha_sampling_review", "float_alpha_resize_uses_existing_encoded_RGB_transfer_not_linear_light", "float_affine_and_dynamic_crop_sampling_have_no_4k_throughput_or_total_memory_acceptance"],
            },
            "queue": {
                "status": "implemented",
                "features": ["enqueue", "list", "inspect", "sequential_run", "bounded_local_workers", "continue_on_error_worker_guard", "serial_metadata_commit", "explicit_retry", "cancel_pending", "cancel_running", "cancel_ack_while_project_lock_held"],
                "state_file": "operations/render-queue.json",
                "execution": "single_process_default_sequential_or_explicit_bounded_local_ffmpeg_workers",
                "worker_contract": "workers_only_render_frozen_project_snapshots_and_quality; project_outputs_operations_and_queue_metadata_commit_serially",
                "cancel_contract": "pending_cancel_confirms_when_queue_lock_is_free; running_or_lock_contended_cancel_acknowledges_marker_then_queue_run_confirms_terminal_state",
                "limits": ["workers_greater_than_one_requires_continue_on_error", "distributed_workers_pending", "priority_and_fairness_pending", "cross_machine_artifacts_pending", "running_cancel_confirmation_is_eventual"],
            },
            "quality": {
                "status": "implemented",
                "features": ["stream_presence", "canvas", "duration", "av_duration_delta", "blackdetect_optional", "ebur128_optional", "target_lufs_gate", "true_peak_gate", "fail_on_black", "waveform_scope", "vectorscope", "histogram_scope", "golden_manifest_capture", "golden_manifest_verify", "golden_hash_and_metric_drift_report", "mask_per_frame_extent", "mask_explicit_positive_negative_checks", "mask_scene_boundary_review"],
                "scope_engine": "ffmpeg-local",
                "scope_artifacts": ["png", "json_report"],
                "defaults": {"max_av_sync_ms": 80.0, "lufs_tolerance": 2.0},
                "limits": ["true_peak_gate_requires_expensive_scan_and_ffmpeg_ebur128", "scope_images_are_review_artifacts_not_automatic_color_judgement", "mask_extent_and_assertions_do_not_establish_object_identity_or_full_segmentation_quality", "mask_temporal_iou_is_not_motion_compensated", "mask_decoded_storage_budget_excludes_ffmpeg_and_total_process_ram", "golden_is_exact_for_the_captured_local_artifact_and_requires_the_same_local_media_and_settings", "cross_device_visual_thresholds_pending"],
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
                "formats": ["agent-json", "package", "otio", "kdenlive-xml", "jianying-draft-json"],
                "features": ["agent_json_exact_roundtrip", "portable_agent_project_package", "package_asset_uri_rewrite", "package_sha256_manifest", "package_path_traversal_and_symlink_gate", "otio_stack_track_gap_clip", "otio_tick_rational_time", "otio_metadata_clip_recovery", "kdenlive_profile_frame_rate", "kdenlive_blank_gap_mapping", "kdenlive_entry_frame_mapping", "jianying_plaintext_import_export", "draft_microsecond_tick_mapping", "draft_transform_crop_linear_keyframe_mapping", "draft_text_local_font_mapping", "draft_explicit_embedded_audio", "draft_strict_loss_gate", "draft_redacted_source_sidecar", "local_reference_only"],
                "report_states": ["Exact", "Mapped", "Approximate", "Baked", "Unsupported", "Failed"],
                "limits": ["package_excludes_renders_cache_operations_and_history", "package_requires_all_referenced_assets_to_exist_locally", "complex_effects_and_advanced_animation_require_explicit_mapping_report", "otio_sequential_track_cannot_represent_overlapping_clips_without_metadata", "kdenlive_effect_filters_and_text_generators_require_explicit_mapping_or_bake", "foreign_relative_references_are_resolved_against_interchange_file", "draft_profile_jianying_plaintext_v1_uses_version_360000_and_new_version_110_0_0_without_runtime_compatibility_claim", "draft_encrypted_files_are_rejected_without_decryption", "draft_private_resources_are_preserved_redacted_and_never_downloaded", "draft_text_layout_and_bezier_are_approximate", "draft_imported_media_and_fonts_have_unverified_rights", "draft_strict_mode_rejects_approximate_baked_unsupported_or_failed_before_target_write", "draft_export_uses_first_sequence_and_preserves_unmapped_parameters_in_sidecar"],
            },
            "segmentation": {
                "status": "local_adapter_only",
                "engine": "transformers-sam2-video-local-v1",
                "protocol": "agent-video-sam2-segmentation-v1",
                "commands": ["media.adapter.register", "media.adapter.inspect", "media.matting"],
                "features": ["native_torch_cpu_or_cuda", "explicit_safetensors_only", "positive_negative_points_and_boxes", "multi_object_union_or_selection", "future_frame_corrections", "explicit_scene_reset", "streamed_frames_and_pruned_memory", "binary_or_probability_alpha", "lossless_rgba_audio_and_rights_pipeline"],
                "limits": ["local_prompt_json_required", "normalized_output_coordinates_and_cfr_frame_indices", "max_8_objects_256_events_32_points_per_object_event", "512_mib_session_tensor_budget_excludes_model_and_process_memory", "no_device_fallback_or_runtime_downloads", "forward_corrections_do_not_rewrite_prior_frames", "explicit_reset_requires_new_prompts", "segmentation_probability_is_not_physical_matte", "broad_advertising_quality_and_commercial_rights_acceptance_pending"],
            },
            "inpainting": {
                "status": "local_adapter_only",
                "engine": "torchscript-lama-local-v1",
                "engines": ["torchscript-lama-local-v1", "diffusers-wan-vace-local-v1"],
                "protocol": "agent-video-lama-inpainting-v1",
                "commands": ["media.adapter.register", "media.adapter.inspect", "media.inpaint"],
                "features": ["native_torch_cpu_or_cuda", "explicit_local_torchscript", "alpha_or_luma_asset_mask", "mask_clock_and_geometry_validation", "bounded_roi_inference", "explicit_direct_or_harmonic_region_color_correction", "selected_pixel_solver_budget_and_convergence_reports", "lazy_model_load_after_mask_admission", "outside_rgb_and_source_alpha_preserved", "qtrle_rgba_decode_hash", "audio_timeline_and_rights_dependencies", "cancel_timeout_and_rollback"],
                "limitations": ["framewise_image_inpainting_not_joint_temporal_video_model", "texture_flicker_and_occlusion_require_review", "harmonic_color_correction_is_spatial_not_structural_or_temporal_repair", "no_text_prompt_generative_fill", "external_model_license_and_broad_quality_not_accepted"],
            },
            "generative_video_editing": {
                "status": "local_adapter_only",
                "engine": "diffusers-wan-vace-local-v1",
                "protocol": "agent-video-wan-vace-inpainting-v1",
                "commands": ["media.adapter.register", "media.adapter.inspect", "media.inpaint"],
                "features": ["fixed_local_wan_vace_1_3b_safetensors", "cuda_bfloat16_and_float32_vae", "staged_local_text_encoder_offload_and_release", "verbatim_prompt_and_negative_prompt_no_truncation", "seed_steps_guidance_and_conditioning", "explicit_flow_shift", "bounded_model_input_scale_1_2_4", "actual_window_input_shapes", "joint_4k_plus_1_frame_windows", "explicit_scene_boundaries_and_overlap_blending", "source_alpha_and_outside_rgb_preserved", "shared_audio_rights_cancel_and_recovery", "harmonic_region_color_correction_after_float_window_mix", "selected_pixel_solver_budget_and_convergence_reports"],
                "generation_parameters": {"flow_shift": {"default": 3.0, "minimum": 0.1, "maximum": 32.0}, "model_input_scale": {"default": 1, "choices": [1, 2, 4]}},
                "limitations": ["joint_windows_not_global_full_video_attention", "harmonic_color_correction_is_spatial_not_structural_or_temporal_repair", "temporal_seams_identity_texture_and_occlusion_need_review", "base_model_max_edge_precedes_explicit_input_scale", "scaled_array_budget_excludes_model_and_torch_memory_and_is_not_a_cuda_oom_guarantee", "no_cross_device_byte_determinism", "commercial_rights_broad_quality_and_full_jianying_parity_unaccepted"],
            },
            "matting": {
                "status": "local_adapter_only",
                "engine": "rvm-onnx-cpu-matting-v1",
                "protocol": "agent-video-rvm-matting-v1",
                "commands": ["media.adapter.register", "media.adapter.inspect", "media.matting"],
                "features": ["native_onnx_cpu", "recurrent_human_video_alpha", "soft_straight_alpha", "input_alpha_multiply", "bounded_rgba_pipeline", "qtrle_argb_mov", "rgba_decode_hash_verification", "audio_offset_and_range_preservation", "source_rotation_and_sar_normalization", "source_model_rights_dependencies", "timeline_apply", "cancel_timeout_process_cleanup"],
                "limits": ["explicit_existing_fp32_onnx_native_python_and_evidence_required", "no_download_install_or_provider_fallback", "self_contained_onnx_without_custom_domains", "sdr_rgb_8bit_only_hdr_requires_explicit_tone_map", "cfr_resampling_and_partial_tail_frame_extension_are_reported", "max_16777216_pixels_per_frame", "default_18000_frames_budget_is_explicitly_adjustable", "project_media_file_size_limit_applies_to_lossless_output", "human_only_quality_hair_motion_occlusion_scene_cuts_require_review", "python_network_guard_is_not_an_os_sandbox", "broad_advertising_quality_and_model_commercial_license_acceptance_pending"],
            },
            "ai": {
                "status": "local_adapter_only",
                "features": ["offline_transformers_asr_gate", "registered_native_whisper_asr", "asr_model_integrity_registry", "asr_long_form_attention_mask", "subtitle_cer_evaluation", "ffmpeg_whisper_cpp_asr", "local_asr_subtitle_generation", "local_flite_tts", "registered_soulx_chinese_tts", "tts_voice_transcript_registry", "tts_generated_audio_asset_and_track_apply", "tts_model_voice_rights_dependencies", "heuristic_highlights", "highlight_rough_cut_apply", "local_ad_plan", "local_ad_plan_apply", "local_template_tracking", "offline_model_registry"],
                "network": "disabled",
                "asr_contract": "asr.adapter_registers_explicit_native_python_safetensors_and_evidence_for_hash_verified_isolated_whisper_inference_and_subtitle_model_rights_dependencies_with_legacy_local_model_path_gates_preserved",
                "tts_contract": "tts.adapter_and_voice_register_explicit_local_soulx_artifacts_and_exact_transcript_then_tts.synthesize_hash_verifies_and_runs_isolated_native_python_without_network_or_downloads_and_registers_generated_wav_with_optional_audio_track_apply",
                "limits": ["model_weights_must_be_provided_locally", "registered_whisper_requires_native_python_with_local_torch_and_transformers", "whisper_segment_timing_is_not_word_alignment_or_diarization", "whisper_cer_does_not_convert_chinese_scripts", "whisper_broad_ad_corpus_acceptance_pending", "python_network_audit_is_not_an_os_sandbox", "ffmpeg_whisper_requires_whisper_enabled_local_ffmpeg", "flite_voice_inventory_depends_on_local_ffmpeg_build", "flite_adapter_is_ascii_english_only", "soulx_hf_full_bf16_weights_and_cuda_required", "soulx_single_voice_per_synthesis_and_max_2000_text_characters", "soulx_model_reference_text_and_output_rights_need_explicit_review", "soulx_emotion_dialect_multispeaker_and_broad_quality_acceptance_pending", "heuristic_highlights_do_not_claim_semantic_or_visual_director_understanding"],
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

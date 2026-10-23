"""Admission for full spatial scratch and bounded conversion tiles.

This is a conservative allocation estimate, not a process peak-RSS promise.
Shrinking a conversion tile never reduces the admitted full-image scratch.
"""

MAX_WORKING_BYTES = 768 * 1024 * 1024
CONVERSION_BYTES_PER_PIXEL = 2048


def admit_spatial(*, surface_bytes, pixels, tile_pixels, tracks_bytes,
                  retained_table_bytes, max_working_bytes, error,
                  line_scratch_bytes=1048576):
    for value in (surface_bytes, pixels, tracks_bytes, line_scratch_bytes):
        if type(value) is not int or value < 0:
            raise error('BUDGET', '空间工作区大小无效')
    if pixels < 1 or surface_bytes != pixels * 16:
        raise error('BUDGET', '空间工作区表面大小无效')
    if type(tile_pixels) is not int or not 1 <= tile_pixels <= 262144:
        raise error('BUDGET', '分块大小无效')
    if (type(max_working_bytes) is not int or not 1 <= max_working_bytes <= MAX_WORKING_BYTES
            or type(retained_table_bytes) is not int or retained_table_bytes < 0):
        raise error('BUDGET', '工作区预算无效')
    overhead = max(1048576, line_scratch_bytes)
    fixed = 6 * surface_bytes + retained_table_bytes + 4 * tracks_bytes + overhead
    capacity = (max_working_bytes - fixed) // CONVERSION_BYTES_PER_PIXEL
    if capacity < 1:
        raise error('BUDGET', '完整空间工作区、保留表及最小转换分块估算超限')
    requested = min(tile_pixels, 16384, pixels)
    admitted = min(requested, capacity)
    estimate = fixed + admitted * CONVERSION_BYTES_PER_PIXEL
    return admitted, estimate, {
        'workspace_protocol': 'full-spatial-scratch-adaptive-conversion-tile-v1',
        'requested_tile_pixels': tile_pixels,
        'effective_requested_tile_pixels': requested,
        'admitted_tile_pixels': admitted,
        'adaptive_tile_reduction': admitted < requested,
        'fixed_spatial_working_bytes': fixed,
        'conversion_scratch_bytes': admitted * CONVERSION_BYTES_PER_PIXEL,
        'line_scratch_reservation_bytes': overhead,
        'max_working_bytes': max_working_bytes,
        'estimated_bytes_are_peak_RSS': False,
    }

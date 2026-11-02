"""Fresh frozen-source attribution, not a controlled throughput comparison.

Copies and verifies archived r7 sources, creates separate timing and event-count
instrumentation builds, and compares every output to the accepted r7 CLI.
No product sources or prior reports are modified. Run from any directory:
  python scripts/profile_faster_than_libflac.py --name revision7-actual
  python scripts/profile_faster_than_libflac.py --name candidate1-profile --identity validation/evidence/faster-than-libflac-candidate1.json --archive validation/baselines/faster-than-libflac-candidate1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / 'validation/evidence/speed-first-candidate-revision7.json'
COARSE = False
FUNCTIONS = [
    ('encoder_frame.mbt', 'encode_frame', 'format, planes, number, variable_block, effort'),
    ('encoder_frame.mbt', 'encoder_subframe', 'samples, width, effort'),
    ('encoder_lpc.mbt', 'encoder_lpc_models', 'samples, max_order'),
    ('encoder_frame.mbt', 'encoder_predictor', 'samples, coefficients, shift'),
    ('encoder_frame.mbt', 'encoder_residual_plan', 'samples, predictor, max_partition, workspace~'),
    ('encoder_search.mbt', 'encoder_adaptive_residual_plan', 'samples, predictor, workspace~'),
    ('encoder_search.mbt', 'encoder_partition_lower_bound', 'widths, predictor, order, stop_at~'),
    ('encoder_search.mbt', 'encoder_lpc_shortlist', 'samples, models, depth, limit~'),
    ('encoder_frame.mbt', 'encoder_write_subframe', 'out, sub'),
    ('md5.mbt', 'Md5::update', 'self, bytes'),
    ('md5.mbt', 'md5_update_frame', 'state, frame'),
    ('wav.mbt', 'frame_pcm', 'frame, wav~'),
    ('pcm_input.mbt', 'PcmInput::next', 'self'),
]
COUNTERS = [
    'coarse_plan_calls', 'lower_bound_visited_samples', 'lower_bound_early_stops',
    'adaptive_coarse_early_return', 'refinements', 'width_array_elements',
    'residual_constant_scan_samples', 'residual_quotient_scan_samples',
    'residual_quotient_additions', 'residual_output_arrays', 'residual_output_elements',
    'predictor_visited_samples', 'predictor_multiply_adds', 'predictor_illegal_stops',
    'scratch_quotient_arrays', 'scratch_quotient_elements', 'choice_arrays',
    'choice_array_elements', 'rice_leaf_records', 'lpc_pool_models',
    'full_pool_decisions', 'full_pool_models', 'shortlist_decisions', 'shortlist_pool_models',
    'lpc_candidate_attempts', 'lpc_valid_candidates', 'shortlist_backfill_attempts',
    'shortlist_model_scores', 'shortlist_probe_samples', 'shortlist_probe_invalid_stops',
    'pcm_int64_copy_elements', 'wasted_shift_copy_elements', 'stereo_side_elements',
    'stereo_mid_elements', 'subframe_winner_constant', 'subframe_winner_verbatim',
    'subframe_winner_fixed', 'subframe_winner_lpc', 'emitted_constant',
    'emitted_verbatim', 'emitted_fixed', 'emitted_lpc', 'frame_pcm_bytes',
    'budget_rejections', 'budget_folded_scan_samples', 'budget_tree_nodes',
    'budget_header_level_stops', 'budget_lower_bound_partition_visits',
    'budget_lower_bound_early_stops', 'budget_lower_bound_level_skips',
    'budget_exact_levels', 'budget_exact_partitions', 'budget_exact_early_stops',
    'budget_winner_updates', 'budget_selected_records', 'lazy_prefix_column_builds',
    'lazy_prefix_build_samples', 'lazy_prefix_array_requests', 'lazy_prefix_array_elements',
    'crc8_bytes', 'crc16_bytes', 'crc_body_copy_bytes', 'crc_header_copy_bytes',
    'prefix_query_calls',
    'double_predictor_tiles', 'double_predictor_computed_samples',
    'double_predictor_multiply_adds', 'double_predictor_checked_samples',
    'double_predictor_illegal_stops', 'rice_ranking_decisions',
    'rice_ranking_pool_models',
    'writer_reserve_copy_bytes',
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def count(name, expression='1L'):
    return f'profile_count({COUNTERS.index(name)}, {expression})'


def transform_function(path: Path, name: str, transform):
    text = path.read_text(encoding='utf-8')
    start = text.index('fn ' + name + '(')
    end = text.find('\n///|', start)
    if end < 0:
        end = len(text)
    text = text[:start] + transform(text[start:end]) + text[end:]
    path.write_text(text, encoding='utf-8')


def replace_once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new, 1)


def add_events(source: Path):
    if COARSE:
        add_coarse_events(source)
        return
    if any(name == 'encoder_budget_residual_plan' for _, name, _ in FUNCTIONS):
        def prefix(t):
            t = replace_once(t, '  if !scratch.ready[parameter] {', '  if !scratch.ready[parameter] {\n    ' + count('lazy_prefix_column_builds') + '\n    ' + count('lazy_prefix_build_samples', 'size.to_int64()'))
            return replace_once(t, '      scratch.prefixes[parameter] = Array::make', '      ' + count('lazy_prefix_array_requests') + '\n      ' + count('lazy_prefix_array_elements', '(size + 1).to_int64()') + '\n      scratch.prefixes[parameter] = Array::make')
        transform_function(source / 'encoder_budget_plan.mbt', 'encoder_prefix_quotient', prefix)

        def budget(t):
            t = replace_once(t, '    for i = start;', '    ' + count('budget_folded_scan_samples', '(end - start).to_int64()') + '\n    for i = start;')
            t = replace_once(t, '  for node = leaves - 1;', '  ' + count('budget_tree_nodes', '(leaves - 1).to_int64()') + '\n  for node = leaves - 1;')
            t = replace_once(t, '    if 6L + 4L * parts.to_int64() >= best_bits {', '    if 6L + 4L * parts.to_int64() >= best_bits {\n      ' + count('budget_header_level_stops'))
            t = replace_once(t, '      let count = if p == 0', '      ' + count('budget_lower_bound_partition_visits') + '\n      let count = if p == 0')
            t = replace_once(t, '      if lower >= best_bits {', '      if lower >= best_bits {\n        ' + count('budget_lower_bound_early_stops'))
            t = replace_once(t, '    if lower >= best_bits {\n      continue', '    if lower >= best_bits {\n      ' + count('budget_lower_bound_level_skips') + '\n      continue')
            t = replace_once(t, '    let mut bits0 =', '    ' + count('budget_exact_levels') + '\n    let mut bits0 =')
            t = replace_once(t, '      let start = if p == 0', '      ' + count('budget_exact_partitions') + '\n      let start = if p == 0')
            t = replace_once(t, '      if bits0 >= best_bits && bits1 >= best_bits {', '      if bits0 >= best_bits && bits1 >= best_bits {\n        ' + count('budget_exact_early_stops'))
            return replace_once(t, '      let selected = Array::makei', '      ' + count('budget_winner_updates') + '\n      ' + count('budget_selected_records', 'parts.to_int64()') + '\n      let selected = Array::makei')
        transform_function(source / 'encoder_budget_plan.mbt', 'encoder_budget_residual_plan', budget)
    def lower(t):
        t = replace_once(t, '    for i = start;', '    ' + count('lower_bound_visited_samples', '(end - start).to_int64()') + '\n    for i = start;')
        return replace_once(t, '      return total', '      ' + count('lower_bound_early_stops') + '\n      return total')
    transform_function(source / 'encoder_search.mbt', 'encoder_partition_lower_bound', lower)

    def adaptive(t):
        t = replace_once(t, '  let coarse =', '  ' + count('coarse_plan_calls') + '\n  let coarse =')
        t = replace_once(t, '    return coarse', '    ' + count('adaptive_coarse_early_return') + '\n    return coarse')
        t = replace_once(t, '  let widths =', '  ' + count('width_array_elements', 'size.to_int64()') + '\n  let widths =')
        return replace_once(t, '      return encoder_residual_plan(', '      ' + count('refinements') + '\n      return encoder_residual_plan(')
    transform_function(source / 'encoder_search.mbt', 'encoder_adaptive_residual_plan', adaptive)

    def residual(t):
        t = replace_once(t, '      if samples[i] != value {', '      ' + count('residual_constant_scan_samples') + '\n      if samples[i] != value {')
        t = replace_once(t, '      workspace.push(Array::make(31, 0L))', '      ' + count('scratch_quotient_arrays') + '\n      ' + count('scratch_quotient_elements', '31L') + '\n      workspace.push(Array::make(31, 0L))')
        t = replace_once(t, '    for i = start;', '    ' + count('residual_quotient_scan_samples', '(end - start).to_int64()') + '\n    for i = start;')
        t = replace_once(t, '        quotients[k] += folded', '        ' + count('residual_quotient_additions') + '\n        quotients[k] += folded')
        t = replace_once(t, '    nodes.push(', '    ' + count('rice_leaf_records') + '\n    nodes.push(')
        return replace_once(t, '  let choices0 =', '  ' + count('choice_arrays', '2L') + '\n  ' + count('choice_array_elements', '(nodes.length() * 4).to_int64()') + '\n  let choices0 =')
    transform_function(source / 'encoder_frame.mbt', 'encoder_residual_plan', residual)

    def predictor(t):
        t = replace_once(t, '  let residual =', '  ' + count('residual_output_arrays') + '\n  ' + count('residual_output_elements', 'samples.length().to_int64()') + '\n  let residual =')
        t = replace_once(t, '    let mut prediction =', '    ' + count('predictor_visited_samples') + '\n    ' + count('predictor_multiply_adds', 'order.to_int64()') + '\n    let mut prediction =')
        return replace_once(t, '      return None', '      ' + count('predictor_illegal_stops') + '\n      return None')
    transform_function(source / 'encoder_frame.mbt', 'encoder_predictor', predictor)

    def shortlist(t):
        t = replace_once(t, '  for model in models {', '  for model in models {\n    ' + count('shortlist_model_scores'))
        t = replace_once(t, '      let i = order +', '      ' + count('shortlist_probe_samples') + '\n      let i = order +')
        return replace_once(t, '        valid = false', '        ' + count('shortlist_probe_invalid_stops') + '\n        valid = false')
    transform_function(source / 'encoder_search.mbt', 'encoder_lpc_shortlist', shortlist)

    def subframe(t):
        t = replace_once(t, '      samples.map(x => x >> wasted)', '      ' + count('wasted_shift_copy_elements', 'size.to_int64()') + '\n      samples.map(x => x >> wasted)')
        t = replace_once(t, '    let candidates = if shortlist {',
                         '    ' + count('lpc_pool_models', 'models.length().to_int64()') + '\n'
                         '    if shortlist {\n      ' + count('shortlist_decisions') + '\n      ' + count('shortlist_pool_models', 'models.length().to_int64()') + '\n    } else {\n      ' + count('full_pool_decisions') + '\n      ' + count('full_pool_models', 'models.length().to_int64()') + '\n    }\n    let candidates = if shortlist {')
        t = replace_once(t, '    let mut valid_candidates = 0', '    let mut profile_attempt = 0\n    let mut valid_candidates = 0')
        t = replace_once(t, '      let order = model.coefficients.length()',
                         '      if shortlist && profile_attempt >= ENCODER_LPC_SHORTLIST { ' + count('shortlist_backfill_attempts') + ' }\n      profile_attempt += 1\n      ' + count('lpc_candidate_attempts') + '\n      let order = model.coefficients.length()')
        return replace_once(t, '          valid_candidates += 1', '          ' + count('lpc_valid_candidates') + '\n          valid_candidates += 1')
    transform_function(source / 'encoder_frame.mbt', 'encoder_subframe', subframe)

    def frame(t):
        t = replace_once(t, '    original.push(', '    ' + count('pcm_int64_copy_elements', 'size.to_int64()') + '\n    original.push(')
        t = replace_once(t, '    let side =', '    ' + count('stereo_side_elements', 'size.to_int64()') + '\n    let side =')
        return replace_once(t, '    let mid =', '    ' + count('stereo_mid_elements', 'size.to_int64()') + '\n    let mid =')
    transform_function(source / 'encoder_frame.mbt', 'encode_frame', frame)


def add_coarse_events(source: Path):
    """Coarse counters selected from the actual archived predictor architecture."""
    def crc(t):
        body = t.index('{') + 1
        return t[:body] + '\n  if width == 8 { ' + count('crc8_bytes', '(end - start).to_int64()') + ' } else { ' + count('crc16_bytes', '(end - start).to_int64()') + ' }\n' + t[body:]
    transform_function(source / 'frame.mbt', 'frame_crc', crc)

    has_predict_into = 'fn encoder_predict_into(' in (source / 'encoder_frame.mbt').read_text(encoding='utf-8')
    def predictor(t):
        t = replace_once(t, '    let mut prediction =', '    ' + count('predictor_visited_samples') + '\n    ' + count('predictor_multiply_adds', 'order.to_int64()') + '\n    let mut prediction =')
        token = '      return false' if has_predict_into else '      return None'
        return replace_once(t, token, '      ' + count('predictor_illegal_stops') + '\n' + token)
    transform_function(source / 'encoder_frame.mbt', 'encoder_predict_into' if has_predict_into else 'encoder_predictor', predictor)
    if 'fn encoder_predict_double_into(' in (source / 'encoder_frame.mbt').read_text(encoding='utf-8'):
        def double_predictor(t):
            token = '    for i = 0; i < count; i = i + 1 {'
            # Only the first loop: a whole tile is computed before residual
            # validity is inspected, including a possible failed suffix.
            assert token in t
            t = t.replace(token, '    ' + count('double_predictor_tiles') + '\n    ' +
                          count('double_predictor_computed_samples', 'count.to_int64()') + '\n    ' +
                          count('double_predictor_multiply_adds', 'count.to_int64() * order.to_int64()') + '\n' + token, 1)
            t = replace_once(t, '      let prediction =', '      ' + count('double_predictor_checked_samples') + '\n      let prediction =')
            return replace_once(t, '        return false', '        ' + count('double_predictor_illegal_stops') + '\n        return false')
        transform_function(source / 'encoder_frame.mbt', 'encoder_predict_double_into', double_predictor)

    def prefix(t):
        t = replace_once(t, '  if !scratch.ready[parameter] {', '  ' + count('prefix_query_calls') + '\n  if !scratch.ready[parameter] {\n    ' + count('lazy_prefix_column_builds') + '\n    ' + count('lazy_prefix_build_samples', 'size.to_int64()'))
        return replace_once(t, '      scratch.prefixes[parameter] = Array::make', '      ' + count('lazy_prefix_array_requests') + '\n      ' + count('lazy_prefix_array_elements', '(size + 1).to_int64()') + '\n      scratch.prefixes[parameter] = Array::make')
    planner = source / 'encoder_budget_plan.mbt'
    if planner.exists():
        if 'fn encoder_prepare_leaf_prefixes(' in planner.read_text(encoding='utf-8'):
            def leaf_queries(t):
                return replace_once(t, '  let prefix = scratch.prefixes[parameter]',
                    '  ' + count('prefix_query_calls') + '\n  let prefix = scratch.prefixes[parameter]')
            def leaf_columns(t):
                columns = '(if k2 >= 0 { 3L } else if k1 >= 0 { 2L } else { 1L })'
                t = replace_once(t, '  let a = scratch.prefixes[k0]',
                    '  ' + count('lazy_prefix_column_builds', columns) + '\n  ' +
                    count('lazy_prefix_build_samples', 'size.to_int64() * ' + columns) +
                    '\n  let a = scratch.prefixes[k0]')
                return replace_once(t, '        scratch.prefixes[k] = Array::make',
                    '        ' + count('lazy_prefix_array_requests') + '\n        ' +
                    count('lazy_prefix_array_elements', '(leaves + 1).to_int64()') +
                    '\n        scratch.prefixes[k] = Array::make')
            transform_function(planner, 'encoder_prefix_quotient', leaf_queries)
            transform_function(planner, 'encoder_prepare_leaf_prefixes', leaf_columns)
        else:
            transform_function(planner, 'encoder_prefix_quotient', prefix)

    def subframe(t):
        rice = '    let candidates = if rice_irregular {' in t
        candidate_token = '    let candidates = if rice_irregular {' if rice else '    let candidates = if shortlist {'
        rice_branch = ('    if rice_irregular {\n      ' + count('rice_ranking_decisions') + '\n      ' + count('rice_ranking_pool_models', 'models.length().to_int64()') + '\n    } else ' if rice else '    ')
        t = replace_once(t, candidate_token,
                         '    ' + count('lpc_pool_models', 'models.length().to_int64()') + '\n'
                         + rice_branch + 'if shortlist {\n      ' + count('shortlist_decisions') + '\n      ' + count('shortlist_pool_models', 'models.length().to_int64()') + '\n    } else {\n      ' + count('full_pool_decisions') + '\n      ' + count('full_pool_models', 'models.length().to_int64()') + '\n    }\n' + candidate_token)
        t = replace_once(t, '    let mut valid_candidates = 0', '    let mut profile_attempt = 0\n    let mut valid_candidates = 0')
        t = replace_once(t, '      let order = model.coefficients.length()',
                         '      if ' + ('(shortlist || rice_irregular)' if rice else 'shortlist') + ' && profile_attempt >= ENCODER_LPC_SHORTLIST { ' + count('shortlist_backfill_attempts') + ' }\n      profile_attempt += 1\n      ' + count('lpc_candidate_attempts') + '\n      let order = model.coefficients.length()')
        return replace_once(t, '          valid_candidates += 1', '          ' + count('lpc_valid_candidates') + '\n          valid_candidates += 1')
    transform_function(source / 'encoder_frame.mbt', 'encoder_subframe', subframe)

    def frame(t):
        if '  let header = Bytes::from_array(out.bytes)' in t:
            t = replace_once(t, '  let header = Bytes::from_array(out.bytes)', '  ' + count('crc_header_copy_bytes', 'out.bytes.length().to_int64()') + '\n  let header = Bytes::from_array(out.bytes)')
            return replace_once(t, '  let body = Bytes::from_array(out.bytes)', '  ' + count('crc_body_copy_bytes', 'out.bytes.length().to_int64()') + '\n  let body = Bytes::from_array(out.bytes)')
        assert 'out.crc(8)' in t and 'out.crc(16)' in t and 'out.finish()' in t, 'Unknown writer architecture'
        return t
    transform_function(source / 'encoder_frame.mbt', frame_entry(source / 'encoder_frame.mbt'), frame)
    frame_source = (source / 'encoder_frame.mbt').read_text(encoding='utf-8')
    if 'fn EncoderBits::crc(' in frame_source:
        def writer_crc(t):
            return replace_once(t, '  self.materialize()', '  self.materialize()\n  if width == 8 { ' + count('crc8_bytes', 'self.length.to_int64()') + ' } else { ' + count('crc16_bytes', 'self.length.to_int64()') + ' }')
        transform_function(source / 'encoder_frame.mbt', 'EncoderBits::crc', writer_crc)
        def reserve(t):
            return replace_once(t, '    for i = 0; i < self.length;', '    ' + count('writer_reserve_copy_bytes', 'self.length.to_int64()') + '\n    for i = 0; i < self.length;')
        transform_function(source / 'encoder_frame.mbt', 'EncoderBits::reserve', reserve)


def frame_entry(path):
    text = path.read_text(encoding='utf-8')
    for name in ['encode_frame_wide_validated', 'encode_frame_validated', 'encode_frame']:
        if 'fn ' + name + '(' in text:
            return name
    raise ValueError('No recognized frame encoder entry')


def instrument(source: Path, mode: str):
    for package in [source / 'moon.pkg', source / 'cmd/moonflac/moon.pkg']:
        package.write_text(package.read_text(encoding='utf-8').replace('import {', 'import {\n  "moonbitlang/core/bench",', 1), encoding='utf-8')
    if mode == 'events':
        add_events(source)
    names = [name for _, name, _ in FUNCTIONS] + ['cli_read_chunk', 'cli_execute_encode']
    wrappers = [
        f'let profile_inclusive : Array[Double] = Array::make({len(names)}, 0.0)',
        f'let profile_exclusive : Array[Double] = Array::make({len(names)}, 0.0)',
        f'let profile_calls : Array[Int64] = Array::make({len(names)}, 0L)',
        'let profile_children : Array[Double] = []',
        f'let profile_counts : Array[Int64] = Array::make({len(COUNTERS)}, 0L)',
        'pub fn profile_push() -> Unit { profile_children.push(0.0) }',
        'fn profile_count(i : Int, n : Int64) -> Unit { profile_counts[i] += n }',
        'pub fn profile_end(i : Int, elapsed : Double) -> Unit {\n'
        '  let children = profile_children.pop().unwrap()\n'
        '  profile_inclusive[i] += elapsed\n  profile_exclusive[i] += elapsed - children\n'
        '  profile_calls[i] += 1L\n  if !profile_children.is_empty() {\n'
        '    let last = profile_children.length() - 1\n    profile_children[last] += elapsed\n  }\n}',
    ]
    for index, (file, name, args) in enumerate(FUNCTIONS):
        path = source / file
        text = path.read_text(encoding='utf-8')
        start = text.index('fn ' + name + '(')
        if text[max(0, start - 4):start] == 'pub ': start -= 4
        end = text.index('{', start)
        signature = text[start:end]
        impl = name + '_profile_impl'
        text = text[:start] + text[start:].replace('fn ' + name + '(', 'fn ' + impl + '(', 1)
        path.write_text(text, encoding='utf-8')
        pre = '  profile_push()\n  let started = @bench.monotonic_clock_start()\n' if mode == 'timing' else ''
        post = f'  profile_end({index}, @bench.monotonic_clock_end(started))\n' if mode == 'timing' else f'  profile_calls[{index}] += 1L\n'
        if mode == 'events' and name in ['encoder_subframe', 'encoder_write_subframe']:
            subject, prefix = ('result', 'subframe_winner') if name == 'encoder_subframe' else ('sub', 'emitted')
            post += f'  if {subject}.kind == 0 {{ {count(prefix + "_constant")} }}\n'
            post += f'  else if {subject}.kind == 1 {{ {count(prefix + "_verbatim")} }}\n'
            post += f'  else if {subject}.kind < 32 {{ {count(prefix + "_fixed")} }}\n'
            post += f'  else {{ {count(prefix + "_lpc")} }}\n'
        if mode == 'events' and name == 'frame_pcm': post += '  ' + count('frame_pcm_bytes', 'result.length().to_int64()') + '\n'
        if mode == 'events' and name == 'encoder_budget_residual_plan': post += '  if result is None { ' + count('budget_rejections') + ' }\n'
        wrappers.append(signature + '{\n' + pre + f'  let result = {impl}({args})\n' + post + '  result\n}')
    wrappers.append('pub fn profile_report() -> Unit {\n' + ''.join(
        f'  println("PROFILE {name} \\{{profile_inclusive[{i}]}} \\{{profile_exclusive[{i}]}} \\{{profile_calls[{i}]}}")\n'
        for i, name in enumerate(names)) + ''.join(
        f'  println("EVENT {name} \\{{profile_counts[{i}]}}")\n' for i, name in enumerate(COUNTERS)) + '\n}')
    (source / 'profile.mbt').write_text('\n\n///|\n'.join(wrappers), encoding='utf-8')
    main = source / 'cmd/moonflac/main.mbt'
    text = main.read_text(encoding='utf-8')
    for name, args, signature, idx in [
        ('read_chunk', 'bytes, length', 'fn read_chunk(bytes : FixedArray[Byte], length : Int) -> Int', len(FUNCTIONS)),
        ('execute_encode', 'options', 'fn execute_encode(options : Options) -> Unit raise', len(FUNCTIONS) + 1),
    ]:
        text = text.replace('fn ' + name + '(', 'fn ' + name + '_profile_impl(', 1)
        pre = '  @flac.profile_push()\n  let started = @bench.monotonic_clock_start()\n'
        post = f'  @flac.profile_end({idx}, @bench.monotonic_clock_end(started))\n'
        text += '\n///|\n' + signature + '{\n' + pre + f'  let result = {name}_profile_impl({args})\n' + post + '  result\n}\n'
    text = replace_once(text, '@sys.exit(status)', '@flac.profile_report()\n  @sys.exit(status)')
    main.write_text(text, encoding='utf-8')


def source_hashes(source):
    return {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file() and '_build' not in p.relative_to(source).parts and '.mooncakes' not in p.relative_to(source).parts}


def instrumented_counters(source):
    indices = set()
    for path in source.glob('*.mbt'):
        indices.update(int(i) for i in re.findall(r'profile_count\((\d+),', path.read_text(encoding='utf-8')))
    return [COUNTERS[i] for i in sorted(indices)]


def build(source, work, mode):
    commands = {}
    log = work / (mode + '-build.log')
    with log.open('w', encoding='utf-8') as stream:
        proc = subprocess.Popen(['moon', '-v', 'build', '--target', 'native', '--release', 'cmd/moonflac'], cwd=source, stdout=stream, stderr=subprocess.STDOUT)
        parent = psutil.Process(proc.pid)
        while proc.poll() is None:
            try: children = parent.children(recursive=True)
            except psutil.NoSuchProcess: children = []
            for child in children:
                try:
                    if child.name().lower() in ['cl.exe', 'link.exe', 'clang.exe', 'gcc.exe']:
                        commands[str(child.pid)] = dict(executable=child.exe(), command=child.cmdline())
                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
            time.sleep(.005)
    assert proc.returncode == 0, f'build failed: {log}'
    binary = source / '_build/native/release/build/cmd/moonflac/moonflac.exe'
    return dict(binary=str(binary.relative_to(ROOT)), sha256=sha(binary), build_log=str(log.relative_to(ROOT)), observed_compiler_commands=list(commands.values()))


def build_clang(source, work, mode, native, frozen_clang):
    """Reuse the maintained builder; never invent a second compiler flag set."""
    native_cli = ROOT / native['binary']
    source_identity = work / (mode + '-clang-input.json')
    save(source_identity, dict(cli=dict(path=native['binary'], sha256=native['sha256']),
                              sources={str((source/name).relative_to(ROOT)): digest
                                       for name, digest in source_hashes(source).items()}))
    libraries = [ROOT / name for name in frozen_clang['libraries']]
    runtime = [p for p in libraries if p.name == 'libruntime.lib']
    support = [p for p in libraries if p.name != 'libruntime.lib']
    assert len(runtime) == len(support) == 1, 'Unsupported link-library configuration'
    for path in libraries:
        assert sha(path) == frozen_clang['libraries'][str(path.relative_to(ROOT))]
    command = frozen_clang['command']
    assert '/clang:-ffp-contract=off' in command and '/MT' in command and '-fuse-ld=link' in command
    driver_path = ROOT / frozen_clang['driver_plan']
    driver_hash = sha(driver_path)
    driver_text = driver_path.read_text(encoding='utf-8')
    derived = dict(
        clang_target_features=re.findall(r'"-target-feature"\s+"([^"]+)"', driver_text),
        prefer_vector_width512='/clang:-mprefer-vector-width=512' in command,
        explicitly_disabled_features=['PKU'] if '/clang:-mno-pku' in command else [],
    )
    assert re.search(r'"-target-cpu"\s+"([^"]+)"', driver_text).group(1) == frozen_clang['clang_target_cpu']
    for key, value in derived.items():
        if key in frozen_clang:
            assert frozen_clang[key] == value, ('Recorded Clang metadata contradicts command/driver', key)
    flags = []
    if '/arch:AVX512' in command:
        assert '/clang:-mno-pku' in command
        flags.append('--avx512')
    elif '/arch:AVX2' in command:
        flags.append('--avx2')
    else:
        raise ValueError('Explicit Clang profiling requires the frozen AVX2 or supported-host AVX512 configuration')
    if derived['prefer_vector_width512']:
        flags.append('--prefer-vector-width512')
    builder = ROOT / 'scripts/faster-than-libflac-build-clang-c4.py'
    result_path = work / (mode + '-clang-build.json')
    invocation = [sys.executable, str(builder), '--artifact', 'cli',
                  '--source-identity', str(source_identity), '--source-root', str(source),
                  '--generated-c', str(native_cli.with_suffix('.c')),
                  '--runtime', str(runtime[0]), '--filesystem', str(support[0]),
                  '--build-dir', str(work / (mode + '-clang')), '--report', str(result_path), *flags]
    log = work / (mode + '-clang-build.log')
    with log.open('w', encoding='utf-8') as stream:
        subprocess.run(invocation, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    result = json.loads(result_path.read_text(encoding='utf-8'))
    for key in ['compiler', 'linker']:
        assert result[key]['sha256'] == frozen_clang[key]['sha256'], key
    for key in ['libraries', 'clang_target_cpu', 'clang_target_features', 'fp_contract',
                'prefer_vector_width512', 'explicitly_disabled_features']:
        assert result[key] == (derived[key] if key in derived else frozen_clang[key]), ('Clang configuration drift', key)
    # Compare semantic options as well as the expanded ISA and library identity.
    def options(argv):
        return [x for x in argv[1:] if x.startswith(('/', '-')) and not x.startswith(('/Fe', '/Fo'))]
    assert options(result['command']) == options(command), 'Compiler/link option drift'
    assert sha(driver_path) == driver_hash
    return dict(binary=result['cli']['path'], sha256=result['cli']['sha256'],
                clang_build_report=str(result_path.relative_to(ROOT)), clang_build_report_sha256=sha(result_path),
                builder_sha256=sha(builder), builder_command=invocation, build_log=str(log.relative_to(ROOT)),
                native_generation_build=native, matched_frozen_configuration=True,
                frozen_configuration_derivation=dict(driver_plan=str(driver_path.relative_to(ROOT)),
                                                     driver_plan_sha256=driver_hash, values=derived,
                                                     origin='Retained driver-plan target features and explicit compiler command; historical identity is unchanged.'))


def main(args):
    global COARSE, FUNCTIONS
    COARSE = args.coarse
    assert re.fullmatch(r'[A-Za-z0-9_-]+', args.name)
    work = ROOT / '_build/faster-than-libflac' / args.name
    evidence = ROOT / 'validation/evidence/faster-than-libflac' / (args.name + '.json')
    assert not work.exists() and not evidence.exists(), 'preserve previous work/evidence: choose a new --name'
    frozen_path = args.identity.resolve()
    archive_root = args.archive.resolve()
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    module_root = args.source_root.resolve() if args.source_root else None
    normalized_sources = {}
    for name, digest in frozen['sources'].items():
        if module_root:
            path = ROOT / name if (ROOT/name).is_file() else module_root/name
            assert sha(path) == digest, name
            relative = path.resolve().relative_to(module_root).as_posix()
        else:
            relative = name
        normalized_sources[relative] = digest
    def frozen_text(name):
        path = module_root/name if module_root else archive_root/(name + '.txt')
        assert sha(path) == normalized_sources[name], name
        return path.read_text(encoding='utf-8')
    frozen_clang = json.loads(args.clang_identity.read_text(encoding='utf-8')) if args.clang_identity else None
    if frozen_clang:
        assert COARSE and module_root, 'Clang attribution requires --coarse and --source-root'
        assert frozen_clang['source_manifest'] == frozen['sources'], 'Compiler identity uses different codec sources'
        reference = ROOT / frozen_clang['reference_identity']
        assert sha(reference) == sha(frozen_path), 'Clang reference identity differs'
    accepted_identity = frozen_clang or frozen
    original_cli = ROOT / accepted_identity['cli']['path']
    assert sha(original_cli) == accepted_identity['cli']['sha256']
    if 'encoder_budget_plan.mbt' in normalized_sources:
        FUNCTIONS.extend([
            ('encoder_budget_plan.mbt', 'encoder_budget_residual_plan', 'samples, predictor, budget, scratch'),
        ])
        if not COARSE:
            FUNCTIONS.append(('encoder_budget_plan.mbt', 'encoder_prefix_quotient', 'scratch, size, start, end, parameter'))
    if COARSE:
        entry = frame_entry(module_root / 'encoder_frame.mbt' if module_root else archive_root / 'encoder_frame.mbt.txt')
        FUNCTIONS = [(file, entry, args.replace('planes', 'original') if entry == 'encode_frame_wide_validated' else args)
                     if name == 'encode_frame' else (file, name, args)
                     for file, name, args in FUNCTIONS]
        lpc_source = frozen_text('encoder_lpc.mbt')
        if 'variances? :' in lpc_source:
            FUNCTIONS = [(file, name, 'samples, max_order, variances~')
                         if name == 'encoder_lpc_models' else (file, name, args)
                         for file, name, args in FUNCTIONS]
            variance_args = 'correlation, model, peak, window_energy'
            if 'signal? :' in lpc_source:
                variance_args += ', signal~'
            FUNCTIONS.append(('encoder_lpc.mbt', 'encoder_lpc_variance', variance_args))
            FUNCTIONS.append(('encoder_search.mbt', 'encoder_lpc_variance_ranking', 'samples, models, variances, depth'))
        frame_source = frozen_text('encoder_frame.mbt')
        if 'fn EncoderBits::crc(' in frame_source:
            FUNCTIONS.append(('encoder_frame.mbt', 'EncoderBits::crc', 'self, width'))
        # Wrappers must forward the caller's actual workspace. Omitting an
        # optional argument would silently allocate a fresh default per call.
        forwarded = []
        for file, name, call_args in FUNCTIONS:
            if file == 'encoder_frame.mbt' and name in [entry, 'encoder_subframe']:
                start = frame_source.index('fn ' + name + '(')
                signature = frame_source[start:frame_source.index('{', start)]
                if re.search(r'\bplan_scratch\?\s*:', signature):
                    call_args += ', plan_scratch~'
            forwarded.append((file, name, call_args))
        FUNCTIONS = forwarded
        if 'fn encoder_predict_double_into(' in frame_source:
            FUNCTIONS.append(('encoder_frame.mbt', 'encoder_predict_double_into', 'samples, signal, coefficients, shift, residual, tile'))
        if 'fn encoder_lpc_rice_ranking(' in frozen_text('encoder_search.mbt'):
            FUNCTIONS.append(('encoder_search.mbt', 'encoder_lpc_rice_ranking', 'samples, models, depth'))
        if 'fn EncoderPlanScratch::predict_fixed(' in frame_source:
            FUNCTIONS.append(('encoder_frame.mbt', 'EncoderPlanScratch::predict_fixed', 'self, samples, coefficients, depth'))
        has_predict_into = 'fn encoder_predict_into(' in frame_source
        if has_predict_into:
            FUNCTIONS = [row for row in FUNCTIONS if row[1] != 'encoder_predictor'] + [
                ('encoder_frame.mbt', 'encoder_predict_into', 'samples, coefficients, shift, residual'),
            ]
        FUNCTIONS.append(('frame.mbt', 'frame_crc', 'data, start, end, width'))
    work.mkdir(parents=True)
    shutil.copy2(Path(__file__), work / 'runner-source.py')
    source = work / 'uninstrumented'
    exclusions = {'_build', '.mooncakes', '.git', 'node_modules', 'cache', 'isolate_build', 'results', 'evidence', 'docs', 'scripts', 'playground', '.github', 'baselines', '__pycache__'}
    copy_root = module_root or ROOT
    for folder, dirs, files in os.walk(copy_root):
        dirs[:] = [n for n in dirs if n not in exclusions]
        for name in files:
            path = Path(folder) / name
            if path.suffix not in ['.mbt', '.mbti', '.c', '.h'] and name not in ['moon.mod', 'moon.pkg', 'README.md', 'LICENSE']: continue
            # Later candidates may add production modules absent from this
            # frozen implementation. Never compile those into an older profile.
            if path.parent == copy_root and path.suffix == '.mbt' and name not in normalized_sources: continue
            target = source / path.relative_to(copy_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for name, digest in normalized_sources.items():
        archive = module_root / name if module_root else archive_root / (name + '.txt')
        assert sha(archive) == digest, name
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, source / name)
    assert 'encoder_sparse_partition_limit' not in (source / 'encoder_search.mbt').read_text(encoding='utf-8')
    shutil.copytree(copy_root / '.mooncakes', source / '.mooncakes')
    accepted = work / 'accepted-frozen.exe'
    shutil.copy2(original_cli, accepted)
    identity = dict(frozen_identity_path=str(frozen_path.relative_to(ROOT)), frozen_identity_sha256=sha(frozen_path), frozen_cli_sha256=sha(accepted), runner_sha256=sha(Path(__file__)), source_files=source_hashes(source), frozen_core_source_files=frozen['sources'], caveat='Root implementation files restored from verified archives; package manifests/CLI scaffolding copied and hashed separately, output identity checked against frozen CLI.')
    if module_root:
        identity['caveat'] = 'Complete module scaffolding copied from explicit frozen source root; all declared codec hashes verified before and after. Instrumentation changes MoonBit only; generated C is not manually edited.'
    if frozen_clang:
        identity['frozen_clang'] = dict(path=str(args.clang_identity.resolve().relative_to(ROOT)), sha256=sha(args.clang_identity), cli=accepted_identity['cli'])
    save(work / 'source-identity.json', identity)
    report = dict(status='building', scope='Shared-host frozen-source attribution, not controlled throughput or speedup.', coarse_only=COARSE, timed_functions=[name for _, name, _ in FUNCTIONS], identity=identity, builds={}, cases=[], limitations=[
        'Timing and exact event counters use separate builds: event increments do not contaminate attribution timings.',
        'Inclusive/exclusive times cover instrumented successful calls; exclusive subtracts nested instrumented intervals, leaving uninstrumented work and probe overhead.',
        'Compiler inlining/code layout may change under instrumentation. No allocation-time or machine-instruction-cost attribution is inferred from source counts.',
        'Events called arrays/elements/records count source-level construction/copy requests, not physical heap allocations, bytes of allocator overhead or their runtime share.',
        'Concurrent local builds/work are allowed; per-case wall time records interference, not a benchmark result.',
        'No per-prefix-query clocks in coarse mode; otherwise prefix wrappers are fine-grained and may perturb inlining/clock overhead. Neither establishes machine instruction cost.',
        'Counter coverage is explicit: raw zero values for counters not in event_counters_instrumented are placeholders, not evidence of absent work. Integer predictor counters exclude fixed-specialized and Double paths; Double computed samples include a whole tile even when validation later rejects its suffix.',
    ])
    report['counter_scope'] = {
        'shortlist_decisions': 'Legacy name: counts only the regular shortlist branch (if shortlist), excluding rice_irregular.',
        'shortlist_pool_models': 'Legacy name: sums models.length only for the regular shortlist branch, excluding rice_irregular; zero is not evidence of no candidate ranking.',
        'rice_ranking_decisions': 'Separate event counter for the rice_irregular branch, when that branch is instrumented.',
        'rice_ranking_pool_models': 'Separate event counter summing actual models.length at the rice_irregular branch; not inferred from function call counts.',
        'rice_ranking_profile_calls': 'events-build PROFILE encoder_lpc_rice_ranking calls independently count executions of the ranking wrapper, not models or selected finalists.',
        'lazy_prefix_build_samples': 'N times each newly built column: quotient sample-column work, not physical folded-buffer reads when columns are fused.',
        'crc_header_copy_bytes': 'Legacy Array writer Bytes::from_array header snapshots only. Uninstrumented for word writer; raw zero is not a count of all writer copies.',
        'crc_body_copy_bytes': 'Legacy Array writer Bytes::from_array body snapshots only. Uninstrumented for word writer; raw zero is not a count of all writer copies.',
        'writer_reserve_copy_bytes': 'Word writer only: self.length bytes copied inside each actual capacity-changing reserve branch, including header preservation or final resize; no allocation-time/RSS inference.',
        'crc8_bytes/crc16_bytes': 'Bytes processed by instrumented frame_crc and, when present, EncoderBits::crc after materialize. Word writer calls its own CRC helper rather than copying Bytes snapshots.',
    }
    report['wrapper_calls'] = {name: call_args for _, name, call_args in FUNCTIONS}
    save(evidence, report)
    for mode in ['timing', 'events']:
        dest = work / mode
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns('_build'))
        instrument(dest, mode)
        before_build = source_hashes(dest)
        assert before_build, 'source binding must not be empty'
        save(work / (mode + '-source-before-build.json'), before_build)
        report['builds'][mode] = build(dest, work, mode)
        if frozen_clang:
            report['builds'][mode] = build_clang(dest, work, mode, report['builds'][mode], frozen_clang)
        report['builds'][mode]['instrumented_source_files'] = source_hashes(dest)
        assert report['builds'][mode]['instrumented_source_files'] == before_build, 'instrumented source changed during build'
        report['builds'][mode]['source_before_build_sha256'] = sha(work / (mode + '-source-before-build.json'))
        report['builds'][mode]['source_unchanged_after_build'] = True
        report['builds'][mode]['event_counters_instrumented'] = instrumented_counters(dest)
        save(evidence, report)
    manifest = ROOT / 'validation/cache/effort8-benchmark/core-inputs.json'
    cases = json.loads(manifest.read_text(encoding='utf-8'))['cases']
    assert len(cases) == 12
    silence = dict(next(c for c in cases if c['name'] == 'silence-16-2'))
    silence_input = work / 'silence-65535.raw'
    silence_input.write_bytes(bytes(65535 * 2 * 2))
    silence.update(name='silence-16-2-block65535', block=65535, samples=65535,
                   path=str(silence_input.relative_to(ROOT)), pcm_bytes=silence_input.stat().st_size,
                   pcm_sha256=sha(silence_input), provenance='Explicit 65535 zero samples per channel, two channels, signed16 raw; exactly one maximal frame.')
    cases.append(silence)
    if args.only:
        cases = [case for case in cases if case['name'] in args.only]
        assert len(cases) == len(args.only), 'unknown case selected'
    report.update(status='running', input_manifest_sha256=sha(manifest), extra_case='65535 explicit zero samples per channel: one full block65535.')
    save(evidence, report)
    for case in cases:
        assert sha(ROOT / case['path']) == case['pcm_sha256']
        entry = dict(case, observations=[])
        report['cases'].append(entry)
        for repetition in range(args.repetitions):
            row = dict(repetition=repetition)
            baseline_digest = None
            for mode in ['accepted-frozen', 'timing', 'events']:
                if mode == 'events' and repetition > 0: continue
                binary = accepted if mode == 'accepted-frozen' else ROOT / report['builds'][mode]['binary']
                output = work / f'{case["name"]}-{mode}-{repetition}.flac'
                command = [str(binary), 'encode', str(ROOT / case['path']), str(output), '--raw', '--sample-rate', str(case['rate']), '--channels', str(case['channels']), '--bits', str(case['bits']), '--block-size', str(case['block']), '--effort', '8']
                started = time.perf_counter()
                proc = subprocess.run(command, capture_output=True, text=True, timeout=600)
                wall = time.perf_counter() - started
                log = work / f'{case["name"]}-{mode}-{repetition}.log'
                log.write_text(proc.stdout + proc.stderr, encoding='utf-8')
                assert proc.returncode == 0, f'{mode} failed: {log}'
                digest = sha(output)
                if mode == 'accepted-frozen': baseline_digest = digest
                else: assert digest == baseline_digest, f'probe output differs from frozen CLI: {case["name"]}/{mode}'
                item = dict(command=command, wall_seconds=wall, log=str(log.relative_to(ROOT)), output_sha256=digest)
                if mode != 'accepted-frozen':
                    item['profiles'] = {n: dict(inclusive_us=float(inc), exclusive_us=float(exc), calls=int(calls)) for n, inc, exc, calls in re.findall(r'^PROFILE (\S+) ([\d.eE+-]+) ([\d.eE+-]+) (\d+)$', proc.stdout, re.M)}
                    assert len(item['profiles']) == len(FUNCTIONS) + 2
                    item['events'] = {n: int(v) for n, v in re.findall(r'^EVENT (\S+) (\d+)$', proc.stdout, re.M)}
                    if mode == 'timing':
                        total = item['profiles']['cli_execute_encode']['inclusive_us']
                        for profile in item['profiles'].values():
                            profile['inclusive_percent_encode'] = 100 * profile['inclusive_us'] / total
                            profile['exclusive_percent_encode'] = 100 * profile['exclusive_us'] / total
                row[mode] = item
            row['bitstreams_identical'] = True
            entry['observations'].append(row)
            save(evidence, report)
        timing = entry['observations'][0]['timing']['profiles']
        events = entry['observations'][0]['events']['events']
        entry['median_timing_profiles'] = {name: {key: statistics.median(obs['timing']['profiles'][name][key] for obs in entry['observations']) for key in timing[name]} for name in timing}
        entry['exact_events'] = events
        covered = report['builds']['events']['event_counters_instrumented']
        entry['instrumented_events_only'] = {name: events[name] for name in covered}
        entry['uninstrumented_counters'] = [name for name in COUNTERS if name not in covered]
        save(evidence, report)
        print(json.dumps(dict(case=case['name'], top_exclusive=sorted(((n,p['exclusive_percent_encode']) for n,p in entry['median_timing_profiles'].items()), key=lambda x:-x[1])[:5], lower_bound_calls=timing['encoder_partition_lower_bound']['calls'], coarse=events['coarse_plan_calls'], visited=events['lower_bound_visited_samples'], refinements=events['refinements'], budget_rejections=events['budget_rejections'], lazy_columns=events['lazy_prefix_column_builds'], lazy_samples=events['lazy_prefix_build_samples'])), flush=True)
    assert sha(original_cli) == accepted_identity['cli']['sha256']
    for name, digest in normalized_sources.items():
        assert sha(module_root/name if module_root else archive_root/(name + '.txt')) == digest
    assert sha(frozen_path) == identity['frozen_identity_sha256']
    if frozen_clang:
        assert sha(args.clang_identity) == identity['frozen_clang']['sha256']
    assert source_hashes(source) == identity['source_files']
    report.update(status='pass', archived_sources_and_frozen_cli_unchanged=True)
    save(evidence, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='revision7-actual')
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--only', nargs='+', help='Optional named subset, e.g. silence-16-2-block65535')
    parser.add_argument('--identity', type=Path, default=FROZEN)
    parser.add_argument('--archive', type=Path, default=ROOT / 'validation/baselines/speed-first-revision7')
    parser.add_argument('--source-root', type=Path, help='Explicit frozen module for identities with isolated source paths; avoids mixing current root scaffolding')
    parser.add_argument('--clang-identity', type=Path, help='Frozen Clang CLI build report: reuse its compiler, ISA and libraries via the maintained Clang builder')
    parser.add_argument('--coarse', action='store_true', help='CRC plus archived predictor architecture, no prefix-query timing')
    main(parser.parse_args())

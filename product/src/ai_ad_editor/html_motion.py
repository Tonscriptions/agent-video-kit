"""Editable local HTML/SVG/Canvas assets on the native Agent/FFmpeg timeline.

OpenFilm's frame contract and MIT clock are reused, not its HTTP/online host.
All runtime paths are explicit and byte-pinned; importing this module starts
no browser. See the HTML motion contract for deliberate format limits.
"""
from __future__ import annotations

import base64
import copy
import contextlib
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile

from .browser_process import BrowserProcessJob
from .edit_planner import project_fingerprint
from .errors import AppError
from .media import ffmpeg_path, ffprobe_path, probe_media
from .policy import resolve_local_path
from .project import asset_map, find_sequence, find_track
from .template import validate_variables
from .utils import assert_id, load_json, new_id, now_iso, sha256_file, run_process
from . import html_shutter

ENGINE = 'agent-local-html-motion-v1'
VERSION = '0.1.0'
MAX_FILES = 256
MAX_BYTES = 64 * 1024**2
MAX_FRAMES = 1800
MAX_PIXELS = 2_000_000_000
CODE_EXTENSIONS = {'.html', '.css', '.js', '.mjs', '.json', '.svg'}
RESOURCE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.ttf', '.otf', '.woff', '.woff2'}


def fail(code, message, path='html_motion'):
    raise AppError(code, message, exit_code=2, path=str(path))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def digest(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def _local(root, value, field):
    path = resolve_local_path(root, value, field=field)
    if str(path).startswith('\\\\') or not path.is_file():
        fail('HTML_PATH_INVALID', '必须为存在的本地磁盘文件', field)
    return path


def _integer(value, name, low=1, high=2**53-1):
    if type(value) is not int or not low <= value <= high:
        fail('HTML_MANIFEST_INVALID', '要求范围内整数，不能是浮点或布尔数', name)
    return value


def _relative(value):
    if not isinstance(value, str) or not value or len(value) > 200 or any(c in value for c in '\\:%?#\x00'):
        fail('HTML_RESOURCE_INVALID', '资源路径必须是无 URI/转义/反斜线的相对路径', value)
    parts = PurePosixPath(value).parts
    if PurePosixPath(value).is_absolute() or not parts or any(p in {'.', '..'} or p.rstrip(' .') != p for p in parts) or '/'.join(parts) != value:
        fail('HTML_RESOURCE_INVALID', '资源路径不能穿越目录或使用别名', value)
    if any(re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts):
        fail('HTML_RESOURCE_INVALID', '资源路径不能使用设备名', value)
    return value


def _check_components(root, relative):
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            fail('HTML_RESOURCE_INVALID', '资源不能通过链接或目录联接读取', relative)
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        fail('HTML_RESOURCE_INVALID', '本地资源缺失或越界', relative)
    return path


def _tree(root, *, browser=False):
    root = root.resolve(strict=True)
    entries, size = [], 0
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            p = Path(folder)/name
            if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
                fail('HTML_TOOLCHAIN_INVALID', '固定工具链目录不能含链接', p)
        for name in sorted(files):
            p = Path(folder)/name
            if browser and p == root/'debug.log':
                continue  # Chromium's mutable diagnostic, never executable input
            size += p.stat().st_size
            if len(entries) >= 4096 or size > 2*1024**3:
                fail('HTML_TOOLCHAIN_BUDGET', '工具链目录超过 4096 文件或 2 GiB', root)
            entries.append({'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': 'sha256:'+sha256_file(p)})
    return sorted(entries, key=lambda e:e['path'])


def prepare_runtime(root, request):
    if not isinstance(request, dict) or set(request) != {'node', 'playwright', 'chromium'}:
        fail('HTML_TOOLCHAIN_INVALID', '注册要求 node/playwright/chromium 三个明确本地路径')
    node = _local(root, request['node'], 'node')
    chromium = _local(root, request['chromium'], 'chromium')
    pw = resolve_local_path(root, request['playwright'], field='playwright')
    if str(pw).startswith('\\\\') or not pw.is_dir():
        fail('HTML_TOOLCHAIN_INVALID', 'playwright 必须是本地包目录')
    package = load_json(pw/'package.json')
    if package.get('name') != 'playwright-core' or not re.fullmatch(r'1\.\d+\.\d+', str(package.get('version'))):
        fail('HTML_TOOLCHAIN_INVALID', '必须为正式 playwright-core 包')
    if not (pw/'LICENSE').is_file() or not (pw/'index.mjs').is_file() or not (chromium.parent/'LICENSE.headless_shell').is_file() or chromium.name != 'chrome-headless-shell.exe':
        fail('HTML_TOOLCHAIN_INVALID', '要求开源 Chromium headless shell 及本地完整许可文件')
    try:
        version = subprocess.run([str(node), '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True).stdout.decode().strip()
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        fail('HTML_TOOLCHAIN_INVALID', '本地 Node 无法完成版本核对: '+str(exc), 'node')
    match = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (22, 2, 0):
        fail('HTML_TOOLCHAIN_INVALID', 'HTML 动效要求本地 Node >=22.2')
    return {'version':VERSION, 'engine':ENGINE, 'node':str(node), 'node_version':version,
            'node_sha256':'sha256:'+sha256_file(node), 'playwright':str(pw), 'playwright_version':package['version'],
            'chromium':str(chromium), 'playwright_files':_tree(pw), 'chromium_files':_tree(chromium.parent,browser=True)}


def verify_runtime(root):
    path = root/'config/html-motion-runtime.json'
    if not path.is_file():
        raise AppError('HTML_TOOLCHAIN_MISSING', '先用 motion html-register 登记已有本地工具链', exit_code=10)
    record = load_json(path)
    current = prepare_runtime(root, {k:record[k] for k in ('node', 'playwright', 'chromium')})
    if current != record:
        fail('HTML_TOOLCHAIN_CHANGED', '已固定工具链字节或版本变化，必须重新审查登记', path)
    return record


def validate_spec(value, ticks_per_second):
    if not isinstance(value, dict) or set(value)-{'entry','width','height','fps','duration_tick','variables','files','resources'}:
        fail('HTML_MANIFEST_INVALID', '清单字段不受支持')
    spec = {k:copy.deepcopy(value.get(k)) for k in ('entry','width','height','fps','duration_tick','variables')}
    spec['entry'] = _relative(spec['entry'])
    if Path(spec['entry']).suffix.lower() != '.html':
        fail('HTML_MANIFEST_INVALID', '入口必须是 HTML')
    w = _integer(spec['width'], 'width', 2, 4096)
    h = _integer(spec['height'], 'height', 2, 4096)
    fps = spec['fps']
    if not isinstance(fps, dict) or set(fps) != {'num','den'}:
        fail('HTML_MANIFEST_INVALID', 'fps 必须为 num/den 对象')
    n, d = _integer(fps['num'],'fps.num',1,120000), _integer(fps['den'],'fps.den',1,10000)
    if not Fraction(1, 1) <= Fraction(n,d) <= 120:
        fail('HTML_MANIFEST_INVALID', 'FPS 要求 1..120')
    duration = _integer(spec['duration_tick'], 'duration_tick')
    count = Fraction(duration*n, ticks_per_second*d)
    if count.denominator != 1 or not 1 <= count <= MAX_FRAMES or w*h*count > MAX_PIXELS:
        fail('HTML_FRAME_BUDGET', '时长须对齐 CFR 帧，且不超过 1800 帧/20 亿像素工作量')
    variables = spec['variables'] or []
    if not isinstance(variables,list) or len(variables)>64:
        fail('HTML_VARIABLE_INVALID','变量声明须为不超过 64 项的数组')
    if any(not isinstance(v,dict) or v.get('type') not in {'string','number','integer','boolean','color','enum'} for v in variables):
        fail('HTML_VARIABLE_INVALID','仅支持明确的基础变量类型')
    if any(str(v.get('name','')) in {'asset_id','rights_ref'} or str(v.get('name','')).endswith(('_asset_id','_clip_id','_track_id','_sequence_id')) for v in variables):
        fail('HTML_VARIABLE_INVALID','变量名不能占用工程 ID 引用字段')
    try:
        validate_variables({'variables':variables},{})
        encoded(variables)  # rejects nonfinite numbers
    except (ValueError,TypeError) as exc:
        fail('HTML_VARIABLE_INVALID',str(exc))
    spec['variables']=variables
    return spec, int(count)


def parameters(spec, values):
    declarations=spec['variables']
    if not isinstance(values,dict) or set(values)-{v['name'] for v in declarations}:
        fail('HTML_VARIABLE_INVALID','参数必须为仅含已声明变量的对象')
    resolved={v['name']:copy.deepcopy(v['default']) for v in declarations if 'default' in v}
    resolved.update(copy.deepcopy(values))
    try:
        if validate_variables(spec,resolved):
            fail('HTML_VARIABLE_INVALID','缺少必填变量')
        if len(encoded(resolved))>65536:
            fail('HTML_VARIABLE_INVALID','参数超过 64 KiB')
    except (ValueError,TypeError) as exc:
        fail('HTML_VARIABLE_INVALID',str(exc))
    return resolved


def build_source(root, project, manifest_path):
    path=_local(root,str(manifest_path),'input')
    if path.stat().st_size>1024**2:
        fail('HTML_MANIFEST_INVALID','清单超过 1 MiB')
    value=load_json(path)
    ticks=project['settings']['timebase']['ticks_per_second']
    spec,count=validate_spec(value,ticks)
    files=value.get('files')
    resources=value.get('resources',[])
    if not isinstance(files,list) or not files or not isinstance(resources,list) or len(files)+len(resources)>MAX_FILES:
        fail('HTML_RESOURCE_INVALID','files/resources 必须为明确且有界的数组')
    data, references={},[]
    seen={'motion.json'}
    def add(relative, content):
        _relative(relative)
        if relative.casefold() in seen:
            fail('HTML_RESOURCE_INVALID','资源路径重复或与包清单冲突',relative)
        seen.add(relative.casefold())
        data[relative]=content
        if sum(map(len,data.values()))>MAX_BYTES:
            fail('HTML_SOURCE_BUDGET','源码与资源合计超过 64 MiB')
    for relative in files:
        _relative(relative)
        if Path(relative).suffix.lower() not in CODE_EXTENSIONS:
            fail('HTML_RESOURCE_INVALID','非代码文件必须通过已登记资源引用',relative)
        file=_check_components(path.parent,relative)
        if file.stat().st_size>MAX_BYTES:
            fail('HTML_SOURCE_BUDGET','单资源超过源码预算',relative)
        add(relative,file.read_bytes())
    assets=asset_map(project)
    for resource in resources:
        if not isinstance(resource,dict) or set(resource)!={'path','asset_id'}:
            fail('HTML_RESOURCE_INVALID','资源项必须为 path/asset_id')
        relative=_relative(resource['path'])
        asset=assets.get(resource['asset_id'])
        if not asset or asset['kind'] not in {'image','font'} or Path(relative).suffix.lower() not in RESOURCE_EXTENSIONS:
            fail('HTML_RESOURCE_INVALID','资源必须是已登记图片或字体',relative)
        file=_local(root,asset['uri'],'resource')
        if file.stat().st_size>MAX_BYTES:
            fail('HTML_SOURCE_BUDGET','单资源超过源码预算',relative)
        content=file.read_bytes()
        if digest(content)!=asset['sha256']:
            fail('HTML_RESOURCE_CHANGED','登记资源字节变化',relative)
        add(relative,content)
        references.append({'path':relative,'asset_id':asset['id'],'sha256':asset['sha256']})
    if spec['entry'] not in data:
        fail('HTML_RESOURCE_INVALID','入口未列入 files')
    return pack_source(spec, data, ticks, references)


def pack_source(spec, data, ticks, references):
    """Pack already validated local generators using the same editable format."""
    spec, count = validate_spec(spec, ticks)
    if spec['entry'] not in data or 'motion.json' in data or len(data) > MAX_FILES:
        fail('HTML_RESOURCE_INVALID', '生成源码缺少入口或成员无效')
    if len({p.casefold() for p in data}) != len(data) or sum(map(len, data.values())) > MAX_BYTES:
        fail('HTML_SOURCE_BUDGET', '生成源码成员重复或超过预算')
    for p in data:
        _relative(p)
    data = dict(data)
    members=[{'path':p,'sha256':digest(b),'bytes':len(b)} for p,b in sorted(data.items())]
    packed={'version':VERSION,'engine':ENGINE,'ticks_per_second':ticks,'spec':spec,'files':members}
    data['motion.json']=encoded(packed)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,content in sorted(data.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,content)
    return out.getvalue(), {'spec':spec,'frame_count':count,'resources':references,'members':members}


def inspect_source(root, project, source_id):
    asset=asset_map(project).get(source_id)
    if not asset or asset.get('html_source',{}).get('engine')!=ENGINE:
        fail('HTML_SOURCE_MISSING','不是已登记 HTML 源码资产',source_id)
    path=_local(root,asset['uri'],'source')
    if path.stat().st_size>MAX_BYTES+1024**2 or 'sha256:'+sha256_file(path)!=asset['sha256']:
        fail('HTML_SOURCE_CHANGED','源码包摘要变化或超过预算',source_id)
    try:
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist()
            names=[_relative(item.filename) for item in infos]
            if len(infos)>MAX_FILES+1 or len(set(n.casefold() for n in names))!=len(names) or sum(i.file_size for i in infos)>MAX_BYTES+1024**2:
                fail('HTML_SOURCE_INVALID','源码包成员重复或超出预算')
            if 'motion.json' not in names or archive.getinfo('motion.json').file_size>1024**2:
                fail('HTML_SOURCE_INVALID','源码包清单缺失或过大')
            manifest=json.loads(archive.read('motion.json'))
            if manifest.get('engine')!=ENGINE or manifest.get('version')!=VERSION:
                fail('HTML_SOURCE_INVALID','源码包版本不兼容')
            ticks=project['settings']['timebase']['ticks_per_second']
            if manifest.get('ticks_per_second')!=ticks:
                fail('HTML_SOURCE_CONTEXT','源码包和目标工程 tick 时基不一致')
            spec,count=validate_spec(manifest['spec'],ticks)
            members=manifest['files']
            if not isinstance(members,list) or len(members)>MAX_FILES or len({e['path'] for e in members})!=len(members) or set(names)!={'motion.json',*(e['path'] for e in members)}:
                fail('HTML_SOURCE_INVALID','源码包成员与清单不一致')
            data={}
            for item in members:
                name=_relative(item['path']);content=archive.read(name)
                if len(content)!=item['bytes'] or digest(content)!=item['sha256']:
                    fail('HTML_SOURCE_CHANGED','源码包内文件摘要不符',name)
                data[name]=content
    except (zipfile.BadZipFile,KeyError,ValueError,TypeError,RuntimeError,OSError) as exc:
        fail('HTML_SOURCE_INVALID','无法读取明确的源码包: '+str(exc))
    if spec['entry'] not in data:
        fail('HTML_SOURCE_INVALID','源码入口缺失')
    for item in asset['html_source'].get('resources',[]):
        resource=asset_map(project).get(item.get('asset_id'))
        if not resource or resource['sha256']!=item['sha256'] or digest(data.get(item['path'],b''))!=item['sha256']:
            fail('HTML_RESOURCE_CHANGED','源码资源映射丢失或摘要变化',item.get('path'))
        file=_local(root,resource['uri'],'resource')
        if 'sha256:'+sha256_file(file)!=item['sha256']:
            fail('HTML_RESOURCE_CHANGED','当前登记资源字节变化',item['path'])
    return {'asset':asset,'spec':spec,'frame_count':count,'files':members,'data':data}


def prepare_render(root,project,args):
    assets=asset_map(project)
    values={}
    saved_overrides=None
    saved_layout_check='off'
    saved_shutter=None
    source_id=args.source_asset_id
    if args.from_asset_id:
        previous=assets.get(args.from_asset_id,{})
        recipe=previous.get('html_motion')
        if not recipe:
            fail('HTML_RECIPE_MISSING','已有输出没有可重建源码配方')
        source_id=recipe['source_asset_id'];values=copy.deepcopy(recipe['parameters'])
        saved_overrides=recipe.get('template_overrides')
        saved_layout_check=recipe.get('layout_check','off')
        saved_shutter=recipe.get('shutter')
    source=inspect_source(root,project,source_id)
    if args.params:
        path=_local(root,args.params,'params')
        if path.stat().st_size>65536:
            fail('HTML_VARIABLE_INVALID','参数输入超过 64 KiB')
        supplied=load_json(path)
        if not isinstance(supplied,dict):
            fail('HTML_VARIABLE_INVALID','参数必须为 JSON 对象')
        values.update(supplied)
    params=parameters(source['spec'],values)
    from .html_template import merge_overrides, read_patch, attach_resources
    changes=merge_overrides(saved_overrides,read_patch(root,getattr(args,'overrides',None)))
    compiled,references=attach_resources(root,project,source,changes)
    assert_id(args.asset_id,'asset_id')
    if args.asset_id in assets:
        fail('HTML_ASSET_EXISTS','输出资产 ID 已存在，须使用新版本 ID')
    _integer(args.timeline_start_tick,'timeline_start_tick',0)
    if not math.isfinite(args.timeout_seconds) or not 1<=args.timeout_seconds<=1800:
        fail('HTML_TIMEOUT_INVALID','总超时要求 1..1800 秒')
    if args.expected_project_sha256 and args.expected_project_sha256!=project_fingerprint(project):
        fail('EDIT_PROJECT_CHANGED','项目已偏离已规划摘要')
    track=None
    if args.apply:
        if not args.track_id:
            fail('HTML_TRACK_INVALID','入轨须指定 track_id')
        seq=find_sequence(project,args.sequence_id)
        track=find_track(seq,args.track_id,None)
        if track.get('kind')!='video' or track.get('locked'):
            fail('HTML_TRACK_INVALID','要求未锁定 video 轨')
        start,end=args.timeline_start_tick,args.timeline_start_tick+source['spec']['duration_tick']
        if any(max(start,c['timeline_start_tick'])<min(end,c['timeline_start_tick']+c['duration_tick']) for c in track['clips']):
            fail('HTML_TRACK_OVERLAP','动效入轨与已有片段重叠')
    elif args.track_id:
        fail('HTML_TRACK_INVALID','track_id 须与 apply 一起使用')
    layout_check=getattr(args,'layout_check',None) or saved_layout_check
    if layout_check not in {'off','strict'}:
        fail('HTML_LAYOUT_MODE_INVALID','layout_check 要求 off 或 strict')
    shutter_config=html_shutter.configuration(saved_shutter,
        samples=getattr(args,'shutter_samples',None),fraction=getattr(args,'shutter_fraction',None),
        cut_ticks=getattr(args,'shutter_cut_tick',None),clear_cuts=getattr(args,'shutter_clear_cuts',False),
        duration_tick=source['spec']['duration_tick'])
    shutter=html_shutter.profile(source['spec'],source['frame_count'],shutter_config,layout_check=layout_check)
    runtime=verify_runtime(root)
    source.update({'source_asset_id':source_id,'parameters':params,'runtime':runtime,'track':track,
                   'template_overrides':changes,'compiled_overrides':compiled,'override_resources':references,
                   'layout_check':layout_check,
                    'shutter':shutter,'shutter_implementation':html_shutter.implementation() if shutter['enabled'] else None,
                   'project_sha256':project_fingerprint(project)})
    return source


def public_plan(plan):
    return {k:copy.deepcopy(v) for k,v in plan.items() if k not in {'data','asset','runtime','track'}} | {
        'engine':ENGINE,'toolchain':{k:plan['runtime'][k] for k in ('node_version','playwright_version','node_sha256')},
        'all_frames_checked_in_two_fresh_context_orders':True,'output':'ffv1-bgra-nut',
        'rights_status':'unverified','limits':['not_full_openfilm_timeline','no_embedded_media_iframes_or_webgl','not_hdr_or_capcut_parity']}


def _shutter_schedule(plan):
    if not plan.get('shutter',{}).get('enabled'):return None
    return html_shutter.schedule(plan['spec'],plan['asset']['html_source']['ticks_per_second'],plan['shutter'])


def inspect_controls(root,plan,report_path,*,frame_index=0,timeout=120,cancel_file=None):
    """Draw one declared frame twice, close all tabs, and return its real DOM."""
    _integer(frame_index,'frame_index',0,plan['frame_count']-1)
    from .utils import atomic_write_json
    report={'engine':ENGINE,'created_at':now_iso(),'status':'started','inspection_only':True,
            'source_asset_id':plan['source_asset_id'],'source_sha256':plan['asset']['sha256'],
            'frame_index':frame_index,'parameters':plan['parameters'],'template_overrides':plan['template_overrides'],
            'override_resources':plan['override_resources'],'project_sha256':plan['project_sha256']}
    job=None
    try:
        with tempfile.TemporaryDirectory(prefix='html-controls-') as folder, contextlib.ExitStack() as cleanup:
            temp=Path(folder);bundle=temp/'source';bundle.mkdir()
            for name,content in plan['data'].items():
                path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            runtime=plan['runtime'];job=BrowserProcessJob(timeout,cancel_file)
            cleanup.callback(job.close)
            env=dict(os.environ)
            env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',NODE_OPTIONS='')
            with (temp/'node.stderr').open('wb') as stderr:
                node=job.start([runtime['node'],str(Path(__file__).with_name('html_motion_worker.mjs'))],cwd=temp,env=env,
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr)
                request={'task':'controls','root':str(bundle),'files':plan['files'],'spec':plan['spec'],'params':plan['parameters'],
                         'overrides':plan['compiled_overrides'],'frame_count':plan['frame_count'],'sample_frame_index':frame_index,
                         'ticks_per_second':plan['asset']['html_source']['ticks_per_second'],
                         'playwright':runtime['playwright'],'chromium':runtime['chromium'],'log_file':str(temp/'chromium.log'),
                         'frame_timeout_ms':min(15000,int(timeout*1000))}
                node.stdin.write(encoded(request).replace(b'\n',b'')+b'\n');node.stdin.flush()
                line=node.stdout.readline(2*1024**2+1);job.check()
                if len(line)>2*1024**2 or not line.endswith(b'\n'):
                    fail('HTML_PROTOCOL_INVALID','模板检查响应缺失或超过 2 MiB')
                item=json.loads(line);report['worker']=item
                if item.get('type')=='error':
                    raise AppError(item['code'],item['message'],exit_code=6)
                if item.get('type')!='done' or not item.get('inspection_only') or not item.get('fresh_contexts_equal') or item.get('sample_frame_index')!=frame_index:
                    fail('HTML_PROTOCOL_INVALID','模板检查采样回执不完整')
                receipt=item.get('cleanup',{})
                if receipt.get('pages_opened')!=2 or receipt.get('pages_closed')!=2 or not receipt.get('browser_closed') or receipt.get('denied_requests')!=0:
                    fail('HTML_PROTOCOL_INVALID','模板检查离线/关闭回执不完整')
                node.stdin.close()
                if node.wait(timeout=15)!=0:
                    fail('HTML_PROCESS_FAILED','模板检查进程异常退出')
                job.check()
            report['cleanup']=job.close()
            report.update(status='succeeded',controls=item['sample']['controls'],effective_controls=item['sample']['effective_controls'],applied=item['sample']['applied'])
            return report
    except BaseException as exc:
        if job:
            try:job.check()
            except AppError as reason:exc=reason
        report.update(status='failed',error=exc.as_dict() if isinstance(exc,AppError) else {'code':'HTML_PROCESS_FAILED','message':str(exc)[:2000]})
        if isinstance(exc,AppError):
            exc.path=str(report_path);raise exc
        raise AppError('HTML_PROCESS_FAILED','模板检查失败',exit_code=6,path=str(report_path),cause=str(exc)[:2000]) from exc
    finally:
        if job:report['cleanup']=job.close()
        atomic_write_json(report_path,report)


def public_quality_plan(plan):
    result=public_plan(plan)
    result.update(output=None,quality_only=True,all_frames_checked_in_two_fresh_context_orders=False,
                  all_frames_checked_in_primary_and_fresh_reverse=True)
    return result


def inspect_layout(root,plan,report_path,*,timeout=600,cancel_file=None):
    """Inspect every actual frame; quality failures retain their complete report."""
    from .html_quality import font_catalogue,review_frame
    from .utils import atomic_write_json
    catalogue,fonts=font_catalogue(plan)
    report={'engine':ENGINE,'report_version':VERSION,'created_at':now_iso(),'status':'started','quality_only':True,
            'plan':public_quality_plan(plan),'font_sources':catalogue,'frames':[],'issues':[],
            'scope':'all-CFR-frames-DOM-range-geometry-and-source-font-Unicode-mapping',
            'shaping_and_aesthetics_accepted':False,'validation_complete':False}
    sampling=_shutter_schedule(plan);capture_count=len(sampling) if sampling else plan['frame_count']
    if sampling:report['scope']='all-declared-shutter-subframes-DOM-range-geometry-and-source-font-Unicode-mapping'
    job=None;previews=root/'cache/html-quality'/report_path.stem;budget_bytes=0
    try:
        with tempfile.TemporaryDirectory(prefix='html-quality-') as folder,contextlib.ExitStack() as cleanup:
            temp=Path(folder);bundle=temp/'source';bundle.mkdir()
            for name,content in plan['data'].items():
                path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            runtime=plan['runtime'];job=BrowserProcessJob(timeout,cancel_file);cleanup.callback(job.close)
            env=dict(os.environ)
            env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',NODE_OPTIONS='')
            with (temp/'node.stderr').open('wb') as stderr:
                node=job.start([runtime['node'],str(Path(__file__).with_name('html_motion_worker.mjs'))],cwd=temp,env=env,
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr)
                request={'task':'quality','root':str(bundle),'files':plan['files'],'spec':plan['spec'],'params':plan['parameters'],
                    'overrides':plan['compiled_overrides'],'frame_count':capture_count,
                    'sampling_times':[r['worker_time_seconds'] for r in sampling] if sampling else None,
                    'ticks_per_second':plan['asset']['html_source']['ticks_per_second'],
                    'playwright':runtime['playwright'],'chromium':runtime['chromium'],'log_file':str(temp/'chromium.log'),
                    'frame_timeout_ms':min(15000,int(timeout*1000))}
                node.stdin.write(encoded(request).replace(b'\n',b'')+b'\n');node.stdin.flush()
                limit=max(2*1024**2,plan['spec']['width']*plan['spec']['height']*6+200000,capture_count*512)
                while True:
                    line=node.stdout.readline(limit+1);job.check()
                    if not line or len(line)>limit or not line.endswith(b'\n'):
                        fail('HTML_PROTOCOL_INVALID','布局检查没有返回完整有界消息')
                    item=json.loads(line)
                    if item.get('type')=='error':
                        report['worker']=item;raise AppError(item['code'],item['message'],exit_code=6)
                    if item.get('type')=='done':
                        report['worker']=item;receipt=item.get('cleanup',{})
                        if not item.get('quality_only') or not item.get('all_frame_orders_equal') or len(report['frames'])!=capture_count or item.get('frame_hashes')!=[f['sha256'] for f in report['frames']]:
                            fail('HTML_PROTOCOL_INVALID','布局检查缺少全帧/独立重绘回执')
                        if receipt.get('pages_opened')!=2 or receipt.get('pages_closed')!=2 or not receipt.get('browser_closed') or receipt.get('denied_requests')!=0:
                            fail('HTML_PROTOCOL_INVALID','布局检查离线或关闭回执不完整')
                        break
                    index=len(report['frames'])
                    if item.get('type')!='quality-frame' or item.get('index')!=index or index>=capture_count:
                        fail('HTML_PROTOCOL_INVALID','布局检查帧序不连续')
                    reviewed=review_frame(item['layout'],fonts)
                    frame={'index':index,'sha256':item['sha256'],'layout':reviewed}
                    if sampling:frame['sampling']=sampling[index]
                    if item.get('png'):
                        png=base64.b64decode(item['png'],validate=True)
                        if png[:8]!=b'\x89PNG\r\n\x1a\n' or len(png)<24 or struct.unpack('>II',png[16:24])!=(plan['spec']['width'],plan['spec']['height']) or digest(png)!=item['sha256']:
                            fail('HTML_PROTOCOL_INVALID','布局预览 PNG 尺寸或摘要不符')
                        previews.mkdir(parents=True,exist_ok=True)
                        preview=previews/f'frame-{index:06}.png';preview.write_bytes(png)
                        frame['preview']=preview.relative_to(root).as_posix()
                    issues=[{'frame':index,**issue} for issue in reviewed['issues']]
                    budget_bytes+=len(encoded(frame))+len(encoded(issues))
                    if budget_bytes>16*1024**2:
                        fail('HTML_LAYOUT_BUDGET','布局报告超过 16 MiB')
                    report['frames'].append(frame);report['issues'].extend(issues)
                    node.stdin.write(encoded({'ack':index}).replace(b'\n',b'')+b'\n');node.stdin.flush()
                node.stdin.close()
                if node.wait(timeout=15)!=0:fail('HTML_PROCESS_FAILED','布局检查进程异常退出')
                job.check()
            report['cleanup']=job.close()
            report.update(validation_complete=True,quality_passed=not report['issues'],all_frame_orders_equal=True,
                frame_count=len(report['frames']),text_ranges_checked=sum(len(f['layout']['rows']) for f in report['frames']),
                issue_count=len(report['issues']),status='succeeded' if not report['issues'] else 'failed')
            if report['issues']:
                raise AppError('HTML_QUALITY_FAILED','文字布局或字体存在问题/未核验项；详情见保留报告',exit_code=2,path=str(report_path))
            return report
    except BaseException as exc:
        if job:
            try:job.check()
            except AppError as reason:exc=reason
        report.update(status='failed',error=exc.as_dict() if isinstance(exc,AppError) else {'code':'HTML_PROCESS_FAILED','message':str(exc)[:2000]})
        if isinstance(exc,AppError):exc.path=str(report_path);raise exc
        raise AppError('HTML_PROCESS_FAILED','布局检查失败',exit_code=6,path=str(report_path),cause=str(exc)[:2000]) from exc
    finally:
        if job:report['cleanup']=job.close()
        atomic_write_json(report_path,report)


def render_frames(root, plan, output, report_path, *, timeout, cancel_file=None):
    report={'engine':ENGINE,'report_version':VERSION,'created_at':now_iso(),'plan':public_plan(plan),'status':'started'}
    job=None
    published=False
    sampling=_shutter_schedule(plan);capture_count=len(sampling) if sampling else plan['frame_count']
    encoded_frames=[];accumulator=None
    from .utils import atomic_write_json
    try:
        with tempfile.TemporaryDirectory(prefix='html-motion-') as temp_name, contextlib.ExitStack() as cleanup:
            if sampling:
                from .artifact_locks import verification_scope
                cleanup.enter_context(verification_scope())
                html_shutter.verify_implementation(plan['shutter_implementation'])
            temp=Path(temp_name)
            bundle=temp/'source';bundle.mkdir()
            for name,content in plan['data'].items():
                path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            runtime=plan['runtime'];spec=plan['spec'];fps=spec['fps']
            worker=Path(__file__).with_name('html_motion_worker.mjs')
            env=dict(os.environ)
            env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',NODE_OPTIONS='',CHROME_LOG_FILE=str(temp/'chromium.log'))
            job=BrowserProcessJob(timeout,cancel_file)
            cleanup.callback(job.close)
            scratch=temp/'result.nut'
            with (temp/'node.stderr.log').open('wb') as node_error, (temp/'ffmpeg.stderr.log').open('wb') as encoder_error:
                encoder=job.start([ffmpeg_path(),'-hide_banner','-v','error','-f','image2pipe','-framerate',f"{fps['num']}/{fps['den']}",
                    '-vcodec','png','-i','pipe:0','-an','-c:v','ffv1','-level','3','-pix_fmt','bgra','-threads','1','-y',str(scratch)],
                    cwd=temp,env=env,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=encoder_error)
                node=job.start([runtime['node'],str(worker)],cwd=temp,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=node_error)
                request={'root':str(bundle),'files':plan['files'],'spec':spec,'params':plan['parameters'],
                         'overrides':plan['compiled_overrides'],
                         'frame_count':capture_count,'ticks_per_second':plan['asset']['html_source']['ticks_per_second'],
                         'sampling_times':[r['worker_time_seconds'] for r in sampling] if sampling else None,
                         'playwright':runtime['playwright'],'chromium':runtime['chromium'],'log_file':str(temp/'chromium.log'),
                         'frame_timeout_ms':min(15000,int(timeout*1000))}
                node.stdin.write(encoded(request).replace(b'\n',b'')+b'\n');node.stdin.flush()
                frames=[]
                limit=max(2*1024**2,spec['width']*spec['height']*6+200000,capture_count*512)
                while True:
                    line=node.stdout.readline(limit+1)
                    job.check()
                    if not line or len(line)>limit or not line.endswith(b'\n'):
                        fail('HTML_PROTOCOL_INVALID','worker 没有返回完整有界消息')
                    item=json.loads(line)
                    if item.get('type')=='ready':
                        report['worker_started']=True
                        report['running_job_pids']=job.pids()
                        atomic_write_json(report_path,report)
                        continue
                    if item.get('type')=='error':
                        report['worker']=item
                        raise AppError(item['code'],item['message'],exit_code=6)
                    if item.get('type')=='done':
                        report['worker']=item
                        if len(frames)!=capture_count or len(encoded_frames)!=plan['frame_count'] or accumulator is not None or item.get('frame_hashes')!=frames or not item.get('all_frame_orders_equal') or not item.get('cleanup',{}).get('browser_closed'):
                            fail('HTML_PROTOCOL_INVALID','全帧或浏览器关闭回执不完整')
                        break
                    if item.get('type')!='frame' or item.get('index')!=len(frames):
                        fail('HTML_PROTOCOL_INVALID','帧序不连续')
                    png=base64.b64decode(item['png'],validate=True)
                    if png[:8]!=b'\x89PNG\r\n\x1a\n' or len(png)<24 or struct.unpack('>II',png[16:24])!=(spec['width'],spec['height']) or digest(png)!=item['sha256']:
                        fail('HTML_PROTOCOL_INVALID','PNG 尺寸或摘要不符')
                    if sampling:
                        row=sampling[item['index']];samples=plan['shutter']['effective_samples']
                        if row['sample_index']==0:accumulator=html_shutter.AlphaAccumulator((spec['width'],spec['height']),samples)
                        accumulator.push(png);job.check()
                        if row['sample_index']==samples-1:
                            html_shutter.verify_implementation(plan['shutter_implementation'])
                            combined,metrics=accumulator.finish();accumulator=None;job.check()
                            encoder.stdin.write(combined);encoder.stdin.flush()
                            encoded_frames.append({'output_frame':row['output_frame'],'png_sha256':digest(combined),
                                'source_capture_start':item['index']-samples+1,'source_capture_count':samples,**metrics})
                            report['progress']={'captured_subframes':item['index']+1,'encoded_output_frames':len(encoded_frames)}
                            atomic_write_json(report_path,report)
                    else:
                        encoder.stdin.write(png);encoder.stdin.flush()
                        encoded_frames.append({'output_frame':item['index'],'png_sha256':item['sha256'],
                            'source_capture_start':item['index'],'source_capture_count':1})
                    frames.append(item['sha256'])
                    node.stdin.write(encoded({'ack':item['index']}).replace(b'\n',b'')+b'\n');node.stdin.flush()
                    if scratch.exists() and scratch.stat().st_size>512*1024**2:
                        fail('HTML_OUTPUT_BUDGET','编码输出超过 512 MiB')
                encoder.stdin.close();node.stdin.close()
                if encoder.wait(timeout=15)!=0 or node.wait(timeout=15)!=0:
                    fail('HTML_ENCODER_FAILED','本地 worker/编码器退出异常')
                job.check()
            report['cleanup']=job.close()
            report['shutter_evidence']={'profile':plan.get('shutter'),'captures':sampling,
                'encoded_frames':encoded_frames,'source_capture_count':len(frames),
                'all_subframes_checked_in_two_fresh_context_orders':True,
                'quality_accepted':False,'continuous_playback_reviewed':False}
            report['stderr']={'node':(temp/'node.stderr.log').read_text(encoding='utf-8',errors='replace')[-4000:],
                              'ffmpeg':(temp/'ffmpeg.stderr.log').read_text(encoding='utf-8',errors='replace')[-4000:]}
            probe=probe_media(scratch)
            videos=[s for s in probe.get('streams',[]) if s.get('codec_type')=='video']
            if len(videos)!=1 or videos[0].get('pix_fmt')!='bgra' or videos[0].get('codec_name')!='ffv1':
                fail('HTML_ENCODER_FAILED','编码结果未保留 FFV1/BGRA')
            pts_result=run_process([ffprobe_path(),'-v','error','-select_streams','v:0','-show_frames',
                '-show_entries','frame=best_effort_timestamp','-of','json',str(scratch)],timeout=60,cancel_file=cancel_file)
            if pts_result.returncode:
                fail('HTML_ENCODER_FAILED','无法核对编码帧时钟')
            timestamps=[f.get('best_effort_timestamp') for f in json.loads(pts_result.stdout).get('frames',[])]
            timebase=Fraction(videos[0]['time_base'])
            expected_step=Fraction(fps['den'],fps['num'])
            if len(timestamps)!=plan['frame_count'] or any(t is None or int(t)*timebase!=i*expected_step for i,t in enumerate(timestamps)):
                fail('HTML_ENCODED_CLOCK_INVALID','内部容器未保留每个有理 CFR 帧时刻')
            report['encoded_clock']={'time_base':str(timebase),'timestamps':timestamps,
                                     'all_frames_exact':True,'frame_count':len(timestamps)}
            # NUT's format duration may name the last frame PTS, excluding its
            # display interval. The verified CFR clock gives the actual extent.
            extent=expected_step*len(timestamps)
            probe['container_duration_seconds']=probe['duration_seconds']
            probe['duration_seconds']=float(extent)
            probe['duration_tick']=round(extent*90000)
            probe['duration_basis']='verified_exact_cfr_frames'
            probe['video']['duration_seconds']=float(extent)
            probe['video']['frame_count']=len(timestamps)
            job.check()
            if scratch.stat().st_size>512*1024**2:
                fail('HTML_OUTPUT_BUDGET','编码输出超过 512 MiB')
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open('xb') as dest, scratch.open('rb') as src:
                published=True
                try:shutil.copyfileobj(src,dest)
                except BaseException:
                    dest.close();output.unlink(missing_ok=True);raise
            report.update(status='succeeded',output_sha256='sha256:'+sha256_file(output),probe=probe)
            return report
    except BaseException as exc:
        if published:
            output.unlink(missing_ok=True)
        if job:
            try:job.check()
            except AppError as reason:exc=reason
        report.update(status='failed',error=exc.as_dict() if isinstance(exc,AppError) else {'code':'HTML_PROCESS_FAILED','message':str(exc)[:2000]})
        if isinstance(exc,AppError):
            exc.path=str(report_path)
            raise exc
        raise AppError('HTML_PROCESS_FAILED','本地 HTML worker 或编码失败',exit_code=6,path=str(report_path),cause=str(exc)[:2000]) from exc
    finally:
        if job:
            report['cleanup']=job.close()
        try:
            atomic_write_json(report_path,report)
        except BaseException:
            if published:
                output.unlink(missing_ok=True)
            raise

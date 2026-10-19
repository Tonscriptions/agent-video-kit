"""OCR commands integrated with the existing CLI lock/transaction envelope."""
from __future__ import annotations
import copy
import math
from pathlib import Path
from . import local_ocr as ocr
from .errors import AppError
from .ocr_geometry import anchor_plan
from .policy import resolve_local_path
from .project import load_project, save_project, create_snapshot
from .rights import load_ledger, save_ledger, add_record
from .sequence_canvas import sequence_canvas
from .utils import atomic_write_json, new_id, now_iso, sha256_file


def add_parser(subs, leaf_common):
    domain=subs.add_parser('ocr',help='离线文字识别与文字框运镜锚点')
    actions=domain.add_subparsers(dest='action',required=True)
    registration=actions.add_parser('adapter');leaves=registration.add_subparsers(dest='registration_action',required=True)
    for action in ('register','list','inspect'):
        leaf=leaf_common(leaves.add_parser(action));leaf.add_argument('--project',required=True)
        if action!='list':
            leaf.add_argument('--adapter-id',required=True)
        if action=='register':
            leaf.add_argument('--model-path',required=True);leaf.add_argument('--python-executable',required=True)
            leaf.add_argument('--evidence',required=True);leaf.add_argument('--threads',type=int,default=4)
            leaf.add_argument('--license-spdx',default='LicenseRef-UNVERIFIED');leaf.add_argument('--creator',default='unknown')
            leaf.add_argument('--verification-status',choices=('unverified','verified','restricted'),default='unverified')
            leaf.add_argument('--permitted-use',action='append',default=None)
    scan=leaf_common(actions.add_parser('scan'))
    for name in ('project','asset-id','adapter-id','output'):
        scan.add_argument('--'+name,required=True)
    scan.add_argument('--start-frame',type=int,default=0);scan.add_argument('--end-frame',type=int)
    scan.add_argument('--step-frames',type=int,default=8);scan.add_argument('--max-frames',type=int,default=120)
    scan.add_argument('--timeout',type=float,default=600);scan.add_argument('--cancel-file')
    anchors=leaf_common(actions.add_parser('anchors'))
    for name in ('project','report','clip-id','query'):
        anchors.add_argument('--'+name,required=True)
    anchors.add_argument('--sequence-id');anchors.add_argument('--frame-index',type=int,required=True)
    anchors.add_argument('--zoom',type=float,default=1.5);anchors.add_argument('--hold-seconds',type=float,default=.5)
    anchors.add_argument('--return-seconds',type=float,default=.5);anchors.add_argument('--apply',action='store_true')


def handle(args):
    try:
        return _handle(args)
    except OSError as exc:
        raise ocr.fail('OCR_LOCAL_IO_FAILED', 'OCR 本地读写失败；元数据事务将回滚', exit_code=6, cause=str(exc)) from exc


def _handle(args):
    # Import after CLI initialization; all commands share its standard envelope.
    from .cli import _envelope, _operation
    root,project=load_project(args.project)
    warnings=[{'code':'OCR_REVIEW_REQUIRED','message':'识别文字/框需复核；抽样文字不证明全隐私覆盖或 UI 动作理解'}]
    command='ocr.'+args.action
    if args.action=='adapter':
        command+='.'+args.registration_action
        if args.registration_action in ('list','inspect'):
            records=ocr.registry(project).get('adapters',[]) if args.registration_action=='list' else [ocr.adapter_for(project,args.adapter_id)]
            return _envelope(command,args,data={'adapters':[{'adapter':a,'verification':ocr.verify_adapter(a)} for a in records],'network':'disabled'})
        if any(a.get('adapter_id')==args.adapter_id for a in ocr.registry(project).get('adapters',[])):
            raise ocr.fail('OCR_ADAPTER_EXISTS','已登记的适配器不可覆盖，请使用新 ID')
        adapter,rights=ocr.prepare_adapter(root,adapter_id=args.adapter_id,model_path=args.model_path,
            python_executable=args.python_executable,evidence=args.evidence,threads=args.threads,
            license_spdx=args.license_spdx,creator=args.creator,status=args.verification_status,uses=args.permitted_use)
        if args.dry_run:
            return _envelope(command,args,status='planned',data={'adapter':adapter,'rights':rights})
        snapshot=create_snapshot(root,project,label='before-ocr-register')
        extension=project.setdefault('extensions',{}).setdefault('local_ocr',{})
        extension.setdefault('adapters',[]).append(adapter)
        ledger=load_ledger(root);add_record(ledger,rights)
        operation=new_id('op')
        project.setdefault('provenance',{}).setdefault('change_log',[]).append({'command':command,'operation_id':operation,'adapter_id':args.adapter_id,'at':now_iso()})
        save_ledger(root,ledger);save_project(root,project)
        _operation(root,operation,{'command':command,'status':'succeeded','snapshot_id':snapshot['snapshot_id'],'adapter_id':args.adapter_id})
        return _envelope(command,args,data={'adapter':adapter,'rights':rights,'snapshot':snapshot},operation_id=operation)
    if args.action=='scan':
        if not math.isfinite(args.timeout) or not .1 <= args.timeout <= 3600:
            raise ocr.fail('OCR_TIMEOUT_INVALID', 'timeout 范围 0.1..3600 秒')
        assets=[a for a in project['assets'] if a['id']==args.asset_id]
        if len(assets)!=1:
            raise ocr.fail('OCR_ASSET_NOT_FOUND','OCR 输入资产不存在',exit_code=3)
        output=resolve_local_path(root,args.output,field='output')
        if not output.is_relative_to(root/'validation') or output.suffix.lower()!='.json' or output.exists():
            raise ocr.fail('OCR_OUTPUT_INVALID','输出须为项目 validation 内未使用的 JSON 路径')
        plan=ocr.scan_plan(root,assets[0],ocr.adapter_for(project,args.adapter_id),start_frame=args.start_frame,
                           end_frame=args.end_frame,step_frames=args.step_frames,max_frames=args.max_frames)
        cancel=resolve_local_path(root,args.cancel_file,field='cancel_file') if args.cancel_file else None
        if args.dry_run:
            return _envelope(command,args,status='planned',data={'plan':plan,'output':str(output),'model_executed':False},warnings=warnings)
        report=ocr.seal_report(ocr.execute_scan(root,plan,timeout=args.timeout,cancel_file=cancel))
        if cancel is not None and cancel.exists():
            raise ocr.fail('CANCELLED','OCR 提交前任务已取消',exit_code=8)
        snapshot=create_snapshot(root,project,label='before-ocr-scan')
        operation=new_id('op')
        try:
            atomic_write_json(output,report)
            project.setdefault('extensions',{}).setdefault('local_ocr',{}).setdefault('reports',[]).append({
                'path':output.relative_to(root).as_posix(),'file_sha256':'sha256:'+sha256_file(output),
                'source_asset_id':args.asset_id,'adapter_id':args.adapter_id,'at':now_iso()})
            project.setdefault('provenance',{}).setdefault('change_log',[]).append({'command':command,'operation_id':operation,'report':output.relative_to(root).as_posix(),'at':now_iso()})
            save_project(root,project)
            _operation(root,operation,{'command':command,'status':'succeeded','report':str(output),'snapshot_id':snapshot['snapshot_id']})
        except BaseException:
            if output.exists():
                output.unlink()
            raise
        return _envelope(command,args,data={'report':str(output),'frames':report['frames'],'process_cleanup':report['process_cleanup'],
                                          'detector_forwards':report['response']['detector_forwards'],
                                          'recognizer_forwards':report['response']['recognizer_forwards']},warnings=warnings,operation_id=operation)
    if args.action=='anchors':
        path,report=ocr.load_report(root,project,args.report)
        sequences=project['sequences']
        sequence_id=args.sequence_id or 'seq_main'
        sequence=next((s for s in sequences if s['id']==sequence_id),None)
        if sequence is None:
            raise ocr.fail('OCR_SEQUENCE_NOT_FOUND','找不到目标序列',exit_code=3)
        matches=[(t,c) for t in sequence['tracks'] for c in t.get('clips',[]) if c['id']==args.clip_id]
        if len(matches)!=1:
            raise ocr.fail('OCR_CLIP_NOT_FOUND','找不到唯一目标片段',exit_code=3)
        track,clip=matches[0]
        if track.get('locked'):
            raise ocr.fail('TRACK_LOCKED', '目标轨道已锁定；文字锚点不会覆盖锁定内容')
        canvas=sequence_canvas(project,sequence)
        plan=anchor_plan(report,clip,(canvas['width'],canvas['height']),query=args.query,frame_index=args.frame_index,
                         tps=project['settings']['timebase']['ticks_per_second'],zoom=args.zoom,hold_seconds=args.hold_seconds,return_seconds=args.return_seconds)
        plan.update(report=str(path),report_sha256=report['sha256'],rights_dependencies=report['rights_dependencies'])
        if args.dry_run or not args.apply:
            return _envelope(command,args,status='planned',data={'plan':plan,'applied':False},warnings=warnings)
        snapshot=create_snapshot(root,copy.deepcopy(project),label='before-ocr-anchors')
        clip.setdefault('keyframes',[]).extend(plan['keyframes'])
        source=next(a for a in project['assets'] if a['id']==report['source']['asset_id'])
        adapter=ocr.adapter_for(project,report['adapter_id'])
        dependencies=[*clip.get('rights_dependencies',[]),
                      {'rights_ref':source.get('rights_ref',source['id']),'sha256':source['sha256']},
                      {'rights_ref':adapter['rights_ref'],'sha256':adapter['sha256']}]
        clip['rights_dependencies']=list({(d['rights_ref'],d['sha256']):d for d in dependencies}.values())
        clip.setdefault('provenance',{})['ocr_anchor']={k:plan[k] for k in ('report_sha256','query','source_frame','source_box','method')}
        operation=new_id('op')
        project.setdefault('provenance',{}).setdefault('change_log',[]).append({'command':command,'operation_id':operation,'clip_id':args.clip_id,'report_sha256':report['sha256'],'at':now_iso()})
        from .validator import validate_project
        validation=validate_project(root,project)
        if not validation['ok']:
            raise AppError('OCR_ANCHOR_VALIDATION_FAILED','文字锚点候选校验失败',exit_code=4,cause=str(validation))
        save_project(root,project)
        _operation(root,operation,{'command':command,'status':'succeeded','clip_id':args.clip_id,'snapshot_id':snapshot['snapshot_id'],'plan':plan})
        return _envelope(command,args,data={'plan':plan,'applied':True,'snapshot':snapshot,'validation':validation},warnings=warnings,operation_id=operation)
    raise ocr.fail('OCR_COMMAND_INVALID','不支持的 OCR 操作')

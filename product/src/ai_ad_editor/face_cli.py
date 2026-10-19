"""Face commands use the standard project lock, snapshot and CLI transaction."""
from __future__ import annotations
import copy
from pathlib import Path

from . import local_face as face
from .media import probe_media
from .policy import resolve_local_path
from .project import load_project,save_project,create_snapshot
from .rights import load_ledger,save_ledger,add_record,record_for
from .utils import assert_id,atomic_write_json,new_id,now_iso,sha256_file,safe_filename


def add_parser(subs,leaf_common):
    domain = subs.add_parser('face',help='离线人脸锚点与显式局部修饰')
    actions = domain.add_subparsers(dest='action',required=True)
    registration = actions.add_parser('adapter').add_subparsers(dest='registration_action',required=True)
    for name in ('register','list','inspect'):
        leaf = leaf_common(registration.add_parser(name));leaf.add_argument('--project',required=True)
        if name != 'list':
            leaf.add_argument('--adapter-id',required=True)
        if name == 'register':
            for field in ('model-path','python-executable','evidence'):
                leaf.add_argument('--'+field,required=True)
            leaf.add_argument('--threads',type=int,default=4)
            leaf.add_argument('--license-spdx',default='LicenseRef-UNVERIFIED');leaf.add_argument('--license-url',default='')
            leaf.add_argument('--creator',default='unknown');leaf.add_argument('--permitted-use',action='append')
            leaf.add_argument('--verification-status',choices=('unverified','verified','restricted'),default='unverified')
    scan = leaf_common(actions.add_parser('scan'))
    for name in ('project','asset-id','adapter-id','output'):
        scan.add_argument('--'+name,required=True)
    scan.add_argument('--max-frames',type=int,default=1800);scan.add_argument('--max-faces',type=int,default=1)
    scan.add_argument('--detection-threshold',type=float,default=.6);scan.add_argument('--landmark-threshold',type=float,default=.6)
    scan.add_argument('--cut-frame',type=int,action='append',default=[])
    retouch = leaf_common(actions.add_parser('retouch'))
    for name in ('project','asset-id','derived-asset-id','python-executable'):
        retouch.add_argument('--'+name,required=True)
    sources = retouch.add_mutually_exclusive_group(required=True)
    sources.add_argument('--report');sources.add_argument('--recipe-from-asset')
    selection = retouch.add_mutually_exclusive_group()
    selection.add_argument('--all-detected',action='store_true');selection.add_argument('--face-id',action='append')
    for key in face.controls():
        retouch.add_argument('--'+key.replace('_','-'),type=float,default=None)
    for leaf in (scan,retouch):
        leaf.add_argument('--timeout',type=float,default=600);leaf.add_argument('--cancel-file')


def handle(args):
    try:
        return _handle(args)
    except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as exc:
        raise face.fail('FACE_ARGUMENT_OR_RECIPE_INVALID','人脸参数/报告/配方无效',cause=str(exc)) from exc
    except OSError as exc:
        raise face.fail('FACE_LOCAL_IO_FAILED','本地人脸文件读写失败，元数据事务将回滚',exit_code=6,cause=str(exc)) from exc


def _handle(args):
    from .cli import _envelope,_operation
    from .validator import validate_project
    root,project = load_project(args.project)
    command = 'face.'+args.action
    warnings = [{'code':'FACE_GEOMETRY_REVIEW_REQUIRED','message':'66 点为几何/表情锚点，不是身份、精确皮肤分割或自然美颜质量验收'}]
    if args.action == 'adapter':
        command += '.'+args.registration_action
        if args.registration_action in ('list','inspect'):
            records = face.registry(project).get('adapters',[]) if args.registration_action == 'list' else [face.adapter_for(project,args.adapter_id)]
            return _envelope(command,args,data={'adapters':[{'adapter':r,'verification':face.verify_adapter(r)} for r in records],'network':'disabled'})
        if any(a.get('adapter_id') == args.adapter_id for a in face.registry(project).get('adapters',[])):
            raise face.fail('FACE_ADAPTER_EXISTS','不覆盖已有适配器，请使用新 ID')
        adapter,rights = face.prepare_adapter(root,adapter_id=args.adapter_id,model_path=args.model_path,
            python_executable=args.python_executable,evidence=args.evidence,threads=args.threads,
            license_spdx=args.license_spdx,license_url=args.license_url,creator=args.creator,
            status=args.verification_status,uses=args.permitted_use)
        if args.dry_run:
            return _envelope(command,args,status='planned',data={'adapter':adapter,'rights':rights})
        snapshot = create_snapshot(root,project,label='before-face-register')
        project.setdefault('extensions',{}).setdefault('local_face',{}).setdefault('adapters',[]).append(adapter)
        ledger = load_ledger(root);add_record(ledger,rights)
        operation = new_id('op')
        project.setdefault('provenance',{}).setdefault('change_log',[]).append({'command':command,'operation_id':operation,'adapter_id':args.adapter_id,'at':now_iso()})
        save_ledger(root,ledger);save_project(root,project)
        _operation(root,operation,{'command':command,'status':'succeeded','adapter_id':args.adapter_id,'snapshot_id':snapshot['snapshot_id']})
        return _envelope(command,args,data={'adapter':adapter,'rights':rights,'snapshot':snapshot},operation_id=operation)

    matches = [a for a in project['assets'] if a['id'] == args.asset_id]
    if len(matches) != 1:
        raise face.fail('FACE_ASSET_NOT_FOUND','找不到唯一来源资产',exit_code=3)
    source = matches[0]
    cancel = resolve_local_path(root,args.cancel_file,field='cancel_file') if args.cancel_file else None
    if args.action == 'scan':
        output = resolve_local_path(root,args.output,field='output')
        if output.exists() or output.suffix.lower() != '.json' or not output.is_relative_to(root/'validation'):
            raise face.fail('FACE_OUTPUT_INVALID','扫描输出需为项目 validation 内未使用的 JSON')
        plan = face.scan_plan(root,source,face.adapter_for(project,args.adapter_id),max_frames=args.max_frames,max_faces=args.max_faces,
                              detection_threshold=args.detection_threshold,landmark_threshold=args.landmark_threshold,cuts=args.cut_frame)
        if args.dry_run:
            return _envelope(command,args,status='planned',data={'plan':plan,'model_executed':False},warnings=warnings)
        report = face.seal(face.execute(root,plan,timeout=args.timeout,cancel_file=cancel))
        if cancel is not None and cancel.exists():
            raise face.fail('CANCELLED','扫描提交前任务已取消',exit_code=8)
        snapshot = create_snapshot(root,project,label='before-face-scan');operation = new_id('op')
        try:
            atomic_write_json(output,report)
            face_ext = project.setdefault('extensions',{}).setdefault('local_face',{})
            face_ext.setdefault('reports',[]).append({'path':output.relative_to(root).as_posix(),'file_sha256':'sha256:'+sha256_file(output),
                                                     'source_asset_id':source['id'],'adapter_id':args.adapter_id,'at':now_iso()})
            project.setdefault('provenance',{}).setdefault('change_log',[]).append({'command':command,'operation_id':operation,'report':output.relative_to(root).as_posix(),'at':now_iso()})
            save_project(root,project)
            _operation(root,operation,{'command':command,'status':'succeeded','report':str(output),'snapshot_id':snapshot['snapshot_id']})
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        return _envelope(command,args,data={'report':str(output),'frames':plan['source']['frame_count'],
            'detector_forwards':report['response']['detector_forwards'],'landmark_forwards':report['response']['landmark_forwards'],
            'process_cleanup':report['process_cleanup']},warnings=warnings,operation_id=operation)

    if args.action != 'retouch':
        raise face.fail('FACE_COMMAND_INVALID','未知人脸命令')
    assert_id(args.derived_asset_id,'derived_asset_id')
    if any(a['id'] == args.derived_asset_id for a in project['assets']):
        raise face.fail('FACE_ASSET_EXISTS','不覆盖已有派生资产')
    output = resolve_local_path(root,'assets/derived/'+safe_filename(args.derived_asset_id)+'.mkv',field='output')
    if output.exists():
        raise face.fail('FACE_OUTPUT_EXISTS','不覆盖已有派生文件')
    ledger = load_ledger(root)
    if args.report:
        if not args.all_detected and not args.face_id:
            raise face.fail('FACE_SELECTION_REQUIRED','明确指定 --all-detected 或 --face-id')
        _,report = face.load_report(root,project,args.report)
        recipe = face.recipe_from_report(report,settings={k:getattr(args,k) or 0. for k in face.controls()},selected_ids=args.face_id)
        parents = [p['rights_ref'] for p in report['request']['rights_dependencies']]
        for parent in report['request']['rights_dependencies']:
            row = record_for(ledger,parent['rights_ref'])
            if row is None or row['sha256'] != parent['sha256']:
                raise face.fail('FACE_RIGHTS_SOURCE_CHANGED','扫描的来源/模型权利链已变更',exit_code=10)
    else:
        if args.all_detected or args.face_id or any(getattr(args,k) is not None for k in face.controls()):
            raise face.fail('FACE_REPLAY_OVERRIDE_UNSUPPORTED','保存配方重放不接受选择/强度覆盖；使用原扫描报告构建新配方')
        previous = next((a for a in project['assets'] if a['id'] == args.recipe_from_asset),None)
        if previous is None:
            raise face.fail('FACE_RECIPE_ASSET_NOT_FOUND','找不到配方资产',exit_code=3)
        recipe = copy.deepcopy(previous.get('source',{}).get('face_retouch',{}).get('recipe'))
        face.validate_recipe(recipe)
        prior_rights = record_for(ledger,previous['rights_ref'])
        if prior_rights is None or prior_rights['sha256'] != previous['sha256']:
            raise face.fail('FACE_RECIPE_RIGHTS_CHANGED','配方资产权利记录无效',exit_code=10)
        parents = [source.get('rights_ref',source['id']),previous['rights_ref']]
    if any(record_for(ledger,p) is None for p in parents):
        raise face.fail('FACE_RIGHTS_PARENT_MISSING','缺少来源/模型权利父链',exit_code=10)
    plan = face.retouch_plan(root,source,recipe,python_executable=args.python_executable,output=output)
    if plan['source']['transfer_assumed']:
        warnings.append({'code':'FACE_UNSPECIFIED_TRANSFER_ASSUMED_SRGB','message':'源未声明传递函数；计划明确按 sRGB 解读，不代表已测得真实色彩空间'})
    if args.dry_run:
        return _envelope(command,args,status='planned',data={'plan':plan,'model_forwards':0,'output':str(output)},warnings=warnings)
    snapshot = create_snapshot(root,project,label='before-face-retouch');operation = new_id('op')
    report_path = root/'validation'/('face-retouch-'+operation+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    committed = False
    try:
        result = face.seal(face.execute(root,plan,python_executable=args.python_executable,timeout=args.timeout,cancel_file=cancel))
        if cancel is not None and cancel.exists():
            raise face.fail('CANCELLED','局部修饰提交前任务已取消',exit_code=8)
        asset = {'id':args.derived_asset_id,'kind':'video','uri':output.relative_to(root).as_posix(),'sha256':'sha256:'+sha256_file(output),
                 'probe':probe_media(output),'rights_ref':args.derived_asset_id,
                 'source':{'kind':'local-face-retouch','derived_from':[source['id']], 'face_retouch':{'recipe':recipe}}}
        rights = {'asset_id':asset['rights_ref'],'kind':'video','sha256':asset['sha256'],'source_url':'local://face-retouch/'+asset['id'],
                  'source_version':face.RETOUCH,'retrieved_at':now_iso(),'creator':'local explicit face retouch',
                  'license_spdx':'LicenseRef-Derived','license_url':'','attribution':'','permitted_uses':['internal'],
                  'permitted_channels':[],'restrictions':[],'derived_from':sorted(set(parents)),
                  'evidence':report_path.relative_to(root).as_posix(),'verification_status':'unverified','verified_by':'',
                  'takedown_status':'clear','notes':'Source/model rights remain in parent chain; output is not automatic publication clearance.'}
        project['assets'].append(asset);add_record(ledger,rights)
        save_ledger(root,ledger)
        validation = validate_project(root,project,strict_rights=False)
        if not validation['ok']:
            raise face.fail('FACE_PROJECT_INVALID','局部修饰候选项目未通过校验',exit_code=4,cause=str(validation))
        atomic_write_json(report_path,result)
        project.setdefault('provenance',{}).setdefault('change_log',[]).append({'command':command,'operation_id':operation,'asset_id':asset['id'],'report':report_path.relative_to(root).as_posix(),'at':now_iso()})
        save_project(root,project)
        _operation(root,operation,{'command':command,'status':'succeeded','asset_id':asset['id'],'snapshot_id':snapshot['snapshot_id'],'report':str(report_path)})
        committed = True
        return _envelope(command,args,data={'asset_id':asset['id'],'output':str(output),'report':str(report_path),'model_forwards':0,
                                          'frames':plan['source']['frame_count'],'validation':validation,'process_cleanup':result['process_cleanup']},warnings=warnings,operation_id=operation)
    finally:
        if not committed:
            output.unlink(missing_ok=True);report_path.unlink(missing_ok=True)

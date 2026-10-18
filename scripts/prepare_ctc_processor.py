"""Explicitly normalize old local processor metadata without changing weights."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(4*1024*1024):h.update(data)
    return h.hexdigest()


def main(args):
    source,output,evidence=args.source.resolve(),args.output.resolve(),args.evidence.resolve()
    assert source.is_relative_to(ROOT/'product/.runtime') and output.is_relative_to(ROOT/'product/.runtime')
    assert not output.exists() and not evidence.exists()
    previous=json.loads(args.conversion_evidence.read_text(encoding='utf-8'))
    assert previous['status']=='verified'
    for row in previous['output_files']:
        p=source/row['name'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    config=json.loads((source/'preprocessor_config.json').read_text(encoding='utf-8'))
    assert config['sampling_rate']==16000 and 'feature_extractor_type' not in config
    shutil.copytree(source,output)
    config['feature_extractor_type']='Wav2Vec2FeatureExtractor'
    path=output/'preprocessor_config.json'
    path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    evidence.parent.mkdir(parents=True,exist_ok=True)
    evidence.write_text(json.dumps({'status':'verified','previous_evidence_sha256':sha(args.conversion_evidence),
        'explicit_generated_field':{'feature_extractor_type':'Wav2Vec2FeatureExtractor'},
        'reason':'Old upstream processor JSON omits the class. Product requires the explicit built-in class; preserve that strict gate.',
        'source_model_weights_changed':False,'generator_sha256':sha(Path(__file__)),
        'output_files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output.iterdir())]},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'verified','files':len(previous['output_files'])}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('source','output','conversion-evidence','evidence'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())

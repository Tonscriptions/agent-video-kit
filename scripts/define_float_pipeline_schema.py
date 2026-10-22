"""Add a discoverable typed pipeline contract to both identical shipped schemas."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    paths=[ROOT/'docs/specs/agent-project.schema.json',ROOT/'product/src/ai_ad_editor/agent-project.schema.json']
    assert paths[0].read_bytes()==paths[1].read_bytes()
    schema=json.loads(paths[0].read_bytes())
    assert 'nativeFloatPipeline' not in schema['$defs']
    signal={'type':'object','additionalProperties':False,'required':['primaries','transfer'],
            'properties':{'primaries':{'enum':['bt709','display-p3','bt2020']},
                          'transfer':{'enum':['linear','srgb','bt709-oetf','gamma22','gamma24']}}}
    source={'type':'object','additionalProperties':False,'required':['source_signal','display_geometry'],
            'properties':{'source_signal':signal,'display_geometry':{'const':'square-unrotated'},
                          'alpha_association':{'enum':['straight','premultiplied']},
                          'scan':{'const':'progressive'},'decoder':{'type':'string','pattern':'^[A-Za-z0-9_]{1,64}$'},
                          'demux_origin':{'oneOf':[{'type':'integer'},{'type':'string','pattern':'^-?[0-9]+(?:/[1-9][0-9]*)?$'}]},
                          'yuv_spec':{'type':'object','additionalProperties':False,'required':['matrix','range','chroma_location'],
                            'properties':{'matrix':{'enum':['bt709','smpte170m','bt470bg','bt2020nc']},
                                          'range':{'enum':['limited','full']},
                                          'chroma_location':{'enum':['left','center','topleft','top','bottomleft','bottom']}}}}}
    schema['$defs']['nativeFloatPipeline']={
        'type':'object','additionalProperties':False,'required':['engine','working_signal','output_signal','sources'],
        'properties':{'engine':{'const':'float32-native-v1'},'working_signal':signal,'output_signal':signal,
            'background_signal':signal,'range_policy':{'enum':['reject','clip']},
            'window_frames':{'type':'integer','minimum':1,'maximum':256},
            'max_source_cache_bytes':{'type':'integer','minimum':1,'maximum':8*1024**3},
            'max_open_sources':{'type':'integer','minimum':1,'maximum':256},
            'native_timeout_seconds':{'type':'integer','minimum':1,'maximum':3600},
            'sources':{'type':'object','maxProperties':4096,'additionalProperties':source}}}
    schema['$defs']['settings']['properties']['pixel_pipeline']={'oneOf':[{'type':'null'},{'$ref':'#/$defs/nativeFloatPipeline'}]}
    text=json.dumps(schema,ensure_ascii=False,indent=2)+'\n'
    for path in paths:path.write_text(text,encoding='utf8',newline='\n')
    print('Both Agent Project schemas contain the identical typed pixel_pipeline contract')

if __name__=='__main__':main()

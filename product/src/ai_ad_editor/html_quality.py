"""Read-only all-frame DOM geometry and local-font quality evidence."""
from __future__ import annotations
import copy
import unicodedata
from .font_coverage import FontCoverage, FontInvalid
from .errors import AppError
from .html_motion import digest


def font_catalogue(plan):
    records=[]; fonts={'names':{},'paths':{}}; identities={};decoded=units=0
    names=[name for name in plan['data'] if name.rsplit('.',1)[-1].lower() in {'ttf','otf','woff','woff2'}]
    if len(names)>64:raise AppError('HTML_LAYOUT_BUDGET','字体解析超过 64 个本地文件',exit_code=2)
    for name,data in sorted(plan['data'].items()):
        if name.rsplit('.',1)[-1].lower() not in {'ttf','otf','woff','woff2'}:continue
        item={'path':name,'sha256':digest(data),'bytes':len(data)}
        try:
            font=FontCoverage(data)
            decoded+=font.decoded_table_bytes;units+=font.mapping_units
            if decoded>128*1024**2 or units>262144:
                raise AppError('HTML_LAYOUT_BUDGET','累计字体解析超过 128 MiB 解压表或 262144 映射单元',exit_code=2)
            item.update(status='mapped',postscript_name=font.postscript_name,family=font.names.get(16,font.names.get(1,'')),cmap_format=font.format,
                        decoded_table_bytes=font.decoded_table_bytes,mapping_units=font.mapping_units)
            identity=(font.postscript_name,item['sha256'])
            if identity in identities:
                font=identities[identity]
            else:
                identities[identity]=font
                fonts['names'].setdefault(font.postscript_name,[]).append(font)
            fonts['paths']['local://html-source/'+name]=font
        except FontInvalid as exc:
            item.update(status='unverified',reason=str(exc))
        records.append(item)
    return records,fonts


def review_frame(layout, fonts):
    result=copy.deepcopy(layout); issues=[]
    for region in layout['unsupported']:
        issues.append({'code':'LAYOUT_UNVERIFIED',**region})
    for row in result['rows']:
        for problem in row['problems']:
            issues.append({'at':row['at'],'text_node':row['text_node'],**problem})
        used=[]; unresolved=[]
        for actual in row['platform_fonts']:
            if actual['glyphCount']<=0:continue
            matches=fonts['names'].get(actual['postScriptName'],[])
            if not actual['isCustomFont'] or len(matches)!=1:
                unresolved.append(actual['postScriptName'])
            else:used.append(matches[0])
        points={ord(c) for c in row['painted_text'] if not c.isspace() and unicodedata.category(c) not in {'Cc','Cf'}}
        if unresolved or (points and not used):
            issues.append({'code':'FONT_SOURCE_UNVERIFIED','at':row['at'],'text_node':row['text_node'],'postscript_names':unresolved})
        # When the declared font has no usable glyphs, Chromium may use only a
        # system fallback. Check its explicit local face URLs as evidence too.
        families=[x.strip().strip('\"\'').casefold() for x in row['font_family'].split(',')]
        declared=[fonts['paths'][url] for face in layout['face_sources'] if face['family'].casefold() in families
                  for url in face['urls'] if url in fonts['paths']]
        candidates=used or declared
        missing=[]; sequences=[]
        for cp in sorted(points):
            if 0xfe00<=cp<=0xfe0f or 0xe0100<=cp<=0xe01ef:
                sequences.append(f'U+{cp:04X}');continue
            try:
                if candidates and not any(font.glyph(cp) for font in candidates):missing.append(f'U+{cp:04X}')
            except FontInvalid as exc:
                issues.append({'code':'FONT_MAPPING_UNVERIFIED','at':row['at'],'reason':str(exc)})
        if '\u200d' in row['painted_text']:sequences.append('U+200D')
        if sequences:issues.append({'code':'FONT_SEQUENCE_UNVERIFIED','at':row['at'],'codepoints':sequences})
        if missing:issues.append({'code':'FONT_GLYPH_MISSING','at':row['at'],'text_node':row['text_node'],'codepoints':missing})
        row['mapping_checked']=bool(used) and not unresolved and not sequences
        row['missing_codepoints']=missing
    result['issues']=issues
    return result

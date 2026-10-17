import {readFileSync} from 'node:fs';
import {segmentLine,alignTranslation,subtitleEnd,subtitleCells,SUBTITLE_SEGMENT_RULES} from "file:///E:/dev/sandbox/AI%E5%B9%BF%E5%91%8A%E5%89%AA%E8%BE%91/product/.runtime/openfilm-audit-20261017/source/packages/openfilm/studio/server/subtitle-segments.mjs";
const requests=JSON.parse(readFileSync(0,'utf8'));
const result=requests.map(r=>{const R={...SUBTITLE_SEGMENT_RULES,...r.rules};const p=segmentLine(r.line,R);const tr=r.translation===undefined||r.translation===null?null:alignTranslation(r.translation,p,R);return p.map((x,i)=>({...x,display_text:subtitleEnd(x.text),cells:subtitleCells(subtitleEnd(x.text)),...(tr?{translation:tr[i]}:{})}));});
process.stdout.write(JSON.stringify(result));

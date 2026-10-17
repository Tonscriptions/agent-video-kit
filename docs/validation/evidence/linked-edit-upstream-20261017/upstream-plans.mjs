import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
const [tree, input] = process.argv.slice(2);
const p = await import(pathToFileURL(resolve(tree, 'packages/openfilm/studio/ui/src/lib/timeline-edit.ts')));
const { applyOps } = await import(pathToFileURL(resolve(tree, 'packages/openfilm/studio/server/ops.mjs')));
const rows = JSON.parse(readFileSync(input, 'utf8'));
const outputs = rows.map(({id,project,request}) => {
  const source = project.sequences[0].tracks;
  const pictures = source.filter(t => t.kind !== 'audio').sort((a,b) => b.order-a.order);
  const audio = source.filter(t => t.kind === 'audio').sort((a,b) => a.order-b.order);
  const ordered = [...pictures,...audio];
  const model = ordered.map((t,index) => ({index,role:t.kind==='audio'?'audio':t.kind==='subtitle'?'mg':'video',
    locked:!!t.locked,clips:t.clips.map(c => ({id:c.id,startMs:c.timeline_start_tick,
      endMs:c.timeline_start_tick+c.duration_tick,inMs:c.source_in_tick,speed:c.speed??1,sourceMs:1e9,
      ...(c.link_id?{link:c.link_id}:{})}))}));
  const film = {stage:{w:160,h:90},tracks:ordered.map(t => ({nativeTrackId:t.id,locked:!!t.locked,
    clips:t.clips.map(c => ({id:c.id,src:c.id+'.mp4',at:c.timeline_start_tick/1000,
      time:[c.source_in_tick/1000,c.source_out_tick/1000],...(c.link_id?{attrs:{'data-link':c.link_id}}:{})}))}))};
  const opts = request.options??{};
  const ids = request.clip_ids??[];
  const track = model.find(t => ordered[t.index].id===(request.track_id??'main')).index;
  let plan;
  if(request.action==='remove') plan = p.planRemove(model,p.linkedIds(model,ids),{...opts,ripple:opts.ripple??false});
  else if(request.action==='close_gaps') plan=p.planCloseTrackGaps(model,track,opts);
  else if(request.action==='link') plan={ops:p.planLink(model,ids),shortMs:0};
  else if(request.action==='unlink') plan={ops:p.planUnlink(model,ids),shortMs:0};
  else throw new Error('Unsupported oracle action');
  const result = applyOps(film,plan.ops);
  const positions={};const links=new Map();
  for(const t of result.tracks)for(const c of t.clips){
    const a=Math.round((c.at??0)*1000);const d=Math.round((c.time[1]-c.time[0])/(c.speed??1)*1000);
    positions[c.id]=[t.nativeTrackId??null,a,a+d];
    const link=c.attrs?.['data-link'];
    if(link){const group=links.get(link)??[];group.push(c.id);links.set(link,group);}
  }
  const groups=[...links.values()].map(g=>g.sort()).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
  return {id,positions,groups,short_tick:Math.round(plan.shortMs),ops:plan.ops};
});
process.stdout.write(JSON.stringify(outputs));

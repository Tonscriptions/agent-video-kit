// Native host geometry extension; the original MIT cutText is injected beside it.
export const QUALITY_DOM = String.raw`
function layoutCapture() {
  const rows=[], unsupported=[]; let nodes=0, chars=0;
  const addUnsupported=(at,kind)=>{
    if(!unsupported.some(x=>x.at===at && x.kind===kind)) unsupported.push({at,kind});
    budget(unsupported.length,64,'unsupported layout regions');
  };
  const rect=r=>({left:r.left,top:r.top,right:r.right,bottom:r.bottom});
  const round=r=>Object.fromEntries(Object.entries(r).map(([k,v])=>[k,Math.round(v*1e6)/1e6]));
  const outside=(r,b,x=true,y=true)=>{
    const badX=x&&(r.left<b.left-0.5 || r.right>b.right+0.5);
    const badY=y&&(r.top<b.top-0.5 || r.bottom>b.bottom+0.5);
    return badX||badY ? {fully_outside:(x&&(r.right<=b.left || r.left>=b.right)) || (y&&(r.bottom<=b.top || r.top>=b.bottom)),axes:[badX&&'x',badY&&'y'].filter(Boolean)} : null;
  };
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  for(let node=walker.nextNode();node;node=walker.nextNode()) {
    budget(++nodes,5000,'layout text nodes');
    const el=node.parentElement, text=node.textContent;
    if(!el || !text.trim() || ['script','style','title','noscript','template'].includes(el.localName))continue;
    let visible=true;const ancestors=[];
    for(let a=el;a;a=a.parentElement) {
      const css=getComputedStyle(a);
      if(css.display==='none'||['hidden','collapse'].includes(css.visibility)||Number(css.opacity)<=0){visible=false;break;}
      ancestors.push({el:a,css});
    }
    if(!visible)continue;
    const range=document.createRange();range.selectNodeContents(node);
    const rects=[...range.getClientRects()].filter(r=>r.width>0 && r.height>0).map(rect);
    if(!rects.length)continue;
    budget(rows.length+1,128,'visible text ranges');budget(rects.length,128,'text line rectangles');
    budget(text.length,8000,'layout text length');budget(chars+=text.length,32768,'visible character budget');
    const at=selectorOf(el), css=getComputedStyle(el), problems=[];
    if(el.namespaceURI!=='http://www.w3.org/1999/xhtml')addUnsupported(at,'non-HTML-text');
    for(const {el:a,css:s} of ancestors) {
      if(s.transform!=='none') {
        const m=new DOMMatrixReadOnly(s.transform);
        if(!m.is2D || Math.abs(m.b)>1e-10 || Math.abs(m.c)>1e-10 || m.a<=0 || m.d<=0)addUnsupported(at,'rotated-or-3d-text');
      }
      if(s.clipPath!=='none'||s.maskImage!=='none'||s.clip!=='auto'||s.filter!=='none'||s.perspective!=='none')addUnsupported(at,'masked-filtered-or-perspective-text');
      if(s.borderRadius!=='0px' && /hidden|clip|scroll|auto/.test(s.overflowX+s.overflowY))addUnsupported(at,'rounded-clip-text');
    }
    for(let i=0;i<rects.length;i++) {
      const r=rects[i], frame=outside(r,{left:0,top:0,right:innerWidth,bottom:innerHeight});
      if(frame)problems.push({code:frame.fully_outside?'TEXT_OUTSIDE_FRAME':'TEXT_CLIPPED_FRAME',line:i,...frame});
      for(const {el:a,css:s} of ancestors) {
        if(a===document.documentElement)continue;
        let x=/^(hidden|clip|scroll|auto)$/.test(s.overflowX),y=/^(hidden|clip|scroll|auto)$/.test(s.overflowY);
        if(a===document.body) {
          // Body overflow propagates to the viewport while the root is visible.
          const root=getComputedStyle(document.documentElement);
          if(root.overflowX==='visible')x=false;
          if(root.overflowY==='visible')y=false;
        }
        if(!x&&!y)continue;
        const box=a.getBoundingClientRect(),sx=a.offsetWidth?box.width/a.offsetWidth:1,sy=a.offsetHeight?box.height/a.offsetHeight:1;
        const bounds={left:box.left+a.clientLeft*sx,top:box.top+a.clientTop*sy};
        bounds.right=bounds.left+a.clientWidth*sx;bounds.bottom=bounds.top+a.clientHeight*sy;
        const issue=outside(r,bounds,x,y);
        if(issue)problems.push({code:issue.fully_outside?'TEXT_OUTSIDE_CONTAINER':'TEXT_CLIPPED_CONTAINER',line:i,container:selectorOf(a),...issue});
      }
    }
    let painted=text;
    const language=el.closest('[lang]')?.getAttribute('lang')||'en-US';
    try {
      if(css.textTransform==='uppercase')painted=text.toLocaleUpperCase(language);
      else if(css.textTransform==='lowercase')painted=text.toLocaleLowerCase(language);
      else if(css.textTransform!=='none')addUnsupported(at,'text-transform-'+css.textTransform);
    } catch {addUnsupported(at,'unknown-text-language');}
    rows.push({at,text,painted_text:painted,text_node:[...el.childNodes].indexOf(node),rects:rects.map(round),
      font_family:css.fontFamily,font_size:css.fontSize,font_weight:css.fontWeight,font_style:css.fontStyle,
      problems});
  }
  for(const el of document.querySelectorAll('canvas,svg text,svg foreignObject')) {
    const r=el.getBoundingClientRect(),s=getComputedStyle(el);
    if(r.width && r.height && s.display!=='none' && s.visibility!=='hidden' && Number(s.opacity)>0)addUnsupported(selectorOf(el),'canvas-or-SVG-semantic-text');
  }
  const face_sources=[];let cssRules=0;
  function fontRules(rules,base) {
    for(const rule of rules) {
      budget(++cssRules,5000,'font CSS rules');
      if(rule.type===CSSRule.FONT_FACE_RULE) {
        const family=rule.style.getPropertyValue('font-family').trim().replace(/^['"]|['"]$/g,'');
        const urls=[...rule.style.getPropertyValue('src').matchAll(/url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*))\s*\)/g)].map(m=>sourceAddress(new URL(m[1]??m[2]??m[3],base).href));
        face_sources.push({family,urls});budget(face_sources.length,64,'declared font faces');
      }
      if(rule.cssRules)fontRules(rule.cssRules,base);
    }
  }
  for(const sheet of document.styleSheets)fontRules(sheet.cssRules,sheet.href||location.href);
  return {rows,unsupported,face_sources,upstream_partial_clipping:cutText(),tolerance_css_pixels:0.5};
}
window.__agentVideoQuality={capture:layoutCapture};
`;

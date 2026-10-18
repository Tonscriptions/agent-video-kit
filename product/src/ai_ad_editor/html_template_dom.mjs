// Agent Video Kit DOM bridge; OpenFilm's MIT functions are injected beside it.
// No network, module imports, user scripts, or raw CSS styles enter this bridge.
export const TEMPLATE_DOM = String.raw`
const state = {win: window, touched: new Map(), found: []};
const issue = (code, message) => {throw Object.assign(new Error(code+': '+message), {code});};
const budget = (value, limit, label) => {
  if(value > limit) issue('HTML_CONTROL_BUDGET', label); return value;
};
function rootNames() {
  const names = new Set(); let rules = 0;
  function walk(list) {
    for(const rule of list) {
      budget(++rules, 5000, 'CSS rules');
      if(rule.selectorText?.split(',').some(s => s.trim() === ':root'))
        for(const key of rule.style) if(key.startsWith('--')) names.add(key);
      if(rule.cssRules) walk(rule.cssRules);
    }
  }
  for(const sheet of document.styleSheets) walk(sheet.cssRules);
  for(const key of document.documentElement.style) if(key.startsWith('--')) names.add(key);
  budget(names.size, 64, 'root variables');
  return names;
}
function selectorOf(el) {
  if(el.id && document.querySelectorAll('#'+CSS.escape(el.id)).length === 1) return '#'+CSS.escape(el.id);
  const chain = [];
  while(el && el.nodeType === 1) {
    let n = 1, prev = el.previousElementSibling;
    while(prev) {if(prev.localName === el.localName) n++; prev = prev.previousElementSibling;}
    chain.unshift(el.localName+':nth-of-type('+n+')'); el = el.parentElement;
  }
  const selector = chain.join(' > ');
  if(selector.length > 512) issue('HTML_CONTROL_BUDGET', 'selector depth');
  return selector;
}
function urlValue(css) {
  const m = /^\s*url\(\s*(?:"((?:\\.|[^"])*)"|'((?:\\.|[^'])*)'|([^)\s]*))\s*\)\s*$/.exec(css ?? '');
  return m ? (m[1] ?? m[2] ?? m[3] ?? '').replace(/\\(.)/g, '$1') : null;
}
function sourceAddress(value) {
  if(!value) return '';
  const url = new URL(value, location.href);
  if(url.protocol === 'data:') return 'embedded-data-image';
  if(url.origin !== location.origin) issue('HTML_OVERRIDE_INVALID', 'Nonlocal image control');
  // Computed background/content URLs are absolute in Chromium. The report
  // uses a metadata-only local identity, never a synthetic HTTP endpoint.
  return 'local://html-source'+url.pathname;
}
function collect() {
  const vars = [], texts = [], images = [], computed = getComputedStyle(document.documentElement);
  for(const name of [...rootNames()].sort()) {
    const value = computed.getPropertyValue(name).trim();
    budget(value.length, 2048, 'variable value');
    const field = fieldOf(value, v => CSS.supports('color', v));
    if(field.kind === 'number' && !Number.isFinite(field.value)) issue('HTML_CONTROL_BUDGET', 'nonfinite CSS number');
    vars.push({name, value, label: labelOf(name), field, font: isFontVar(name, value)});
  }
  const elements = document.querySelectorAll('*'); budget(elements.length, 5000, 'DOM elements');
  for(const el of elements) {
    if(['script','style','head','meta','link','title','noscript','template'].includes(el.localName)) continue;
    const css = getComputedStyle(el);
    if(css.display === 'none' || css.visibility === 'hidden') continue;
    const value = linesOf(el);
    if(value.trim()) {
      budget(texts.length+1, 128, 'text controls'); budget(value.length, 8000, 'text length');
      texts.push({at: selectorOf(el), label: value.trim().slice(0,120), value});
    }
    const bg = urlValue(css.backgroundImage);
    if(el.localName === 'img' || bg) {
      budget(images.length+1, 64, 'image controls');
      images.push({at: selectorOf(el), kind: el.localName === 'img' ? 'img' : 'bg',
        label: (el.getAttribute('alt') || el.id || el.localName).slice(0,120),
        src: sourceAddress(el.localName === 'img' ? urlValue(css.content) || el.getAttribute('src') || '' : bg)});
    }
  }
  return {vars, texts, images, scope: 'visible-DOM-direct-text-single-image-and-root-CSS-at-sampled-frame'};
}
async function apply(list) {
  const known = rootNames(); let total = 0;
  for(const item of list) {
    let nodes;
    try {nodes = [...document.querySelectorAll(item.at)];}
    catch {issue('HTML_OVERRIDE_SELECTOR_INVALID', 'Invalid selector '+item.at);}
    if(item.n != null) nodes = nodes.slice(item.n-1, item.n);
    if(!nodes.length) issue('HTML_OVERRIDE_TARGET_MISSING', item.at);
    budget(nodes.length, 128, 'matches per override'); budget(total += nodes.length, 1024, 'total override matches');
    for(const key of Object.keys(item.style || {}))
      if(key.startsWith('--') && !known.has(key)) issue('HTML_OVERRIDE_VARIABLE_MISSING', key);
    for(const el of nodes) {
      if(item.text != null && ![...el.children].every(c => c.localName === 'br') &&
          ![...el.childNodes].some(n => n.nodeType === 3 && n.data.trim()))
        issue('HTML_OVERRIDE_TEXT_UNSUPPORTED', item.at);
      if(item._image_kind === 'img' && el.localName !== 'img') issue('HTML_OVERRIDE_IMAGE_KIND', item.at);
      if(item._image_kind === 'bg' && (el.localName === 'img' || !urlValue(getComputedStyle(el).backgroundImage)))
        issue('HTML_OVERRIDE_IMAGE_KIND', item.at);
    }
  }
  const replacementUrls = list.flatMap(item => Object.values(item.style || {})).map(urlValue).filter(Boolean);
  await Promise.all([...new Set(replacementUrls)].map(async src => {
    const image = new Image(); image.src = src; await image.decode();
  }));
  override(state, list);
  await document.fonts.ready;
  // CSS content/background replacements are awaited by screenshot and a pair
  // of animation frames; source <img> decoding has its own explicit failure.
  await Promise.all([...document.images].map(async image => {
    if(image.getAttribute('src')) await image.decode();
  }));
  return {entries: list.length, matches: total, every_target_found: state.found.every(Boolean)};
}
window.__agentVideoTemplate = {collect, apply, restore: () => restore(state)};
`;

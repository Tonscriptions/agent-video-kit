// Adapted from OpenFilm eefd6a8d379289102141359a4718dbab12170526 template-controls.ts (MIT).
// Copyright (c) 2026 OpenFilm contributors. See OPENFILM_LICENSE.txt.
// Only TypeScript annotations/assertions are removed; four function bodies retain upstream rules.
const COLOR = /^(#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})|(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(.*\))$/i;
const NUMBER = /^(-?(?:\d+\.?\d*|\.\d+))([a-z%]*)$/i;
const QUOTED = /^(["'])((?:\\.|(?!\1).)*)\1$/;

/** The field for a value. `isColor` also takes a named color (`red`), which only a browser knows. */
export function fieldOf(value, isColor = () => false) {
  const v = value.trim();
  if (COLOR.test(v) || (/^[a-z]+$/i.test(v) && isColor(v))) return { kind: 'color', value: v };
  const num = NUMBER.exec(v);
  if (num) return { kind: 'number', value: Number(num[1]), unit: num[2].toLowerCase() };
  const quoted = QUOTED.exec(v);
  if (quoted) return { kind: 'text', value: quoted[2].replace(/\\(.)/g, '$1') };
  return { kind: 'raw', value: v };
}

/** A custom property that names a font (`--title-font: "Inter", sans-serif`): changed with the font picker. */
export function isFontVar(name, value) {
  return /font|family|typeface/i.test(name) && !NUMBER.test(value.trim()) && !COLOR.test(value.trim());
}

/** What a field writes back: a number with its unit, words quoted as CSS writes a string. */
export function valueOf(field) {
  if (field.kind === 'number') return `${Math.round(field.value * 1000) / 1000}${field.unit}`;
  if (field.kind === 'text') return `"${field.value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\A ')}"`;
  return field.value.trim();
}

/** A custom property's name as a person reads it: `--accent-color` → "Accent color", `--titleSize` → "Title size". */
export function labelOf(name) {
  const words = name.replace(/^-+/, '').replace(/([a-z0-9])([A-Z])/g, '$1 $2').split(/[-_\s]+/).filter(Boolean).join(' ').toLowerCase();
  return words ? words[0].toUpperCase() + words.slice(1) : name;
}


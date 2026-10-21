"""Bounded local SFNT/WOFF1 Unicode mapping inspection, standard library only.

Mapping to a nonzero glyph does not establish shaping or visual correctness.
"""
from __future__ import annotations
import bisect
import struct
import zlib

MAX_FONT_BYTES = 64 * 1024**2


class FontInvalid(ValueError):
    pass


def unpack(data, fmt, offset):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise FontInvalid('font table exceeds its byte boundary')
    return struct.unpack_from(fmt, data, offset)


def tables_of(data):
    if len(data) > MAX_FONT_BYTES:
        raise FontInvalid('font exceeds 64 MiB')
    signature = data[:4]
    if signature == b'wOFF':
        _, length, count = unpack(data, '>4sIH', 4)
        if length != len(data):
            raise FontInvalid('WOFF length differs from file')
        stride, start = 20, 44
    elif signature in (b'\0\1\0\0', b'OTTO', b'true'):
        count, = unpack(data, '>H', 4)
        stride, start = 16, 12
    else:
        raise FontInvalid('unsupported font container (requires SFNT or WOFF1)')
    if not 1 <= count <= 256:
        raise FontInvalid('font table count exceeds budget')
    out = {}; total = 0
    for i in range(count):
        if signature == b'wOFF':
            tag, offset, compressed, length, _ = unpack(data, '>4sIIII', start+i*stride)
        else:
            tag, _, offset, length = unpack(data, '>4sIII', start+i*stride)
            compressed = length
        total += length
        if tag in out or offset < start+count*stride or offset+compressed > len(data) or compressed > length or total > MAX_FONT_BYTES:
            raise FontInvalid('invalid, duplicate or oversized font table')
        body = data[offset:offset+compressed]
        if compressed < length:
            decoder = zlib.decompressobj()
            try:
                body = decoder.decompress(body, length+1)
            except zlib.error as exc:
                raise FontInvalid('invalid compressed WOFF table') from exc
            if len(body) != length or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise FontInvalid('WOFF decompression length mismatch')
        out[tag] = body
    return out


class FontCoverage:
    def __init__(self, data):
        tables = tables_of(data)
        self.decoded_table_bytes=sum(map(len,tables.values()))
        if not {b'cmap', b'maxp', b'name'}.issubset(tables):
            raise FontInvalid('font requires name, maxp and cmap tables')
        self.glyph_count, = unpack(tables[b'maxp'], '>H', 4)
        if not self.glyph_count:
            raise FontInvalid('empty glyph inventory')
        self.names = self._names(tables[b'name'])
        if not self.names.get(6):
            raise FontInvalid('font has no unambiguous PostScript name')
        raw = tables[b'cmap']; version, count = unpack(raw, '>HH', 0)
        if version or not 1 <= count <= 64:
            raise FontInvalid('invalid cmap record count')
        candidates = []
        preference = {(3,10):9, (0,6):8, (0,4):7, (3,1):6, (0,3):5, (0,2):4, (0,1):3, (0,0):2}
        for i in range(count):
            platform, encoding, offset = unpack(raw, '>HHI', 4+8*i)
            if (platform, encoding) not in preference:
                continue
            fmt, = unpack(raw, '>H', offset)
            if fmt not in {0,4,6,10,12,13}:
                raise FontInvalid('unsupported Unicode cmap format')
            length, = unpack(raw, '>I' if fmt in {10,12,13} else '>H', offset+(4 if fmt in {10,12,13} else 2))
            if length < 6 or offset < 4+8*count or offset+length > len(raw):
                raise FontInvalid('invalid cmap subtable boundary')
            candidates.append((preference[(platform,encoding)], fmt, raw[offset:offset+length]))
        if not candidates:
            raise FontInvalid('no supported Unicode cmap')
        _, self.format, self.data = max(candidates, key=lambda x:x[0])
        self._prepare()
        self.mapping_units=len(self.groups) if self.format in {12,13} else len(self.ends) if self.format==4 else 256 if self.format==0 else self.count

    def _names(self, data):
        version, count, offset = unpack(data, '>HHH', 0)
        if version not in {0,1} or count > 4096 or offset < 6+12*count:
            raise FontInvalid('invalid font name records')
        values = {}
        for i in range(count):
            platform, encoding, language, name, length, at = unpack(data, '>HHHHHH', 6+i*12)
            if at+offset+length > len(data):
                raise FontInvalid('font name exceeds table')
            if name not in {1,6,16} or platform not in {0,1,3}:
                continue
            try:
                value = data[offset+at:offset+at+length].decode('mac_roman' if platform==1 else 'utf-16-be').strip()
            except UnicodeError as exc:
                raise FontInvalid('invalid font name encoding') from exc
            rank = (platform==3, language in {0,0x409}, platform==0)
            if name not in values or rank > values[name][0]:
                values[name] = (rank,value)
        return {key:value for key,(_,value) in values.items()}

    @property
    def postscript_name(self):
        return self.names[6]

    def _prepare(self):
        d = self.data; fmt = self.format
        if fmt in {12,13}:
            count, = unpack(d, '>I', 12)
            if count > 65536 or 16+count*12 != len(d):
                raise FontInvalid('cmap group budget or length invalid')
            self.groups = [unpack(d, '>III', 16+i*12) for i in range(count)]
            previous = -1
            for start,end,gid in self.groups:
                last = gid+(end-start if fmt==12 else 0)
                if not previous < start <= end <= 0x10ffff or last >= self.glyph_count:
                    raise FontInvalid('invalid cmap group or glyph ID')
                previous = end
            self.ends = [g[1] for g in self.groups]
        elif fmt == 4:
            twice, = unpack(d, '>H', 6)
            count = twice//2
            if twice%2 or not 1 <= count <= 8192 or len(d) < 16+8*count:
                raise FontInvalid('invalid cmap segments')
            self.ends = list(unpack(d, '>'+str(count)+'H', 14))
            if unpack(d,'>H',14+2*count)[0] or self.ends[-1] != 0xffff:
                raise FontInvalid('invalid cmap segment terminator')
            self.starts = list(unpack(d,'>'+str(count)+'H',16+2*count))
            self.deltas = list(unpack(d,'>'+str(count)+'h',16+4*count))
            self.range_at = 16+6*count
            self.ranges = list(unpack(d,'>'+str(count)+'H',self.range_at))
            previous = -1
            for i,(start,end) in enumerate(zip(self.starts,self.ends)):
                if not previous < start <= end:
                    raise FontInvalid('overlapping or unsorted cmap segments')
                previous = end
                if self.ranges[i] and (self.ranges[i]%2 or self.range_at+2*i+self.ranges[i]+2*(end-start)+2 > len(d)):
                    raise FontInvalid('cmap glyph array exceeds table')
        elif fmt == 0:
            if len(d)!=262:
                raise FontInvalid('invalid byte cmap length')
        elif fmt in {6,10}:
            self.first,self.count = unpack(d,'>HH' if fmt==6 else '>II',6 if fmt==6 else 12)
            self.array_at = 10 if fmt==6 else 20
            if self.first+self.count > (0x10000 if fmt==6 else 0x110000) or self.array_at+2*self.count != len(d):
                raise FontInvalid('invalid trimmed cmap array')

    def glyph(self, codepoint):
        if not 0 <= codepoint <= 0x10ffff:
            return 0
        d=self.data; fmt=self.format; gid=0
        if fmt in {12,13}:
            i=bisect.bisect_left(self.ends,codepoint)
            if i<len(self.groups):
                start,end,first=self.groups[i]
                if start<=codepoint<=end:
                    gid=first+(codepoint-start if fmt==12 else 0)
        elif fmt==4 and codepoint<=0xffff:
            i=bisect.bisect_left(self.ends,codepoint)
            if i<len(self.ends) and self.starts[i]<=codepoint:
                if self.ranges[i]:
                    gid=unpack(d,'>H',self.range_at+2*i+self.ranges[i]+2*(codepoint-self.starts[i]))[0]
                    if gid:gid=(gid+self.deltas[i])&0xffff
                else:
                    gid=(codepoint+self.deltas[i])&0xffff
        elif fmt==0 and codepoint<256:
            gid=d[6+codepoint]
        elif fmt in {6,10} and self.first<=codepoint<self.first+self.count:
            gid=unpack(d,'>H',self.array_at+2*(codepoint-self.first))[0]
        if gid>=self.glyph_count:
            raise FontInvalid('mapped glyph outside font inventory')
        return gid

from __future__ import annotations
import struct
import unittest
from pathlib import Path
from ai_ad_editor.font_coverage import FontCoverage,FontInvalid,tables_of

ROOT=Path(__file__).resolve().parents[2]
FONT=ROOT/'docs/assets/html-template-20261018/template/font.ttf'


def sfnt(cmap,*,glyphs=8):
    name='KnownFont'.encode('utf-16-be')
    names=struct.pack('>HHH',0,1,18)+struct.pack('>HHHHHH',3,1,0x409,6,len(name),0)+name
    maps=struct.pack('>HHHHI',0,1,3,10 if int.from_bytes(cmap[:2],'big') in {10,12,13} else 1,12)+cmap
    values={b'cmap':maps,b'name':names,b'maxp':struct.pack('>IH',0x10000,glyphs)}
    header=struct.pack('>IHHHH',0x10000,len(values),0,0,0);offset=12+16*len(values);rows=[];body=b''
    for tag,data in values.items():
        rows.append(struct.pack('>4sIII',tag,0,offset,len(data)));body+=data;offset+=len(data)
    return header+b''.join(rows)+body


class FontCoverageTests(unittest.TestCase):
    def test_original_font_maps_only_authored_characters(self):
        font=FontCoverage(FONT.read_bytes())
        self.assertEqual(font.postscript_name,'AgentGridCC0-Regular')
        for ch in 'CTA EDIT VIDE2':self.assertGreater(font.glyph(ord(ch)),0)
        for cp in (ord('B'),ord('O'),0x4e2d,0x1f642,-1,0x110000):self.assertEqual(font.glyph(cp),0)

    def test_full_unicode_sequential_groups(self):
        data=struct.pack('>HHIII',12,0,40,0,2)+struct.pack('>III',65,66,1)+struct.pack('>III',0x1f600,0x1f600,3)
        font=FontCoverage(sfnt(data))
        self.assertEqual([font.glyph(c) for c in (64,65,66,67,0x1f600)],[0,1,2,0,3])

    def test_many_to_one_groups_and_zero_is_missing(self):
        data=struct.pack('>HHIII',13,0,40,0,2)+struct.pack('>III',65,70,2)+struct.pack('>III',90,92,0)
        font=FontCoverage(sfnt(data))
        self.assertEqual([font.glyph(c) for c in (65,70,71,90,91)],[2,2,0,0,0])

    def test_trimmed_bmp_and_full_unicode_arrays(self):
        for fmt,start in ((6,65),(10,0x1f600)):
            head=struct.pack('>HHHHH',6,16,0,start,3) if fmt==6 else struct.pack('>HHIIII',10,0,26,0,start,3)
            font=FontCoverage(sfnt(head+struct.pack('>HHH',1,0,2)))
            self.assertEqual([font.glyph(x) for x in range(start-1,start+4)],[0,1,0,2,0])

    def test_byte_unicode_cmap(self):
        values=bytearray(256);values[65]=3
        font=FontCoverage(sfnt(struct.pack('>HHH',0,262,0)+values))
        self.assertEqual(font.glyph(65),3);self.assertEqual(font.glyph(256),0)

    def test_format_four_glyph_array_and_delta(self):
        # A->array glyph 1 + delta 2; B->zero remains missing. Final sentinel.
        cmap=struct.pack('>HHHHHHH',4,36,0,4,4,1,0)
        cmap+=struct.pack('>HHHHHhhHHHH',66,0xffff,0,65,0xffff,2,1,4,0,1,0)
        font=FontCoverage(sfnt(cmap))
        self.assertEqual([font.glyph(c) for c in (64,65,66,67,0xffff)],[0,3,0,0,0])

    def test_format_four_bad_array_offset_is_rejected(self):
        cmap=struct.pack('>HHHHHHH',4,36,0,4,4,1,0)
        cmap+=struct.pack('>HHHHHhhHHHH',66,0xffff,0,65,0xffff,2,1,0xfffc,0,1,0)
        with self.assertRaises(FontInvalid):FontCoverage(sfnt(cmap))
        with self.assertRaises(FontInvalid):FontCoverage(FONT.read_bytes()[:40])

    def test_unsorted_overlapping_and_impossible_glyph_groups_reject(self):
        for groups in (((70,72,1),(65,66,2)),((65,70,1),(70,71,2)),((65,66,7),),((0x110000,0x110001,1),)):
            cmap=struct.pack('>HHIII',12,0,16+12*len(groups),0,len(groups))+b''.join(struct.pack('>III',*g) for g in groups)
            with self.assertRaises(FontInvalid):FontCoverage(sfnt(cmap))

    def test_out_of_inventory_array_glyph_is_not_a_character(self):
        font=FontCoverage(sfnt(struct.pack('>HHHHHH',6,12,0,65,1,20)))
        with self.assertRaises(FontInvalid):font.glyph(65)

    def test_woff1_decompression_and_invalid_length(self):
        import zlib
        source=tables_of(FONT.read_bytes());start=44+20*len(source);entries=[];body=b'';sfnt_size=12+16*len(source)
        for tag,value in source.items():
            compressed=zlib.compress(value);compressed=compressed if len(compressed)<len(value) else value
            entries.append(struct.pack('>4sIIII',tag,start+len(body),len(compressed),len(value),0));body+=compressed
            sfnt_size+=(len(value)+3)&~3
        header=struct.pack('>4s4sIHHIHHIIIII',b'wOFF',b'\0\1\0\0',start+len(body),len(entries),0,sfnt_size,1,0,0,0,0,0,0)
        data=header+b''.join(entries)+body
        self.assertEqual(FontCoverage(data).glyph(65),FontCoverage(FONT.read_bytes()).glyph(65))
        with self.assertRaises(FontInvalid):FontCoverage(data[:-1])

    def test_unsupported_font_and_invalid_table_bounds_do_not_pass(self):
        for value in (b'wOF2'+b'\0'*100,b'ttcf'+b'\0'*100,b'bad',b'\0\1\0\0'+b'\xff'*100):
            with self.assertRaises(FontInvalid):FontCoverage(value)

    def test_identical_font_aliases_are_one_proven_mapping(self):
        from ai_ad_editor.html_quality import font_catalogue
        records,fonts=font_catalogue({'data':{'a.ttf':FONT.read_bytes(),'b.ttf':FONT.read_bytes()}})
        self.assertEqual(len(records),2);self.assertEqual(len(fonts['paths']),2)
        self.assertEqual(len(fonts['names']['AgentGridCC0-Regular']),1)

    def test_catalogue_font_count_has_an_explicit_budget(self):
        from ai_ad_editor.html_quality import font_catalogue
        from ai_ad_editor.errors import AppError
        with self.assertRaises(AppError) as caught:
            font_catalogue({'data':{str(i)+'.ttf':FONT.read_bytes() for i in range(65)}})
        self.assertEqual(caught.exception.code,'HTML_LAYOUT_BUDGET')


if __name__=='__main__':unittest.main()

"""Static contact sheets from decoded real CLI media; no playback claim."""
import argparse
from pathlib import Path
import subprocess


def run(public):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    font = ImageFont.truetype(str(public/'DejaVuSans.ttf'), 12)
    for name, width, height, moments in [('MR04', 240, 136, (5, 15, 25)), ('MR07', 160, 64, (5, 25))]:
        values = []
        for suffix in ('-before', ''):
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(public/(name+suffix+'.mkv')),
                '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
            values.append(np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 3))
        contact = Image.new('RGB', (2*width, (height+48)*len(moments)), '#102030')
        draw = ImageDraw.Draw(contact)
        for row, index in enumerate(moments):
            y = row*(height+48)
            draw.text((4, y+2), f'{name} t={index/10:.1f}s BEFORE', font=font, fill='white')
            draw.text((width+4, y+2), 'AFTER', font=font, fill='white')
            for column, picture in enumerate(values): contact.paste(Image.fromarray(picture[index]), (column*width, y+24))
            draw.text((4, y+height+25), 'decoded CLI frames; static only', font=font, fill='#a9e6c4')
        path = public/(name+'-contact-v2.png');assert not path.exists();contact.save(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('--public', type=Path, required=True)
    args = parser.parse_args();run(args.public.resolve())

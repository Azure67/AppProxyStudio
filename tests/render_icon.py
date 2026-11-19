"""Render the vector master to a PNG and a multi-resolution Windows icon."""
import sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'vendor'))
from PySide6.QtCore import QByteArray,QBuffer,QIODevice,Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
renderer=QSvgRenderer(str(ROOT/'assets'/'app.svg'))
images=[]
for size in (16,24,32,48,64,128,256):
 image=QImage(size,size,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
 painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing);renderer.render(painter);painter.end()
 data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG');images.append((size,bytes(data)))
image=QImage(1024,1024,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent);painter=QPainter(image);renderer.render(painter);painter.end();image.save(str(ROOT/'assets'/'app.png'))
header=struct.pack('<HHH',0,1,len(images));offset=6+16*len(images);entries=b'';payload=b''
for size,data in images:
 entries+=struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset);payload+=data;offset+=len(data)
(ROOT/'assets'/'app.ico').write_bytes(header+entries+payload)
print('SVG, 1024px PNG, 7-size ICO created.')

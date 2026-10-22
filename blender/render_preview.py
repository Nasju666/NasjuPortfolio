"""Renders a preview image of blender/room.blend.
    python blender/render_preview.py [out.png] [scale_percent] [samples]
"""
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'preview.png')
pct = int(sys.argv[2]) if len(sys.argv) > 2 else 100
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 64

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'room.blend'))
s = bpy.context.scene
s.render.resolution_percentage = pct
s.cycles.samples = samples
s.render.filepath = out
t = time.time()
bpy.ops.render.render(write_still=True)
print(f'rendered {out} in {time.time() - t:.0f}s')

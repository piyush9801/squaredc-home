import bpy
print("SCENES:")
for s in bpy.data.scenes:
    print(" ", s.name, s.render.engine, s.render.resolution_x, s.render.resolution_y, "cam:", s.camera.name if s.camera else None)
print("COLLECTIONS:")
for c in bpy.data.collections:
    print(" ", c.name, [o.name for o in c.objects][:12], "children:", [ch.name for ch in c.children])
print("OBJECTS:")
for o in bpy.data.objects:
    print(" ", o.name, o.type, tuple(round(v,3) for v in o.location), tuple(round(v,3) for v in o.dimensions), [m.name for m in o.material_slots if m.material] if o.type=='MESH' else '', [md.type for md in o.modifiers] if hasattr(o,'modifiers') else '')
print("MATERIALS:")
for m in bpy.data.materials:
    if m.use_nodes:
        print(" ", m.name, [n.bl_idname for n in m.node_tree.nodes][:14])
print("WORLDS:", [w.name for w in bpy.data.worlds])

import bpy
s = bpy.context.scene
ng = bpy.data.node_groups.new("t", 'CompositorNodeTree')
g = ng.nodes.new('CompositorNodeGlare')
for i in g.inputs:
    if i.bl_idname.endswith('Menu') or i.type == 'MENU':
        try:
            print("MENU", i.name, [it.identifier for it in i.bl_rna.properties['default_value'].enum_items])
        except Exception as e: print("menu err", i.name, e)
print([ (i.name, i.type) for i in g.inputs])
print("views:", [v for v in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items.keys()])
s.view_settings.view_transform='AgX'
print("looks:", [l.name for l in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items])
print("scene attrs:", [a for a in dir(s) if 'node' in a or 'compos' in a])
print("render attrs:", [a for a in dir(s.render) if 'compos' in a or 'persistent' in a])
print("cycles attrs:", [a for a in dir(s.cycles) if 'denois' in a or 'gpu' in a])
print("img formats:", [f.identifier for f in bpy.types.ImageFormatSettings.bl_rna.properties['file_format'].enum_items])
for t in ['CompositorNodeLensdist','CompositorNodeSunBeams','CompositorNodeDenoise','CompositorNodeMixRGB','CompositorNodeAlphaOver','CompositorNodeCurveRGB','CompositorNodeBrightContrast','CompositorNodeColorBalance','CompositorNodeMath','ShaderNodeMix','CompositorNodeColorCorrection']:
    try:
        n = ng.nodes.new(t); print("OK", t, [(i.name, i.type) for i in n.inputs][:12])
    except Exception as e: print("NO", t, e)

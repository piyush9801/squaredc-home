import bpy
s = bpy.data.scenes['Yellow Square • Studio']
print("compositing attrs:", [a for a in dir(s) if 'compos' in a.lower() or 'node' in a.lower()])
ng = getattr(s, 'compositing_node_group', None)
print("compositing_node_group:", ng)
if ng:
    for n in ng.nodes:
        print("  NODE", n.bl_idname, n.name, {i.name: (getattr(i,'default_value',None) if not hasattr(getattr(i,'default_value',None),'__len__') else tuple(i.default_value)) for i in n.inputs if not i.is_linked} )
        for p in ['glare_type','quality','mix','threshold','size','streaks','angle_offset','fade']:
            if hasattr(n,p): print("     ", p, getattr(n,p))
    for l in ng.links:
        print("  LINK", l.from_node.name, l.from_socket.name, "->", l.to_node.name, l.to_socket.name)
print("view:", s.view_settings.view_transform, s.view_settings.look, s.view_settings.exposure, s.view_settings.gamma)
c = s.cycles
print("cycles:", c.samples, c.use_denoising, c.denoiser, c.max_bounces, c.transmission_bounces, c.use_adaptive_sampling, c.adaptive_threshold)
for mname in ['01 • Luminous golden yellow','04 • Cobalt optical glass','05 • Cyan edge light','05 • Sapphire optical glass']:
    m = bpy.data.materials[mname]
    print("MAT", mname)
    for n in m.node_tree.nodes:
        vals = {}
        for i in n.inputs:
            if i.is_linked or not hasattr(i,'default_value'): continue
            v = i.default_value
            try: v = tuple(round(x,3) for x in v)
            except TypeError:
                try: v = round(v,3)
                except: pass
            vals[i.name]=v
        interesting = {k:v for k,v in vals.items() if k in ('Base Color','Roughness','IOR','Transmission Weight','Emission Color','Emission Strength','Strength','Color','Coat Weight','Subsurface Weight','Alpha','Thin Film Thickness')}
        print("   ", n.bl_idname, n.name, interesting)
    for l in m.node_tree.links:
        print("    L", l.from_node.name, l.from_socket.name, "->", l.to_node.name, l.to_socket.name)
w = s.world
print("WORLD", w.name if w else None)
if w:
    for n in w.node_tree.nodes: print("   ", n.bl_idname, n.name)

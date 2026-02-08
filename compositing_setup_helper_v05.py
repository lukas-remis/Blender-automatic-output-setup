bl_info = {
    "name": "Output Setup Helper",
    "author": "Lukas Remis (Imaginary Pixels)",
    "version": (3, 18, 3),
    "blender": (5, 0, 0),
    "category": "Compositing",
    "description": "Automatically creates a compositing denoising setup for each pass, configures output paths and render versions."
}

import bpy
import re

# ------------------------------------------------------------
# Add-on Preferences
# ------------------------------------------------------------

class CompositingSetupHelperPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    base_renders_path: bpy.props.StringProperty(
        name="Base renders path",
        default="//../renders/",
        subtype='DIR_PATH'
    )

    preview_render_type: bpy.props.EnumProperty(
        name="Preview Render Type",
        items=[
            ('IMAGE', "Image", ""),
            ('VIDEO', "Video", ""),
        ],
        default='IMAGE'
    )

    preview_image_format: bpy.props.EnumProperty(
        name="File Format",
        items=[
            ('JPEG', "JPEG", ""),
            ('PNG', "PNG", ""),
        ],
        default='JPEG'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "base_renders_path")
        layout.prop(self, "preview_render_type")
        if self.preview_render_type == 'IMAGE':
            layout.prop(self, "preview_image_format")
        
        layout.separator()
        row = layout.row()
        op = row.operator("wm.url_open", text="Project page", icon='URL')
        op.url = "https://github.com/lukas-remis?tab=repositories"

# ------------------------------------------------------------
# Scene Properties
# ------------------------------------------------------------

def register_properties():
    bpy.types.Scene.compositing_denoise_mix_factor = bpy.props.FloatProperty(
        name="Denoise level",
        min=0.0,
        max=1.0,
        default=1.0,
        subtype='FACTOR'
    )

    bpy.types.Scene.compositing_setup_created = bpy.props.BoolProperty(
        name="Compositing Setup Created",
        default=False
    )

def unregister_properties():
    del bpy.types.Scene.compositing_denoise_mix_factor
    del bpy.types.Scene.compositing_setup_created

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def extract_version():
    if not bpy.data.filepath:
        return None
    m = re.search(r'_v(\d{2,3})', bpy.path.basename(bpy.data.filepath), re.IGNORECASE)
    return f"v{m.group(1).zfill(3)}" if m else None

def get_prefs(context):
    return context.preferences.addons[__name__].preferences

def join_blender_path(base, *paths):
    return "/".join([base.rstrip("/\\")] + [p for p in paths if p])

def socket_is_linked(socket):
    return any(l.is_valid for l in socket.links)

def lowest_denoise_group_y(tree):
    ys = [
        n.location.y for n in tree.nodes
        if n.type == 'GROUP'
        and n.node_tree
        and n.node_tree.name == "DenoiseWithMix"
    ]
    return min(ys) if ys else None

# ------------------------------------------------------------
# Denoise Group
# ------------------------------------------------------------

def get_or_create_denoise_group(mix_factor):
    name = "DenoiseWithMix"
    group = bpy.data.node_groups.get(name)

    if not group:
        group = bpy.data.node_groups.new(name, 'CompositorNodeTree')

        iface = group.interface
        iface.new_socket("Image",  in_out='INPUT',  socket_type='NodeSocketColor')
        iface.new_socket("Normal", in_out='INPUT',  socket_type='NodeSocketVector')
        iface.new_socket("Albedo", in_out='INPUT',  socket_type='NodeSocketColor')
        iface.new_socket("Image",  in_out='OUTPUT', socket_type='NodeSocketColor')

        nodes = group.nodes
        links = group.links

        gi = nodes.new('NodeGroupInput')
        gi.location = (-600, 0)

        denoise = nodes.new('CompositorNodeDenoise')
        denoise.location = (-200, 150)

        mix = nodes.new('ShaderNodeMix')
        mix.location = (100, 0)
        mix.data_type = 'RGBA'
        mix.blend_type = 'MIX'

        go = nodes.new('NodeGroupOutput')
        go.location = (400, 0)

        links.new(gi.outputs["Image"], denoise.inputs[0])
        links.new(gi.outputs["Normal"], denoise.inputs[2])
        links.new(gi.outputs["Albedo"], denoise.inputs[1])
        links.new(gi.outputs["Image"], mix.inputs["A"])
        links.new(denoise.outputs[0], mix.inputs["B"])
        links.new(mix.outputs["Result"], go.inputs["Image"])

    for n in group.nodes:
        if n.bl_idname == 'ShaderNodeMix':
            n.inputs[0].default_value = mix_factor

    return group

# ------------------------------------------------------------
# CREATE (destructive)
# ------------------------------------------------------------

def setup_compositing_nodes(context):
    scene = context.scene
    prefs = get_prefs(context)
    version = extract_version()

    if prefs.preview_render_type == 'IMAGE':
        scene.render.image_settings.media_type = 'IMAGE'
        scene.render.image_settings.file_format = prefs.preview_image_format
    else:
        scene.render.image_settings.media_type = 'VIDEO'

    scene.render.filepath = join_blender_path(
        prefs.base_renders_path, version, "preview", "preview_"
    )

    if hasattr(context.view_layer, "cycles"):
        context.view_layer.cycles.denoising_store_passes = True

    scene.use_nodes = True
    if not scene.compositing_node_group:
        scene.compositing_node_group = bpy.data.node_groups.new(
            "Compositor Nodes", 'CompositorNodeTree'
        )

    tree = scene.compositing_node_group
    tree.nodes.clear()

    rl = tree.nodes.new('CompositorNodeRLayers')
    rl.location = (0, 0)

    denoise_group = get_or_create_denoise_group(
        scene.compositing_denoise_mix_factor
    )

    def create_out(label, path_suffix, loc, codec):
        n = tree.nodes.new('CompositorNodeOutputFile')
        n.label = label
        n.location = loc
        n.width = 450
        n.directory = join_blender_path(
            prefs.base_renders_path, version, path_suffix
        )
        n.file_name = f"{path_suffix}_"
        n.format.file_format = 'OPEN_EXR_MULTILAYER'
        n.format.exr_codec = codec
        n.file_output_items.clear()
        return n

    out_beauty = create_out("Beauty Output", "beauty", (1300, 400), 'DWAB')
    out_util   = create_out("Utility Output", "utils", (1300, -500), 'ZIP')

    beauty_passes = {
        "Image": "rgba", "Grease Pencil": "Grease_Pencil", "Mist": "Mist",
        "Diffuse Direct": "DiffDir", "Diffuse Indirect": "DiffInd", "Diffuse Color": "DiffCol",
        "Glossy Direct": "GlossDir", "Glossy Indirect": "GlossInd", "Glossy Color": "GlossCol",
        "Transmission Direct": "TransDir", "Transmission Indirect": "TransInd", "Transmission Color": "TransCol",
        "Volume Direct": "VolumeDir", "Volume Indirect": "VolumeInd",
        "Emission": "Emit", "Environment": "Env",
        "Ambient Occlusion": "ao", "Shadow Catcher": "ShadowCatcher",
    }

    util_passes = {
        "Depth": "Depth", "Position": "Position", "Pref": "Pref",
        "Normal": "Normal", "Vector": "Vector", "UV": "UV",
        "CryptoObject00": "CryptoObject00", "CryptoObject01": "CryptoObject01", "CryptoObject02": "CryptoObject02",
        "CryptoMaterial00": "CryptoMaterial00", "CryptoMaterial01": "CryptoMaterial01", "CryptoMaterial02": "CryptoMaterial02",
        "CryptoAsset00": "CryptoAsset00", "CryptoAsset01": "CryptoAsset01", "CryptoAsset02": "CryptoAsset02",
        "Object Index": "Object_Index", "Material Index": "Material_Index",
    }

    d_norm = rl.outputs.get("Denoising Normal")
    d_albe = rl.outputs.get("Denoising Albedo")

    y = 600
    for pass_name, slot in beauty_passes.items():
        out = rl.outputs.get(pass_name)
        if not out:
            continue

        gn = tree.nodes.new('CompositorNodeGroup')
        gn.node_tree = denoise_group
        gn.location = (900, y)
        gn.hide = True

        tree.links.new(out, gn.inputs[0])
        if d_norm:
            tree.links.new(d_norm, gn.inputs[1])
        if d_albe:
            tree.links.new(d_albe, gn.inputs[2])

        item = out_beauty.file_output_items.new('RGBA', slot)
        tree.links.new(gn.outputs[0], out_beauty.inputs[item.name])
        y -= 60

    y = 200
    for pass_name, slot in util_passes.items():
        out = rl.outputs.get(pass_name)
        if not out:
            continue

        item = out_util.file_output_items.new('RGBA', slot)
        tree.links.new(out, out_util.inputs[item.name])
        y -= 40

# ------------------------------------------------------------
# UPDATE (non-destructive)
# ------------------------------------------------------------

def update_compositing_settings(context):
    scene = context.scene
    prefs = get_prefs(context)
    version = extract_version()

    scene.render.filepath = join_blender_path(
        prefs.base_renders_path, version, "preview", "preview_"
    )

    tree = scene.compositing_node_group
    if not tree:
        return

    rl = next((n for n in tree.nodes if n.type == 'R_LAYERS'), None)
    if not rl:
        return

    out_beauty = next((n for n in tree.nodes if n.type == 'OUTPUT_FILE' and "beauty" in n.label.lower()), None)
    out_util   = next((n for n in tree.nodes if n.type == 'OUTPUT_FILE' and "util" in n.label.lower()), None)

    beauty_passes = {
        "Image": "rgba", "Grease Pencil": "Grease_Pencil", "Mist": "Mist",
        "Diffuse Direct": "DiffDir", "Diffuse Indirect": "DiffInd", "Diffuse Color": "DiffCol",
        "Glossy Direct": "GlossDir", "Glossy Indirect": "GlossInd", "Glossy Color": "GlossCol",
        "Transmission Direct": "TransDir", "Transmission Indirect": "TransInd", "Transmission Color": "TransCol",
        "Volume Direct": "VolumeDir", "Volume Indirect": "VolumeInd",
        "Emission": "Emit", "Environment": "Env",
        "Ambient Occlusion": "ao", "Shadow Catcher": "ShadowCatcher",
    }

    util_passes = {
        "Depth": "Depth", "Position": "Position", "Pref": "Pref",
        "Normal": "Normal", "Vector": "Vector", "UV": "UV",
        "CryptoObject00": "CryptoObject00", "CryptoObject01": "CryptoObject01", "CryptoObject02": "CryptoObject02",
        "CryptoMaterial00": "CryptoMaterial00", "CryptoMaterial01": "CryptoMaterial01", "CryptoMaterial02": "CryptoMaterial02",
        "CryptoAsset00": "CryptoAsset00", "CryptoAsset01": "CryptoAsset01", "CryptoAsset02": "CryptoAsset02",
        "Object Index": "Object_Index", "Material Index": "Material_Index",
    }

    beauty_slots_map = {v: k for k, v in beauty_passes.items()}
    util_slots_map = {v: k for k, v in util_passes.items()}

    # Cleanup Output Beauty
    if out_beauty:
        to_remove = [item.name for item in out_beauty.file_output_items 
                     if beauty_slots_map.get(item.name) and beauty_slots_map.get(item.name) not in rl.outputs]
        for name in to_remove:
            item = out_beauty.file_output_items.get(name)
            if item:
                out_beauty.file_output_items.remove(item)

    # Cleanup Output Utility
    if out_util:
        to_remove = [item.name for item in out_util.file_output_items 
                     if util_slots_map.get(item.name) and util_slots_map.get(item.name) not in rl.outputs]
        for name in to_remove:
            item = out_util.file_output_items.get(name)
            if item:
                out_util.file_output_items.remove(item)

    # Cleanup Denoise
    for node in list(tree.nodes):
        if (node.type == 'GROUP' and 
            node.node_tree and 
            node.node_tree.name == "DenoiseWithMix"):
            if not node.outputs[0].is_linked:
                tree.nodes.remove(node)

    # Re-link/Add
    denoise_group = get_or_create_denoise_group(scene.compositing_denoise_mix_factor)
    d_norm = rl.outputs.get("Denoising Normal")
    d_albe = rl.outputs.get("Denoising Albedo")

    base_y = lowest_denoise_group_y(tree)
    y = base_y - 60 if base_y is not None else -200

    if out_beauty:
        for pass_name, slot in beauty_passes.items():
            sock = rl.outputs.get(pass_name)
            if not sock or socket_is_linked(sock):
                continue

            gn = tree.nodes.new('CompositorNodeGroup')
            gn.node_tree = denoise_group
            gn.location = (900, y)
            gn.hide = True

            tree.links.new(sock, gn.inputs[0])
            if d_norm:
                tree.links.new(d_norm, gn.inputs[1])
            if d_albe:
                tree.links.new(d_albe, gn.inputs[2])

            item = out_beauty.file_output_items.new('RGBA', slot)
            tree.links.new(gn.outputs[0], out_beauty.inputs[item.name])
            y -= 60

    if out_util:
        for pass_name, slot in util_passes.items():
            sock = rl.outputs.get(pass_name)
            if not sock or socket_is_linked(sock):
                continue

            item = out_util.file_output_items.new('RGBA', slot)
            tree.links.new(sock, out_util.inputs[item.name])

    for node in tree.nodes:
        if node.type == 'OUTPUT_FILE':
            if "beauty" in node.label.lower():
                node.directory = join_blender_path(prefs.base_renders_path, version, "beauty")
            elif "util" in node.label.lower():
                node.directory = join_blender_path(prefs.base_renders_path, version, "utils")

# ------------------------------------------------------------
# Operators / UI / Registration
# ------------------------------------------------------------

class COMPOSITING_OT_CreateSetup(bpy.types.Operator):
    bl_idname = "compositing.create_setup"
    bl_label = "Create Compositing Setup"
    bl_description = "Create new node setup - overwrites existing one!"

    def execute(self, context):
        setup_compositing_nodes(context)
        context.scene.compositing_setup_created = True
        return {'FINISHED'}

class COMPOSITING_OT_UpdateSetup(bpy.types.Operator):
    bl_idname = "compositing.update_setup"
    bl_label = "Update Compositing"
    bl_description = "Update passes, denoise level, paths and versions"

    def execute(self, context):
        update_compositing_settings(context)
        return {'FINISHED'}

class COMPOSITING_PT_SetupPanel(bpy.types.Panel):
    bl_label = "Setup Helper 5.0"
    bl_idname = "COMPOSITING_PT_SetupPanel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Setup Helper"
    bl_context = "compositor"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "compositing_denoise_mix_factor")
        layout.operator("compositing.create_setup")

        row = layout.row()
        row.enabled = scene.compositing_setup_created
        row.operator("compositing.update_setup")

classes = (
    CompositingSetupHelperPreferences,
    COMPOSITING_OT_CreateSetup,
    COMPOSITING_OT_UpdateSetup,
    COMPOSITING_PT_SetupPanel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    register_properties()

def unregister():
    unregister_properties()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Gears 2.0, a Blender addon
#  (c) 2013 Michel J. Anders (varkenvarken)
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

bl_info = {
    "name": "Gears 2.0",
    "author": "Michel Anders (varkenvarken)",
    "version": (0, 0, 1),
    "blender": (2, 68, 0),
    "location": "View3D > Add > Mesh",
    "description": "Adds a mesh representing a gear (cogwheel)",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Add Mesh"}

from math import pi as PI, sin, cos
import bpy
import bmesh
from bpy.props import FloatProperty, IntProperty, BoolProperty, EnumProperty, StringProperty
from mathutils import Vector, Euler

def availableGears(o, context):
    return [('','','',0)]+[(name, name, name, n+2) for n,name in enumerate(bpy.data.objects.keys()) if (('reg' in bpy.data.objects[name]) and (bpy.data.objects[name].reg == 'Gears') and (name != o.name))]

def isGear(o):
    return o is not None and 'reg' in o and o.reg == 'Gears'
    
# Vector.rotate() does NOT return anything, contrary to what the docs say
# docs are now fixed (https://projects.blender.org/tracker/index.php?func=detail&aid=36518&group_id=9&atid=498)
# but unfortunately no rotated() function was added
def rotate(v, r):
    v2 = v.copy()
    v2.rotate(r)
    return v2

def tooth(radius, arc):
    bm = bmesh.new()

    h = arc / 4
    c0 = cos(h/2)
    s0 = sin(h/2)
    c1 = cos(h)
    s1 = sin(h)
    c2 = cos(h*2)
    s2 = sin(h*2)
    r0 = radius * 0.5
    r1 = radius - 0.2
    r2 = radius
    r3 = radius + 0.19
    
    verts = [
        ( r0 * c2,  r0 * s2, 0),  # 0
        ( r0 * c1,  r0 * s1, 0),  # 1
        ( r0 * c1, -r0 * s1, 0),  # 2
        ( r0 * c2, -r0 * s2, 0),  # 3
        ( r1 * c2,  r1 * s2, 0),  # 4
        ( r1 * c1,  r1 * s1, 0),  # 5
        ( r1 * c1, -r1 * s1, 0),  # 6
        ( r1 * c2, -r1 * s2, 0),  # 7
        ( r2 * c1,  r2 * s1, 0),  # 8
        ( r2 * c1, -r2 * s1, 0),  # 9
        ( r3 * c0,  r3 * s0, 0),  # 10
        ( r3 * c0, -r3 * s0, 0)   # 11
    ]
    faces = [
        (0, 1, 2, 3, 7, 6, 9, 11, 10, 8, 5, 4)
    ]
    
    for v in verts:
        bm.verts.new(v)
    for f in faces:
        bm.faces.new([bm.verts[i] for i in f])
    return bm

def rootArc(object):
    if 'reg' in object and object.reg == 'Gears':
        if object.driver == '':
            return object.radius, object.nteeth
        else:
            parent = bpy.data.objects[object.driver]
            return rootArc(parent)
    return 1.0, 4
    
def focus(object, context):
    bpy.ops.object.select_all(action='DESELECT')
    object.select = True
    context.scene.objects.active = object

def relradius(rootr, nt, nrt):
    return (rootr * nt) / nrt

def rotate_mesh(object, euler):
    bm = bmesh.new()
    bm.from_mesh(object.data)
    bmesh.ops.rotate(bm, cent=(0,0,0), matrix=euler.to_matrix(), verts=bm.verts[:])
    bm.to_mesh(object.data)
    bm.free()

# TODO this can fail if gearhead is removed/ chain of dependencies is broken    
def setLocation(object, context, seen, rot_changed):
    offset = 0
    if object.driver != '':
        rootradius, rootnteeth, offset = setLocation(context.scene.objects[object.driver], context, seen, rot_changed)
        if object.name not in seen:
            if object.twin == 'Up':
                offset += 1
            elif object.twin == 'Down':
                offset -= 1
            object.location = context.scene.objects[object.driver].location
            if object.twin == 'None':  # ! string not None object
                object.location.x += relradius(rootradius, context.scene.objects[object.driver].nteeth, rootnteeth) + relradius(rootradius, object.nteeth, rootnteeth)
            object.location.z += offset * 0.1
            #print(object.name, '-->', object.driver, 'driver changed',object.driver in rot_changed, 'odd', object.nteeth % 2 == 1, 'rotated', rot_changed,'seen', seen)
            if ((object.driver in rot_changed) and (object.nteeth % 2 == 1)
                    or
                (object.driver not in rot_changed) and (object.nteeth % 2 == 0)):
                    rotate_mesh(object, Euler((0,0,PI / object.nteeth), 'XYZ'))  # half a tooth
                    rot_changed.add(object.name)
                    #print('ob rotated')
    else:
        object.location = Vector((0, 0, 0))
        rootradius, rootnteeth = object.radius, object.nteeth
    seen.add(object.name)
    return rootradius, rootnteeth, offset

# this fails if there is more than one gear train
def unParentFromEmpty(gears, context):
    empty = None
    for g in gears:
        if g.parent:
            empty = g.parent
            mat = g.matrix_world
            g.parent = None
            #g.matrix_world
    return empty
    
def parentToEmpty(gears, empty, context):
    newempty = False
    if empty is None:
        bpy.ops.object.empty_add(type='SPHERE')
        empty = context.active_object
        empty.name = 'GearHeadEmpty'
        empty.location.zero()
        newempty = True

    #for g in gears:
    #    if g.driver == '':  # the head
    #        empty.matrix_world = g.matrix_world
    #        g.matrix_world.identity()
    #        break
    for g in gears:
        #mat = g.matrix_world
        g.parent = empty
        #g.matrix_world = mat
    if newempty:
        empty.location = context.scene.cursor_location
        
def clearDriversAndKeys(gears, context):
    for g in gears:
        g.animation_data_clear()
        g.rotation_euler.zero()

def setDriversAndKeys(gears, context):
    # set keyframes for head and drivers for driven gears
    for g in gears:
        if g.driver != '':  # driven gear
            ratio = 1
            if g.twin == 'None':  # the string not the object None!
                ratio = -float(bpy.data.objects[g.driver].nteeth)/float(g.nteeth)

            # add driver to Z rotation
            driver = g.driver_add('rotation_euler', 2)
            driver.driver.type = 'SCRIPTED'
            driver.driver.expression = str(ratio) + '* bpy.data.objects["' + g.driver + '"].rotation_euler.z'
            
            # add/replace variable just to make updates instantaneous
            variable = None
            for v in driver.driver.variables:
                if v.targets[0].transform_type == 'ROT_Z':
                    variable = v
                    break
            if variable is None:
                variable = driver.driver.variables.new()
            variable.type = 'TRANSFORMS'
            variable.targets[0].id = context.scene.objects[g.driver]
            variable.targets[0].transform_type = 'ROT_Z' # actually it doesn't matter what we monitor
        else: # the gear head
            # add keyframes on the Z rotation
            g.rotation_euler.z = 0
            g.keyframe_insert(data_path="rotation_euler", index=2, frame=-10)
            g.animation_data.action.fcurves[0].keyframe_points[-1].handle_right_type = 'FREE'
            g.animation_data.action.fcurves[0].keyframe_points[-1].handle_left_type = 'FREE'
            g.rotation_euler.z = 0.5 * PI*10
            g.keyframe_insert(data_path="rotation_euler", index=2, frame=25*10)
            # doesnt work? : g.animation_data.action.fcurves[0].extrapolation = 'LINEAR'
            g.animation_data.action.fcurves[0].keyframe_points[-1].handle_right_type = 'FREE'
            g.animation_data.action.fcurves[0].keyframe_points[-1].handle_left_type = 'FREE'
            
def updateObjects(context):
    gears = [o for o in context.scene.objects if 'reg' in o and o.reg == 'Gears']
    empty = unParentFromEmpty(gears, context)
    clearDriversAndKeys(gears, context)
    
    # create/replace meshes
    for g in gears:
        rootradius, rootteeth = rootArc(g)
        radius = (rootradius * g.nteeth) / rootteeth
        arc = 2 * PI / g.nteeth
        bm = tooth(radius, arc)
        bmesh.ops.spin(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            angle=2 * PI,
            steps=g.nteeth,
            use_duplicate=True,
            axis=(0.0, 0.0, 1.0),
            cent=(0.0, 0.0, 0.0))
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)
        ret = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        bmesh.ops.translate(bm, verts=[ele for ele in ret["geom"] if isinstance(ele, bmesh.types.BMVert)], vec=(0.0, 0.0, 0.1))
        del ret
        
        me = bpy.data.meshes.new("Gear")
        bm.to_mesh(me)
        bm.free()
        g.data = me
            
    # rotate gears so that teeth fit
    location_set = set()
    rotated_set = set()
    for g in gears:
        if g.name not in location_set:
            setLocation(g, context, location_set, rotated_set)

    parentToEmpty(gears, empty, context)
    setDriversAndKeys(gears, context)
                
def updateMesh(self, context):
    object = context.object
    updateObjects(context)
    focus(object, context)
    
bpy.types.Object.reg = StringProperty(default='Gears')

bpy.types.Object.radius = FloatProperty(name="Radius",
                                        description="Radius of gear",
                                        default=1,
                                        soft_min=0.1,
                                        soft_max=40.0,
                                        subtype='DISTANCE',
                                        unit='LENGTH',
                                        update=updateMesh)

bpy.types.Object.nteeth = IntProperty(name="Number of teeth",
                                       description="Number of teeth",
                                       default=12,
                                       soft_min=4,
                                       update=updateMesh)

bpy.types.Object.twin = EnumProperty(items=[('None','None','None',0), ('Up','Up','Up',1), ('Down','Down','Down',2)], update=updateMesh)

bpy.types.Object.driver = EnumProperty(items=availableGears , update=updateMesh)

class Gears(bpy.types.Panel):
    bl_idname = "gears2"
    bl_label = "Gears"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "modifier"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        if bpy.context.mode == 'EDIT_MESH':
            layout.label('Gears doesn\'t work in the EDIT-Mode.')
        else:
            o = context.object
            if 'reg' in o:
                if o['reg'] == 'Gears':
                    layout.prop(o, 'nteeth')
                    col = layout.column()
                    col.prop(o, 'radius')
                    col.enabled = o.driver == ''
                    col = layout.column()
                    col.prop(o, 'twin')
                    col.enabled = o.driver != ''
                    layout.prop(o, 'driver')
                    layout.operator('mesh.gear2_add')
                else:
                    layout.operator('mesh.gear2_convert')
            else:
                layout.operator('mesh.gear2_convert')


class GearAdd(bpy.types.Operator):
    bl_idname = "mesh.gear2_add"
    bl_label = "Gear"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        current = context.active_object
        bpy.ops.mesh.primitive_cube_add()
        context.active_object.name = 'Gear'
        print('GearAdd')
        
        if isGear(current):
            print('current is gear',current.name)
            newgear = context.active_object
            newgear.driver = current.name
            newgear.reg = 'Gears'
            bpy.ops.mesh.gear2_convert(
                {'object':newgear, 'active_object':newgear, 
                # IMHO the following keys wouldn't be needed because this dict is an override, but Blender prints al sorts of messages if I leave these out (2.68a)
                'scene':context.scene, 'blend_data':context.blend_data,
                'window':context.window, 'screen':context.screen,
                'area':context.area, 'region':context.region},
                'INVOKE_DEFAULT')
        else:
            bpy.ops.mesh.gear2_convert('INVOKE_DEFAULT')
        print('I am here')
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(GearAdd.bl_idname, text="Add gear mesh",
                         icon='PLUGIN')


class GearConvert(bpy.types.Operator):
    bl_idname = 'mesh.gear2_convert'
    bl_label = 'Convert to Gear object'
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        print('invoke convert', context.object, context.active_object)
        print(context.window, context.screen, context.area)
        o = context.object
        o.reg = 'Gears'
        o.nteeth = 12
        return {"FINISHED"}

    def execute(self, context):
        print('execute convert', context.object, context.active_object)
        print(context.window, context.screen, context.area, context.region)
        o = context.object
        o.reg = 'Gears'
        o.nteeth = 12
        return {"FINISHED"}


def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_mesh_add.append(menu_func)


def unregister():
    bpy.types.INFO_MT_mesh_add.remove(menu_func)
    bpy.utils.unregister_module(__name__)
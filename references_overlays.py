import bpy
import gpu
import os
import math
from gpu_extras.batch import batch_for_shader
from bpy_extras.io_utils import ImportHelper

def draw_overlays_toggle():
	if bpy.context.screen.references_overlays.overlays_toggle == True:
		for item in bpy.context.screen.references_overlays.reference:

			if bpy.data.images.get(item.name):

				image = bpy.data.images[item.name]
				texture = gpu.texture.from_image(image)

				if item.flip_x:
					min_x = item.x+image.size[0]/2 * item.size/2
					max_x = item.x-image.size[0]/2 * item.size/2
				else:
					min_x = item.x-image.size[0]/2 * item.size/2
					max_x = item.x+image.size[0]/2 * item.size/2

				if item.flip_y:
					min_y = item.y+image.size[1]/2 * item.size/2
					max_y = item.y-image.size[1]/2 * item.size/2
				else:
					min_y = item.y-image.size[1]/2 * item.size/2
					max_y = item.y+image.size[1]/2 * item.size/2

				center_x = (min_x + max_x) / 2
				center_y = (min_y + max_y) / 2
				rotation_angle = item.rotation * -1

				tex_vert_shader = """
				in vec2 texCoord;
				in vec2 pos;
				out vec2 uv;

				uniform mat4 ModelViewProjectionMatrix;
				uniform float RotationAngle;
				uniform vec2 Center;

				void main() {
					uv = texCoord;

					// Calculate rotation based on position
					vec2 from_center = pos - Center;
					float cos_a = cos(RotationAngle);
					float sin_a = sin(RotationAngle);
					vec2 rotated_pos = vec2(from_center.x * cos_a - from_center.y * sin_a, from_center.x * sin_a + from_center.y * cos_a) + Center;
					gl_Position = ModelViewProjectionMatrix * vec4(rotated_pos, 0.0, 1.0);
				}
				"""

				tex_frag_shader = """
				in vec2 uv;
				out vec4 fragColor;

				uniform sampler2D image;
				uniform float opacity;

				void main() {
					vec4 color = texture(image, uv);
					fragColor = vec4(color.rgb * 1, color.a * opacity);
				}
				"""
				
				shader = gpu.types.GPUShader(tex_vert_shader, tex_frag_shader)
				
				batch = batch_for_shader(
					shader, 'TRI_FAN',
					{
						"pos": ((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)),
						"texCoord": ((0, 0), (1, 0), (1, 1), (0, 1)),
					},
				)
				gpu.state.blend_set('ALPHA')
				shader.bind()
				shader.uniform_sampler("image", texture)
				shader.uniform_float("RotationAngle", rotation_angle)
				shader.uniform_float("Center", (center_x, center_y))
				shader.uniform_float("opacity", item.opacity)
				batch.draw(shader)

class References(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(name = 'References Name')
	size : bpy.props.FloatProperty(name = 'References Size', default=1)
	flip_x : bpy.props.BoolProperty(name = 'References Flip X',default=False)
	flip_y : bpy.props.BoolProperty(name = 'References Flip Y',default=False)
	rotation : bpy.props.FloatProperty(name = 'References Rotation', default=0, subtype='ANGLE')
	x : bpy.props.FloatProperty(name = 'References Position X', default=0)
	y : bpy.props.FloatProperty(name = 'References Position Y', default=0)
	opacity : bpy.props.FloatProperty(name = 'References Opacity',min=0, max = 1, default=1)

class Reference_Overlay_Props(bpy.types.PropertyGroup):
	def update_overlays_toggle(self, context):

		dns = bpy.app.driver_namespace

		if self.overlays_toggle == True:
			
			dns["draw_overlays_toggle"] = bpy.types.SpaceView3D.draw_handler_add(draw_overlays_toggle, (), 'WINDOW', 'POST_PIXEL')

		if self.overlays_toggle == False:

			if dns.get("draw_overlays_toggle"):

				bpy.types.SpaceView3D.draw_handler_remove(dns["draw_overlays_toggle"], 'WINDOW')

	reference : bpy.props.CollectionProperty(type=References)
	reference_index : bpy.props.IntProperty(name = "References Overlay", description = "References Overlay")
	overlays_toggle : bpy.props.BoolProperty(default=False, update=update_overlays_toggle)

class REFERENCES_UL_Overlays(bpy.types.UIList):
	# The draw_item function is called for each item of the collection that is visible in the list.
	#   data is the RNA object containing the collection,
	#   item is the current drawn item of the collection,
	#   icon is the "computed" icon for the item (as an integer, because some objects like materials or textures
	#   have custom icons ID, which are not available as enum items).
	#   active_data is the RNA object containing the active property for the collection (i.e. integer pointing to the
	#   active item of the collection).
	#   active_propname is the name of the active property (use 'getattr(active_data, active_propname)').
	#   index is index of the current item in the collection.
	#   flt_flag is the result of the filtering process for this item.
	#   Note: as index and flt_flag are optional arguments, you do not have to use/declare them here if you don't
	#         need them.
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		# draw_item must handle the three layout types... Usually 'DEFAULT' and 'COMPACT' can share the same code.
		if self.layout_type in {'DEFAULT'}:
			# You should always start your row layout by a label (icon + text), or a non-embossed text field,
			# this will also make the row easily selectable in the list! The later also enables ctrl-click rename.
			# We use icon_value of label, as our given i
			# con is an integer value, not an enum ID.
			# Note "data" names should never be translated!
			row = layout.row(align = True)

			if bpy.data.images.get(item.name):
				image = bpy.data.images[item.name]
				if image.preview:
					row.label(text=item.name, icon_value = image.preview.icon_id)
				else:
					row.label(text=item.name, icon = 'IMAGE_DATA')
				row.operator("screen.move_reference", icon = "VIEW_PAN", text = "", emboss = False).index = index
			else:
				row.prop_search(item, "name", bpy.data, "images", text = "")

			row.operator("screen.remove_references_slot", icon = "X", text = "", emboss = False).index = index

	def filter_items(self, context, data, propname):
		"""Filter and sort items in the list"""
		helper_funcs = bpy.types.UI_UL_list	

		filtered = []
		ordered = []

		items = getattr(data, propname)

		filtered = helper_funcs.filter_items_by_name(self.filter_name, self.bitflag_filter_item, items, "name",
													reverse=self.use_filter_invert)

		ordered = list(reversed(range(len(items))))

		return filtered, ordered

class Load_References_OT(bpy.types.Operator, ImportHelper):
	bl_idname = "screen.load_references"
	bl_label = "Load References"
	bl_description = "Load References"
	bl_options = {'REGISTER', 'UNDO'}
	
	filename_ext = '.png, .jpg, .jpeg'  # List of acceptable image file extensions
	
	filter_glob: bpy.props.StringProperty(
		default='*.png;*.jpg;*.jpeg',  # Update the default filter to include multiple image types
		options={'HIDDEN'}
	)

	directory: bpy.props.StringProperty(
			subtype='DIR_PATH',
	)
	
	files: bpy.props.CollectionProperty(
			type=bpy.types.OperatorFileListElement,
	)

	def execute(self, context):
		references_overlays = context.screen.references_overlays

		directory = self.directory
		
		for file_elem in self.files:
			image_path = os.path.join(directory, file_elem.name)
			image = bpy.data.images.load(image_path)
			image.use_fake_user = True
			item = references_overlays.reference.add()
			item.name = image.name
			item.x = image.size[0]/4
			item.y = image.size[1]/4

		references_overlays.reference_index = len(references_overlays.reference) - 1

		return {'FINISHED'}
	
class Add_References_OT(bpy.types.Operator):
	bl_idname = "screen.add_references_slot"
	bl_label = "Add References Slots"
	bl_description = "Add References Slots"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		references_overlays = context.screen.references_overlays
		references_overlays.reference.add()

		references_overlays.reference_index = len(references_overlays.reference) - 1

		return{'FINISHED'}
	
class Rest_References_OT(bpy.types.Operator):
	bl_idname = "screen.rest_reference"
	bl_label = "Rest References"
	bl_description = "Rest References"
	bl_options = {'REGISTER', 'UNDO'}

	index : bpy.props.IntProperty(options={'HIDDEN'})

	def execute(self, context):
		mode = context.screen.references_overlays.overlays_toggle

		references_overlays = context.screen.references_overlays
		item = references_overlays.reference[self.index]
		image = bpy.data.images[item.name]

		item.size = 1
		item.rotation = 0
		item.x = image.size[0]/4
		item.y = image.size[1]/4
		item.flip_x = False
		item.flip_y = False
		item.opacity = 1

		context.screen.references_overlays.overlays_toggle = False
		context.screen.references_overlays.overlays_toggle = mode

		return{'FINISHED'}

class Remove_References_OT(bpy.types.Operator):
	bl_idname = "screen.remove_references_slot"
	bl_label = "Remove References Slots"
	bl_description = "Remove References Slots"
	bl_options = {'REGISTER', 'UNDO'}

	index : bpy.props.IntProperty(options={'HIDDEN'})

	def execute(self, context):
		mode = context.screen.references_overlays.overlays_toggle

		references_overlays = context.screen.references_overlays
		references_overlays.reference.remove(self.index)

		if references_overlays.reference_index > len(references_overlays.reference) - 1:
			references_overlays.reference_index = references_overlays.reference_index - 1

		context.screen.references_overlays.overlays_toggle = False
		context.screen.references_overlays.overlays_toggle = mode

		return{'FINISHED'}

class Clear_References_OT(bpy.types.Operator):
	bl_idname = "screen.clear_references_slot"
	bl_label = "Clear References Slots"
	bl_description = "Clear References Slots"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		mode = context.screen.references_overlays.overlays_toggle

		references_overlays = context.screen.references_overlays
		references_overlays.reference.clear()

		references_overlays.reference_index = 0

		context.screen.references_overlays.overlays_toggle = False
		context.screen.references_overlays.overlays_toggle = mode

		return{'FINISHED'}

class Move_References_OT(bpy.types.Operator):
	bl_idname = "screen.move_reference"
	bl_label = "Move References"
	bl_description = "Move References"
	bl_options = {'REGISTER', 'UNDO'}

	index : bpy.props.IntProperty(options={'HIDDEN'})

	x = None
	y = None
	size = None
	rotation = None
	opacity= None

	def modal(self, context, event):
		context.area.tag_redraw()
		references_overlays = context.screen.references_overlays
		item = references_overlays.reference[self.index]
		
		if event.type == 'MOUSEMOVE':
			item.x = event.mouse_region_x
			item.y = event.mouse_region_y

		elif event.type == 'WHEELUPMOUSE':
			# Handle mouse scroll up events
			item.size = item.size * 1.1
			
		elif event.type == 'WHEELDOWNMOUSE':
			# Handle mouse scroll down events
			item.size = item.size * 0.9

		elif event.type == 'S':
			item.size = 1

		elif event.type == 'R':
			item.rotation = 0

		elif event.type == 'C':
			item.opacity = item.opacity + 0.1
		elif event.type == 'Z':
			item.opacity = item.opacity - 0.1

		elif event.type == 'E':
			if event.shift:
				item.rotation += math.radians(1)  # Small rotation increment when SHIFT is pressed
			else:
				item.rotation += math.radians(5)  # Default rotation increment

		elif event.type == 'Q':
			if event.shift:
				item.rotation -= math.radians(1)  # Small rotation increment when SHIFT is pressed
			else:
				item.rotation -= math.radians(5)  # Default rotation increment

		elif event.type == 'LEFTMOUSE':
			return {'FINISHED'}

		elif event.type in {'RIGHTMOUSE', 'ESC'}:
			item.x = self.x
			item.y = self.y 
			item.size = self.size
			item.rotation = self.rotation 
			item.opacity = self.opacity

			return {'CANCELLED'}

		return {'RUNNING_MODAL'}
	
	def invoke(self, context, event):
		if context.area.type == 'VIEW_3D':
			references_overlays = context.screen.references_overlays
			item = references_overlays.reference[self.index]
			self.x = item.x
			self.y = item.y 
			self.size = item.size
			self.rotation = item.rotation 
			self.opacity = item.opacity
			# The arguments we pass the callback.
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, "View3D not found, cannot run operator")
			return {'CANCELLED'}

class OVERLAY_PT_Reference(bpy.types.Panel):
	bl_idname = "OVERLAY_PT_Reference"
	bl_options = {"DEFAULT_CLOSED"}
	bl_label = "References Overlay"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'HEADER'

	def draw(self, context):
		references_overlays = context.screen.references_overlays

		layout = self.layout
		layout.label(text="References Overlay")

		layout.label(text = "References Total "+ str(len(references_overlays.reference)), icon = "IMAGE_REFERENCE")
		row = layout.row(align=True)
		row.operator("screen.load_references", icon = "FILEBROWSER", text = "Load Image")
		row.operator("screen.clear_references_slot", icon = "TRASH", text = "")

		row = layout.row()
		row.template_list("REFERENCES_UL_Overlays", "", references_overlays, "reference", references_overlays, "reference_index")
		col = row.column(align=True)
		col.operator("screen.add_references_slot", icon = "ADD", text = "")
		col.operator("screen.remove_references_slot", icon = "REMOVE", text = "").index = references_overlays.reference_index
		col.separator()

		sub = col.column()
		sub.enabled = len(references_overlays.reference) > 0

		up = sub.operator("uilist.entry_move", icon = "TRIA_UP", text = "")
		up.list_path = 'screen.references_overlays.reference'
		up.active_index_path = 'screen.references_overlays.reference_index'
		up.direction = 'DOWN'

		down = sub.operator("uilist.entry_move", icon = "TRIA_DOWN", text = "")
		down.list_path ='screen.references_overlays.reference'
		down.active_index_path = 'screen.references_overlays.reference_index'
		down.direction = 'UP'

		sub.separator()

		sub.operator("screen.move_reference", icon = "VIEW_PAN", text = "").index = references_overlays.reference_index
		
		if len(references_overlays.reference) > 0:

			item = references_overlays.reference[references_overlays.reference_index]
			image = bpy.data.images.get(item.name)
			if image:

				if image.preview:

					layout.template_icon(image.preview.icon_id, scale=10.0)

				layout.separator()

				row = layout.row(align=True)

				row.prop_search(item, "name", bpy.data, "images", text = "")
				row.operator("screen.rest_reference", icon = "FILE_REFRESH", text = "").index = references_overlays.reference_index

				layout.separator()

				layout.prop(image, "filepath", text="Path")
				row = layout.row(align=True, heading = "Flip")
				row.prop(item, "flip_x", text="X", toggle=True)
				row.prop(item, "flip_y", text="Y", toggle=True)
				row = layout.row(align=True)
				row.prop(item, "x", text="X")
				row.prop(item, "y", text="Y")
				layout.prop(item, "rotation", text="Rotation")
				layout.prop(item, "size", text="Size")
				layout.prop(item, "opacity", text="Opacity", slider = True)

def references_overlays_header(self, context):
	layout = self.layout
	row = layout.row(align=True)
	row.prop(context.screen.references_overlays, "overlays_toggle", icon='IMAGE_REFERENCE', text="")
	sub = row.row(align=True)

	sub.popover(panel="OVERLAY_PT_Reference", text="")

classes = (
	 References,
	 Reference_Overlay_Props,
	 REFERENCES_UL_Overlays,
	 Load_References_OT,
	 Add_References_OT,
	 Remove_References_OT,
	 Rest_References_OT,
 	 Clear_References_OT,
	 Move_References_OT,
	 OVERLAY_PT_Reference,
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Screen.references_overlays = bpy.props.PointerProperty(type = Reference_Overlay_Props)

	dns = bpy.app.driver_namespace
		
	dns["draw_overlays_toggle"] = bpy.types.SpaceView3D.draw_handler_add(draw_overlays_toggle, (), 'WINDOW', 'POST_PIXEL')

	bpy.types.VIEW3D_HT_header.append(references_overlays_header)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	bpy.types.VIEW3D_HT_header.remove(references_overlays_header)

	del bpy.types.Screen.references_overlays





import bpy
import gpu
import os
import math
from gpu_extras.batch import batch_for_shader
from bpy_extras.io_utils import ImportHelper
from bpy.app.handlers import persistent
import rna_keymap_ui

dns = bpy.app.driver_namespace

@persistent
def check_overlays_toggle(self, context):
	if bpy.context.screen.references_overlays.overlays_toggle == True:
		for item in bpy.context.screen.references_overlays.reference:
			if bpy.data.images.get(item.name) and item.hide == False:
				dns["draw_overlays_toggle"] = bpy.types.SpaceView3D.draw_handler_add(draw_overlays_toggle, (), 'WINDOW', 'POST_PIXEL')


def draw_outline(context, min_x, min_y, max_x, max_y, thickness):
	vertices = [
		(min_x, min_y),
		(max_x, min_y),
		(max_x, max_y),
		(min_x, max_y),
		(min_x, min_y),
	]

	shader = gpu.shader.from_builtin("UNIFORM_COLOR")
	gpu.state.blend_set("ALPHA")
	gpu.state.line_width_set(thickness)
	batch = batch_for_shader(shader, "LINE_STRIP", {"pos": vertices})
	shader.uniform_float("color", (0.394198,0.569371,1,1))
	batch.draw(shader)
	gpu.state.blend_set("NONE")

def draw_overlays_toggle():
	if bpy.context.screen.references_overlays.overlays_toggle == True:
		for i, item in enumerate(bpy.context.screen.references_overlays.reference):
			if bpy.data.images.get(item.name) and item.hide == False:

				image = bpy.data.images[item.name]

				if image.source in {'SEQUENCE', 'MOVIE'}:
					if image.pixels:
						image.update()

					if item.use_cyclic:
						image.gl_load(frame=int((bpy.context.scene.frame_current + item.frame_offset)*item.speed % image.frame_duration))
					else:
						image.gl_load(frame=int((bpy.context.scene.frame_current + item.frame_offset)*item.speed) if bpy.context.scene.frame_current > 0 else item.frame_offset + 1)

				try:

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
					uniform bool depthSet;

					void main() {
						uv = texCoord;

						// Calculate rotation based on position
						vec2 from_center = pos - Center;
						float cos_a = cos(RotationAngle);
						float sin_a = sin(RotationAngle);
						vec2 rotated_pos = vec2(from_center.x * cos_a - from_center.y * sin_a, from_center.x * sin_a + from_center.y * cos_a) + Center;
						gl_Position = ModelViewProjectionMatrix * vec4(rotated_pos, 0.0, 1.0);
						if (depthSet) {
							gl_Position.z = gl_Position.w - 2.4e-7;
						}
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
					if item.depth_set == "Back":
						gpu.state.depth_test_set('LESS_EQUAL')
						shader.uniform_bool("depthSet", True)
					else:
						shader.uniform_bool("depthSet", False)
						
					batch.draw(shader)

					if i == bpy.context.screen.references_overlays.reference_index and bpy.context.screen.references_overlays.active_highlight:
						draw_outline(bpy.context, min_x-3, min_y, max_x, max_y, 3.0)

				except:
					continue

class References(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(name = 'References Name')
	size : bpy.props.FloatProperty(name = 'References Size', default=1)
	flip_x : bpy.props.BoolProperty(name = 'References Flip X',default=False)
	flip_y : bpy.props.BoolProperty(name = 'References Flip Y',default=False)
	rotation : bpy.props.FloatProperty(name = 'References Rotation', default=0, subtype='ANGLE')
	x : bpy.props.FloatProperty(name = 'References Position X', default=0)
	y : bpy.props.FloatProperty(name = 'References Position Y', default=0)
	opacity : bpy.props.FloatProperty(name = 'References Opacity',min=0, max = 1, default=1)
	depth_set : bpy.props.EnumProperty(default = 'Default',
							items = [('Default', 'Default', ''),
									('Back', 'Back', ''),
									],
							name="Depth"
									)
	speed : bpy.props.FloatProperty(name = 'Speed', default=1.0)
	use_cyclic : bpy.props.BoolProperty(name = 'Cyclic',default=False)
	frame_offset : bpy.props.IntProperty(name = 'Frame Offset', default=0)
	hide : bpy.props.BoolProperty(name = 'Hide',default=False)

class Reference_Overlay_Props(bpy.types.PropertyGroup):
	def update_overlays_toggle(self, context):

		if self.overlays_toggle == True:
			
			dns["draw_overlays_toggle"] = bpy.types.SpaceView3D.draw_handler_add(draw_overlays_toggle, (), 'WINDOW', 'POST_PIXEL')

		if self.overlays_toggle == False:

			if dns.get("draw_overlays_toggle"):

				bpy.types.SpaceView3D.draw_handler_remove(dns["draw_overlays_toggle"], 'WINDOW')

	reference : bpy.props.CollectionProperty(type=References)
	reference_index : bpy.props.IntProperty(name = "References Overlay", description = "References Overlay")
	overlays_toggle : bpy.props.BoolProperty(default=False, update=update_overlays_toggle)

	active_highlight : bpy.props.BoolProperty(name = "Active Highlight", default=False)

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
				row.prop(item, 'hide', text= '', icon = 'HIDE_ON' if item.hide else 'HIDE_OFF', emboss = False)
				xrow = row.row()
				xrow.enabled = not item.hide
				if image.preview:
					xrow.label(text=item.name, icon_value = image.preview.icon_id)
				else:
					xrow.label(text=item.name, icon = 'IMAGE_DATA')
				xrow.operator("screen.move_reference", icon = "VIEW_PAN", text = "", emboss = False).index = index
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
	
	filename_ext = '.bmp, .tiff, .png, .jpg, .jpeg, .gif, .mp4, .webm'  # List of acceptable image file extensions
	
	filter_glob: bpy.props.StringProperty(
		default='*.bmp;*.tiff;*.png;*.jpg;*.jpeg;*.gif;*.mp4;*.webm',  # Update the default filter to include multiple image types
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

		self.report({'INFO'}, f"Loaded {file_elem.name} Image.")

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
		item.depth_set = 'Default'

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

class Copy_References_From_OT(bpy.types.Operator):
	bl_idname = "screen.copy_references_from"
	bl_label = "Copy References From Other Screen"
	bl_description = "Copy References From Other Screen"
	bl_options = {'REGISTER', 'UNDO'}

	name : bpy.props.StringProperty(options={'HIDDEN'})
	override : bpy.props.BoolProperty(name='Override References', default=False)

	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def execute(self, context):
		current = context.screen.references_overlays
		target = bpy.data.screens[self.name].references_overlays

		if self.override:
			current.reference.clear()

		for target_item in target.reference:
			item = current.reference.add()
			item.name = target_item.name
			item.size = target_item.size
			item.flip_x = target_item.flip_x
			item.flip_y = target_item.flip_y
			item.rotation = target_item.rotation
			item.x = target_item.x
			item.y = target_item.y
			item.opacity = target_item.opacity
			item.depth_set = target_item.depth_set
			item.speed = target_item.speed
			item.use_cyclic = target_item.use_cyclic
			item.frame_offset = target_item.frame_offset
			item.hide = target_item.hide

		if target.overlays_toggle == True:
			target.overlays_toggle = False
			target.overlays_toggle = True

		self.report({'INFO'}, f"Copyed {self.name} References.")

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
	depth_set = None

	def modal(self, context, event):
		context.area.tag_redraw()
		references_overlays = context.screen.references_overlays
		item = references_overlays.reference[self.index]
		
		if event.type == 'ONE':
			item.depth_set = 'Default'
		elif event.type == 'TWO':
			item.depth_set = 'Back'

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
			item.depth_set = self.depth_set

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
			self.depth_set = item.depth_set
			# The arguments we pass the callback.
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, "View3D not found, cannot run operator")
			return {'CANCELLED'}

class Align_References_OT(bpy.types.Operator):
	bl_idname = "screen.align_reference"
	bl_label = "Align References"
	bl_description = "Align References"
	bl_options = {'REGISTER', 'UNDO'}

	align_x : bpy.props.StringProperty(name='Align X', options={'HIDDEN'})
	align_y : bpy.props.StringProperty(name='Align Y', options={'HIDDEN'})

	def execute(self, context):
		mode = context.screen.references_overlays.overlays_toggle
		references_overlays = context.screen.references_overlays
		item = references_overlays.reference[references_overlays.reference_index]
		image = bpy.data.images[item.name]

		region_width = context.region.width
		region_height = context.region.height

		if self.align_x == 'LEFT':
			item.x = image.size[0]/2 * item.size/2
		elif self.align_x == 'RIGHT':
			item.x = region_width - image.size[0]/2 * item.size/2
		elif self.align_x == 'CENTER':
			item.x = region_width/2

		if self.align_y == 'DOWN':
			item.y = image.size[1]/2 * item.size/2
		elif self.align_y == 'UP':
			item.y = region_height - image.size[1]/2 * item.size/2
		elif self.align_y == 'CENTER':
			item.y = region_height/2

		context.screen.references_overlays.overlays_toggle = False
		context.screen.references_overlays.overlays_toggle = mode

		return{'FINISHED'}

class Toggle_References_OT(bpy.types.Operator):
	bl_idname = "screen.toggle_references_overlays"
	bl_label = "Toggle References Overlays"
	bl_description = "Toggle References Overlays"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		context.screen.references_overlays.overlays_toggle = not context.screen.references_overlays.overlays_toggle
		return {'FINISHED'}

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

		col = layout.column()
		col.label(text="Copying references from other screen.")

		for screen in bpy.data.screens:
			if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
				col.enabled = True
				break
			else:
				col.enabled = False

		row = col.row(align=True)
		row.operator("wm.call_menu", text="Add", icon='PASTEDOWN').name='OVERLAY_MT_Add_References'
		row.operator("wm.call_menu", text="Override").name='OVERLAY_MT_Override_References'

		row = layout.row(align=True)
		row.operator("screen.load_references", icon = "FILEBROWSER", text = "Load Image")
		row.operator("screen.clear_references_slot", icon = "TRASH", text = "")

		row = layout.row()
		row.template_list("REFERENCES_UL_Overlays", "", references_overlays, "reference", references_overlays, "reference_index")
		col = row.column(align=True)
		col.operator("screen.add_references_slot", icon = "ADD", text = "")
		col.operator("screen.remove_references_slot", icon = "REMOVE", text = "").index = references_overlays.reference_index
		col.separator()
		
		sub = col.column(align=True)
		sub.enabled = len(references_overlays.reference) > 0

		up = sub.operator("uilist.entry_move", icon = "TRIA_UP", text = "")
		up.list_path = 'screen.references_overlays.reference'
		up.active_index_path = 'screen.references_overlays.reference_index'
		up.direction = 'DOWN'

		down = sub.operator("uilist.entry_move", icon = "TRIA_DOWN", text = "")
		down.list_path ='screen.references_overlays.reference'
		down.active_index_path = 'screen.references_overlays.reference_index'
		down.direction = 'UP'

		col.prop(references_overlays, "active_highlight", text="", icon='HIDE_OFF')

		if len(references_overlays.reference) > 0:

			item = references_overlays.reference[references_overlays.reference_index]
			image = bpy.data.images.get(item.name)
			if image:

				sub.separator()
				subcol = sub.column()
				subcol.enabled = not item.hide
				subcol.operator("screen.move_reference", icon = "VIEW_PAN", text = "").index = references_overlays.reference_index

				if image.preview:

					layout.template_icon(image.preview.icon_id, scale=10.0)

				layout.separator()

				row = layout.row(align=True)

				row.prop_search(item, "name", bpy.data, "images", text = "")
				row.operator("screen.rest_reference", icon = "FILE_REFRESH", text = "").index = references_overlays.reference_index

				layout.separator()

				col = layout.column()
				col.use_property_split = True
				col.use_property_decorate = False

				col.prop(image, "filepath", text= "Path")

				if image.source in {'SEQUENCE', 'MOVIE'}:
					col.separator()
					col.prop(item, "speed", text="Speed")
					col.prop(item, "frame_offset", text="Offset")
					col.prop(item, "use_cyclic", text="Cyclic")

				col.separator()
				col.prop(item, "size", text="Size")

				col.separator()
				col.prop(item, "x", text="Position X")
				col.prop(item, "y", text="Y")

				col.separator()
				col.prop(item, "rotation", text="Rotation")

				col.separator()
				col.row().prop(item, "depth_set", text="Depth", expand=True)

				row = col.row(align=True, heading = "Flip")
				row.prop(item, "flip_x", text="X", toggle=True)
				row.prop(item, "flip_y", text="Y", toggle=True)

				col.separator()
				col.prop(item, "opacity", text="Opacity", slider = True)

				col.separator()
				xrow = col.row()
				xrow.label(text='Align')
				sub = xrow.column(align=True)
				colrow = sub.row(align=True)
				op = colrow.operator("screen.align_reference", icon = "BLANK1", text = "")
				op.align_x = 'LEFT'
				op.align_y =  'UP'
				op = colrow.operator("screen.align_reference", icon = "TRIA_UP_BAR", text = "")
				op.align_x = 'CENTER'
				op.align_y =  'UP'
				op = colrow.operator("screen.align_reference", icon = "BLANK1", text = "")
				op.align_x = 'RIGHT'
				op.align_y =  'UP'
				colrow = sub.row(align=True)
				op = colrow.operator("screen.align_reference", icon = "TRIA_LEFT_BAR", text = "")
				op.align_x = 'LEFT'
				op.align_y =  'CENTER'
				op = colrow.operator("screen.align_reference", icon = "LAYER_ACTIVE", text = "")
				op.align_x = 'CENTER'
				op.align_y =  'CENTER'
				op = colrow.operator("screen.align_reference", icon = "TRIA_RIGHT_BAR", text = "")
				op.align_x = 'RIGHT'
				op.align_y =  'CENTER'
				colrow = sub.row(align=True)
				op = colrow.operator("screen.align_reference", icon = "BLANK1", text = "")
				op.align_x = 'LEFT'
				op.align_y =  'DOWN'
				op = colrow.operator("screen.align_reference", icon = "TRIA_DOWN_BAR", text = "")
				op.align_x = 'CENTER'
				op.align_y =  'DOWN'
				op = colrow.operator("screen.align_reference", icon = "BLANK1", text = "")
				op.align_x = 'RIGHT'
				op.align_y =  'DOWN'

class OVERLAY_MT_Add_References(bpy.types.Menu):
	bl_idname = "OVERLAY_MT_Add_References"
	bl_label = "Add References"

	@classmethod
	def poll(cls, context):
		for screen in bpy.data.screens:
			if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
				return True

	def draw(self, context):
		layout = self.layout
		for screen in bpy.data.screens:
			if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
				op = layout.operator("screen.copy_references_from", icon = "PASTEDOWN", text = screen.name)
				op.name = screen.name
				op.override = False

class OVERLAY_MT_Override_References(bpy.types.Menu):
	bl_idname = "OVERLAY_MT_Override_References"
	bl_label = "Override References"

	@classmethod
	def poll(cls, context):
		for screen in bpy.data.screens:
			if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
				return True

	def draw(self, context):
		layout = self.layout
		for screen in bpy.data.screens:
			if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
				op = layout.operator("screen.copy_references_from", icon = "PASTEDOWN", text = screen.name)
				op.name = screen.name
				op.override = True
				
def references_overlays_header(self, context):
	layout = self.layout
	row = layout.row(align=True)
	row.prop(context.screen.references_overlays, "overlays_toggle", icon='IMAGE_REFERENCE', text="")
	sub = row.row(align=True)

	sub.popover(panel="OVERLAY_PT_Reference", text="")

class AddonPreferences(bpy.types.AddonPreferences):
	bl_idname = __package__

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		row = col.row()
		row.label(text = "", icon = "EVENT_CTRL")
		row.label(text = "HotKey")

		wm = context.window_manager
		kc = wm.keyconfigs.user
		  
		property_editor_reg_location = "3D View"
		km = kc.keymaps[property_editor_reg_location]
		col.label(text="3D View")
		kmi = get_hotkey_entry_item(km, 'screen.toggle_references_overlays', '')
		if kmi:
			col.context_pointer_set("keymap", km)
			rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)
			col.separator()
		else:
			col.label(text="No hotkey entry found")
			col.operator('references_overlays.add_hotkey', text = "Add hotkey entry", icon = 'ZOOM_IN')

def get_hotkey_entry_item(km, kmi_name, kmi_value):
	for i, km_item in enumerate(km.keymap_items):
		if km.keymap_items.keys()[i] == kmi_name:
			# if km.keymap_items[i].properties.name == kmi_value: # プロパティがある場合は有効にする
			return km_item
	return None

class References_Overlays_OT_AddHotkey(bpy.types.Operator):
	''' Add hotkey entry '''
	bl_idname = "references_overlays.add_hotkey"
	bl_label = "Add Hotkey"
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):
		add_hotkey()
		return {'FINISHED'}

def add_hotkey():

	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon

	if kc:
		################################################

		km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new('screen.toggle_references_overlays', 'F1', 'PRESS',ctrl=True)
		kmi.active = True
		addon_keymaps.append((km, kmi))

def remove_hotkey():
	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon

	keymaps_to_remove = ['3D View']

	for keymap_name in keymaps_to_remove:
		keymap = kc.keymaps.get(keymap_name)
		if keymap:
			keymap_items = [kmi for kmi in keymap.keymap_items if kmi in addon_keymaps]
			for kmi in keymap_items:
				keymap.keymap_items.remove(kmi)
			kc.keymaps.remove(keymap)

	addon_keymaps.clear()

addon_keymaps = []

classes = (
	 References,
	 Reference_Overlay_Props,
	 REFERENCES_UL_Overlays,
	 Load_References_OT,
	 Add_References_OT,
	 Remove_References_OT,
	 Rest_References_OT,
 	 Clear_References_OT,
	 Copy_References_From_OT,
	 Move_References_OT,
	 Align_References_OT,
	 Toggle_References_OT,
	 OVERLAY_PT_Reference,
	 OVERLAY_MT_Add_References,
	 OVERLAY_MT_Override_References,
	 References_Overlays_OT_AddHotkey,
	 AddonPreferences,
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Screen.references_overlays = bpy.props.PointerProperty(type = Reference_Overlay_Props)
	
	bpy.app.handlers.load_post.append(check_overlays_toggle)

	bpy.types.VIEW3D_HT_header.append(references_overlays_header)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	bpy.types.VIEW3D_HT_header.remove(references_overlays_header)

	del bpy.types.Screen.references_overlays





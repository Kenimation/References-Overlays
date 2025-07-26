import bpy
import gpu
import os
import blf
from gpu_extras.batch import batch_for_shader
from .defs import *

def draw_name(context, item, x, y):
	font_id = 0  # XXX, need to find out how best to get this.

	blf.enable(font_id, blf.SHADOW)

	color = (1,1,1,1)
	
	blf.color(font_id, color[0], color[1], color[2], color[3])

	if context.screen.references_overlays.tweak_size:
		region_size = map_range(3, 0, context.window.width/2, 0, context.region.width) * map_range(3, 0, context.window.height/2, 0, context.region.height)
		blf.size(font_id, region_size)
	else:
		blf.size(font_id, 16)
	dimensions = blf.dimensions(font_id, item.tag_name)
	
	blf.position(font_id, x, y + dimensions[1]/2, 0)

	blf.draw(font_id, item.tag_name)

	blf.disable(font_id, blf.SHADOW)

def draw_outline(context, min_x, min_y, max_x, max_y, rotation_angle, color, thickness):
	# Calculate the center of the rectangle
	center_x = (min_x + max_x) / 2
	center_y = (min_y + max_y) / 2
	
	# Define the vertices of the rectangle
	vertices = [
		(min_x+2, min_y),
		(max_x, min_y),
		(max_x, max_y),
		(min_x+2, max_y),
		(min_x+2, min_y)
	]
	
	rotated_vertices = rotate_vertices(vertices, center_x, center_y, rotation_angle)

	shader = gpu.shader.from_builtin("UNIFORM_COLOR")
	gpu.state.blend_set("ALPHA")
	gpu.state.line_width_set(thickness)
	batch = batch_for_shader(shader, "LINE_STRIP", {"pos": rotated_vertices})
	
	shader.uniform_float("color", color)
	batch.draw(shader)
	gpu.state.blend_set("NONE")

class Overlay_Reference_Shape(bpy.types.Gizmo):
	bl_idname = "VIEW3D_GT_Overlay_Reference_Shape"
	bl_target_properties = ()
	index = None
	
	# Convenience wrappers around private `_gpu` module.
	def draw_custom_shape(self, shader, index, select_id=None):
		context = bpy.context
		if index < len(context.screen.references_overlays.reference):
			item = context.screen.references_overlays.reference[index]
			if bpy.data.images.get(item.name) and item.hide == False:

				region_x = map_range(item.x, 0, context.window.width, 0, context.region.width)
				region_y = map_range(item.y, 0, context.window.height, 0, context.region.height)

				if context.screen.references_overlays.tweak_size:
					region_size = map_range(item.size/1.75, 0, context.window.width/2, 0, context.region.width) * map_range(item.size/1.75, 0, context.window.height/2, 0, context.region.height)
				else:
					region_size = item.size

				image = bpy.data.images[item.name]

				if image.source in {'SEQUENCE', 'MOVIE'}:
					if image.pixels:
						image.update()

					fps = item.fps/10
 
					if item.use_cyclic:
						image.gl_load(frame=int((context.scene.frame_current + item.frame_offset)*(item.speed/fps) % image.frame_duration))
					else:
						image.gl_load(frame=int((context.scene.frame_current + item.frame_offset)*item.speed/fps) if context.scene.frame_current > 0 else item.frame_offset + 1)

				texture = gpu.texture.from_image(image)

				zoom = item.zoom*-1/2
				
				if item.flip_x:
					pivot_x = item.pivot_x*-1
					left = item.crop_right
					right = item.crop_left
					min_x = region_x+image.size[0]/2 * region_size/2*(1-left)
					max_x = region_x-image.size[0]/2 * region_size/2*(1-right)
				else:
					pivot_x = item.pivot_x
					left = item.crop_left
					right = item.crop_right
					min_x = region_x-image.size[0]/2 * region_size/2*(1-left) 
					max_x = region_x+image.size[0]/2 * region_size/2*(1-right)

				if item.flip_y:
					pivot_y = item.pivot_y * -1
					top = item.crop_bottom
					bottom = item.crop_top
					min_y = region_y+image.size[1]/2 * region_size/2*(1-bottom)
					max_y = region_y-image.size[1]/2 * region_size/2*(1-top)
				else:
					pivot_y = item.pivot_y
					top = item.crop_top
					bottom = item.crop_bottom
					min_y = region_y-image.size[1]/2 * region_size/2*(1-bottom)
					max_y = region_y+image.size[1]/2 * region_size/2*(1-top)

				center_x = (min_x + max_x) / 2
				center_y = (min_y + max_y) / 2
				rotation_angle = item.rotation * -1
				opacity = item.opacity

				pos = ((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y))

				batch = batch_for_shader(
					shader, 'TRI_FAN',
					{
						"pos": rotate_vertices(pos, center_x, center_y, rotation_angle),
						"texCoord": (
									((0+left/2+pivot_x)-zoom*(1-left), (0+bottom/2+pivot_y)-zoom*(1-bottom)), 
				   					((1-right/2+pivot_x)+zoom*(1-right), (0+bottom/2+pivot_y)-zoom*(1-bottom)),
									((1-right/2+pivot_x)+zoom*(1-right), (1-top/2+pivot_y)+zoom*(1-top)),
									((0+left/2+pivot_x)-zoom*(1-left), (1-top/2+pivot_y)+zoom*(1-top))
									),
					},
				)

				gpu.state.blend_set('ALPHA')

				shader.uniform_sampler("image", texture)
				shader.uniform_float("opacity", opacity)
				if item.depth_set == "Back":
					gpu.state.depth_test_set('LESS_EQUAL')
					shader.uniform_bool("depthSet", True)
				else:
					shader.uniform_bool("depthSet", False)
				
				batch.draw(shader)

				if select_id is not None:
					gpu.select.load_id(select_id)
				else:
					if self.is_highlight:
						draw_outline(context, min_x-3, min_y, max_x, max_y, rotation_angle, (1, 0.5, 0.5, 1) if item.lock == True else (0.394198,0.569371,1,1), 2.5)
					elif opacity < 0.2:
						draw_outline(context, min_x-3, min_y, max_x, max_y, rotation_angle, (1, 0.5, 0.5, 1), 2.5)

				if context.screen.references_overlays.show_name:
					if item.flip_x:
						x = max_x
					else:
						x = min_x
					if item.flip_y:
						y = min_y
					else:
						y = max_y
					draw_name(context, item, x, y)
	
	@staticmethod
	def new_custom_shape(self):       
		 
		vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
		vert_out.smooth('VEC2', "uv")

		shader_info = gpu.types.GPUShaderCreateInfo()

		shader_info.sampler(0, 'FLOAT_2D', "image")
		shader_info.vertex_in(0, 'VEC2', "pos")
		shader_info.vertex_in(1, 'VEC2', "texCoord")
		shader_info.vertex_out(vert_out)

		shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
		shader_info.push_constant('FLOAT', "opacity")
		shader_info.push_constant('BOOL', "depthSet")

		shader_info.fragment_out(0, 'VEC4', "fragColor")

		shader_info.vertex_source(
			"void main()"
			"{"
			"   uv = texCoord;"
			"   gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);"
			"   if (depthSet) {"
			"       gl_Position.z = gl_Position.w - 2.4e-7;"
			"   }"
			"}"
		)

		shader_info.fragment_source(
			"void main()"
			"{"
			"  vec4 color = texture(image, uv);"
			"  fragColor = vec4(color.rgb * 1.0, color.a*opacity);"
			"}"
		)

		# Create a shader from the shader info
		shader = gpu.shader.create_from_info(shader_info)

		return shader
	
	def draw(self, context):
		self.draw_custom_shape(self.custom_shape, self.index)
		
	def draw_select(self, context, select_id):
		self.draw_custom_shape(self.custom_shape, self.index, select_id=select_id)

	def setup(self):
		self.custom_shape = self.new_custom_shape(self)

	def test_select(self, context, location):
		if context.screen.references_overlays.full_lock or self.index >= len(context.screen.references_overlays.reference):
			return -1
		
		item = context.screen.references_overlays.reference[self.index]
		if bpy.data.images.get(item.name):
			image = bpy.data.images[item.name]

			if context.screen.references_overlays.tweak_size:
				region_size = map_range(item.size/1.75, 0, context.window.width/2, 0, context.region.width) * map_range(item.size/1.75, 0, context.window.height/2, 0, context.region.height)
			else:
				region_size = item.size

			region_x = map_range(item.x, 0, context.window.width, 0, context.region.width)
			region_y = map_range(item.y, 0, context.window.height, 0, context.region.height)
			
			if item.flip_x:
				left = item.crop_right
				right = item.crop_left
				min_x = region_x+image.size[0]/2 * region_size/2*(1-left)
				max_x = region_x-image.size[0]/2 * region_size/2*(1-right)
			else:
				left = item.crop_left
				right = item.crop_right
				min_x = region_x-image.size[0]/2 * region_size/2*(1-left)
				max_x = region_x+image.size[0]/2 * region_size/2*(1-right)
			if item.flip_y:
				top = item.crop_bottom
				bottom = item.crop_top
				min_y = region_y+image.size[1]/2 * region_size/2*(1-bottom)
				max_y = region_y-image.size[1]/2 * region_size/2*(1-top)
			else:
				top = item.crop_top
				bottom = item.crop_bottom
				min_y = region_y-image.size[1]/2 * region_size/2*(1-bottom)
				max_y = region_y+image.size[1]/2 * region_size/2*(1-top)

			center_x = (min_x + max_x) / 2
			center_y = (min_y + max_y) / 2
			rotation_angle = item.rotation * -1
			pos = ((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y))
			
			area = rotate_vertices(pos, center_x, center_y, rotation_angle)

			if point_in_area(location, area):
				return 0  # Location matches the gizmo's position within the area
			else:
				return -1  # Location is outside the defined area
			
		else:
			return -1

class Overlay_Reference_UI_Control(bpy.types.GizmoGroup):
	bl_idname = "Overlay_Reference_UI_Control"
	bl_label = "Overlay Reference Control"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'WINDOW'
	bl_options = {'PERSISTENT', 'SCALE'}
	
	def draw_gizmo(self, i):
		gizmo = self.gizmos.new(Overlay_Reference_Shape.bl_idname)   #GIZMO_GT_button_2d
		gizmo.target_set_operator("screen.move_reference").index = i
		gizmo.use_draw_value = True
		gizmo.use_tooltip = True
		gizmo.index = i
		
	@classmethod
	def poll(cls, context):
		return (context.screen.references_overlays.overlays_toggle == True and len(context.screen.references_overlays.reference) > 0)

	def draw_prepare(self, context):
		for i, item in enumerate(context.screen.references_overlays.reference):
			if bpy.data.images.get(item.name):
				if i + 1 > len(self.gizmos):
					self.draw_gizmo(i)
				else:
					gizmo = self.gizmos[i]
					gizmo.hide = item.hide
					gizmo.hide_select = item.lock
					region_x = map_range(item.x, 0, context.window.width, 0, context.region.width)
					region_y = map_range(item.y, 0, context.window.height, 0, context.region.height)
					gizmo.matrix_basis[0][3] = region_x
					gizmo.matrix_basis[1][3] = region_y

	def setup(self, context):
		for i, item in enumerate(context.screen.references_overlays.reference):
			if bpy.data.images.get(item.name):
				self.draw_gizmo(i)

class References(bpy.types.PropertyGroup):
	def update_tag_name(self, context):
		name, _ = os.path.splitext(self.name)
		self.tag_name = name

	tag_name : bpy.props.StringProperty(name = 'References Tag Name')
	name : bpy.props.StringProperty(name = 'References Name', update=update_tag_name)
	size : bpy.props.FloatProperty(name = 'References Size', default=1, min=0.01)
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
	
	crop_left : bpy.props.FloatProperty(name = 'Crop Left',min=0, max = 1, default=0)
	crop_top : bpy.props.FloatProperty(name = 'Crop Top',min=0, max = 1, default=0)
	crop_right : bpy.props.FloatProperty(name = 'Crop Right',min=0, max = 1, default=0)
	crop_bottom : bpy.props.FloatProperty(name = 'Crop Bottom',min=0, max = 1, default=0)

	pivot_x : bpy.props.FloatProperty(name = 'References Pivot X', default=0)
	pivot_y : bpy.props.FloatProperty(name = 'References Pivot Y', default=0)
	zoom : bpy.props.FloatProperty(name = 'References Zoom', default=0, min = 0, max = 1)

	speed : bpy.props.FloatProperty(name = 'Speed', default=1.0)
	use_cyclic : bpy.props.BoolProperty(name = 'Cyclic',default=False)
	frame_offset : bpy.props.IntProperty(name = 'Frame Offset', default=0)
	fps : bpy.props.IntProperty(name = 'FPS Tempo', default=0)
	hide : bpy.props.BoolProperty(name = 'Hide',default=False)
	lock : bpy.props.BoolProperty(name = 'Lock',default=False)

class Reference_Overlay_Props(bpy.types.PropertyGroup):
	reference : bpy.props.CollectionProperty(type=References)
	reference_index : bpy.props.IntProperty(name = "References Overlay", description = "References Overlay")
	overlays_toggle : bpy.props.BoolProperty(name = "References Overlay Toggle",default=True)
	show_name : bpy.props.BoolProperty(name = "Show Tag Name",default=False)
	tweak_size : bpy.props.BoolProperty(name = "Auto Tweak Size",default=False)
	full_lock : bpy.props.BoolProperty(name = "Full Lock", default=False, description = "Ignore mouse event")

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
					xrow.prop(item, "tag_name", text= "", icon_value = image.preview.icon_id, emboss = False)
				else:
					xrow.prop(item, "tag_name", text= "", icon = 'IMAGE_DATA', emboss = False)
			else:
				row.prop_search(item, "name", bpy.data, "images", text = "")

			row.prop(item, "lock", text= "", icon = "LOCKED" if item.lock else "UNLOCKED", emboss = False)
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
		col.prop(references_overlays, "full_lock", text="Full Lock")
		col.prop(references_overlays, "show_name", text="Show Tag Name")
		col.prop(references_overlays, "tweak_size", text="Auto Tweak Size")
		
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
		row.operator("screen.paste_reference", icon = "PASTEDOWN", text="")
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

		if len(references_overlays.reference) > 0:

			item = references_overlays.reference[references_overlays.reference_index]
			image = bpy.data.images.get(item.name)
			if image:

				if image.preview:

					layout.template_icon(image.preview.icon_id, scale=10.0)

				layout.separator()

				row = layout.row(align=True)
				row.prop(item, "tag_name", text= "Name")
				row.prop(item, "lock", text= "", icon = "LOCKED" if item.lock else "UNLOCKED", emboss = False)

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
					col.prop(item, "fps", text="FPS Tempo")
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
				col.prop(item, "crop_left", text="Crop Left")
				col.prop(item, "crop_top", text="Top")
				col.prop(item, "crop_right", text="Right")
				col.prop(item, "crop_bottom", text="Bottom")

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

		km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new('screen.toggle_lock_references_overlays', 'T', 'PRESS',ctrl=True)
		kmi.active = True
		addon_keymaps.append((km, kmi))

		km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new('screen.paste_reference', 'V', 'PRESS',ctrl=True, alt=True)
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
	 Overlay_Reference_Shape,
	 Overlay_Reference_UI_Control,
	 REFERENCES_UL_Overlays,
	 OVERLAY_PT_Reference,
	 OVERLAY_MT_Add_References,
	 OVERLAY_MT_Override_References,
	 References_Overlays_OT_AddHotkey,
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Screen.references_overlays = bpy.props.PointerProperty(type = Reference_Overlay_Props)

	add_hotkey()
	
	bpy.types.VIEW3D_HT_header.append(references_overlays_header)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	bpy.types.VIEW3D_HT_header.remove(references_overlays_header)

	remove_hotkey()

	del bpy.types.Screen.references_overlays
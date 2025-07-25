import math

def map_range(value, in_min, in_max, out_min, out_max):
	if value < 0:
		new_value = value*-1
	else:
		new_value = value

	# First, normalize the input value
	normalized_value = (new_value - in_min) / (in_max - in_min)
	
	# Apply the mapping to the output range
	mapped_value = normalized_value * (out_max - out_min) + out_min

	if value < 0:
		mapped_value = mapped_value*-1
	else:
		mapped_value = mapped_value
	
	return mapped_value

def point_in_area(point, area):
    x, y = point
    n = len(area)
    inside = False

    p1x, p1y = area[0]
    for i in range(n + 1):
        p2x, p2y = area[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
        p1x, p1y = p2x, p2y

    return inside

def rotate_vertices(vertices, center_x, center_y, rotation_angle):
	rotated_vertices = []
	for vertex in vertices:
		# Translate the vertex so that the center of rotation is at the origin
		translated_x = vertex[0] - center_x
		translated_y = vertex[1] - center_y
		
		# Apply rotation
		rotated_x = translated_x * math.cos(rotation_angle) - translated_y * math.sin(rotation_angle)
		rotated_y = translated_x * math.sin(rotation_angle) + translated_y * math.cos(rotation_angle)
		
		# Translate the vertex back to its original position
		rotated_vertices.append((rotated_x + center_x, rotated_y + center_y))
	return rotated_vertices

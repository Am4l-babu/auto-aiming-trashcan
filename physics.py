"""
Physics simulation for throwable objects
"""

import pybullet as p
import math
import time
from config import OBJECT_TYPES, SIMULATION, GRAVITY

class PhysicsSimulation:
    def __init__(self):
        """Initialize physics simulation"""
        self.objects_to_catch = []
        
    def create_throwable_object(self, start_pos, target_pos, object_type="bottle"):
        """Create more visible objects with enhanced tracking"""
        
        if object_type not in OBJECT_TYPES:
            raise ValueError(f"Unknown object type: {object_type}")
            
        obj_config = OBJECT_TYPES[object_type]
        
        # Make objects BIGGER and more visible for testing
        if obj_config['shape'] == 'cylinder':
            collision_shape = p.createCollisionShape(
                p.GEOM_CYLINDER, 
                radius=obj_config['radius'] * 1.5,  # 50% bigger
                height=obj_config['height'] * 1.5
            )
            visual_shape = p.createVisualShape(
                p.GEOM_CYLINDER, 
                radius=obj_config['radius'] * 1.5, 
                length=obj_config['height'] * 1.5,
                rgbaColor=[obj_config['color'][0], obj_config['color'][1], obj_config['color'][2], 1]
            )
        elif obj_config['shape'] == 'box':
            dims = [d * 2 for d in obj_config['dimensions']]  # Double size
            collision_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=dims)
            visual_shape = p.createVisualShape(
                p.GEOM_BOX, 
                halfExtents=dims,
                rgbaColor=[obj_config['color'][0], obj_config['color'][1], obj_config['color'][2], 1]
            )
        
        # Create object
        object_id = p.createMultiBody(
            baseMass=obj_config['mass'],
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=start_pos
        )
        
        # Calculate and apply velocity
        initial_velocity = self.calculate_throw_velocity(start_pos, target_pos)
        p.resetBaseVelocity(object_id, initial_velocity)
        
        # Store with enhanced info
        obj_info = {
            'id': object_id,
            'start_pos': start_pos,
            'target_pos': target_pos,
            'initial_velocity': initial_velocity,
            'start_time': time.time(),
            'type': object_type,
            'active': True
        }
        
        self.objects_to_catch.append(obj_info)
        
        print(f"🎯 Created ENHANCED {object_type} (ID: {object_id})")
        print(f"   From: ({start_pos[0]:.1f}, {start_pos[1]:.1f}, {start_pos[2]:.1f})")
        print(f"   To: ({target_pos[0]:.1f}, {target_pos[1]:.1f}, {target_pos[2]:.1f})")
        print(f"   Velocity: ({initial_velocity[0]:.1f}, {initial_velocity[1]:.1f}, {initial_velocity[2]:.1f})")
        
        return object_id

    def calculate_throw_velocity(self, start_pos, target_pos):
        """Calculate initial velocity needed to reach target position"""
        
        # Extract positions
        x0, y0, z0 = start_pos
        xt, yt, zt = target_pos
        
        # Horizontal distance and direction
        dx = xt - x0
        dy = yt - y0
        horizontal_distance = math.sqrt(dx**2 + dy**2)
        
        # Trajectory parameters
        g = abs(GRAVITY)
        height_diff = z0 - zt
        
        # Calculate optimal angle (45 degrees or best angle for distance)
        angle = math.radians(35)  # 35 degrees for good arc
        
        # Calculate initial speed needed
        # Using kinematic equations for projectile motion
        if horizontal_distance > 0:
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)
            tan_angle = math.tan(angle)
            
            # v0 = sqrt(g * d / (cos²θ * (d*tanθ - h)))
            denominator = cos_angle**2 * (horizontal_distance * tan_angle - height_diff)
            
            if denominator > 0:
                v0 = math.sqrt(g * horizontal_distance / denominator)
            else:
                v0 = 10.0  # Default speed
        else:
            v0 = 5.0  # Default for vertical throws
        
        # Calculate velocity components
        direction_x = dx / horizontal_distance if horizontal_distance > 0 else 0
        direction_y = dy / horizontal_distance if horizontal_distance > 0 else 0
        
        vx = v0 * math.cos(angle) * direction_x
        vy = v0 * math.cos(angle) * direction_y
        vz = v0 * math.sin(angle)
        
        return [vx, vy, vz]
        
    def get_object_state(self, obj_info):
        """Get current position and velocity of object"""
        try:
            pos, orn = p.getBasePositionAndOrientation(obj_info['id'])
            vel, ang_vel = p.getBaseVelocity(obj_info['id'])
            return pos, vel
        except:
            return None, None
            
    def cleanup_old_objects(self):
        """Remove old or out-of-bounds objects"""
        current_time = time.time()
        objects_to_remove = []
        
        for i, obj in enumerate(self.objects_to_catch):
            if not obj['active']:
                objects_to_remove.append(i)
                continue
                
            age = current_time - obj['start_time']
            
            try:
                pos, _ = p.getBasePositionAndOrientation(obj['id'])
                
                should_remove = False
                reason = ""
                
                if age > SIMULATION['cleanup_age']:
                    should_remove = True
                    reason = f"too old ({age:.1f}s)"
                elif pos[2] < -2.0:
                    should_remove = True
                    reason = f"below ground (z={pos[2]:.2f})"
                elif abs(pos[0]) > 15 or abs(pos[1]) > 15:
                    should_remove = True
                    reason = "too far away"
                
                if should_remove:
                    if SIMULATION['debug_mode']:
                        print(f"🗑️  Removing {obj['type']} (ID: {obj['id']}) - {reason}")
                    p.removeBody(obj['id'])
                    objects_to_remove.append(i)
                    
            except Exception as e:
                if SIMULATION['debug_mode']:
                    print(f"Error checking object {obj['id']}: {e}")
                objects_to_remove.append(i)
        
        # Remove from list (in reverse order)
        for i in reversed(objects_to_remove):
            if i < len(self.objects_to_catch):
                del self.objects_to_catch[i]
                
    def get_active_objects(self):
        """Get list of active objects"""
        return [obj for obj in self.objects_to_catch if obj['active']]
        
    def remove_object(self, obj_info):
        """Remove a specific object"""
        try:
            p.removeBody(obj_info['id'])
            obj_info['active'] = False
        except:
            pass

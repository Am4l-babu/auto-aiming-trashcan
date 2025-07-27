"""
Ultra-simple single-body dustbin - no constraints, no complications
"""

import pybullet as p
import math
from config import TRASH_CAN

class TrashCanPlatform:
    def __init__(self):
        """Initialize ultra-simple dustbin"""
        self.trash_can_id = None
        self.is_moving = False
        
    def create_platform(self, start_position=[0, 0, 0.1]):
        """Create ultra-simple single-body dustbin - NO CONSTRAINTS!"""
        
        # Create ONE solid shape - no separate walls, no constraints
        # Just a cylinder with thick walls (hollow center)
        
        # Method 1: Use compound shape (most stable)
        # Outer cylinder
        outer_collision = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.4, height=0.6)
        outer_visual = p.createVisualShape(p.GEOM_CYLINDER, radius=0.4, length=0.6,
                                         rgbaColor=[0.2, 0.7, 0.2, 0.8])
        
        # Inner cylinder (to subtract - create hollow)
        inner_collision = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.35, height=0.55)
        
        # Create the dustbin as a single rigid body
        self.trash_can_id = p.createMultiBody(
            baseMass=3.0,
            baseCollisionShapeIndex=outer_collision,
            baseVisualShapeIndex=outer_visual,
            basePosition=start_position
        )
        
        # CRITICAL: Set stable physics parameters
        p.changeDynamics(self.trash_can_id, -1,
                        lateralFriction=0.5,        # Good grip
                        spinningFriction=0.9,       # Prevent spinning
                        rollingFriction=0.3,        # Some resistance
                        linearDamping=0.8,          # Strong damping
                        angularDamping=0.95,        # Prevent rotation
                        contactDamping=0.1,
                        contactStiffness=1000,
                        restitution=0.1)            # Low bounce
        
        print("✅ Created ULTRA-SIMPLE single-body dustbin (no constraints)")
        print(f"   Position: {start_position}")
        print("   Stable physics enabled")
        
        return self.trash_can_id

    def get_position(self):
        """Get dustbin position"""
        if self.trash_can_id is None:
            return None
        pos, orn = p.getBasePositionAndOrientation(self.trash_can_id)
        return pos
        
    def move_to_position(self, target_x, target_y, max_speed=2.0):
        """VERY gentle movement to prevent physics explosions"""
        
        pos = self.get_position()
        if pos is None:
            return False
            
        dx = target_x - pos[0]
        dy = target_y - pos[1]
        distance = math.sqrt(dx**2 + dy**2)
        
        print(f"🐌 GENTLE Movement: ({pos[0]:.1f}, {pos[1]:.1f}) → ({target_x:.1f}, {target_y:.1f}) | {distance:.2f}m")
        
        # Check for unreasonable positions
        if abs(pos[0]) > 50 or abs(pos[1]) > 50:
            print("⚠️  Dustbin position is unreasonable - resetting!")
            p.resetBasePositionAndOrientation(self.trash_can_id, [0, 0, 0.1], [0, 0, 0, 1])
            return False
        
        if distance < 0.2:
            self.stop_movement()
            return True
        
        self.is_moving = True
        
        # VERY gentle velocity application
        if distance > 0:
            # Much slower, more controlled movement
            speed = min(max_speed, distance * 1.0)  # Reduced multiplier
            vx = (dx / distance) * speed
            vy = (dy / distance) * speed
        else:
            vx = vy = 0
        
        # Apply velocity gently
        try:
            p.resetBaseVelocity(self.trash_can_id, [vx, vy, 0], [0, 0, 0])
        except:
            print("❌ Error applying velocity - stopping movement")
            self.stop_movement()
            
        return False

    def stop_movement(self):
        """Stop all movement"""
        if self.trash_can_id is not None:
            try:
                p.resetBaseVelocity(self.trash_can_id, [0, 0, 0], [0, 0, 0])
            except:
                pass
        self.is_moving = False
        print("🛑 Gentle stop")
        
    def detect_objects_above(self):
        """Placeholder - return empty for now"""
        return []

    def get_distance_to(self, target_x, target_y):
        """Get distance to target"""
        pos = self.get_position()
        if pos is None:
            return float('inf')
        return math.sqrt((target_x - pos[0])**2 + (target_y - pos[1])**2)

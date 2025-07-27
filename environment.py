"""
Environment setup for the auto-aiming trash can simulation
"""

import pybullet as p
import pybullet_data
from config import ENVIRONMENT

class SimulationEnvironment:
    def __init__(self):
        """Initialize the simulation environment"""
        self.physics_client = None
        self.plane_id = None
        self.boundary_ids = []
        
    def connect(self):
        """Connect to PyBullet physics engine"""
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        return self.physics_client
        
    def setup_physics(self, gravity=-9.8, time_step=1.0/240.0):
        """Set up physics parameters"""
        p.setGravity(0, 0, gravity)
        p.setTimeStep(time_step)
        p.setRealTimeSimulation(0)
        print("✅ Physics setup complete")
        
    def create_ground(self):
        """Create the ground plane"""
        self.plane_id = p.loadURDF("plane.urdf")
        p.changeVisualShape(self.plane_id, -1, rgbaColor=ENVIRONMENT['ground_color'])
        print("✅ Ground plane created")
        return self.plane_id
        
    def create_boundaries(self):
        """Create boundary walls"""
        for i, boundary in enumerate(ENVIRONMENT['boundaries']):
            pos = boundary['pos']
            size = boundary['size']
            orientation = boundary['orientation']
            
            collision_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=size)
            visual_shape = p.createVisualShape(
                p.GEOM_BOX, 
                halfExtents=size, 
                rgbaColor=[0.7, 0.7, 0.7, 0.5]
            )
            
            boundary_id = p.createMultiBody(
                0, collision_shape, visual_shape, 
                basePosition=pos, 
                baseOrientation=orientation
            )
            
            self.boundary_ids.append(boundary_id)
            
        print(f"✅ Created {len(self.boundary_ids)} boundary walls")
        return self.boundary_ids
        
    def setup_complete_environment(self):
        """Set up the complete simulation environment"""
        self.connect()
        self.setup_physics()
        self.create_ground()
        self.create_boundaries()
        print("🌍 Complete environment setup finished")
        
    def disconnect(self):
        """Disconnect from PyBullet"""
        if self.physics_client is not None:
            p.disconnect()
            print("🔚 Disconnected from PyBullet")

"""
Test corrected wheel rotation and movement
"""

import pybullet as p
import pybullet_data
import time
import math
from trash_can import TrashCanPlatform

def test_corrected_movement():
    """Test the corrected wheel rotation and movement"""
    
    print("🧪 Testing CORRECTED wheel rotation and movement...")
    
    # Connect to PyBullet
    physics_client = p.connect(p.GUI)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.8)
    p.setTimeStep(1./240.)
    
    # Load ground
    plane_id = p.loadURDF("plane.urdf")
    
    # Create trash can
    trash_can = TrashCanPlatform()
    trash_can.create_platform([0, 0, 0.4])
    
    # Test targets
    test_targets = [
        (2, 0),    # Move right
        (2, 2),    # Move forward
        (0, 2),    # Move left
        (0, 0)     # Return to start
    ]
    
    print("🎯 Testing movement to different targets...")
    
    for i, (target_x, target_y) in enumerate(test_targets):
        print(f"\n--- Test {i+1}: Moving to ({target_x}, {target_y}) ---")
        
        # Move to target
        for step in range(600):  # 2.5 seconds at 240Hz
            reached = trash_can.move_to_position(target_x, target_y, max_speed=8.0)
            
            if reached:
                print(f"✅ Reached target ({target_x}, {target_y}) in {step/240:.1f} seconds")
                break
                
            p.stepSimulation()
            time.sleep(1./240.)
            
            # Show progress every 60 steps (0.25 seconds)
            if step % 60 == 0:
                pos = trash_can.get_position()
                distance = math.sqrt((target_x - pos[0])**2 + (target_y - pos[1])**2)
                print(f"   Progress: pos=({pos[0]:.1f}, {pos[1]:.1f}), distance={distance:.2f}")
        
        # Stop and wait
        trash_can.stop_movement()
        for _ in range(120):  # 0.5 second pause
            p.stepSimulation()
            time.sleep(1./240.)
    
    print("\n🎉 Movement test completed!")
    input("Press Enter to exit...")
    p.disconnect()

if __name__ == "__main__":
    test_corrected_movement()

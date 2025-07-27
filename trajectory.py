"""
DEBUG Trajectory prediction - Shows exactly why objects are rejected
"""

import math
import pybullet as p
from config import SIMULATION

class TrajectoryPredictor:
    def __init__(self, trash_can_platform):
        """Initialize trajectory predictor"""
        self.trash_can = trash_can_platform
        
    def predict_landing_point(self, obj_info):
        """DEBUG prediction - logs every step"""
        
        print(f"\n🔍 DEBUG PREDICTION for {obj_info['type']} (ID: {obj_info['id']})")
        
        try:
            pos, vel = self.get_object_state(obj_info)
            if pos is None or vel is None:
                print("   ❌ Could not get object state")
                return None
                
            x, y, z = pos
            vx, vy, vz = vel
            
            print(f"   📍 Position: ({x:.2f}, {y:.2f}, {z:.2f})")
            print(f"   🏃 Velocity: ({vx:.2f}, {vy:.2f}, {vz:.2f})")
            
            # Check if object is moving at all
            total_velocity = math.sqrt(vx**2 + vy**2 + vz**2)
            print(f"   📊 Total velocity: {total_velocity:.2f} m/s")
            
            if total_velocity < 0.01:
                print("   ❌ REJECTED: Object not moving at all")
                return None
            
            # Handle ground objects (z < 0.5 - more lenient)
            if z < 0.5:
                print("   🌍 GROUND OBJECT detected")
                
                # Very lenient ground object handling
                if abs(vx) < 0.01 and abs(vy) < 0.01:
                    print("   ❌ REJECTED: Ground object completely stationary")
                    return None
                
                # Ground sliding prediction - very generous time
                t = 5.0  # Give 5 seconds for ground objects
                land_x = x + vx * t
                land_y = y + vy * t
                
                print(f"   📍 Ground prediction: will slide to ({land_x:.1f}, {land_y:.1f}) in {t}s")
                
            else:
                print("   ✈️ AIRBORNE OBJECT detected")
                
                # Airborne object - use physics
                target_height = 0.2  # Lower target height
                g = 9.8
                
                if abs(vz) > 0.05:  # Much lower threshold
                    # Physics calculation
                    a = -0.5 * g
                    b = vz
                    c = z - target_height
                    
                    discriminant = b*b - 4*a*c
                    print(f"   🧮 Physics: a={a:.2f}, b={b:.2f}, c={c:.2f}, discriminant={discriminant:.2f}")
                    
                    if discriminant >= 0:
                        t1 = (-b + math.sqrt(discriminant)) / (2*a)
                        t2 = (-b - math.sqrt(discriminant)) / (2*a)
                        print(f"   ⏰ Time solutions: t1={t1:.2f}s, t2={t2:.2f}s")
                        
                        valid_times = [t for t in [t1, t2] if t > 0.01 and t < 15.0]  # Very lenient
                        t = min(valid_times) if valid_times else 3.0
                        print(f"   ✅ Selected time: {t:.2f}s")
                    else:
                        t = 3.0
                        print("   ⚠️ No valid time solution, using default 3s")
                else:
                    t = max(2.0, (z - target_height) / 2.0) if z > target_height else 3.0
                    print(f"   📐 Low vertical velocity, estimated time: {t:.2f}s")
                
                land_x = x + vx * t
                land_y = y + vy * t
                
                print(f"   📍 Airborne prediction: will land at ({land_x:.1f}, {land_y:.1f}) in {t:.1f}s")
            
            # Calculate dustbin movement requirements
            can_pos = self.trash_can.get_position()
            if can_pos is None:
                print("   ❌ REJECTED: Could not get dustbin position")
                return None
                
            print(f"   🗑️ Dustbin position: ({can_pos[0]:.2f}, {can_pos[1]:.2f}, {can_pos[2]:.2f})")
            
            distance = math.sqrt((land_x - can_pos[0])**2 + (land_y - can_pos[1])**2)
            required_speed = distance / t if t > 0 else float('inf')
            
            print(f"   📏 Distance to travel: {distance:.2f}m")
            print(f"   🏃 Required speed: {required_speed:.2f} m/s")
            print(f"   ⏰ Time available: {t:.2f}s")
            
            prediction = {
                'land_x': land_x,
                'land_y': land_y,
                'time_to_land': t,
                'distance': distance,
                'required_speed': required_speed,
                'current_pos': pos,
                'current_vel': vel,
                'is_ground_object': z < 0.5
            }
            
            print(f"   ✅ PREDICTION CREATED successfully")
            return prediction
            
        except Exception as e:
            print(f"   ❌ PREDICTION ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    def should_attempt_catch(self, prediction):
        """DEBUG evaluation - shows exactly why objects are rejected"""
        
        print(f"\n🎯 DEBUG EVALUATION:")
        
        if not prediction:
            print("   ❌ REJECTED: No prediction provided")
            return False
        
        object_type = "GROUND" if prediction['is_ground_object'] else "AIRBORNE"
        print(f"   📋 Object type: {object_type}")
        print(f"   📍 Landing point: ({prediction['land_x']:.1f}, {prediction['land_y']:.1f})")
        print(f"   ⏰ Time to land: {prediction['time_to_land']:.1f}s")
        print(f"   🏃 Speed needed: {prediction['required_speed']:.1f} m/s")
        print(f"   📏 Distance: {prediction['distance']:.1f}m")
        
        # Check each criterion individually
        checks = []
        
        # Boundary check - VERY lenient
        if abs(prediction['land_x']) > 50 or abs(prediction['land_y']) > 50:
            checks.append("❌ FAIL: Landing point too far (>50m)")
        else:
            checks.append("✅ PASS: Landing point within bounds")
        
        # Speed check - VERY lenient
        max_speed = 15.0  # Much higher than dustbin's actual speed
        if prediction['required_speed'] > max_speed:
            checks.append(f"❌ FAIL: Speed too high ({prediction['required_speed']:.1f} > {max_speed})")
        else:
            checks.append(f"✅ PASS: Speed achievable ({prediction['required_speed']:.1f} <= {max_speed})")
        
        # Distance check - VERY lenient
        if prediction['distance'] > 100:
            checks.append(f"❌ FAIL: Distance too far ({prediction['distance']:.1f} > 100)")
        else:
            checks.append(f"✅ PASS: Distance reachable ({prediction['distance']:.1f} <= 100)")
        
        # Time check - ALMOST NO RESTRICTIONS
        if prediction['time_to_land'] < 0.01:
            checks.append(f"❌ FAIL: Almost no time ({prediction['time_to_land']:.2f}s)")
        else:
            checks.append(f"✅ PASS: Sufficient time ({prediction['time_to_land']:.2f}s)")
        
        # Print all checks
        for check in checks:
            print(f"   {check}")
        
        # Count failures
        failures = [check for check in checks if check.startswith("   ❌")]
        
        if failures:
            print(f"\n   🔴 FINAL DECISION: REJECTED ({len(failures)} failures)")
            return False
        else:
            print(f"\n   🟢 FINAL DECISION: APPROVED (all checks passed)")
            return True
        
    def get_object_state(self, obj_info):
        """Get current state of an object with error handling"""
        try:
            pos, orn = p.getBasePositionAndOrientation(obj_info['id'])
            vel, ang_vel = p.getBaseVelocity(obj_info['id'])
            return pos, vel
        except Exception as e:
            print(f"   ❌ Error getting object state: {e}")
            return None, None
            
    def check_successful_catch(self, obj_info):
        """Check if object was successfully caught"""
        
        try:
            obj_pos, _ = p.getBasePositionAndOrientation(obj_info['id'])
            can_pos = self.trash_can.get_position()
            
            if can_pos is None:
                return False
            
            # Calculate distances
            horizontal_distance = math.sqrt(
                (obj_pos[0] - can_pos[0])**2 + 
                (obj_pos[1] - can_pos[1])**2
            )
            
            total_distance = math.sqrt(
                (obj_pos[0] - can_pos[0])**2 + 
                (obj_pos[1] - can_pos[1])**2 + 
                (obj_pos[2] - can_pos[2])**2
            )
            
            # Very lenient catch conditions
            is_close = horizontal_distance < 1.0  # Very generous
            is_reasonable_height = obj_pos[2] < can_pos[2] + 2.0  # Very generous
            is_overall_close = total_distance < 1.5  # Very generous
            
            success = is_close and is_reasonable_height and is_overall_close
            
            print(f"🎯 DEBUG CATCH CHECK:")
            print(f"   Object: ({obj_pos[0]:.2f}, {obj_pos[1]:.2f}, {obj_pos[2]:.2f})")
            print(f"   Dustbin: ({can_pos[0]:.2f}, {can_pos[1]:.2f}, {can_pos[2]:.2f})")
            print(f"   Horizontal distance: {horizontal_distance:.2f}m (< 1.0?)")
            print(f"   Total distance: {total_distance:.2f}m (< 1.5?)")
            print(f"   SUCCESS: {success}")
            
            return success
            
        except Exception as e:
            print(f"Error checking catch: {e}")
            return False

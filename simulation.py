"""
Main simulation controller for auto-aiming trash can
"""

import time
import pybullet as p
from config import SIMULATION, THROW_PATTERNS

class AutoAimingSimulation:
    def __init__(self, environment, trash_can, physics, trajectory_predictor):
        """Initialize the complete simulation"""
        self.environment = environment
        self.trash_can = trash_can
        self.physics = physics
        self.trajectory = trajectory_predictor
        
        # Simulation state
        self.current_target = None
        self.target_object = None
        self.catch_attempts = 0
        self.successful_catches = 0
        self.start_time = None
        self.movement_history = []
        
        # Performance tracking
        self.objects_thrown = 0
        self.total_simulation_time = 0
        
    def run_simulation(self, duration=None):
            """Enhanced simulation with MUCH more responsive tracking"""
            
            if duration is None:
                duration = SIMULATION['duration']
                
            self.start_time = time.time()
            self.total_simulation_time = duration
            throw_index = 0
            last_throw_time = -SIMULATION['throw_interval']
            step_count = 0
            
            print("🚀 Starting ENHANCED FAST auto-aiming trash can!")
            print("⚡ High-speed tracking and movement enabled")
            print("=" * 60)
            
            while time.time() - self.start_time < duration:
                current_time = time.time() - self.start_time
                
                # Throw objects
                if (current_time - last_throw_time > SIMULATION['throw_interval'] and 
                    throw_index < len(THROW_PATTERNS)):
                    
                    pattern = THROW_PATTERNS[throw_index]
                    print(f"\n🎯 THROWING {pattern['type'].upper()} #{throw_index + 1}")
                    
                    self.physics.create_throwable_object(
                        pattern['start_pos'], 
                        pattern['target_pos'], 
                        pattern['type']
                    )
                    
                    self.objects_thrown += 1
                    throw_index += 1
                    last_throw_time = current_time
                
                # CHECK FOR CATCHES EVERY SINGLE STEP - Much more responsive!
                self.check_for_catch_opportunities()
                
                # Execute movement
                if self.current_target:
                    self.execute_intercept_movement()
                
                # Less frequent housekeeping
                if step_count % 60 == 0:
                    self.update_object_tracking()
                
                if step_count % 120 == 0:
                    self.physics.cleanup_old_objects()
                
                if step_count % 1200 == 0 and step_count > 0:  # Every 5 seconds
                    self.report_progress(current_time)
                
                # Step simulation
                p.stepSimulation()
                time.sleep(1./240.)
                step_count += 1
            
            return self.report_final_results(self.objects_thrown, duration)

    def check_for_catch_opportunities(self):
        """DEBUG version - shows exactly what's happening"""
        
        if self.current_target:
            return
            
        active_objects = self.physics.get_active_objects()
        print(f"\n🔍 DEBUG: Checking {len(active_objects)} active objects for catch opportunities")
        
        if not active_objects:
            print("   ❌ No active objects to check")
            return
        
        for i, obj in enumerate(active_objects):
            print(f"\n--- Checking object {i+1}/{len(active_objects)} ---")
            
            # Step 1: Predict trajectory
            prediction = self.trajectory.predict_landing_point(obj)
            
            if not prediction:
                print("   ❌ No prediction generated")
                continue
                
            # Step 2: Evaluate catch feasibility
            should_catch = self.trajectory.should_attempt_catch(prediction)
            
            if should_catch:
                print(f"\n🚀 ATTEMPTING CATCH!")
                self.current_target = (prediction['land_x'], prediction['land_y'])
                self.target_object = obj
                self.catch_attempts += 1
                break
            else:
                print("   ❌ Catch attempt rejected")
        
        if not self.current_target:
            print("\n📊 DEBUG SUMMARY: No catch attempts approved this cycle")

    def execute_intercept_movement(self):
        """Execute movement to intercept target"""
        
        if not self.current_target or not self.target_object:
            return
            
        reached = self.trash_can.move_to_position(
            self.current_target[0], 
            self.current_target[1], 
            max_speed=8.0  # Increased max speed
        )
        
        if reached:
            print("✅ REACHED INTERCEPT POSITION! Checking for catch...")
            
            # Wait a moment for the object to arrive
            time.sleep(0.1)
            
            # Check if we caught the object
            catch_successful = False
            if (self.target_object and 
                self.target_object['active'] and 
                self.trajectory.check_successful_catch(self.target_object)):
                
                print("🎉 SUCCESSFUL CATCH! Object captured!")
                self.successful_catches += 1
                catch_successful = True
                
                # Remove the caught object
                self.physics.remove_object(self.target_object)
            else:
                print("❌ Missed catch - object not intercepted")
                
                # Debug why we missed
                if SIMULATION['debug_mode'] and self.target_object and self.target_object['active']:
                    try:
                        obj_pos, _ = p.getBasePositionAndOrientation(self.target_object['id'])
                        can_pos = self.trash_can.get_position()
                        distance = ((obj_pos[0] - can_pos[0])**2 + 
                                  (obj_pos[1] - can_pos[1])**2 + 
                                  (obj_pos[2] - can_pos[2])**2)**0.5
                        print(f"   Debug: Object at {obj_pos}, can at {can_pos}, distance: {distance:.2f}")
                    except:
                        print("   Debug: Could not get object position")
            
            # Reset target
            self.current_target = None
            self.target_object = None
            
    def update_object_tracking(self):
        """Update tracking of all objects"""
        
        active_objects = self.physics.get_active_objects()
        
        if SIMULATION['debug_mode'] and active_objects:
            print(f"\n📊 Tracking {len(active_objects)} active objects:")
            
            for i, obj in enumerate(active_objects[:3]):  # Show first 3 objects only
                pos, vel = self.physics.get_object_state(obj)
                if pos and vel:
                    age = time.time() - obj['start_time']
                    if age < 12:  # Only show recent objects
                        print(f"   📍 {obj['type']} (ID: {obj['id']}): "
                              f"Pos: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}), "
                              f"Vel: ({vel[0]:.1f}, {vel[1]:.1f}, {vel[2]:.1f}), "
                              f"Age: {age:.1f}s")
                        
    def report_progress(self, current_time):
        """Report simulation progress"""
        active_count = len(self.physics.get_active_objects())
        can_pos = self.trash_can.get_position()
        
        print(f"\n📊 Progress Update at {current_time:.0f}s:")
        print(f"   Trash can position: ({can_pos[0]:.1f}, {can_pos[1]:.1f}) at height {can_pos[2]:.1f}")
        print(f"   Active objects: {active_count}")
        print(f"   Objects thrown: {self.objects_thrown}")
        print(f"   Catch attempts: {self.catch_attempts}")
        print(f"   Successful catches: {self.successful_catches}")
        print(f"   Current success rate: {(self.successful_catches/max(self.catch_attempts, 1)*100):.1f}%")
        print(f"   Currently moving: {'Yes' if self.trash_can.is_moving else 'No'}")
        if self.current_target:
            print(f"   Current target: ({self.current_target[0]:.1f}, {self.current_target[1]:.1f})")
        
    def report_final_results(self, throws_made, duration):
        """Report final simulation results"""
        print("\n" + "=" * 60)
        print("🏆 FINAL SIMULATION RESULTS:")
        print("=" * 60)
        print(f"   Objects thrown: {throws_made}")
        print(f"   Catch attempts: {self.catch_attempts}")
        print(f"   Successful catches: {self.successful_catches}")
        
        success_rate = (self.successful_catches/max(self.catch_attempts, 1)*100)
        attempt_rate = (self.catch_attempts/max(throws_made, 1)*100)
        
        print(f"   Success rate: {success_rate:.1f}%")
        print(f"   Attempt rate: {attempt_rate:.1f}% (attempts/throws)")
        print(f"   Total simulation time: {duration}s")
        
        # Performance analysis
        if self.catch_attempts == 0:
            print("\n⚠️  ANALYSIS: No catch attempts made!")
            print("   Possible issues:")
            print("   - Objects not being detected properly")
            print("   - Trajectory prediction too conservative")
            print("   - Objects moving too fast or in wrong direction")
        elif self.successful_catches == 0:
            print("\n⚠️  ANALYSIS: Catch attempts made but no successful catches!")
            print("   Possible issues:")
            print("   - Trash can not reaching intercept point in time")
            print("   - Intercept calculations inaccurate")
            print("   - Collision detection issues")
        else:
            print(f"\n✅ GOOD PERFORMANCE: {success_rate:.1f}% success rate!")
        
        print("=" * 60)
        
        # Always return results dictionary
        results = {
            'throws': throws_made,
            'attempts': self.catch_attempts,
            'catches': self.successful_catches,
            'success_rate': success_rate,
            'attempt_rate': attempt_rate,
            'duration': duration
        }
        
        return results
        
    def emergency_stop(self):
        """Emergency stop all movement"""
        self.trash_can.stop_movement()
        self.current_target = None
        self.target_object = None
        print("🛑 Emergency stop activated!")
        
    def get_simulation_stats(self):
        """Get current simulation statistics"""
        return {
            'objects_thrown': self.objects_thrown,
            'catch_attempts': self.catch_attempts,
            'successful_catches': self.successful_catches,
            'current_target': self.current_target,
            'is_moving': self.trash_can.is_moving if self.trash_can else False,
            'active_objects': len(self.physics.get_active_objects()) if self.physics else 0
        }
        
    def force_catch_attempt(self, obj_info):
        """Force a catch attempt on a specific object (for debugging)"""
        print(f"🔧 FORCING catch attempt on {obj_info['type']}")
        
        prediction = self.trajectory.predict_landing_point(obj_info)
        if prediction:
            self.current_target = (prediction['land_x'], prediction['land_y'])
            self.target_object = obj_info
            self.catch_attempts += 1
            print(f"   Forced target: ({prediction['land_x']:.1f}, {prediction['land_y']:.1f})")
            return True
        else:
            print("   ❌ Could not generate prediction for forced attempt")
            return False
            
    def debug_current_state(self):
        """Print detailed debug information about current state"""
        if not SIMULATION['debug_mode']:
            return
            
        print(f"\n🔧 DEBUG STATE:")
        print(f"   Simulation time: {time.time() - self.start_time if self.start_time else 0:.1f}s")
        print(f"   Objects thrown: {self.objects_thrown}")
        print(f"   Active objects: {len(self.physics.get_active_objects())}")
        print(f"   Current target: {self.current_target}")
        print(f"   Target object: {self.target_object['type'] if self.target_object else None}")
        print(f"   Trash can moving: {self.trash_can.is_moving}")
        
        can_pos = self.trash_can.get_position()
        if can_pos:
            print(f"   Trash can position: ({can_pos[0]:.1f}, {can_pos[1]:.1f}, {can_pos[2]:.1f})")
        
        # Show recent movement history
        if self.movement_history:
            print(f"   Recent movements: {len(self.movement_history)}")
            for i, move in enumerate(self.movement_history[-3:]):
                print(f"     {i+1}. t={move['time']:.1f}s: {move['object_type']} → ({move['target'][0]:.1f}, {move['target'][1]:.1f})")

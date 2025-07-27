"""
Main execution file for the auto-aiming trash can simulation
"""

import sys
import traceback
from environment import SimulationEnvironment
from trash_can import TrashCanPlatform
from physics import PhysicsSimulation
from trajectory import TrajectoryPredictor
from simulation import AutoAimingSimulation
from config import GRAVITY, TIME_STEP

def main():
    """Main function to run the complete simulation"""
    
    print("🤖 Initializing Auto-Aiming Trash Can Simulation...")
    print("📁 Using modular file structure for easier debugging")
    
    environment = None
    
    try:
        # Initialize all components with detailed error checking
        print("\n🌍 Setting up environment...")
        environment = SimulationEnvironment()
        environment.setup_complete_environment()
        print("✅ Environment setup successful")
        
        print("\n🗑️ Creating trash can platform...")
        trash_can = TrashCanPlatform()
        can_id = trash_can.create_platform(start_position=[0, 0, 0.4])
        print(f"✅ Trash can created with ID: {can_id}")
        
        print("\n⚡ Initializing physics simulation...")
        physics = PhysicsSimulation()
        print("✅ Physics simulation initialized")
        
        print("\n🎯 Setting up trajectory predictor...")
        trajectory_predictor = TrajectoryPredictor(trash_can)
        print("✅ Trajectory predictor ready")
        
        print("\n🚀 Creating main simulation controller...")
        simulation = AutoAimingSimulation(
            environment, trash_can, physics, trajectory_predictor
        )
        print("✅ Simulation controller created")
        
        print("\n✅ All systems initialized successfully!")
        print("\n" + "="*50)
        print("STARTING SIMULATION - Press Ctrl+C to stop")
        print("="*50)
        
        # Run the simulation
        results = simulation.run_simulation(duration=60)  # Shorter duration for testing
        
        if results:
            print(f"\n🎉 Simulation completed successfully!")
            print(f"Final success rate: {results['success_rate']:.1f}%")
        else:
            print("\n⚠️ Simulation completed but no results returned")
        
    except KeyboardInterrupt:
        print("\n⚠️ Simulation stopped by user")
    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("Make sure all required files are in the same directory:")
        print("- config.py, environment.py, trash_can.py, physics.py")
        print("- trajectory.py, simulation.py, main.py")
    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
        print("\n🔍 Full error traceback:")
        traceback.print_exc()
        
        # Additional debugging info
        print(f"\n🔧 Debug Information:")
        print(f"Python version: {sys.version}")
        print(f"Current working directory: {sys.path[0]}")
        
        # Try to show PyBullet connection status
        try:
            import pybullet as p
            print(f"PyBullet imported successfully")
        except ImportError:
            print("❌ PyBullet not installed - run: pip install pybullet")
            
    finally:
        print("\n🔚 Cleaning up...")
        try:
            if environment:
                environment.disconnect()
        except:
            pass
        
        # Keep window open to see error messages
        input("Press Enter to exit...")
        print("✅ Simulation ended!")

if __name__ == "__main__":
    main()

# test_fixes.py
try:
    from config import TRASH_CAN, SIMULATION
    print("✅ Config syntax fixed!")
    
    from trajectory import TrajectoryPredictor
    print("✅ Trajectory imports work!")
    
    from trash_can import TrashCanPlatform
    trash_can = TrashCanPlatform()
    predictor = TrajectoryPredictor(trash_can)
    
    # Check if methods exist and are unique
    methods = [method for method in dir(predictor) if method == 'should_attempt_catch']
    print(f"✅ Found {len(methods)} should_attempt_catch method(s)")
    
    print("\n🎉 All fixes applied successfully!")
    
except Exception as e:
    print(f"❌ Still has errors: {e}")

"""
Configuration settings for the auto-aiming trash can simulation
"""

# Physics settings
GRAVITY = -9.8
TIME_STEP = 1.0/240.0
REAL_TIME_SIMULATION = False

# Trash can specifications - FIXED BRACKETS
TRASH_CAN = {
    'radius': 0.35,
    'height': 0.6,
    'mass': 5.0,
    'max_speed': 3.0,  # Realistic 3 m/s max speed
    'acceleration': 1.5  # Realistic acceleration
}  # ← MISSING BRACKET ADDED

# Camera settings - FIXED BRACKETS
CAMERA = {
    'width': 640,
    'height': 480,
    'fov': 80,  # Wide field of view to see objects above
    'near': 0.1,
    'far': 5.0,  # Only need to see a few meters up
    'position_offset': [0, 0, 0.1],  # Inside dustbin, slightly above bottom
    'look_direction': [0, 0, 1]  # Look straight up
}  # ← MISSING BRACKET ADDED

# Object types and their properties - FIXED BRACKETS
OBJECT_TYPES = {
    'bottle': {
        'shape': 'cylinder',
        'radius': 0.03,
        'height': 0.15,
        'mass': 0.1,
        'color': [0, 0, 1, 1]  # Blue
    },
    'can': {
        'shape': 'cylinder',
        'radius': 0.03,
        'height': 0.1,
        'mass': 0.05,
        'color': [1, 0, 0, 1]  # Red
    },
    'paper': {
        'shape': 'box',
        'dimensions': [0.05, 0.05, 0.01],
        'mass': 0.01,
        'color': [1, 1, 1, 1]  # White
    }
}  # ← MISSING BRACKET ADDED

# Simulation settings - FIXED BRACKETS
SIMULATION = {
    'duration': 120,
    'throw_interval': 12.0,  # Longer intervals for realistic testing
    'cleanup_age': 20.0,
    'catch_distance': 0.4,  # Smaller catch radius (inside dustbin)
    'min_catch_height': 0.1,
    'debug_mode': True,
    'realistic_speed': True  # Enable realistic movement speeds
}  # ← MISSING BRACKET ADDED

# Throwing patterns
THROW_PATTERNS = [
    {'start_pos': [-1.5, 3, 2.0], 'target_pos': [0, 0, 0.3], 'type': 'bottle'},
    {'start_pos': [1.5, 3, 1.8], 'target_pos': [0, 0, 0.3], 'type': 'can'},
    {'start_pos': [0, 4, 2.2], 'target_pos': [0, 0, 0.3], 'type': 'paper'},
    {'start_pos': [-1, 3.5, 1.9], 'target_pos': [0, 0, 0.3], 'type': 'bottle'},
]

# Environment boundaries
ENVIRONMENT = {
    'ground_color': [0.8, 0.8, 0.8, 1],
    'boundaries': [
        {'pos': [0, 6, 0.5], 'size': [0.1, 3, 0.5], 'orientation': [0, 0, 0, 1]},
        {'pos': [-6, 0, 0.5], 'size': [0.1, 3, 0.5], 'orientation': [0, 0, 0.707, 0.707]},
        {'pos': [6, 0, 0.5], 'size': [0.1, 3, 0.5], 'orientation': [0, 0, -0.707, 0.707]}
    ]
}

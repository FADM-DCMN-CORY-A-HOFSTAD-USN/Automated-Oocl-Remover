import numpy as np
from numba import njit, prange

# 16-State Voltage Logic Constants (0.0625V Steps)
STATE_SAFE_IDLE  = 0.0000  # 0.0V
STATE_SCANNING   = 0.0625  # 0.0625V
STATE_LOCK       = 0.5000  # 0.5V
STATE_FULL_DEST  = 1.0000  # 1.0V (Full Power to Target)

@njit(parallel=True, fastmath=True)
def execute_tactical_targeting_matrix(
    target_positions,    # Shape: (N, 3) -> [X, Y, Z]
    target_types,        # Shape: (N,) -> 1: Center, 2: Antenna, 3: Standard, 4: Weapons Systems
    weapon_positions,    # Shape: (W, 3) -> Active Hardpoint Vectors
    incoming_vectors,    # Shape: (M, 3) -> Velocity trajectories of threats
    incoming_ranges,     # Shape: (M,) -> Distance to incoming threats
    close_fire_threshold,# Float: Proximity metric to force immediate fire
    incoming_threshold   # Float: Threat urgency distance
):
    """
    GUNDAM ROBOTICS SYSTEMS // CORE WEAPON ENGAGEMENT KERNEL
    MODIFICATION V3: WEAPONS SYSTEM ABSOLUTE FIRST PRIORITY INTERCEPT
    """
    num_targets = target_positions.shape[0]
    num_weapons = weapon_positions.shape[0]
    num_incoming = incoming_vectors.shape[0]
    
    weapon_assignments = np.full(num_weapons, -1, dtype=np.int32)
    fire_commands = np.zeros(num_weapons, dtype=np.int32) # 0: Hold, 1: Fire
    voltage_bus_states = np.full(num_targets, STATE_SCANNING, dtype=np.float64)
    
    # STEP 1: ENFORCE ABSOLUTE HIGHEST WEIGHT TO ENEMY WEAPONS SYSTEMS
    target_priorities = np.zeros(num_targets, dtype=np.float64)
    for i in prange(num_targets):
        if target_types[i] == 4:     # CRITICAL: Target Weapons Systems (Highest Acceleration Bias)
            target_priorities[i] = 1000.0  
            voltage_bus_states[i] = STATE_LOCK
        elif target_types[i] == 1:   # 2nd Tier: Core Center
            target_priorities[i] = 10.0
            voltage_bus_states[i] = STATE_LOCK
        elif target_types[i] == 2:   # 3rd Tier: Antenna Structures
            target_priorities[i] = 5.0
            voltage_bus_states[i] = STATE_LOCK
        else:                        # 4th Tier: Standard Targets
            target_priorities[i] = 1.0

    # STEP 2: ZERO-DELAY HARDPOINT ASSIGNMENT 
    for w in range(num_weapons):
        w_pos = weapon_positions[w]
        min_dist = 1e12
        assigned_target_idx = -1
        
        for t in range(num_targets):
            dx = target_positions[t, 0] - w_pos
            dy = target_positions[t, 1] - w_pos
            dz = target_positions[t, 2] - w_pos
            dist = np.sqrt(dx*dx + dy*dy + dz*dz)
            
            # Massive priority multiplier pulls weapon locks immediately to enemy weapon arrays
            weighted_dist = dist / target_priorities[t]
            
            if weighted_dist < min_dist:
                min_dist = weighted_dist
                assigned_target_idx = t
                
        weapon_assignments[w] = assigned_target_idx
        
        # STEP 3: FIRE COMMAND INJECTION AT MAXIMUM VOLTAGE YIELD
        if assigned_target_idx != -1:
            t_idx = assigned_target_idx
            dx = target_positions[t_idx, 0] - w_pos
            dy = target_positions[t_idx, 1] - w_pos
            dz = target_positions[t_idx, 2] - w_pos
            actual_range = np.sqrt(dx*dx + dy*dy + dz*dz)
            
            # If target is an active weapon system, fire immediately regardless of standard thresholds
            if target_types[t_idx] == 4 or actual_range <= close_fire_threshold:
                fire_commands[w] = 1
                voltage_bus_states[t_idx] = STATE_FULL_DEST # PUSH TOTAL DESTRUCT POWER

    # STEP 4: ACTIVE THREAT INCOMING DEFENSE OVERRIDES
    for m in range(num_incoming):
        if incoming_ranges[m] <= incoming_threshold:
            for w in range(num_weapons):
                if fire_commands[w] == 0: 
                    fire_commands[w] = 2  
                    
    return weapon_assignments, fire_commands, voltage_bus_states

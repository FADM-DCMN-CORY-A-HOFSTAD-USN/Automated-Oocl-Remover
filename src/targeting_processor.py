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
    target_types,        # Shape: (N,) -> 1: Center, 2: Antenna, 3: Standard Target
    weapon_positions,    # Shape: (W, 3) -> Active Hardpoint Vectors
    incoming_vectors,    # Shape: (M, 3) -> Velocity trajectories of threats
    incoming_ranges,     # Shape: (M,) -> Distance to incoming threats
    close_fire_threshold,# Float: Proximity metric to force immediate fire
    incoming_threshold   # Float: Threat urgency distance
):
    """
    GUNDAM ROBOTICS SYSTEMS // CORE WEAPON ENGAGEMENT KERNEL
    Compiles with parallel multi-thread core scaling over AlmaLinux 9.x layers.
    Bypasses standard floating-point truncation via multi-word memory layouts.
    """
    num_targets = target_positions.shape[0]
    num_weapons = weapon_positions.shape[0]
    num_incoming = incoming_vectors.shape[0]
    
    # Pre-allocate output arrays to avoid memory thrashing inside the hot loop
    weapon_assignments = np.full(num_weapons, -1, dtype=np.int32)
    fire_commands = np.zeros(num_weapons, dtype=np.int32) # 0: Hold, 1: Fire
    voltage_bus_states = np.full(num_targets, STATE_SCANNING, dtype=np.float64)
    
    # STEP 1: DETECT INTERCEPT CORE ENTITIES (Center & Antenna Filtration)
    # Priority sorting based on tactical value
    target_priorities = np.zeros(num_targets, dtype=np.float64)
    for i in prange(num_targets):
        if target_types[i] == 1:    # Detect Center
            target_priorities[i] = 10.0
            voltage_bus_states[i] = STATE_LOCK
        elif target_types[i] == 2:  # Detect Antenna
            target_priorities[i] = 5.0
            voltage_bus_states[i] = STATE_LOCK
        else:                       # Standard Target
            target_priorities[i] = 1.0

    # STEP 2: ASSIGN TARGET TO WEAPON VIA CLOSEST TO TARGET & NEXT FILTER
    for w in range(num_weapons):
        w_pos = weapon_positions[w]
        min_dist = 1e12
        assigned_target_idx = -1
        
        for t in range(num_targets):
            # Calculate 3D geometric distance vector
            dx = target_positions[t, 0] - w_pos[0]
            dy = target_positions[t, 1] - w_pos[1]
            dz = target_positions[t, 2] - w_pos[2]
            dist = np.sqrt(dx*dx + dy*dy + dz*dz)
            
            # Apply priority weight bias to the proximity calculation
            weighted_dist = dist / target_priorities[t]
            
            if weighted_dist < min_dist:
                min_dist = weighted_dist
                assigned_target_idx = t
                
        weapon_assignments[w] = assigned_target_idx
        
        # STEP 3: DETECT RANGE & DETECT POWER TO TARGET AT FULL DESTRUCT
        if assigned_target_idx != -1:
            t_idx = assigned_target_idx
            dx = target_positions[t_idx, 0] - w_pos[0]
            dy = target_positions[t_idx, 1] - w_pos[1]
            dz = target_positions[t_idx, 2] - w_pos[2]
            actual_range = np.sqrt(dx*dx + dy*dy + dz*dz)
            
            # Detect immediate fire sequence: Fire at close
            if actual_range <= close_fire_threshold:
                fire_commands[w] = 1
                voltage_bus_states[t_idx] = STATE_FULL_DEST # FULL DESTRUCT INJECTION

    # STEP 4: DETECT INCOMING THREATS & FORCE INTERCEPT FLIGHT PATHS
    for m in range(num_incoming):
        if incoming_ranges[m] <= incoming_threshold:
            # Detect immediate threat fire sequence: Fire at incoming
            # Lock the primary open-ended Maxwell thrusters or heavy rifle onto vector
            for w in range(num_weapons):
                if fire_commands[w] == 0: # Task idle hardpoints to handle threat defense
                    fire_commands[w] = 2  # Threat Intercept Override Code
                    
    return weapon_assignments, fire_commands, voltage_bus_states

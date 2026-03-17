import json
import os

def lap_time(base_lap_time, tire, tire_age, temp_mult, params):
    """
    Calculates the lap time for a single lap.
    
    Parameters:
    - base_lap_time: The starting lap time for the track.
    - tire: SOFT, MEDIUM, or HARD.
    - tire_age: Number of laps the current tire has been used.
    - temp_mult: Temperature multiplier for the tire compound.
    - params: Dictionary containing degradation, offsets, and power factors.
    """
    thresh = params['thresholds'][tire]
    pwr = params['power_factors'][tire]
    deg = 0.0
    if tire_age > thresh:
        # Degradation starts after a certain number of laps (threshold)
        # It follows a power-law curve: deg = rate * (age - threshold)^power
        deg = params['degradation'][tire] * ((tire_age - thresh) ** pwr)
    
    # Track-specific degradation scale to account for surface roughness/layout
    if 'BBB_TRACK_DEG_SCALE' in params:
        deg *= params['BBB_TRACK_DEG_SCALE']

    # Final lap time: base + tire offset + temperature-scaled degradation
    return base_lap_time + params['offsets'][tire] + (deg * temp_mult)

BBB_PARAMS_OVERRIDE = None

def simulate_race(data):
    """
    Simulates a full race for all drivers and returns finishing IDs in order.
    """
    if BBB_PARAMS_OVERRIDE:
        p = BBB_PARAMS_OVERRIDE
    else:
        with open('solution/learned_params.json', 'r') as f:
            p = json.load(f)
    
    rc = data['race_config']
    # Delta temperature from reference (30.0C)
    dt = rc['track_temp'] - p['temp_ref']
    
    # Dynamic Temperature Model
    # dt_hot/dt_cold are used for non-linear temperature effects (if any)
    dt_hot = max(0.0, dt)
    dt_cold = max(0.0, -dt)
    hot_f = p.get('temp_hot_factors', {})
    cold_f = p.get('temp_cold_factors', {})
    
    tm = {}
    for t in ['SOFT', 'MEDIUM', 'HARD']:
        # Temperature multiplier: 1.0 + linear_factor * dt + hot/cold corrections
        t_mult = (1.0 
                  + p['temp_factors'][t] * dt 
                  + hot_f.get(t, 0.0) * dt_hot
                  + cold_f.get(t, 0.0) * dt_cold)
        tm[t] = max(0.05, t_mult)
    
    # Track-specific degradation scale
    track_deg_maps = p.get('track_deg_multipliers', {})
    p['BBB_TRACK_DEG_SCALE'] = track_deg_maps.get(rc['track'], 1.0)
    
    results = []
    for pk in sorted(data['strategies'].keys(), key=lambda x: int(x[3:])):
        s = data['strategies'][pk]
        compounds = {s['starting_tire']}
        stops = s.get('pit_stops', [])
        
        # Pit penalty varies by track (real-world pit loss model)
        track_penalties = p.get('track_pit_penalties', {})
        pit_pen = track_penalties.get(rc['track'], p.get('pit_exit_penalty', 0.0))
        total = len(stops) * (rc['pit_lane_time'] + pit_pen)
        
        cur_tire = s['starting_tire']
        cur_lap = 1
        for st in stops:
            # Driver finishes lap 'st[lap]' and then pits
            stint_laps = st['lap'] - cur_lap + 1
            for age in range(1, stint_laps + 1):
                total += lap_time(rc['base_lap_time'], cur_tire, age, tm[cur_tire], p)
            cur_tire = st['to_tire']
            compounds.add(cur_tire)
            cur_lap = st['lap'] + 1
        
        final_laps = rc['total_laps'] - cur_lap + 1
        for age in range(1, final_laps + 1):
            total += lap_time(rc['base_lap_time'], cur_tire, age, tm[cur_tire], p)
            
        if len(compounds) < 2: total += 1500.0
        results.append({'id': s['driver_id'], 'time': total})
    
    results.sort(key=lambda x: (x['time'], x['id']))
    return [r['id'] for r in results]

if __name__ == "__main__":
    import sys
    try:
        data = json.load(sys.stdin)
        positions = simulate_race(data)
        # Submission requirement: include race_id and finishing_positions
        output = {
            "race_id": data.get('race_id', 'UNKNOWN'),
            "finishing_positions": positions
        }
        print(json.dumps(output))
    except Exception as e:
        sys.stderr.write(f"Error: {str(e)}\n")
        sys.exit(1)
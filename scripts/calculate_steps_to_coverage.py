
import json
import numpy as np

def calculate_steps(filename, label):
    # Store data by episode
    episodes = {}
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                except:
                    continue
                    
                ep = data['episode']
                step = data['step']
                cov = data.get('coverage_ratio', 0)
                
                if ep not in episodes:
                    episodes[ep] = {
                        'start_step': step,
                        'end_step': step,
                        'completion_step': None,
                        'max_coverage': 0.0
                    }
                
                ep_data = episodes[ep]
                # Update bounds
                if step < ep_data['start_step']: ep_data['start_step'] = step
                if step > ep_data['end_step']: ep_data['end_step'] = step
                
                if cov > ep_data['max_coverage']:
                    ep_data['max_coverage'] = cov
                
                # Check completion
                if ep_data['completion_step'] is None and cov >= 1.0:
                    ep_data['completion_step'] = step
                    
    except FileNotFoundError:
        print(f"File not found: {filename}")
        return

    durations = []
    
    sorted_eps = sorted(episodes.keys())
    for ep in sorted_eps:
        data = episodes[ep]
        start = data['start_step']
        
        if data['completion_step'] is not None:
            # Duration to 100%
            dur = data['completion_step'] - start
            # Special case: if completion step is same as start (unlikely but possible if 1.0 immediately), it's 0? 
            # Usually step 1 gives >0.
            # Adjust if 1-based vs 0-based? 
            # Steps count = (end - start).
            # If step 4000 is completion and start is 0, duration is 4000.
        else:
            # Did not finish? Use total duration?
            dur = data['end_step'] - start
            print(f"[{label}] Ep {ep} did not reach 1.0 (Max: {data['max_coverage']:.3f})")

        durations.append(dur)

    if not durations:
        print(f"[{label}] No data.")
        return

    mean_steps = np.mean(durations)
    std_steps = np.std(durations)
    print(f"[{label}] Episodes: {len(durations)} | Steps to Complete: {mean_steps:.1f} +/- {std_steps:.1f}")

if __name__ == "__main__":
    calculate_steps("trajectory_session_116.jsonl", "PPO (Session 116)")
    calculate_steps("trajectory_zigzag.jsonl", "Zigzag")
    calculate_steps("trajectory_spiral.jsonl", "Spiral")

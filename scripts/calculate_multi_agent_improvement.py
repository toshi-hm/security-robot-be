
import json
import numpy as np
import os

REWARD_FILE = "multi_agent_rewards_117_118_119.json"
COVERAGE_FILE = "multi_agent_coverage_data.json"
THREAT_FILE = "multi_agent_threat_data.json"

SESSION_MAP = {
    "116": 1,
    "117": 2,
    "118": 3,
    "119": 4
}

def load_json(filename):
    if not os.path.exists(filename):
        print(f"Error: {filename} not found.")
        return {}
    with open(filename, 'r') as f:
        return json.load(f)

def get_mean_for_range(episodes, values, start_ep, end_ep):
    # Filter values where episode is in [start_ep, end_ep]
    subset = []
    for ep, val in zip(episodes, values):
        if start_ep <= ep <= end_ep:
            if val is not None: # Filter out None (did not reach 100%)
                subset.append(val)
    
    if not subset:
        return 0.0, 0 # Return mean and count
    return np.mean(subset), len(subset)

def calculate_improvement():
    rewards_data = load_json(REWARD_FILE)
    coverage_data = load_json(COVERAGE_FILE)
    threat_data = load_json(THREAT_FILE)
    
    print("--- Multi-Agent Learning Progress (Initial: Ep 1-10, Final: Ep 41-50) ---")
    
    sorted_sessions = sorted(SESSION_MAP.items(), key=lambda x: x[1])
    
    for sess_id, robots in sorted_sessions:
        if sess_id not in rewards_data or sess_id not in coverage_data or sess_id not in threat_data:
            print(f"Missing data for session {sess_id} ({robots} robots)")
            continue
            
        r_eps = rewards_data[sess_id]['episodes']
        r_vals = rewards_data[sess_id]['rewards']
        
        c_eps = coverage_data[sess_id]['episodes']
        # Use steps_to_100 instead of max_coverage
        s_vals = coverage_data[sess_id]['steps_to_100']
        
        t_eps = threat_data[sess_id]['episodes']
        t_vals = threat_data[sess_id]['threats']
        
        # Initial (1-10)
        init_r, _ = get_mean_for_range(r_eps, r_vals, 1, 10)
        init_s, init_s_count = get_mean_for_range(c_eps, s_vals, 1, 10)
        init_t, _ = get_mean_for_range(t_eps, t_vals, 1, 10)
        
        # Final (41-50)
        final_r, _ = get_mean_for_range(r_eps, r_vals, 41, 50)
        final_s, final_s_count = get_mean_for_range(c_eps, s_vals, 41, 50)
        final_t, _ = get_mean_for_range(t_eps, t_vals, 41, 50)
        
        # Text Generation Helpers
        r_change = (final_r - init_r) / init_r * 100 if init_r != 0 else 0
        s_change = (final_s - init_s) / init_s * 100 if init_s != 0 else 0
        t_change = (final_t - init_t) / init_t * 100 if init_t != 0 else 0
        
        print(f"\n[{robots} Robots]")
        print(f"  Initial: Steps={init_s:.1f} (n={init_s_count}), Threat={init_t:.3f}, Reward={init_r:,.0f}")
        print(f"  Final  : Steps={final_s:.1f} (n={final_s_count}), Threat={final_t:.3f}, Reward={final_r:,.0f}")
        
        print(f"  Steps Change : {init_s:.1f} -> {final_s:.1f} ({s_change:+.1f}%)")
        print(f"  Reward Change: {init_r:,.0f} -> {final_r:,.0f} ({r_change:+.1f}%)")
        print(f"  Threat Change: {init_t:.3f} -> {final_t:.3f} ({t_change:+.1f}%)")
        
        # Latex Table Row format
        # \multirow{2}{*}{2} & 初期(ep 1-10) & 1,234 & 0.661 & 47,483 \\
        #  & 最終(ep 41-50) & 987 & 0.613 & 61,665 \\
        print("  Latency Table Rows:")
        print(f"    \\multirow{{2}}{{*}}{{{robots}}} & 初期(ep 1-10) & {init_s:,.0f} & {init_t:.3f} & {init_r:,.0f} \\\\")
        print(f"     & 最終(ep 41-50) & {final_s:,.0f} & {final_t:.3f} & {final_r:,.0f} \\\\")
        print("    \\hline")

if __name__ == "__main__":
    calculate_improvement()

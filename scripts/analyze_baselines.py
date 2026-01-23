
import json
import numpy as np
import pandas as pd
import os

def analyze_jsonl(filename, agent_name):
    print(f"Analyzing {filename}...")
    if not os.path.exists(filename):
        print("  File not found.")
        return None
        
    records = []
    with open(filename, 'r') as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except:
                pass
                
    if not records:
        print("  No records.")
        return None
        
    # Group by episode (using 'episode' field)
    episodes = {}
    for r in records:
        ep = r['episode']
        if ep not in episodes: episodes[ep] = []
        episodes[ep].append(r)
        
    stats = []
    for ep, recs in episodes.items():
        # Sort by step to be safe
        recs.sort(key=lambda x: x['step'])
        
        # Coverage (Time Average)
        covs = [r['coverage_ratio'] for r in recs]
        mean_cov_time = np.mean(covs)
        
        # Final Coverage
        final_cov = covs[-1]
        
        # Threat (Time Average)
        threats = []
        for r in recs:
            grid = np.array(r['threat_levels'])
            threats.append(np.mean(grid))
        mean_threat = np.mean(threats)
        
        # Final Threat
        # final_threat = mean(grid) of last step
        
        # Reward
        rewards = [r['reward'] for r in recs]
        total_reward = sum(rewards)
        
        stats.append({
            'episode': ep,
            'cov_time_avg': mean_cov_time,
            'cov_final': final_cov,
            'threat_mean': mean_threat,
            'reward': total_reward
        })
        
    df = pd.DataFrame(stats)
    
    # Filter incomplete?
    # For Zigzag (killed), last ep might be partial.
    # Exclude if steps < 3999?
    # Let's verify lengths. Max length is 4000.
    # df['count'] = [len(episodes[x]) for x in df['episode']]
    # But I don't have counts in df.
    # I'll just rely on "Final" being the last recorded step.
    
    print(f"  Parsed {len(df)} episodes.")
    
    res = {
        'name': agent_name,
        'cov_final_mean': df['cov_final'].mean(),
        'cov_final_std': df['cov_final'].std(),
        'cov_time_mean': df['cov_time_avg'].mean(),
        'cov_time_std': df['cov_time_avg'].std(),
        'threat_mean': df['threat_mean'].mean(),
        'threat_std': df['threat_mean'].std(),
        'reward_mean': df['reward'].mean(),
        'reward_std': df['reward'].std()
    }
    
    print(f"--- {agent_name} Results ---")
    print(f"Cov Final: {res['cov_final_mean']:.3f} +/- {res['cov_final_std']:.3f}")
    print(f"Cov Time:  {res['cov_time_mean']:.3f} +/- {res['cov_time_std']:.3f}")
    print(f"Threat:    {res['threat_mean']:.3f} +/- {res['threat_std']:.3f}")
    print(f"Reward:    {res['reward_mean']:,.0f} +/- {res['reward_std']:,.0f}")
    return res

if __name__ == "__main__":
    analyze_jsonl("trajectory_zigzag.jsonl", "Zigzag")
    analyze_jsonl("trajectory_spiral.jsonl", "Spiral")

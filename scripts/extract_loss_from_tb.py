
import os
import sys
import numpy as np
import pandas as pd
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

LOG_DIR = "tensorboard_logs/PPO_5" # Matched to Session 116 timestamp

def extract_tb_stats():
    print(f"Extracting Loss Stats from {LOG_DIR}...")
    
    if not os.path.exists(LOG_DIR):
        print("Log directory not found.")
        return

    ea = EventAccumulator(LOG_DIR, size_guidance={'scalars': 0})
    ea.Reload()
    
    tags = {
        "approx_kl": "train/approx_kl",
        "clip_fraction": "train/clip_fraction",
        "policy_gradient_loss": "train/policy_gradient_loss",
        "value_loss": "train/value_loss",
        "entropy_loss": "train/entropy_loss"
    }
    
    data = {}
    for name, tag in tags.items():
        if tag in ea.Tags()['scalars']:
            events = ea.Scalars(tag)
            # steps = [e.step for e in events]
            values = [e.value for e in events]
            data[name] = values
        else:
            print(f"Tag {tag} not found.")
            data[name] = []
            
    # Calculate Stats
    print("\n=== PPO Loss Stats (Session 116 / PPO_5) ===")
    print(f"{'Metric':<25} | {'Mean':<12} | {'Std':<12} | {'Max':<12}")
    
    for name, values in data.items():
        if not values: continue
        vals = np.array(values)
        print(f"{name:<25} | {vals.mean():<12.5f} | {vals.std():<12.5f} | {vals.max():<12.5f}")
        
    # Standard Deviations Analysis for KL
    kl_vals = np.array(data["approx_kl"])
    n_pts = len(kl_vals)
    # Approx 60 updates total? 
    # Let's say Init = first 10, Final = last 10
    if n_pts >= 20:
        init_std = kl_vals[:10].std()
        final_std = kl_vals[-10:].std()
        red_rate = (1 - final_std/init_std)*100 if init_std > 0 else 0
        print(f"\nKL Std Dev: Init {init_std:.5f} -> Final {final_std:.5f} (Red {red_rate:.1f}%)")
        
        # Clip Fraction Mean
        clip_vals = np.array(data["clip_fraction"])
        mean_clip = clip_vals.mean()
        max_clip = clip_vals.max()
        print(f"Clip Fraction: Mean {mean_clip:.3f} ({mean_clip*100:.1f}%), Max {max_clip:.3f} ({max_clip*100:.1f}%)")
        
    # Init vs Final
    # Provide approximate index split (assuming linear steps 1 to 100 or similar?)
    # SB3 logs every `n_steps=2048`? Or every update?
    # 200,000 steps total. 2048 per update. ~98 updates.
    # Init (Ep 1-10) -> Approx first 20%? or first 10 updates?
    # Let's assume indices.
    # First 10 updates vs Last 10 updates.
    
    print("\n=== Initial (First 10) vs Final (Last 10) Updates ===")
    print(f"{'Metric':<25} | {'Init Mean':<12} | {'Init Std':<12} | {'Final Mean':<12} | {'Final Std':<12}")
    
    for name, values in data.items():
        if not values: continue
        vals = np.array(values)
        if len(vals) < 20:
            print(f"{name:<25} | Not enough data points ({len(vals)})")
            continue
            
        init_v = vals[:10]
        final_v = vals[-10:]
        
        print(f"{name:<25} | {init_v.mean():<12.5f} | {init_v.std():<12.5f} | {final_v.mean():<12.5f} | {final_v.std():<12.5f}")

if __name__ == "__main__":
    extract_tb_stats()

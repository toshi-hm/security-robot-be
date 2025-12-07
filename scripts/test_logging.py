from rl.environments.enhanced_env import EnhancedSecurityEnvironment
import logging
import sys
import numpy as np

# Config logging to stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

def test():
    print("Initializing Env...")
    env = EnhancedSecurityEnvironment(
        battery_drain_rate=0.1, # fast drain
        num_robots=1,
        episode_log_file="/app/report/result/test_log.jsonl"
    )
    
    print("Reset 1")
    obs, info = env.reset()
    
    print("Stepping 1100 times...")
    for i in range(1100):
        # Action 0: Move
        obs, reward, term, trunc, info = env.step(np.array([0]))
        if term or trunc:
            print(f"Terminated at step {i+1}")
            obs, info = env.reset()
            # Loop continues, but env is reset.
            # reset() should have logged.
            break

if __name__ == "__main__":
    test()

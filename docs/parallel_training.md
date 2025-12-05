# Parallel Training & GPU Optimization

## Overview
This system supports parallel training using `SubprocVecEnv` and GPU acceleration. This allows for significantly faster training (higher FPS) by utilizing multiple CPU cores for environment simulation and CUDA for policy optimization.

## Configuration
To enable parallel training, set `num_envs > 1` in the training configuration.

### Auto-Tuning Hyperparameters
When `num_envs > 1` or `policy_type="CnnPolicy"`, the system automatically adjusts hyperparameters for efficiency unless explicitly overridden:

- **Batch Size**: Defaults to `2048` (vs `64` for single env)
- **N Steps**: Defaults to `4096` (vs `2048` for single env)

## Limitations

### Playback Recording
> [!WARNING]
> **Playback recording is limited to Rank 0 environment.**
>
> When training with `num_envs > 1`, playback recording is **disabled** by default for all environments except the first one (Rank 0) if enabled at all. However, to strictly avoid database contention and pickling errors with `SubprocVecEnv`, we currently **force disable** playback recording entirely or strictly limit it.
>
> *Current Implementation*: If `num_envs > 1`, playback is automatically disabled to prevent `PicklingError` when passing database sessions to subprocesses.

### Docker Security
- The containers use `seccomp:unconfined` and `shm_size: 8gb` to support PyTorch shared memory usage without requiring full `privileged` mode.

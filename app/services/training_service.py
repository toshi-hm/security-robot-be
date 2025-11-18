"""Domain service for managing training jobs and related workflows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import (TrainingAlgorithm, TrainingJob,
                                 TrainingJobStatus)
from app.schemas.training import TrainingSessionCreate
from app.utils.datetime import utcnow


class TrainingService:
    """Service layer that encapsulates training job persistence logic."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create_session(self, payload: TrainingSessionCreate) -> TrainingJob:
        """Create a new training session based on the provided payload."""

        if payload.total_timesteps <= 0:
            raise ValueError("total_timesteps must be greater than zero")

        algorithm = (
            payload.algorithm
            if isinstance(payload.algorithm, TrainingAlgorithm)
            else TrainingAlgorithm(payload.algorithm)
        )

        if algorithm == TrainingAlgorithm.a3c and payload.num_workers < 1:
            raise ValueError("num_workers must be at least 1 when using the A3C algorithm")

        job = TrainingJob(
            name=payload.name,
            algorithm=algorithm,
            environment_type=payload.environment_type,
            status=TrainingJobStatus.created,
            total_timesteps=payload.total_timesteps,
            env_width=payload.env_width,
            env_height=payload.env_height,
            coverage_weight=payload.coverage_weight,
            exploration_weight=payload.exploration_weight,
            diversity_weight=payload.diversity_weight,
            learning_rate=payload.learning_rate,
            batch_size=payload.batch_size,
            num_workers=payload.num_workers,
            config=payload.config,
        )

        self._db.add(job)
        await self._db.commit()
        await self._db.refresh(job)
        return job

    async def mark_queued(self, job_id: int) -> TrainingJob:
        """Mark the specified job as queued for execution."""

        job = await self.get_session(job_id)
        if job is None:
            raise ValueError(f"Training session {job_id} not found")

        job.status = TrainingJobStatus.queued
        job.updated_at = utcnow()
        await self._db.commit()
        await self._db.refresh(job)
        return job

    async def update_status(
        self,
        job: TrainingJob,
        status: TrainingJobStatus,
        *,
        mark_completed: bool = False,
        reset_completion: bool = False,
    ) -> TrainingJob:
        """Update a job status and persist the change."""

        job.status = status

        if mark_completed:
            job.completed_at = utcnow()
        if reset_completion:
            job.completed_at = None

        job.updated_at = utcnow()
        await self._db.commit()
        await self._db.refresh(job)
        return job

    async def list_sessions(self, page: int, page_size: int) -> tuple[list[TrainingJob], int]:
        """Return paginated training sessions ordered by creation date."""

        total_stmt = select(func.count()).select_from(TrainingJob)
        total_result = await self._db.execute(total_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        sessions_stmt = (
            select(TrainingJob)
            .order_by(TrainingJob.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        sessions_result = await self._db.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()
        return sessions, total

    async def get_session(self, job_id: int) -> TrainingJob | None:
        """Retrieve a training job by its primary key."""

        return await self._db.get(TrainingJob, job_id)

    async def delete_session(self, job: TrainingJob) -> None:
        """Delete a training job and cascade to related entities."""

        await self._db.delete(job)
        await self._db.commit()

    def build_training_config(
        self,
        job: TrainingJob,
        payload: TrainingSessionCreate | None = None,
    ) -> dict[str, Any]:
        """Construct the configuration dictionary passed to background workers."""

        extra_config = payload.config if payload is not None else job.config

        try:
            algorithm = (
                job.algorithm
                if isinstance(job.algorithm, TrainingAlgorithm)
                else TrainingAlgorithm(job.algorithm)
            )
        except ValueError as exc:
            raise ValueError(f"Unsupported training algorithm: {job.algorithm}") from exc

        config: dict[str, Any] = {
            "session_id": job.id,
            "name": job.name,
            "algorithm": algorithm.value,
            "environment_type": job.environment_type,
            "total_timesteps": job.total_timesteps,
            "env_width": job.env_width,
            "env_height": job.env_height,
            "coverage_weight": job.coverage_weight,
            "exploration_weight": job.exploration_weight,
            "diversity_weight": job.diversity_weight,
            "learning_rate": job.learning_rate,
            "batch_size": job.batch_size,
            "num_workers": job.num_workers,
            "model_path": job.model_path,
            "log_path": job.log_path,
        }

        if extra_config is not None:
            config["config"] = extra_config

        if payload is not None and payload.config is None and job.config is not None:
            # Preserve persisted configuration when the resume payload omits overrides.
            config["config"] = job.config

        return config

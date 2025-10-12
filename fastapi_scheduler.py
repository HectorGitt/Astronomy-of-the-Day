#!/usr/bin/env python3
"""
FastAPI Outfit Scheduler Server
Provides REST API endpoints for managing outfit generation scheduling
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Import outfit generator
from outfit_generator import (
    generate_refined_prompts,
    generate_outfit_images,
    post_outfits_to_twitter,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


# Lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("🚀 Starting FastAPI Outfit Scheduler Server")

    # Start the scheduler
    scheduler.start()
    logger.info("📅 Scheduler started")

    yield

    # Shutdown
    logger.info("🛑 Shutting down FastAPI Outfit Scheduler Server")
    scheduler.shutdown()
    logger.info("📅 Scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title="Outfit Scheduler API",
    description="AI-powered outfit generation and scheduling service",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class ScheduleRequest(BaseModel):
    cron_expression: str
    enabled: bool = True
    description: str = "Scheduled outfit generation"


class JobInfo(BaseModel):
    id: str
    name: str
    next_run_time: Optional[datetime]
    trigger: str
    enabled: bool


class SchedulerStatus(BaseModel):
    running: bool
    jobs_count: int
    next_run_times: List[Dict]


# Global state
scheduler_jobs = {}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Outfit Scheduler API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "scheduler_running": scheduler.running,
    }


@app.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status():
    """Get scheduler status and upcoming jobs"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "trigger": str(job.trigger),
            }
        )

    return SchedulerStatus(
        running=scheduler.running, jobs_count=len(jobs), next_run_times=jobs
    )


@app.post("/schedule")
async def schedule_outfit_generation(
    request: ScheduleRequest, background_tasks: BackgroundTasks
):
    """Schedule outfit generation with cron expression"""

    try:
        # Validate cron expression
        trigger = CronTrigger.from_crontab(request.cron_expression)

        # Create job ID
        job_id = f"outfit_gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Add job to scheduler
        job = scheduler.add_job(
            func=run_outfit_generation,
            trigger=trigger,
            id=job_id,
            name=request.description,
            replace_existing=True,
        )

        scheduler_jobs[job_id] = {
            "job": job,
            "description": request.description,
            "cron_expression": request.cron_expression,
            "enabled": request.enabled,
        }

        logger.info(
            f"📅 Scheduled outfit generation: {job_id} - {request.cron_expression}"
        )

        return {
            "message": "Outfit generation scheduled successfully",
            "job_id": job_id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        }

    except Exception as e:
        logger.error(f"Failed to schedule outfit generation: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cron expression or scheduling error: {str(e)}",
        )


@app.delete("/schedule/{job_id}")
async def remove_schedule(job_id: str):
    """Remove a scheduled job"""

    if job_id not in scheduler_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        scheduler.remove_job(job_id)
        del scheduler_jobs[job_id]

        logger.info(f"🗑️ Removed scheduled job: {job_id}")

        return {"message": f"Job {job_id} removed successfully"}

    except Exception as e:
        logger.error(f"Failed to remove job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove job: {str(e)}")


@app.post("/generate-now")
async def generate_outfits_now(background_tasks: BackgroundTasks):
    """Trigger immediate outfit generation"""

    background_tasks.add_task(run_outfit_generation)

    logger.info("🚀 Triggered immediate outfit generation")

    return {
        "message": "Outfit generation started in background",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/jobs")
async def list_jobs():
    """List all scheduled jobs"""

    jobs = []
    for job_id, job_info in scheduler_jobs.items():
        job = job_info["job"]
        jobs.append(
            {
                "id": job_id,
                "description": job_info["description"],
                "cron_expression": job_info["cron_expression"],
                "enabled": job_info["enabled"],
                "next_run": job.next_run_time.isoformat()
                if job.next_run_time
                else None,
                "running": job.next_run_time is not None,
            }
        )

    return {"jobs": jobs}


async def run_outfit_generation():
    """Run the outfit generation process"""
    logger.info("🎨 Starting outfit generation process")

    try:
        # Generate and refine prompts
        prompts = await generate_refined_prompts(4)
        logger.info("Generated and refined 4 outfit prompts")

        # Generate outfit images
        outfits = await generate_outfit_images(prompts)

        if not outfits:
            logger.error("No outfits were generated")
            return {"status": "failed", "message": "No outfits generated"}

        logger.info(f"Successfully generated {len(outfits)} outfits")

        # Post to Twitter
        success = await post_outfits_to_twitter(outfits)

        if success:
            logger.info("✅ Successfully posted outfits to Twitter")
            return {
                "status": "success",
                "message": f"Generated and posted {len(outfits)} outfits",
            }
        else:
            logger.error("❌ Failed to post outfits to Twitter")
            return {
                "status": "partial",
                "message": f"Generated {len(outfits)} outfits but failed to post",
            }

    except Exception as e:
        logger.error(f"❌ Error in outfit generation: {e}")
        return {"status": "error", "message": str(e)}

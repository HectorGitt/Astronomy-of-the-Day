import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import outfit generation functions
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

# Global variables for scheduler state
scheduler = AsyncIOScheduler()
generation_status = {
    "is_running": False,
    "last_run": None,
    "next_run": None,
    "total_runs": 0,
    "successful_runs": 0,
    "failed_runs": 0,
    "current_status": "idle",
}


class GenerationRequest(BaseModel):
    """Request model for manual outfit generation"""

    count: Optional[int] = 4
    force: Optional[bool] = False  # Force generation even if recently run


class StatusResponse(BaseModel):
    """Response model for status endpoint"""

    is_running: bool
    last_run: Optional[str]
    next_run: Optional[str]
    total_runs: int
    successful_runs: int
    failed_runs: int
    current_status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 Starting Outfit Generator Scheduler")

    # Start the scheduler
    scheduler.start()
    logger.info("📅 Scheduler started")

    # Schedule the outfit generation job (every 6 hours)
    scheduler.add_job(
        run_scheduled_generation,
        trigger=CronTrigger(hour="*/6"),  # Every 6 hours
        id="outfit_generation",
        name="Generate and post outfits",
        replace_existing=True,
    )

    # Update next run time
    jobs = scheduler.get_jobs()
    if jobs:
        generation_status["next_run"] = str(jobs[0].next_run_time)

    logger.info("✅ Outfit Generator Scheduler ready")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Outfit Generator Scheduler")
    scheduler.shutdown()
    logger.info("📅 Scheduler stopped")


app = FastAPI(
    title="Outfit Generator Scheduler",
    description="AI-powered outfit generation and Twitter posting service",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def run_scheduled_generation():
    """Run the scheduled outfit generation"""
    global generation_status

    if generation_status["is_running"]:
        logger.warning("⚠️ Generation already running, skipping scheduled run")
        return

    generation_status["is_running"] = True
    generation_status["current_status"] = "running"
    generation_status["total_runs"] += 1
    generation_status["last_run"] = datetime.now().isoformat()

    try:
        logger.info("🤖 Starting scheduled outfit generation")

        # Reset global variables from outfit_generator
        import outfit_generator

        outfit_generator.tweet_status = False
        outfit_generator.tries = 0

        # Generate and refine random prompts with AI
        prompts = await generate_refined_prompts(4)
        logger.info("Generated and refined 4 outfit prompts with AI")

        # Generate outfit images
        outfits = await generate_outfit_images(prompts)

        if not outfits:
            raise Exception("No outfits were successfully generated")

        logger.info(f"Successfully generated {len(outfits)} outfits")

        # Post to Twitter
        success = await post_outfits_to_twitter(outfits)

        if success:
            generation_status["successful_runs"] += 1
            generation_status["current_status"] = "success"
            logger.info("✅ Scheduled generation completed successfully!")
        else:
            generation_status["failed_runs"] += 1
            generation_status["current_status"] = "failed"
            logger.error("❌ Scheduled generation failed to post to Twitter")

    except Exception as e:
        generation_status["failed_runs"] += 1
        generation_status["current_status"] = "error"
        logger.error(f"💥 Scheduled generation error: {e}")

    finally:
        generation_status["is_running"] = False

        # Update next run time
        jobs = scheduler.get_jobs()
        if jobs:
            generation_status["next_run"] = str(jobs[0].next_run_time)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Outfit Generator Scheduler API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "GET /": "This information",
            "GET /status": "Get scheduler status",
            "POST /generate": "Trigger manual generation",
            "GET /health": "Health check",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "outfit-generator-scheduler",
    }


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get the current status of the scheduler"""
    return StatusResponse(**generation_status)


@app.post("/generate")
async def trigger_generation(
    request: GenerationRequest, background_tasks: BackgroundTasks
):
    """Manually trigger outfit generation"""

    if generation_status["is_running"] and not request.force:
        raise HTTPException(
            status_code=409,
            detail="Generation is already running. Use force=true to override.",
        )

    # Add to background tasks
    background_tasks.add_task(run_manual_generation, request.count or 4)

    return {
        "message": "Outfit generation started in background",
        "count": request.count or 4,
        "timestamp": datetime.now().isoformat(),
    }


async def run_manual_generation(count: int):
    """Run manual outfit generation"""
    global generation_status

    generation_status["is_running"] = True
    generation_status["current_status"] = "running"
    generation_status["total_runs"] += 1
    generation_status["last_run"] = datetime.now().isoformat()

    try:
        logger.info(f"🤖 Starting manual outfit generation (count: {count})")

        # Reset global variables from outfit_generator
        import outfit_generator

        outfit_generator.tweet_status = False
        outfit_generator.tries = 0

        # Generate and refine random prompts with AI
        prompts = await generate_refined_prompts(count)
        logger.info(f"Generated and refined {count} outfit prompts with AI")

        # Generate outfit images
        outfits = await generate_outfit_images(prompts)

        if not outfits:
            raise Exception("No outfits were successfully generated")

        logger.info(f"Successfully generated {len(outfits)} outfits")

        # Post to Twitter
        success = await post_outfits_to_twitter(outfits)

        if success:
            generation_status["successful_runs"] += 1
            generation_status["current_status"] = "success"
            logger.info("✅ Manual generation completed successfully!")
        else:
            generation_status["failed_runs"] += 1
            generation_status["current_status"] = "failed"
            logger.error("❌ Manual generation failed to post to Twitter")

    except Exception as e:
        generation_status["failed_runs"] += 1
        generation_status["current_status"] = "error"
        logger.error(f"💥 Manual generation error: {e}")

    finally:
        generation_status["is_running"] = False


if __name__ == "__main__":
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"🌐 Starting FastAPI server on {host}:{port}")

    uvicorn.run(
        "outfit_scheduler:app", host=host, port=port, reload=False, log_level="info"
    )

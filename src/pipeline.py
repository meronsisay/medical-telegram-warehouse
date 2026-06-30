"""
Dagster pipeline for Medical Telegram Data Warehouse.
"""

import os
import sys  # <--- Added to handle virtual environment tracking seamlessly
import subprocess
import json
from pathlib import Path

import dagster as dg
from dagster import (
    op,
    job,
    schedule,
    Definitions,
)
from dotenv import load_dotenv

load_dotenv()


# ============================================
# OPS - Individual pipeline steps
# ============================================

@op(
    config_schema={
        "limit": dg.Field(int, default_value=1000, description="Messages per channel"),
    }
)
def scrape_telegram_data(context) -> dict:
    """Scrape data from Telegram channels."""
    context.log.info("Starting Telegram data scraping...")
    project_root = Path(__file__).parent.parent
    scraper_path = project_root / "src" / "scraper.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(scraper_path)],  
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            raise Exception(f"Scraping failed: {result.stderr}")
        
        return {
            "status": "success",
            "messages_scraped": "~3000",
            "output": result.stdout
        }
    except Exception as e:
        context.log.error(f"Scraping failed: {e}")
        raise


@op
def load_raw_to_postgres(context, scraped_data: dict) -> dict:
    """Step 2: Load raw JSON data to PostgreSQL."""
    context.log.info("Loading raw data to PostgreSQL...")
    project_root = Path(__file__).parent.parent
    loader_path = project_root / "scripts" / "load_to_postgres.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(loader_path)],  # <--- Changed from "python"
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            raise Exception(f"Loading failed: {result.stderr}")
        
        return {
            "status": "success",
            "loaded_data": "raw.telegram_messages",
            "scraped_data": scraped_data
        }
    except Exception as e:
        context.log.error(f"Loading failed: {e}")
        raise


@op
def run_yolo_enrichment(context, loaded_data: dict) -> dict:
    """Step 3: Run YOLO object detection and populate image staging tables."""
    context.log.info("Running YOLO image enrichment...")
    project_root = Path(__file__).parent.parent
    yolo_path = project_root / "src" / "yolo_detect.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(yolo_path)],  # <--- Changed from "python"
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            raise Exception(f"YOLO detection script failed: {result.stderr}")
        
        # Load YOLO results to PostgreSQL
        loader_path = project_root / "scripts" / "load_yolo_to_postgres.py"
        load_result = subprocess.run(
            [sys.executable, str(loader_path)],  # <--- Changed from "python"
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=os.environ.copy(),
        )
        if load_result.returncode != 0:
            raise Exception(f"YOLO PostgreSQL loading failed: {load_result.stderr}")
        
        return {
            "status": "success",
            "yolo_complete": True,
            "yolo_loaded": True,
            "previous_stage": loaded_data
        }
    except Exception as e:
        context.log.error(f"YOLO enrichment layer failed: {e}")
        raise


@op
def run_dbt_transformations(context, enriched_data: dict) -> dict:
    """Step 4: Execute dbt models once all staging assets exist."""
    context.log.info("Running dbt transformations...")
    project_root = Path(__file__).parent.parent
    dbt_path = project_root / "medical_warehouse"
    
    try:
        # Install packages
        subprocess.run(["dbt", "deps"], capture_output=True, text=True, cwd=str(dbt_path))
        
        # Run models
        run_result = subprocess.run(
            ["dbt", "run"],
            capture_output=True,
            text=True,
            cwd=str(dbt_path),
        )
        if run_result.returncode != 0:
            raise Exception(f"dbt run failed: {run_result.stderr}")
        
        # Run validation tests
        test_result = subprocess.run(
            ["dbt", "test"],
            capture_output=True,
            text=True,
            cwd=str(dbt_path),
        )
        
        return {
            "status": "success",
            "models_run": True,
            "tests_passed": test_result.returncode == 0,
            "enriched_data": enriched_data
        }
    except Exception as e:
        context.log.error(f"dbt transformations failed: {e}")
        raise


@op
def notify_completion(context, final_data: dict) -> str:
    """Final step: Logging and system notification wrapper."""
    context.log.info("=" * 60)
    context.log.info("🎉 Pipeline completed successfully!")
    context.log.info("=" * 60)
    context.log.info(f"Final Execution State Summary:\n{json.dumps(final_data, indent=2)}")
    context.log.info("=" * 60)
    return "Pipeline Finished"


# ============================================
# JOB - Defines the explicit asset tracking flow
# ============================================

@job(
    description="Complete ETL pipeline for Medical Telegram Data Warehouse",
    config={"ops": {"scrape_telegram_data": {"config": {"limit": 1000}}}}
)
def telegram_pipeline():
    """Flow graph setup: Scrape -> Load Text -> Run YOLO -> Transform with dbt -> Notify"""
    scraped = scrape_telegram_data()
    loaded = load_raw_to_postgres(scraped)
    enriched = run_yolo_enrichment(loaded)            
    transformed = run_dbt_transformations(enriched)  
    notify_completion(transformed)


# ============================================
# SCHEDULES
# ============================================

@schedule(cron_schedule="0 8 * * *", job=telegram_pipeline, execution_timezone="UTC")
def daily_pipeline_schedule(context):
    return {}

@schedule(cron_schedule="0 0 * * 0", job=telegram_pipeline, execution_timezone="UTC")
def weekly_full_refresh_schedule(context):
    return {}


# ============================================
# DEFS COMPILATION
# ============================================

defs = Definitions(
    jobs=[telegram_pipeline],
    schedules=[daily_pipeline_schedule, weekly_full_refresh_schedule],
)
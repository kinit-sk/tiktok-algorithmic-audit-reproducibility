"""
parallel_runner.py

This module manages parallel execution of multiple TikTok scraping instances,
each with its own configuration and scenario.

Features:
- Runs multiple scraping instances with different configs
- Adds delay between starts for manual captcha solving
- Maintains same config structure as config.py
- Provides logging for parallel execution management
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Dict, List
from scenario_configs import get_scenario_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("parallel_runner.log", mode="w", encoding="utf-8"),
    ],
)

async def run_instance(scenario: float, user_id: int) -> None:
    """Runs a single scraping instance with the given scenario and user ID"""
    
    try:
        # Get configuration for this scenario and user
        config = get_scenario_config(scenario, user_id)
        
        # Create unique temp log file and config file for this run
        temp_log = f"temp_{scenario}_{user_id}.log"
        config_path = f"temp_config_{scenario}_{user_id}.py"  # Define config_path here
        
        try:
            # Write configuration to temporary file
            with open(config_path, "w", encoding="utf-8") as f:
                f.write('"""Temporary configuration file for parallel TikTok scraping"""\n\n')
                f.write(f"SCENARIO = {scenario}\n")  # Write scenario ID first
                for key, value in config.items():
                    if key != "SCENARIO":  # Skip SCENARIO as we already wrote it
                        f.write(f"{key} = {repr(value)}\n")
                
                # Add the get_user_config function
                f.write("\ndef get_user_config(user_id: int) -> dict:\n")
                f.write("    user_profile = USER_PROFILES.get(user_id, {})\n")
                f.write("    return user_profile\n")

            # Run the instance
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd()
            env["CONFIG_PATH"] = config_path
            env["SCENARIO"] = str(scenario)
            env["TEMP_LOG"] = temp_log  # Pass temp log filename through environment
            
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "main.py",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                logging.info(f"Instance output (scenario {scenario}, user {user_id}):\n{stdout.decode()}")
            if stderr:
                logging.error(f"Instance errors (scenario {scenario}, user {user_id}):\n{stderr.decode()}")
            
            # Check if process was successful
            if process.returncode != 0:
                logging.error(f"Instance failed with return code {process.returncode}")
                return False
            
            return True
                
        finally:
            # Cleanup temporary files
            try:
                if os.path.exists(config_path):  # Check if file exists before trying to remove
                    os.remove(config_path)
                if os.path.exists(temp_log):
                    os.remove(temp_log)
            except Exception as e:
                logging.error(f"Error removing temporary files: {e}")
                
    except Exception as e:
        logging.error(f"Error running instance: {e}")
        return False

async def run_parallel(runs: List[tuple]) -> None:
    """
    Runs multiple scraping instances in parallel with a delay between starts.
    Continues with remaining runs if some fail.
    """
    tasks = []
    failed_runs = []
    
    for i, (scenario, user_id) in enumerate(runs):
        try:
            # Start the instance
            task = asyncio.create_task(run_instance(scenario, user_id))
            tasks.append(task)
            
            # Wait before starting next instance (except for the last one)
            if i < len(runs) - 1:
                logging.info("Waiting 2 minutes before starting next instance...")
                await asyncio.sleep(120)
                
        except Exception as e:
            logging.error(f"Error in run_parallel for scenario {scenario}, user {user_id}: {e}")
            failed_runs.append((scenario, user_id))
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Check results
    for (scenario, user_id), result in zip(runs, results):
        if isinstance(result, Exception) or result is False:
            failed_runs.append((scenario, user_id))
            logging.error(f"Run failed for scenario {scenario}, user {user_id}")
    
    if failed_runs:
        logging.error("The following runs failed:")
        for scenario, user_id in failed_runs:
            logging.error(f"  - Scenario {scenario}, User {user_id}")
    else:
        logging.info("All runs completed successfully")

if __name__ == "__main__":
    # Define which scenarios and users to run
    runs = [
        (40.1,39),
        (40.2,40),





    ]
    
    # Run the parallel instances
    asyncio.run(run_parallel(runs)) 
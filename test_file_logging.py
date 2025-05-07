#!/usr/bin/env python3
"""
Script to test if the file logging configuration works correctly.
"""
import logging
import os
from datetime import datetime

# Import the logger from the main application
from app.main import logger

# Log some test messages
logger.info("Test info message from test_file_logging.py")
logger.warning("Test warning message from test_file_logging.py")
logger.error("Test error message from test_file_logging.py")

# Check if the log file exists and contains the test messages
log_date = datetime.now().strftime("%Y-%m-%d")
log_file = os.path.join("logs", f"garden10_{log_date}.log")

print(f"Checking log file: {log_file}")
if os.path.exists(log_file):
    print(f"Log file exists: {log_file}")
    with open(log_file, 'r') as f:
        content = f.read()
        if "Test info message from test_file_logging.py" in content:
            print("Test message found in log file!")
        else:
            print("Test message NOT found in log file.")
else:
    print(f"Log file does not exist: {log_file}")
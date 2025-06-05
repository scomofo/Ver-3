# utils/general_utils.py - Verified (Minor changes)
import os
import re
import json
import datetime
import hashlib  # Was missing import
import logging
import platform
import sys
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

def sanitize_filename(filename: str) -> str:
    """Sanitize a string to be used as a filename."""
    if not isinstance(filename, str):
        logger.warning(f"Attempted to sanitize non-string filename: {type(filename)}")
        filename = str(filename)
    # Remove invalid characters for Windows/Unix filenames
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Replace sequences of whitespace with a single underscore
    sanitized = re.sub(r'\s+', "_", sanitized).strip('_')
    # Limit length if necessary (e.g., 255 bytes is common limit)
    # sanitized = sanitized[:200] # Example length limit
    if not sanitized: # Handle cases where the name becomes empty
        sanitized = "_" + hashlib.md5(filename.encode()).hexdigest()[:8]
    return sanitized

def format_currency(amount: Union[float, int, str]) -> str:
    """Format a number as currency (e.g., $1,234.56). Handles errors gracefully."""
    try:
        # Convert to float if it's a string, cleaning it first
        if isinstance(amount, str):
            # Remove currency symbols, commas, whitespace
            clean_amount = re.sub(r'[$,\s]', '', amount)
            if not clean_amount: # Handle empty string after cleaning
                 amount_float = 0.0
            else:
                 amount_float = float(clean_amount)
        elif isinstance(amount, (int, float)):
            amount_float = float(amount)
        else:
             raise TypeError("Amount must be int, float, or string")

        return f"${amount_float:,.2f}"
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not format currency for input '{amount}': {e}")
        return "$0.00" # Default value on error

def format_date(date_obj: Optional[Union[datetime.date, datetime.datetime]],
                output_format: str = "%Y-%m-%d") -> str:
    """Format a date/datetime object into a string. Returns empty string on error or None input."""
    if date_obj is None:
        return ""
    try:
        return date_obj.strftime(output_format)
    except Exception as e:
        logger.warning(f"Could not format date object '{date_obj}': {e}")
        return "" # Default value on error


def parse_date(date_str: Optional[str],
               input_formats: List[str] = ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y%m%d"]) -> Optional[datetime.date]:
    """Parse a date string using multiple formats. Returns date object or None."""
    if not date_str:
        return None
    for fmt in input_formats:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue # Try next format
    logger.debug(f"Could not parse date string '{date_str}' with formats: {input_formats}")
    return None


def get_project_root(start_path: str = __file__, marker: str = '.git') -> Optional[str]:
    """Find the project root directory by looking upwards for a marker file/dir.

    Args:
        start_path: The path to start searching upwards from.
        marker: A filename or directory name that indicates the root (e.g., '.git', 'pyproject.toml').

    Returns:
        The absolute path to the project root, or None if not found.
    """
    current_dir = os.path.dirname(os.path.abspath(start_path))
    while True:
        if os.path.exists(os.path.join(current_dir, marker)):
            return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            # Reached the filesystem root
            logger.warning(f"Project root marker '{marker}' not found upwards from {start_path}")
            return None
        current_dir = parent_dir


def get_resource_path(relative_path: str, resources_dir: Optional[str] = None) -> str:
    """Get the absolute path to a resource file, prioritizing the provided resources_dir.

    Args:
        relative_path: Path relative to the resources directory (e.g., "icons/logo.png").
        resources_dir: The absolute path to the resources directory (ideally from Config).

    Returns:
        Absolute path to the resource file. Falls back to guessing if resources_dir not provided.
    """
    if resources_dir and os.path.isdir(resources_dir):
        potential_path = os.path.join(resources_dir, relative_path)
        if os.path.exists(potential_path):
            return potential_path
        else:
            logger.warning(f"Resource '{relative_path}' not found in provided resources directory: {resources_dir}")
            # Fall through to guessing logic if not found in provided dir

    # Guessing logic (fallback if resources_dir not provided or file not found there)
    logger.debug(f"Resources directory not provided or file not found, attempting to guess path for: {relative_path}")
    script_dir = os.path.dirname(os.path.abspath(__file__)) # utils directory
    base_dir = os.path.dirname(script_dir) # Project base directory (usually)

    potential_paths = [
        os.path.join(base_dir, "resources", relative_path),
        os.path.join(base_dir, "assets", relative_path), # Check assets too
        # Add other potential locations if necessary
    ]

    for path in potential_paths:
        if os.path.exists(path):
            logger.debug(f"Guessed resource path found: {path}")
            return path

    # If still not found, return path relative to assumed resources dir as last resort
    logger.error(f"Resource file could not be reliably located: {relative_path}. Returning default guess.")
    return os.path.join(base_dir, "resources", relative_path) # Default guess


def parse_price(text: Optional[str]) -> float:
    """Parse a price string (e.g., '$1,234.56 CAD', '500.00') to float.

    Args:
        text: The price string to parse.

    Returns:
        The price as a float, or 0.0 if parsing fails.
    """
    if not text:
        return 0.0

    try:
        # Remove currency symbols, thousands separators, and extra whitespace/text
        clean_text = re.sub(r'[$,\sA-Za-z]', '', str(text))
        if not clean_text:
            return 0.0
        return float(clean_text)
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse price string '{text}': {e}")
        return 0.0


# ===== ADDITIONAL FUNCTIONS NEEDED FOR MAIN APP =====

# Alias for get_resource_path to match main.py imports
resource_path = get_resource_path

def set_app_user_model_id(app_id: str) -> bool:
    """
    Set the Application User Model ID for Windows taskbar grouping.
    This is primarily used on Windows to ensure proper taskbar grouping and icons.
    
    Args:
        app_id: Application User Model ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Only applicable on Windows
        if platform.system() != 'Windows':
            logger.debug(f"set_app_user_model_id is only applicable on Windows, not {platform.system()}")
            return False
        
        # Import Windows-specific libraries
        try:
            import ctypes
            windll = ctypes.windll
        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not import Windows libraries: {e}")
            return False
        
        # Set the app ID
        try:
            logger.debug(f"Setting Application User Model ID to: {app_id}")
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            return True
        except Exception as e:
            logger.error(f"Error setting Application User Model ID: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in set_app_user_model_id: {e}")
        return False
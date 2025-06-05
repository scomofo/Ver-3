# utils/cache_handler.py - Verified (Minor changes)
import os
import json
import time
import logging
from typing import Any, Optional, Dict, Tuple

logger = logging.getLogger(__name__)

class CacheHandler:
    """Utility class for caching data to improve application performance."""

    def __init__(self, cache_dir=None):
        """Initialize the cache handler.

        Args:
            cache_dir: Directory for cache files (obtained from Config ideally)
        """
        self.cache_dir = cache_dir
        if self.cache_dir:
            try:
                os.makedirs(self.cache_dir, exist_ok=True) # Ensure directory exists
                logger.debug(f"Cache directory set to: {self.cache_dir}")
            except OSError as e:
                 logger.error(f"Failed to create cache directory {self.cache_dir}: {e}")
                 self.cache_dir = None # Disable caching if dir creation fails
                 logger.warning("Caching will be disabled.")
        else:
            logger.warning("No cache directory provided, caching will be disabled")


    def _get_cache_path(self, cache_key: str) -> Optional[str]:
        """Get the file path for a cache key.

        Args:
            cache_key: Cache identifier

        Returns:
            Absolute path to cache file or None if caching is disabled.
        """
        if not self.cache_dir:
            return None

        # Sanitize the cache key to be safe for filenames
        # Keep it simple: replace non-alphanumeric with underscore
        safe_key = "".join(c if c.isalnum() else "_" for c in str(cache_key))
        # Add a simple hash for uniqueness if keys can be very long or complex
        # key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:8]
        # safe_key = f"{safe_key}_{key_hash}" # Example if needed
        return os.path.join(self.cache_dir, f"{safe_key}.json")


    def get(self, cache_key: str, default: Any = None, ttl: Optional[int] = None) -> Tuple[Optional[Any], bool]:
        """Get data from cache if it exists and is not expired.

        Args:
            cache_key: Cache identifier
            default: Value to return if cache miss or expired
            ttl: Time-to-live in seconds. If None, cache never expires based on time.

        Returns:
            Tuple: (Cached data or default value, True if cache hit and valid, False otherwise)
        """
        cache_path = self._get_cache_path(cache_key)
        if not cache_path or not os.path.exists(cache_path):
            logger.debug(f"Cache miss (not found): {cache_key}")
            return default, False

        try:
            # Check TTL if specified
            if ttl is not None:
                file_mod_time = os.path.getmtime(cache_path)
                if (time.time() - file_mod_time) > ttl:
                    logger.info(f"Cache expired (TTL {ttl}s): {cache_key}")
                    # Optionally remove expired file
                    # self.invalidate(cache_key)
                    return default, False

            # Read cache file
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Cache hit: {cache_key}")
            return data, True

        except json.JSONDecodeError:
             logger.warning(f"Cache corrupted (JSON decode error): {cache_key}. Invalidating.")
             self.invalidate(cache_key) # Remove corrupted file
             return default, False
        except Exception as e:
            logger.error(f"Error reading cache for {cache_key}: {str(e)}")
            return default, False

    def set(self, cache_key: str, data: Any) -> bool:
        """Set data into cache.

        Args:
            cache_key: Cache identifier
            data: Data to cache (must be JSON serializable)

        Returns:
            True if successful, False otherwise
        """
        cache_path = self._get_cache_path(cache_key)
        if not cache_path:
            return False

        try:
            # Ensure directory exists just in case
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2) # Use indent for readability
            logger.debug(f"Cache set: {cache_key}")
            return True
        except TypeError as e:
             logger.error(f"Cache data for {cache_key} is not JSON serializable: {e}")
             return False
        except Exception as e:
            logger.error(f"Error writing cache for {cache_key}: {str(e)}")
            return False

    def invalidate(self, cache_key: str) -> bool:
        """Invalidate (delete) a cache entry.

        Args:
            cache_key: Cache identifier

        Returns:
            True if successful or file didn't exist, False on error
        """
        cache_path = self._get_cache_path(cache_key)
        if not cache_path: # Caching disabled
            return False

        if not os.path.exists(cache_path):
            logger.debug(f"Cache invalidate (already not found): {cache_key}")
            return True # Considered success

        try:
            os.remove(cache_path)
            logger.debug(f"Cache invalidated: {cache_key}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating cache for {cache_key}: {str(e)}")
            return False

    def clear_all(self) -> bool:
        """Clear all *.json cache entries from the cache directory.

        Returns:
            True if successful, False otherwise
        """
        if not self.cache_dir or not os.path.exists(self.cache_dir):
             logger.warning("Cache directory does not exist, cannot clear.")
             return False

        cleared_count = 0
        errors = 0
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(file_path)
                        cleared_count += 1
                    except Exception as e:
                         logger.error(f"Error removing cache file {file_path}: {e}")
                         errors += 1

            if errors > 0:
                 logger.warning(f"Cleared {cleared_count} cache entries from {self.cache_dir} with {errors} errors.")
                 return False # Indicate partial success/failure
            else:
                 logger.info(f"Cleared {cleared_count} cache entries from {self.cache_dir}")
                 return True
        except Exception as e:
            logger.error(f"Error listing or clearing cache directory {self.cache_dir}: {str(e)}")
            return False
# app/core/threading.py
import asyncio
import logging
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, List, Optional, Union
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QRunnable, QThreadPool
from dataclasses import dataclass
from datetime import datetime
import weakref

logger = logging.getLogger(__name__)

@dataclass
class TaskResult:
    """Result of a task execution"""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class Worker(QRunnable):
    """
    Qt Worker thread for background tasks.
    
    Usage:
        worker = Worker(my_function, arg1, arg2, kwarg1=value1)
        worker.signals.result.connect(handle_result)
        worker.signals.error.connect(handle_error)
        QThreadPool.globalInstance().start(worker)
    """
    
    class Signals(QObject):
        """Signals for worker communication"""
        finished = pyqtSignal()
        error = pyqtSignal(Exception)
        result = pyqtSignal(object)
        progress = pyqtSignal(int)  # Progress percentage
        status = pyqtSignal(str)    # Status message
    
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = self.Signals()
        self.is_cancelled = False
        
    def run(self):
        """Execute the worker function"""
        try:
            if self.is_cancelled:
                return
                
            result = self.fn(*self.args, **self.kwargs)
            
            if not self.is_cancelled:
                self.signals.result.emit(result)
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()
    
    def cancel(self):
        """Cancel the worker (if it supports cancellation)"""
        self.is_cancelled = True

class AsyncWorker(QThread):
    """
    Qt Thread for async operations.
    
    Usage:
        worker = AsyncWorker(my_async_function, arg1, arg2)
        worker.result_ready.connect(handle_result)
        worker.error_occurred.connect(handle_error)
        worker.start()
    """
    
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(Exception)
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    
    def __init__(self, async_fn: Callable, *args, **kwargs):
        super().__init__()
        self.async_fn = async_fn
        self.args = args
        self.kwargs = kwargs
        self.is_cancelled = False
        self._loop = None
        
    def run(self):
        # Try to get a more descriptive name for the worker, fallback to objectName or id
        worker_name_for_log = self.objectName() if self.objectName() else f"UnnamedAsyncWorker-{id(self)}"
        try:
            # Check if an object name was set, perhaps from the task_name
            # This might require passing task_name to AsyncWorker's __init__ and setting it.
            # For now, let's use a simpler identifier if objectName() is not set by default for QThread.
            # Example: worker_name_for_log = f"AsyncWorker(fn={self.async_fn.__name__})-{self.thread().currentThreadId()}"
            # For simplicity, we'll stick to objectName or a generic label for now if objectName is not typically set.
            # If self.objectName() is consistently empty, a more robust naming might be needed later.
            log_prefix = f"AsyncWorker ({worker_name_for_log})" # Use a consistent prefix

            logger.debug(f"{log_prefix}: run() started.")
            self._loop = None # Ensure _loop is initialized for the finally block

            logger.debug(f"{log_prefix}: Creating new event loop...")
            self._loop = asyncio.new_event_loop()
            logger.debug(f"{log_prefix}: New event loop created: {self._loop}")

            logger.debug(f"{log_prefix}: Setting event loop...")
            asyncio.set_event_loop(self._loop)
            logger.debug(f"{log_prefix}: Event loop set.")
            
            target_fn_name = getattr(self.async_fn, '__name__', str(self.async_fn))
            logger.debug(f"{log_prefix}: Calling run_until_complete for {target_fn_name}...")
            result = self._loop.run_until_complete(
                self.async_fn(*self.args, **self.kwargs)
            )
            logger.debug(f"{log_prefix}: run_until_complete finished for {target_fn_name}. Result type: {type(result)}")
            
            if not self.is_cancelled:
                logger.debug(f"{log_prefix}: Emitting result_ready signal.")
                self.result_ready.emit(result)
                logger.debug(f"{log_prefix}: result_ready signal emitted.")
            else:
                logger.debug(f"{log_prefix}: Task was cancelled, not emitting result_ready.")
                
        except Exception as e:
            # Ensure logger is defined and accessible here
            # Assuming 'logger' is module-level logger from 'logging.getLogger(__name__)'
            logger.error(f"{log_prefix}: Error in run() - {type(e).__name__}: {e}", exc_info=True)
            if not self.is_cancelled:
                logger.debug(f"{log_prefix}: Emitting error_occurred signal.")
                self.error_occurred.emit(e)
                logger.debug(f"{log_prefix}: error_occurred signal emitted.")
            else:
                logger.debug(f"{log_prefix}: Task was cancelled, not emitting error_occurred for this exception: {e}")
        finally:
            logger.debug(f"{log_prefix}: run() finally block executing.")
            if self._loop:
                logger.debug(f"{log_prefix}: Closing event loop {self._loop}.")
                self._loop.close()
                logger.debug(f"{log_prefix}: Event loop closed.")
            logger.debug(f"{log_prefix}: run() finished.")
    
    def cancel(self):
        """Cancel the async worker"""
        self.is_cancelled = True
        if self._loop and self._loop.is_running():
            # Cancel all pending tasks
            for task in asyncio.all_tasks(self._loop):
                task.cancel()

class TaskManager:
    """Manage background tasks and workers"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(max_workers)
        self.active_tasks: Dict[str, Union[Worker, AsyncWorker]] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self._task_counter = 0
        self._lock = threading.Lock()
        
    def _generate_task_id(self) -> str:
        """Generate unique task ID"""
        with self._lock:
            self._task_counter += 1
            return f"task_{self._task_counter}_{int(time.time())}"
    
    def run_task(self, 
                 fn: Callable, 
                 *args, 
                 task_name: Optional[str] = None,
                 on_result: Optional[Callable] = None,
                 on_error: Optional[Callable] = None,
                 **kwargs) -> str:
        """Run a synchronous task in background"""
        task_id = self._generate_task_id()
        task_name = task_name or f"Task {task_id}"
        
        worker = Worker(fn, *args, **kwargs)
        
        # Connect signals
        if on_result:
            worker.signals.result.connect(on_result)
        if on_error:
            worker.signals.error.connect(on_error)
            
        # Track completion
        def on_finished():
            self._task_completed(task_id, task_name)
        worker.signals.finished.connect(on_finished)
        
        # Store and start
        self.active_tasks[task_id] = worker
        self.thread_pool.start(worker)
        
        logger.debug(f"Started task {task_id}: {task_name}")
        return task_id
    
    def run_async_task(self,
                      async_fn: Callable,
                      *args,
                      task_name: Optional[str] = None,
                      on_result: Optional[Callable] = None,
                      on_error: Optional[Callable] = None,
                      **kwargs) -> str:
        """Run an async task in background"""
        task_id = self._generate_task_id()
        task_name = task_name or f"AsyncTask {task_id}"
        
        worker = AsyncWorker(async_fn, *args, **kwargs)
        
        # Connect signals
        if on_result:
            worker.result_ready.connect(on_result)
        if on_error:
            worker.error_occurred.connect(on_error)
            
        # Track completion
        def on_finished():
            self._task_completed(task_id, task_name)
        worker.finished.connect(on_finished)
        
        # Store and start
        self.active_tasks[task_id] = worker
        worker.start()
        
        logger.debug(f"Started async task {task_id}: {task_name}")
        return task_id
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self.active_tasks:
            worker = self.active_tasks[task_id]
            worker.cancel()
            logger.debug(f"Cancelled task {task_id}")
            return True
        return False
    
    def _task_completed(self, task_id: str, task_name: str):
        """Handle task completion"""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        logger.debug(f"Completed task {task_id}: {task_name}")
    
    def get_active_task_count(self) -> int:
        """Get number of active tasks"""
        return len(self.active_tasks)
    
    def cancel_all_tasks(self):
        """Cancel all running tasks"""
        for task_id in list(self.active_tasks.keys()):
            self.cancel_task(task_id)
        logger.info("Cancelled all active tasks")
    
    def shutdown(self):
        """Shutdown the task manager"""
        self.cancel_all_tasks()
        self.thread_pool.waitForDone(5000)  # Wait up to 5 seconds
        logger.info("TaskManager shutdown complete")

class AsyncTaskManager:
    """Manage async tasks with proper lifecycle management"""
    
    def __init__(self, max_concurrent_tasks: int = 10):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self._task_counter = 0
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4)
        
    async def _generate_task_id(self) -> str:
        """Generate unique task ID"""
        async with self._lock:
            self._task_counter += 1
            return f"async_task_{self._task_counter}_{int(time.time())}"
    
    async def run_async_task(self,
                           coro_fn: Callable,
                           *args,
                           task_name: Optional[str] = None,
                           **kwargs) -> str:
        """Run an async task"""
        task_id = await self._generate_task_id()
        task_name = task_name or f"AsyncTask {task_id}"
        
        # Create and start the task
        async def wrapped_task():
            start_time = time.time()
            try:
                result = await coro_fn(*args, **kwargs)
                execution_time = time.time() - start_time
                
                task_result = TaskResult(
                    task_id=task_id,
                    success=True,
                    result=result,
                    execution_time=execution_time
                )
                self.task_results[task_id] = task_result
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                task_result = TaskResult(
                    task_id=task_id,
                    success=False,
                    error=e,
                    execution_time=execution_time
                )
                self.task_results[task_id] = task_result
                logger.error(f"Async task {task_id} failed: {e}", exc_info=True)
                raise
            finally:
                # Clean up
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
        
        task = asyncio.create_task(wrapped_task(), name=task_name)
        self.active_tasks[task_id] = task
        
        logger.debug(f"Started async task {task_id}: {task_name}")
        return task_id
    
    async def run_sync_task(self,
                          fn: Callable,
                          *args,
                          task_name: Optional[str] = None,
                          **kwargs) -> str:
        """Run a sync function in executor"""
        task_id = await self._generate_task_id()
        task_name = task_name or f"SyncTask {task_id}"
        
        loop = asyncio.get_running_loop()
        
        async def wrapped_task():
            start_time = time.time()
            try:
                result = await loop.run_in_executor(self._executor, fn, *args)
                execution_time = time.time() - start_time
                
                task_result = TaskResult(
                    task_id=task_id,
                    success=True,
                    result=result,
                    execution_time=execution_time
                )
                self.task_results[task_id] = task_result
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                task_result = TaskResult(
                    task_id=task_id,
                    success=False,
                    error=e,
                    execution_time=execution_time
                )
                self.task_results[task_id] = task_result
                logger.error(f"Sync task {task_id} failed: {e}", exc_info=True)
                raise
            finally:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
        
        task = asyncio.create_task(wrapped_task(), name=task_name)
        self.active_tasks[task_id] = task
        
        logger.debug(f"Started sync task {task_id}: {task_name}")
        return task_id
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.debug(f"Cancelled async task {task_id}")
            return True
        return False
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Wait for a task to complete"""
        if task_id in self.active_tasks:
            try:
                await asyncio.wait_for(self.active_tasks[task_id], timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Task {task_id} timed out")
                return None
        
        return self.task_results.get(task_id)
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get result of completed task"""
        return self.task_results.get(task_id)
    
    def get_active_task_count(self) -> int:
        """Get number of active tasks"""
        return len(self.active_tasks)
    
    async def cancel_all_tasks(self):
        """Cancel all running tasks"""
        tasks_to_cancel = list(self.active_tasks.values())
        for task in tasks_to_cancel:
            task.cancel()
        
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        
        self.active_tasks.clear()
        logger.info("Cancelled all async tasks")
    
    def shutdown(self):
        """Shutdown the async task manager"""
        # Cancel all tasks synchronously
        for task in self.active_tasks.values():
            task.cancel()
        
        # Shutdown executor
        self._executor.shutdown(wait=False)
        logger.info("AsyncTaskManager shutdown complete")

# Global instances
_task_manager: Optional[TaskManager] = None
_async_task_manager: Optional[AsyncTaskManager] = None

def get_task_manager() -> TaskManager:
    """Get or create global task manager"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager

def get_async_task_manager() -> AsyncTaskManager:
    """Get or create global async task manager"""
    global _async_task_manager
    if _async_task_manager is None:
        _async_task_manager = AsyncTaskManager()
    return _async_task_manager

# Convenience functions
def run_in_background(fn: Callable, 
                     *args, 
                     task_name: Optional[str] = None,
                     on_result: Optional[Callable] = None,
                     on_error: Optional[Callable] = None,
                     **kwargs) -> str:
    """Run function in background thread"""
    return get_task_manager().run_task(
        fn, *args, 
        task_name=task_name,
        on_result=on_result,
        on_error=on_error,
        **kwargs
    )

async def run_async_in_background(async_fn: Callable,
                                *args,
                                task_name: Optional[str] = None,
                                **kwargs) -> str:
    """Run async function in background"""
    return await get_async_task_manager().run_async_task(
        async_fn, *args,
        task_name=task_name,
        **kwargs
    )
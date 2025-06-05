from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot

class WorkerSignals(QObject):
    """Signals for worker thread."""
    
    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

class Worker(QRunnable):
    """Worker thread for background tasks."""
    
    def __init__(self, fn, *args, **kwargs):
        """Initialize the worker.
        
        Args:
            fn: Function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function
        """
        super().__init__()
        
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        
    @pyqtSlot()
    def run(self):
        """Execute the function in the thread."""
        try:
            self.signals.started.emit()
            result = self.fn(
                *self.args, 
                progress_callback=self.signals.progress.emit,
                status_callback=self.signals.status.emit,
                **self.kwargs
            )
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()
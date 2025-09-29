"""Qt worker objects for background operations."""

import threading

from PyQt5 import QtCore

from app.services import (
    MeshOperationError,
    compute_distance,
    DistanceComputationCancelled,
)


class DistanceComputationWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object, object)
    error = QtCore.pyqtSignal(str)
    cancelled = QtCore.pyqtSignal()

    def __init__(self, source_mesh, target_mesh, reduction=None):
        super().__init__()
        self._source = source_mesh.copy()
        self._target = target_mesh.copy()
        self._reduction = reduction
        self._cancel_requested = False
        self._cancel_lock = threading.Lock()
        self._current_filter = None

    @QtCore.pyqtSlot()
    def run(self):
        try:
            result_mesh, min_dist = compute_distance(
                self._source,
                self._target,
                reduction=self._reduction,
                abort_event=self._should_cancel,
                filter_callback=self._register_filter,
            )
        except DistanceComputationCancelled:
            self.cancelled.emit()
            return
        except MeshOperationError as exc:  # pragma: no cover - signalized upwards
            self.error.emit(str(exc))
            return
        finally:
            self._register_filter(None)

        self.finished.emit(result_mesh, min_dist)

    def cancel(self):
        with self._cancel_lock:
            self._cancel_requested = True
            filt = self._current_filter
        thread = self.thread()
        if thread is not None:
            thread.requestInterruption()
        if filt is not None:
            try:
                filt.AbortExecuteOn()
            except AttributeError:
                try:
                    filt.SetAbortExecute(True)
                except AttributeError:
                    pass
            try:
                execu = filt.GetExecutive()
                if execu is not None:
                    execu.SetAbortExecute(1)
            except AttributeError:
                pass

    def _should_cancel(self):
        interrupted = False
        thread = QtCore.QThread.currentThread()
        if thread is not None:
            interrupted = thread.isInterruptionRequested()
        with self._cancel_lock:
            return self._cancel_requested or interrupted

    def _register_filter(self, filt):
        with self._cancel_lock:
            self._current_filter = filt

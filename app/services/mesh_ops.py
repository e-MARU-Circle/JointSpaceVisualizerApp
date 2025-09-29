import logging
from typing import Callable, Optional, Tuple

import pyvista as pv
import vtk

logger = logging.getLogger(__name__)


class MeshOperationError(RuntimeError):
    """Raised when a mesh-related operation fails."""


class DistanceComputationCancelled(RuntimeError):
    """Raised when distance computation has been cancelled."""


def load_mesh(path: str) -> pv.PolyData:
    try:
        mesh = pv.read(path)
    except Exception as exc:  # pragma: no cover - PyVista provides detail
        logger.exception("Failed to load mesh from %s", path)
        raise MeshOperationError(str(exc)) from exc

    logger.info("Loaded mesh from %s (%d points)", path, mesh.n_points)
    return mesh


def save_mesh(mesh: pv.DataSet, path: str) -> None:
    try:
        mesh.save(path)
    except Exception as exc:  # pragma: no cover - PyVista provides detail
        logger.exception("Failed to save mesh to %s", path)
        raise MeshOperationError(str(exc)) from exc

    logger.info("Saved mesh to %s", path)


def _extract_scalar_array(mesh: pv.DataSet, name: str):
    if name in mesh.point_data:
        return mesh.point_data[name]
    if name in mesh.cell_data:
        return mesh.cell_data[name]
    if name in mesh.field_data:
        return mesh.field_data[name]
    return None


def save_colored_mesh(mesh: pv.DataSet, lut: pv.LookupTable, path: str, scalar_name: str = "Distance") -> None:
    distances = _extract_scalar_array(mesh, scalar_name)
    if distances is None or len(distances) == 0:
        message = f"Mesh missing '{scalar_name}' scalars; cannot bake colors"
        logger.error(message)
        raise MeshOperationError(message)

    import numpy as np

    colored_mesh = mesh.copy()
    try:
        rng_min, rng_max = lut.scalar_range
        if rng_max <= rng_min:
            rng_min, rng_max = float(np.min(distances)), float(np.max(distances))
            if rng_max <= rng_min:
                rng_max = rng_min + 1.0
        norm = (np.asarray(distances) - rng_min) / (rng_max - rng_min)
        norm = np.clip(norm, 0.0, 1.0)
        cmap = lut.cmap
        rgba = cmap(norm)
        colored_mesh.point_data['RGB'] = (rgba[:, :3] * 255).astype(np.uint8)
        colored_mesh.save(path, binary=True)
    except Exception as exc:  # pragma: no cover - PyVista provides detail
        logger.exception("Failed to save colored mesh to %s", path)
        raise MeshOperationError(str(exc)) from exc

    logger.info("Saved colored mesh to %s", path)


def compute_distance(
    source_mesh: pv.PolyData,
    target_mesh: pv.PolyData,
    reduction: Optional[float] = None,
    abort_event: Optional[Callable[[], bool]] = None,
    filter_callback: Optional[Callable[[vtk.vtkDistancePolyDataFilter], None]] = None,
) -> Tuple[pv.PolyData, Optional[float]]:
    def _should_abort() -> bool:
        if abort_event is None:
            return False
        try:
            return bool(abort_event())
        except TypeError:
            checker = getattr(abort_event, "is_set", None)
            if checker is None:
                return False
            try:
                return bool(checker())
            except Exception:
                return False
        except Exception:
            return False

    try:
        src = source_mesh
        tgt = target_mesh
        if _should_abort():
            logger.info("Distance computation aborted before processing")
            raise DistanceComputationCancelled()
        if reduction is not None:
            src = src.decimate(reduction)
            if _should_abort():
                logger.info("Distance computation aborted after source decimation")
                raise DistanceComputationCancelled()
            tgt = tgt.decimate(reduction)
            logger.info("Applied decimation with reduction %.2f", reduction)
            if _should_abort():
                logger.info("Distance computation aborted after target decimation")
                raise DistanceComputationCancelled()

        dist_filter = vtk.vtkDistancePolyDataFilter()
        dist_filter.SetInputData(0, src)
        dist_filter.SetInputData(1, tgt)
        dist_filter.SignedDistanceOff()

        if filter_callback is not None:
            try:
                filter_callback(dist_filter)
            except Exception:  # noqa: S110 - defensive
                logger.debug("Filter callback raised", exc_info=True)

        aborted = {"flag": False}

        if abort_event is not None:
            def _vtk_abort(caller, event):  # pragma: no cover - callback invoked by VTK
                if _should_abort():
                    aborted["flag"] = True
                    try:
                        caller.AbortExecuteOn()
                    except AttributeError:
                        caller.SetAbortExecute(True)
                    try:
                        execu = caller.GetExecutive()
                    except AttributeError:
                        execu = None
                    if execu is not None:
                        try:
                            execu.SetAbortExecute(1)
                        except AttributeError:
                            pass

            for evt in (
                vtk.vtkCommand.AbortCheckEvent,
                vtk.vtkCommand.ProgressEvent,
                vtk.vtkCommand.StartEvent,
                vtk.vtkCommand.EndEvent,
            ):
                dist_filter.AddObserver(evt, _vtk_abort)

        dist_filter.Update()
        if _should_abort():
            aborted["flag"] = True

        if aborted["flag"] or _should_abort():
            try:
                dist_filter.AbortExecuteOff()
            except AttributeError:  # pragma: no cover - older VTK
                pass
            logger.info("Distance computation aborted during filter execution")
            raise DistanceComputationCancelled()

        result = pv.wrap(dist_filter.GetOutput())
        distances = result.get_array('Distance')
    except DistanceComputationCancelled:
        raise
    except Exception as exc:  # pragma: no cover - VTK provides detail
        if aborted["flag"] or _should_abort():
            logger.info("Distance computation aborted during execution")
            raise DistanceComputationCancelled() from exc
        logger.exception("Distance computation failed")
        raise MeshOperationError(str(exc)) from exc

    min_distance: Optional[float] = None
    if distances is not None and len(distances) > 0:
        min_distance = float(distances.min())
        max_distance = float(distances.max())
        logger.info(
            "Distance computed; min=%.4f max=%.4f (points=%d)",
            min_distance,
            max_distance,
            len(distances),
        )
    else:
        logger.warning("Distance result missing scalars")

    return result, min_distance


def create_custom_colormap() -> pv.LookupTable:
    """Construct a smooth lookup table matching the joint-space color spec."""
    from matplotlib.colors import LinearSegmentedColormap

    color_points = [
        (0.0, (1.0, 0.0, 0.0)),
        (1.0, (1.0, 0.0, 0.0)),
        (1.6, (1.0, 1.0, 0.0)),
        (2.5, (0.0, 1.0, 0.0)),
        (3.3, (0.0, 1.0, 1.0)),
        (4.0, (0.0, 0.0, 1.0)),
        (5.0, (0.0, 0.0, 1.0)),
    ]
    positions = [value / 5.0 for value, _ in color_points]
    colors = [rgb for _, rgb in color_points]
    cmap = LinearSegmentedColormap.from_list(
        "jointspace", list(zip(positions, colors))
    )
    lut = pv.LookupTable()
    lut.apply_cmap(cmap, n_values=256)
    lut.scalar_range = (0.0, 5.0)
    logger.debug("Created custom lookup table with range %s", lut.scalar_range)
    return lut

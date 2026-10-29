from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat


REPOSITORY_ROOT = Path(__file__).parents[1]


def _write_synthetic_dxpx(path: Path, lap_count: int) -> Path:
    laps = [
        {
            "Header": {"TrackName": "Synthetic Circuit", "NRun": index + 1},
            "Data": {
                "sLap": np.array([0.0, 1.0, 2.0]),
                "gCarPotential": np.array([1.0 + index, 2.0 + index, 3.0 + index]),
            },
        }
        for index in range(lap_count)
    ]
    if lap_count == 1:
        savemat(path, {"D": laps[0]})
    else:
        entries = np.empty((1, lap_count), dtype=object)
        for index, lap in enumerate(laps):
            entries[0, index] = lap
        savemat(path, {"D": entries})
    return path


@dataclass(frozen=True)
class LocalExploration:
    raw_directory: Path
    dxpx_directory: Path
    run_files: tuple[Path, ...]
    track_name: str
    workbook: Path


def _require_files(directory: Path, pattern: str, purpose: str) -> tuple[Path, ...]:
    files = tuple(sorted(directory.rglob(pattern))) if directory.is_dir() else ()
    if not files:
        pytest.fail(
            f"Local sample data for {purpose} is missing: expected {pattern} under {directory}. "
            "Provision the approved local test-data folders described in README.md; "
            "these files are intentionally not stored in Git."
        )
    return files


@pytest.fixture
def sample_dxpx() -> Path:
    return _require_files(REPOSITORY_ROOT / "DATA_dXpx", "*.dXpx", "DXPX parsing")[0]


@pytest.fixture
def sample_exploration() -> LocalExploration:
    from canopy_processor import load_dxpx
    from canopy_processor.turn_zones import list_circuit_names
    from canopy_processor.ui.discovery import discover_dataset

    raw_root = REPOSITORY_ROOT / "DATA_Raw"
    workbook = REPOSITORY_ROOT / "CircuitsData_Canopy_Hypercar.xlsx"
    studies = tuple(sorted(raw_root.rglob("exploration-map.json"))) if raw_root.is_dir() else ()
    compatible_pairs = []
    for metadata_file in studies:
        raw_directory = metadata_file.parent
        if (
            not (raw_directory / "scalar-inputs.csv").is_file()
            or not any(
                child.is_dir()
                and child.name.isdigit()
                and (child / "job-document.json").is_file()
                for child in raw_directory.iterdir()
            )
        ):
            continue
        discovery = discover_dataset(raw_directory, workbook if workbook.is_file() else None)
        dxpx_directory = discovery.dxpx_directory
        run_files = tuple(sorted(dxpx_directory.rglob("*.dXpx"))) if dxpx_directory and dxpx_directory.is_dir() else ()
        if len(discovery.variables) < 2 or not run_files:
            continue
        first_run = load_dxpx(run_files[0])
        if "gCarPotential" not in first_run.data:
            continue
        track_name = first_run.track_name
        if not track_name:
            continue
        compatible_pairs.append((raw_directory, dxpx_directory, run_files, track_name))

    if not compatible_pairs:
        pytest.fail(
            "A compatible local integration study is missing. DATA_Raw must contain a study with "
            "exploration metadata and at least two variables, paired with numbered DXPX runs under "
            "DATA_dXpx. Provision representative local data; files are intentionally not stored in Git."
        )
    if not workbook.is_file():
        pytest.fail(
            f"Local integration tests require the circuit workbook at {workbook}; "
            "the workbook is intentionally not stored in Git."
        )

    for raw_directory, dxpx_directory, run_files, track_name in compatible_pairs:
        circuit_names = list_circuit_names(workbook)
        if track_name in circuit_names:
            return LocalExploration(raw_directory, dxpx_directory, run_files, track_name, workbook)
    expected_tracks = ", ".join(sorted({pair[3] for pair in compatible_pairs}))
    pytest.fail(
        f"The local circuit workbook {workbook} must contain a track matching a paired DXPX run "
        f"(available tracks: {expected_tracks})."
    )


@pytest.fixture
def sample_baseline_dxpx(sample_exploration: LocalExploration) -> Path:
    from canopy_processor import load_dxpx_laps

    baseline_files = _require_files(
        REPOSITORY_ROOT / "BaselineExample", "*.dXpx", "same-track baseline comparisons"
    )
    for baseline_file in baseline_files:
        laps = load_dxpx_laps(baseline_file)
        if laps and all(lap.track_name == sample_exploration.track_name for lap in laps):
            return baseline_file
    pytest.fail(
        "No local baseline DXPX file matches the selected exploration track "
        f"{sample_exploration.track_name!r}. Provision a comparable baseline for the same track."
    )


@pytest.fixture
def multi_lap_baseline_dxpx() -> Path:
    from canopy_processor import load_dxpx_laps

    baseline_files = _require_files(
        REPOSITORY_ROOT / "BaselineExample", "*.dXpx", "multi-lap baseline parsing"
    )
    for baseline_file in baseline_files:
        if len(load_dxpx_laps(baseline_file)) > 1:
            return baseline_file
    pytest.fail("BaselineExample must contain at least one multi-lap DXPX file for parser integration tests.")


@pytest.fixture
def synthetic_single_lap_dxpx(tmp_path: Path) -> Path:
    return _write_synthetic_dxpx(tmp_path / "synthetic-single.dXpx", 1)


@pytest.fixture
def synthetic_multi_lap_dxpx(tmp_path: Path) -> Path:
    return _write_synthetic_dxpx(tmp_path / "synthetic-multi.dXpx", 3)
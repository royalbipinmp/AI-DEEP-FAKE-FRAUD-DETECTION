from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import train_test_split


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


@dataclass
class VideoEntry:
    video_path: Path
    label: int
    split_key: str
    source_name: str


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    cleaned = re.sub(r"_(deepfake|fake|real|original|video|image)+$", "", cleaned)
    return cleaned or value.lower()


def infer_identity_key(path: Path) -> str:
    stem = normalize_name(path.stem)
    parts = [part for part in stem.split("_") if part]
    if len(parts) >= 3:
        return "_".join(parts[:3])
    if len(parts) >= 2:
        return "_".join(parts[:2])
    return stem


def build_metadata_identity_map(metadata_path: Path) -> dict[str, str]:
    if not metadata_path.exists():
        return {}

    table = pd.read_csv(metadata_path)
    lowered = {column.lower(): column for column in table.columns}
    identity_column = None
    for candidate in ["person_id", "person", "id", "name"]:
        if candidate in lowered:
            identity_column = lowered[candidate]
            break

    if identity_column is None:
        return {}

    candidate_name_columns = [
        lowered[column]
        for column in ["video", "video_name", "filename", "file_name", "fake_video", "real_video"]
        if column in lowered
    ]

    if not candidate_name_columns:
        return {}

    identity_map: dict[str, str] = {}
    for _, row in table.iterrows():
        identity_value = normalize_name(str(row[identity_column]))
        for column in candidate_name_columns:
            raw_value = str(row[column])
            if raw_value and raw_value != "nan":
                identity_map[normalize_name(Path(raw_value).stem)] = identity_value
    return identity_map


def list_videos(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def build_entries(dataset_config: dict) -> list[VideoEntry]:
    dataset_root = Path(dataset_config["root"]).resolve()
    fake_dir = dataset_root / dataset_config["fake_dir"]
    real_dir = dataset_root / dataset_config["real_dir"]
    metadata_csv = str(dataset_config.get("metadata_csv", "") or "").strip()
    metadata_path = (dataset_root / metadata_csv) if metadata_csv else Path("__no_metadata__")
    identity_map = build_metadata_identity_map(metadata_path)

    entries: list[VideoEntry] = []
    for label_name, label_value, root in [("fake", 1, fake_dir), ("real", 0, real_dir)]:
        for video_path in list_videos(root):
            normalized = normalize_name(video_path.stem)
            split_key = identity_map.get(normalized) or infer_identity_key(video_path)
            entries.append(
                VideoEntry(
                    video_path=video_path,
                    label=label_value,
                    split_key=split_key,
                    source_name=video_path.name,
                )
            )

    max_per_class = dataset_config.get("max_videos_per_class")
    if max_per_class:
        rng = random.Random(dataset_config.get("random_seed", 42))
        by_class: dict[int, list[VideoEntry]] = defaultdict(list)
        for entry in entries:
            by_class[entry.label].append(entry)
        trimmed: list[VideoEntry] = []
        for label_value, samples in by_class.items():
            rng.shuffle(samples)
            trimmed.extend(samples[: int(max_per_class)])
        entries = trimmed

    return entries


def split_entries(entries: list[VideoEntry], dataset_config: dict) -> dict[str, list[VideoEntry]]:
    random_seed = int(dataset_config.get("random_seed", 42))
    train_ratio = float(dataset_config.get("train_ratio", 0.8))
    val_ratio = float(dataset_config.get("val_ratio", 0.1))
    test_ratio = float(dataset_config.get("test_ratio", 0.1))

    grouped: dict[str, list[VideoEntry]] = defaultdict(list)
    for entry in entries:
        grouped[f"{entry.label}:{entry.split_key}"].append(entry)

    group_items = list(grouped.items())
    group_labels = [value[0].split(":")[0] for value in group_items]

    def has_safe_stratify(labels: list[str]) -> bool:
        return bool(labels) and len(set(labels)) > 1 and min(labels.count(label) for label in set(labels)) >= 2

    if len(group_items) < 3 or not has_safe_stratify(group_labels):
        shuffled_items = group_items[:]
        random.Random(random_seed).shuffle(shuffled_items)

        total_items = len(shuffled_items)
        train_count = max(1, int(round(total_items * train_ratio)))
        remaining_after_train = max(0, total_items - train_count)
        val_count = 1 if remaining_after_train >= 2 else 0

        train_items = shuffled_items[:train_count]
        val_items = shuffled_items[train_count:train_count + val_count]
        test_items = shuffled_items[train_count + val_count:]

        if not test_items and val_items:
            test_items = [val_items.pop()]
        if not val_items and len(test_items) > 1:
            val_items = [test_items.pop(0)]

        return {
            "train": [entry for _, group in train_items for entry in group],
            "val": [entry for _, group in val_items for entry in group],
            "test": [entry for _, group in test_items for entry in group],
        }

    train_items, temp_items = train_test_split(
        group_items,
        test_size=(1.0 - train_ratio),
        random_state=random_seed,
        stratify=group_labels,
    )

    temp_ratio = val_ratio + test_ratio
    val_share = val_ratio / temp_ratio if temp_ratio else 0.5
    temp_labels = [value[0].split(":")[0] for value in temp_items]
    if len(temp_items) < 2 or not has_safe_stratify(temp_labels):
        shuffled_temp = temp_items[:]
        random.Random(random_seed).shuffle(shuffled_temp)
        split_index = 1 if len(shuffled_temp) > 1 else 0
        val_items = shuffled_temp[:split_index]
        test_items = shuffled_temp[split_index:]
    else:
        val_items, test_items = train_test_split(
            temp_items,
            test_size=(1.0 - val_share),
            random_state=random_seed,
            stratify=temp_labels,
        )

    split_map = {
        "train": [entry for _, group in train_items for entry in group],
        "val": [entry for _, group in val_items for entry in group],
        "test": [entry for _, group in test_items for entry in group],
    }
    return split_map


def choose_frame_indexes(frame_count: int, frames_per_video: int) -> list[int]:
    if frame_count <= 0:
        return []
    if frame_count <= frames_per_video:
        return list(range(frame_count))
    return np.linspace(0, frame_count - 1, num=frames_per_video, dtype=int).tolist()


def extract_frames(entry: VideoEntry, split: str, output_root: Path, frames_per_video: int) -> list[dict[str, object]]:
    capture = cv2.VideoCapture(str(entry.video_path))
    if not capture.isOpened():
        return []

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_indexes = choose_frame_indexes(frame_count, frames_per_video)
    rows: list[dict[str, object]] = []

    for frame_number, frame_index in enumerate(frame_indexes):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        success, frame = capture.read()
        if not success or frame is None:
            continue

        target_dir = output_root / "frames" / split / ("fake" if entry.label == 1 else "real")
        target_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{entry.video_path.stem}__frame_{frame_number:02d}.jpg"
        target_path = target_dir / file_name
        cv2.imwrite(str(target_path), frame)

        rows.append(
            {
                "split": split,
                "label": entry.label,
                "label_name": "fake" if entry.label == 1 else "real",
                "video_path": str(entry.video_path),
                "frame_path": str(target_path),
                "frame_index": int(frame_index),
                "identity_key": entry.split_key,
                "source_name": entry.source_name,
            }
        )

    capture.release()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Kaggle deepfake videos for fine-tuning.")
    parser.add_argument(
        "--config",
        default="training/deepfake_finetune.yaml",
        help="Path to YAML config file.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    dataset_config = config["dataset"]
    output_root = Path(dataset_config["processed_root"]).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    entries = build_entries(dataset_config)
    if not entries:
        raise RuntimeError("No videos were found. Check the dataset root and folder names in the config.")

    split_map = split_entries(entries, dataset_config)
    frames_per_video = int(dataset_config.get("frames_per_video", 8))
    manifest_rows: list[dict[str, object]] = []

    for split, split_entries_list in split_map.items():
        for entry in split_entries_list:
            manifest_rows.extend(extract_frames(entry, split, output_root, frames_per_video))

    manifest_path = output_root / "frame_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)

    summary = {
        "videos": {split: len(values) for split, values in split_map.items()},
        "frames": {
            split: sum(1 for row in manifest_rows if row["split"] == split)
            for split in ["train", "val", "test"]
        },
        "manifest": str(manifest_path),
    }
    (output_root / "prepare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

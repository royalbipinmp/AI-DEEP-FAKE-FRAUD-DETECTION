from __future__ import annotations

import argparse
from pathlib import Path

import kagglehub


DATASET_HANDLE = "bhargavichauhan/deepfake-videos-merged-dataset"


def download_class_subset(label: str, count: int, output_root: Path, start_index: int = 0) -> None:
    target_dir = output_root / label
    target_dir.mkdir(parents=True, exist_ok=True)

    for index in range(start_index, start_index + count):
        relative_path = f"merged_vid_dataset/{label}/{label}_{index}.mp4"
        print(f"Downloading {relative_path}")
        kagglehub.dataset_download(
            DATASET_HANDLE,
            path=relative_path,
            output_dir=str(output_root),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a small real/fake subset from the merged Kaggle deepfake dataset.")
    parser.add_argument("--output", default="training/datasets/merged-subset", help="Target dataset folder.")
    parser.add_argument("--real-count", type=int, default=20, help="Number of real videos to download.")
    parser.add_argument("--fake-count", type=int, default=20, help="Number of fake videos to download.")
    parser.add_argument("--real-start", type=int, default=0, help="Starting index for real videos.")
    parser.add_argument("--fake-start", type=int, default=0, help="Starting index for fake videos.")
    args = parser.parse_args()

    output_root = Path(args.output).resolve()
    download_class_subset("real", args.real_count, output_root, args.real_start)
    download_class_subset("fake", args.fake_count, output_root, args.fake_start)

    print(f"Subset ready at: {output_root}")


if __name__ == "__main__":
    main()

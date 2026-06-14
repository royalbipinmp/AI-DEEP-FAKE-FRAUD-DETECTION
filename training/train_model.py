from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from torch.utils.data import DataLoader, Dataset
from transformers import AutoImageProcessor, AutoModelForImageClassification
import yaml


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class FrameDataset(Dataset):
    def __init__(self, rows: pd.DataFrame, processor):
        self.rows = rows.reset_index(drop=True)
        self.processor = processor

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        row = self.rows.iloc[index]
        image = Image.open(row["frame_path"]).convert("RGB")
        encoded = self.processor(images=image, return_tensors="pt")
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = torch.tensor(int(row["label"]), dtype=torch.long)
        return item


def make_loader(rows: pd.DataFrame, processor, batch_size: int, shuffle: bool, num_workers: int) -> DataLoader:
    dataset = FrameDataset(rows, processor)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers)


def evaluate(model, loader, device) -> dict[str, float]:
    model.eval()
    all_labels = []
    all_predictions = []
    total_loss = 0.0
    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(**batch)
            loss = criterion(outputs.logits, labels)
            predictions = torch.argmax(outputs.logits, dim=1)

            total_loss += float(loss.item()) * labels.size(0)
            all_labels.extend(labels.cpu().tolist())
            all_predictions.extend(predictions.cpu().tolist())

    if not all_labels:
        return {
            "loss": 0.0,
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }

    accuracy = accuracy_score(all_labels, all_predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_labels,
        all_predictions,
        average="binary",
        zero_division=0,
    )

    return {
        "loss": total_loss / max(len(all_labels), 1),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune the deepfake classifier on prepared frames.")
    parser.add_argument(
        "--config",
        default="training/deepfake_finetune.yaml",
        help="Path to YAML config file.",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config).resolve())
    dataset_config = config["dataset"]
    training_config = config["training"]

    manifest_path = Path(dataset_config["processed_root"]).resolve() / "frame_manifest.csv"
    if not manifest_path.exists():
        raise RuntimeError(
            "Prepared manifest not found. Run training/prepare_kaggle_dataset.py first."
        )

    frame_table = pd.read_csv(manifest_path)
    processor = AutoImageProcessor.from_pretrained(training_config["model_id"], local_files_only=True)
    model = AutoModelForImageClassification.from_pretrained(
        training_config["model_id"],
        local_files_only=True,
        num_labels=2,
        ignore_mismatched_sizes=True,
    )

    output_dir = Path(training_config["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if training_config.get("frame_sample_limit"):
        limit = int(training_config["frame_sample_limit"])
        frame_table = frame_table.groupby(["split", "label"], group_keys=False).head(limit)

    train_rows = frame_table[frame_table["split"] == "train"]
    val_rows = frame_table[frame_table["split"] == "val"]
    test_rows = frame_table[frame_table["split"] == "test"]

    batch_size = int(training_config.get("batch_size", 8))
    num_workers = int(training_config.get("num_workers", 0))
    train_loader = make_loader(train_rows, processor, batch_size, True, num_workers)
    val_loader = make_loader(val_rows, processor, batch_size, False, num_workers)
    test_loader = make_loader(test_rows, processor, batch_size, False, num_workers)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training_config.get("learning_rate", 2e-5)),
        weight_decay=float(training_config.get("weight_decay", 0.01)),
    )

    best_state = None
    best_val_f1 = -1.0
    history = []

    for epoch in range(int(training_config.get("epochs", 3))):
        model.train()
        running_loss = 0.0
        total_examples = 0

        for batch in train_loader:
            labels = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}

            optimizer.zero_grad()
            outputs = model(**batch)
            loss = criterion(outputs.logits, labels)
            loss.backward()
            optimizer.step()

            running_loss += float(loss.item()) * labels.size(0)
            total_examples += labels.size(0)

        train_loss = running_loss / max(total_examples, 1)
        val_metrics = evaluate(model, val_loader, device)
        epoch_metrics = {
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "val_loss": val_metrics["loss"],
            "val_accuracy": val_metrics["accuracy"],
            "val_precision": val_metrics["precision"],
            "val_recall": val_metrics["recall"],
            "val_f1": val_metrics["f1"],
        }
        history.append(epoch_metrics)
        print(json.dumps(epoch_metrics))

        if val_metrics["f1"] > best_val_f1:
            best_val_f1 = val_metrics["f1"]
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }

    if best_state is not None:
        model.load_state_dict(best_state)

    test_metrics = evaluate(model, test_loader, device)
    final_metrics = {"best_val_f1": best_val_f1, "test": test_metrics, "history": history}

    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)
    (output_dir / "metrics.json").write_text(json.dumps(final_metrics, indent=2), encoding="utf-8")
    print(json.dumps(final_metrics, indent=2))


if __name__ == "__main__":
    main()

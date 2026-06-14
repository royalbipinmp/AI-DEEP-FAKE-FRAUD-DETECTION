# Deepfake Fine-Tuning Pipeline

This folder contains the first full training path for improving the TruthShield detector with the Kaggle dataset you shared.

## Expected dataset layout

Place the downloaded Kaggle dataset under:

`training/datasets/dfd-original`

The DFD configuration now expects the dataset root to contain folders like:

- `DFD_manipulated_sequences/DFD_manipulated_sequences`
- `DFD_original sequences/DFD_original_sequences`

These names can be changed in `training/deepfake_finetune.yaml`.

## If you want to pull the dataset directly from Kaggle

This machine now has the Kaggle CLI installed, but it does not yet have a Kaggle API key.

To enable direct download, place your Kaggle API file here:

`C:\Users\Dell\.kaggle\kaggle.json`

Or download the dataset zip manually and unpack it into:

`training/datasets/dfd-original`

## Step 1: Prepare frame dataset

```powershell
python training/prepare_kaggle_dataset.py --config training/deepfake_finetune.yaml
```

This will:

- scan real and fake videos
- split them into train / validation / test
- keep identity groups apart when possible
- extract a small number of representative frames
- write `training/processed/kaggle-deepfake/frame_manifest.csv`

## Step 2: Fine-tune the model

```powershell
python training/train_model.py --config training/deepfake_finetune.yaml
```

This will:

- load the current ViT deepfake model
- fine-tune it on the prepared frames
- evaluate validation and test performance
- save the improved model to the output directory from the config

## One-command run

After the dataset is present, you can run both steps with:

```powershell
powershell -ExecutionPolicy Bypass -File training/run_dfd_training.ps1
```

## Quick 5-minute version

If you want a much faster demo-style improvement run, use a very small subset instead of the full dataset.

Create this layout:

`training/datasets/dfd-quick/real`

`training/datasets/dfd-quick/fake`

Then place a small number of DFD videos there, for example:

- 20 to 24 real videos
- 20 to 24 fake videos

Keep the total size under about 700 MB.

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File training/run_quick_training.ps1
```

This quick mode uses:

- fewer videos
- fewer frames per video
- one short training pass

It is not final-quality training, but it is the fastest practical way to get a better local model quickly.

## What happens after training

The detection backend in `app.py` now automatically prefers the fine-tuned checkpoint at:

`training/checkpoints/vit-kaggle-deepfake`

If that folder exists, TruthShield will use the improved model automatically on the next backend start.
If it does not exist yet, the app continues using the current baseline model.

## Notes

- The current pipeline is designed to reduce false positives by learning from real and fake video frames in your own dataset.
- Once a fine-tuned model is saved, we can update `app.py` to load that local checkpoint instead of the current pretrained baseline.
- For stronger results later, we can add:
  - face-only training
  - full-frame plus face-branch fusion
  - hard-example mining for webcam-style real clips

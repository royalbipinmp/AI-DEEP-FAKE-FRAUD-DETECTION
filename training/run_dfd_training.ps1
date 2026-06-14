$datasetRoot = "training/datasets/dfd-original"
$configPath = "training/deepfake_finetune.yaml"

if (-not (Test-Path $datasetRoot)) {
    Write-Host "Dataset not found at $datasetRoot" -ForegroundColor Yellow
    Write-Host "Download and unpack the DFD Kaggle dataset first." -ForegroundColor Yellow
    exit 1
}

python training/prepare_kaggle_dataset.py --config $configPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python training/train_model.py --config $configPath
exit $LASTEXITCODE

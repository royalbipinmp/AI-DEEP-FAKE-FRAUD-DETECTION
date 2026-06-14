$datasetRoot = "training/datasets/dfd-quick"
$configPath = "training/deepfake_quick_finetune.yaml"

if (-not (Test-Path $datasetRoot)) {
    Write-Host "Quick dataset not found at $datasetRoot" -ForegroundColor Yellow
    Write-Host "Create two folders: real and fake, then place a small DFD subset inside them." -ForegroundColor Yellow
    exit 1
}

python training/prepare_kaggle_dataset.py --config $configPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python training/train_model.py --config $configPath
exit $LASTEXITCODE

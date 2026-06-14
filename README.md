# TruthShield

TruthShield is a local AI-powered deepfake fraud detection project with a Flask backend and a multi-page frontend. It lets users register, sign in, upload image, video, or audio files, run a detection workflow, save scan history, and review results in an admin dashboard.

## Features

- Image, video, and audio upload workflow
- Detection result with confidence score, summary, notes, and signal breakdown
- User registration and login
- Detection history for signed-in users
- Admin dashboard for monitoring users and recent detections
- MySQL-first database setup with automatic SQLite fallback
- Training utilities for fine-tuning the image model in the `training/` folder

## Project Structure

```text
.
|-- app.py
|-- index.html
|-- upload.html
|-- login.html
|-- register.html
|-- history.html
|-- admin.html
|-- *.js / *.css
|-- training/
|   |-- README.md
|   |-- train_model.py
|   |-- prepare_kaggle_dataset.py
|   `-- *.yaml
`-- uploads/
```

## Tech Stack

- Frontend: HTML, CSS, JavaScript
- Backend: Python With Flask 
- Database: MySQL or SQLite
- AI/ML: PyTorch, Transformers, OpenCV, Pillow, NumPy

## Local Setup

### 1. Clone the repository

```powershell
git clone https://github.com/royalbipinmp/AI-DEEP-FAKE-FRAUD-DETECTION.git
cd AI-DEEP-FAKE-FRAUD-DETECTION
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

This project uses the libraries imported in `app.py`. If you do not already have them installed, install at least:

```powershell
pip install flask opencv-python mysql-connector-python numpy torch pillow transformers werkzeug
```

### 4. Start the backend

```powershell
python app.py
```

The Flask API runs on:

`http://127.0.0.1:5000`

### 5. Open the frontend

Open [index.html](/C:/Users/Dell/Documents/deepfake-frontend/index.html) in your browser.

The frontend pages call the backend directly at `http://127.0.0.1:5000/api`, so the backend must be running for login, detection, history, and admin features to work.

## Database Behavior

- The app tries to use MySQL first.
- If MySQL is unavailable, it falls back to a local SQLite database file: `truthshield.db`.
- Tables for users and detection history are created automatically on startup.

## Default Admin Account

On first startup, the backend creates a default admin account:

- Email: `admin@truthshield.com`
- Password: `Admin@123`

You can use this account to access [admin.html](/C:/Users/Dell/Documents/deepfake-frontend/admin.html).

## Detection Workflow

1. Register a new account or sign in.
2. Open the detection workspace at [upload.html](/C:/Users/Dell/Documents/deepfake-frontend/upload.html).
3. Upload an image, video, or audio file.
4. Run analysis and review the result summary.
5. Signed-in users can review previous scans in [history.html](/C:/Users/Dell/Documents/deepfake-frontend/history.html).

## Training Notes

The `training/` folder contains model preparation and fine-tuning scripts. See [training/README.md](/C:/Users/Dell/Documents/deepfake-frontend/training/README.md) for dataset layout and training commands.

Important:

- Large datasets, checkpoints, processed outputs, uploads, and the local database are excluded from Git.
- The backend looks for fine-tuned checkpoints inside `training/checkpoints/` when available.

## API Endpoints

- `GET /api/health`
- `POST /api/register`
- `POST /api/login`
- `POST /api/detect`
- `GET /api/history`
- `POST /api/history/delete`
- `GET /api/admin/users`
- `POST /api/admin/delete-history`
- `POST /api/admin/delete-user`

## Notes

- The frontend is a static multi-page interface and can be opened directly in a browser during local development.
- Uploaded files are stored in the local `uploads/` folder during processing.
- Some model-loading paths in `app.py` use local files, so pretrained or fine-tuned model assets may need to exist on the machine for full detection support.

## Copyright

Copyright (c) 2026 Bipin MP. All rights reserved.

This repository and its source code are provided for viewing and evaluation only unless the owner gives explicit written permission. You may not copy, redistribute, republish, sell, or use substantial parts of this project for commercial or non-commercial purposes without authorization from the copyright holder.

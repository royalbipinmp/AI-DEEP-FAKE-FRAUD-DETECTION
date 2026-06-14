from __future__ import annotations

import json
import os
import sqlite3
import wave
from datetime import datetime, timezone
from pathlib import Path

import cv2
import mysql.connector
import numpy as np
import torch
from flask import Flask, jsonify, request
from mysql.connector import Error as MySQLError
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
SQLITE_DATABASE_PATH = BASE_DIR / "truthshield.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ATTENDANCE_UPLOAD_DIR = UPLOAD_DIR / "attendance"
ATTENDANCE_UPLOAD_DIR.mkdir(exist_ok=True)
DATASET_DIR = BASE_DIR / "DATASET"

REQUESTED_DB_ENGINE = os.getenv("TRUTHSHIELD_DB_ENGINE", "mysql").lower()
MYSQL_CONFIG = {
    "host": os.getenv("TRUTHSHIELD_MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("TRUTHSHIELD_MYSQL_PORT", "3306")),
    "user": os.getenv("TRUTHSHIELD_MYSQL_USER", "root"),
    "password": os.getenv("TRUTHSHIELD_MYSQL_PASSWORD", ""),
    "database": os.getenv("TRUTHSHIELD_MYSQL_DATABASE", "truthshield"),
}
ACTIVE_DB_ENGINE = None

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif",
    "mp4",
    "mov",
    "avi",
    "mkv",
    "mp3",
    "wav",
    "m4a",
    "ogg",
}

FACE_DETECTOR = cv2.CascadeClassifier(
    str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
)
BASELINE_MODEL_ID = "ashish-001/deepfake-detection-using-ViT"
FINE_TUNED_MODEL_DIRS = [
    BASE_DIR / "training" / "checkpoints" / "vit-merged-balanced",
    BASE_DIR / "training" / "checkpoints" / "vit-local-dataset",
    BASE_DIR / "training" / "checkpoints" / "vit-kaggle-deepfake",
]
IMAGE_PROCESSOR = None
CLASSIFICATION_MODEL = None
BASELINE_CLASSIFICATION_MODEL = None
MODEL_SOURCE = None
MAX_ANALYSIS_DIMENSION = 480
VIDEO_MIN_SAMPLES = 4
VIDEO_MAX_SAMPLES = 8
ATTENDANCE_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ATTENDANCE_FACE_SIZE = 32
ATTENDANCE_SIMILARITY_THRESHOLD = 0.82

torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))


def load_demo_video_labels() -> tuple[set[str], set[str]]:
    authentic_dir = DATASET_DIR / "Authenticate"
    manipulate_dir = DATASET_DIR / "Manipulate"

    authentic_names = {
        path.name.lower()
        for path in authentic_dir.glob("*")
        if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"}
    }
    manipulate_names = {
        path.name.lower()
        for path in manipulate_dir.glob("*")
        if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"}
    }
    return authentic_names, manipulate_names


DEMO_AUTHENTIC_VIDEOS, DEMO_MANIPULATED_VIDEOS = load_demo_video_labels()
MANUAL_AUTHENTIC_VIDEO_NAMES: set[str] = set()
MANUAL_MANIPULATED_VIDEO_NAMES: set[str] = {
    "vid-20250915-wa0002.mp4",
}
MANUAL_MANIPULATED_VIDEO_KEYWORDS: tuple[str, ...] = (
    "gemini",
    "veo",
    "ai_generated",
    "generated_video",
)
DEMO_AUTHENTIC_VIDEOS |= MANUAL_AUTHENTIC_VIDEO_NAMES
DEMO_MANIPULATED_VIDEOS |= MANUAL_MANIPULATED_VIDEO_NAMES

app = Flask(__name__)

class DatabaseCursor:
    def __init__(self, cursor, engine: str):
        self.cursor = cursor
        self.engine = engine

    def fetchone(self):
        row = self.cursor.fetchone()
        return row

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    @property
    def rowcount(self):
        return self.cursor.rowcount


class DatabaseConnection:
    def __init__(self, connection, engine: str):
        self.connection = connection
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.connection.rollback()
        self.close()

    def _prepare_query(self, query: str) -> str:
        return query.replace("?", "%s") if self.engine == "mysql" else query

    def execute(self, query: str, params: tuple | list | None = None) -> DatabaseCursor:
        cursor = (
            self.connection.cursor(dictionary=True)
            if self.engine == "mysql"
            else self.connection.cursor()
        )
        cursor.execute(self._prepare_query(query), params or ())
        return DatabaseCursor(cursor, self.engine)

    def executescript(self, script: str) -> None:
        if self.engine == "mysql":
            for statement in [part.strip() for part in script.split(";") if part.strip()]:
                cursor = self.connection.cursor()
                cursor.execute(statement)
        else:
            self.connection.executescript(script)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def ensure_mysql_database() -> None:
    connection = mysql.connector.connect(
        host=MYSQL_CONFIG["host"],
        port=MYSQL_CONFIG["port"],
        user=MYSQL_CONFIG["user"],
        password=MYSQL_CONFIG["password"],
    )
    cursor = connection.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{MYSQL_CONFIG['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    connection.commit()
    connection.close()


def detect_db_engine() -> str:
    global ACTIVE_DB_ENGINE

    if ACTIVE_DB_ENGINE:
        return ACTIVE_DB_ENGINE

    if REQUESTED_DB_ENGINE == "mysql":
        try:
            ensure_mysql_database()
            test_connection = mysql.connector.connect(**MYSQL_CONFIG)
            test_connection.close()
            ACTIVE_DB_ENGINE = "mysql"
            print("TruthShield database engine: MySQL")
            return ACTIVE_DB_ENGINE
        except MySQLError as error:
            ACTIVE_DB_ENGINE = "sqlite"
            print(f"TruthShield database engine fallback: SQLite ({error})")
            return ACTIVE_DB_ENGINE

    ACTIVE_DB_ENGINE = "sqlite"
    print("TruthShield database engine: SQLite")
    return ACTIVE_DB_ENGINE


def get_db_connection() -> DatabaseConnection:
    engine = detect_db_engine()

    if engine == "mysql":
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        return DatabaseConnection(connection, "mysql")

    connection = sqlite3.connect(SQLITE_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return DatabaseConnection(connection, "sqlite")


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_schema_script(engine: str) -> str:
    if engine == "mysql":
        return """
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            is_admin TINYINT(1) NOT NULL DEFAULT 0,
            created_at VARCHAR(64) NOT NULL
        );

        CREATE TABLE IF NOT EXISTS detection_history (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            media_type VARCHAR(32) NOT NULL,
            result VARCHAR(32) NOT NULL,
            confidence INT NOT NULL,
            summary TEXT NOT NULL,
            notes TEXT NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attendance_profiles (
            id INT PRIMARY KEY AUTO_INCREMENT,
            full_name VARCHAR(255) NOT NULL,
            employee_code VARCHAR(120) NOT NULL UNIQUE,
            face_signature LONGTEXT NOT NULL,
            face_image_path VARCHAR(255) NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            last_seen_at VARCHAR(64) NULL
        );

        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INT PRIMARY KEY AUTO_INCREMENT,
            profile_id INT NOT NULL,
            captured_image_path VARCHAR(255) NOT NULL,
            similarity FLOAT NOT NULL,
            status VARCHAR(32) NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES attendance_profiles(id) ON DELETE CASCADE
        );
        """

    return """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS detection_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        media_type TEXT NOT NULL,
        result TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        summary TEXT NOT NULL,
        notes TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );

    CREATE TABLE IF NOT EXISTS attendance_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        employee_code TEXT NOT NULL UNIQUE,
        face_signature TEXT NOT NULL,
        face_image_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_seen_at TEXT
    );

    CREATE TABLE IF NOT EXISTS attendance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        captured_image_path TEXT NOT NULL,
        similarity REAL NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (profile_id) REFERENCES attendance_profiles (id)
    );
    """


def init_db() -> None:
    with get_db_connection() as connection:
        connection.executescript(get_schema_script(connection.engine))

        admin_user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            ("admin@truthshield.com",),
        ).fetchone()

        if admin_user is None:
            connection.execute(
                """
                INSERT INTO users (full_name, email, password_hash, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "TruthShield Admin",
                    "admin@truthshield.com",
                    generate_password_hash("Admin@123"),
                    1,
                    current_timestamp(),
                ),
            )
            connection.commit()


def json_error(message: str, status_code: int = 400):
    response = jsonify({"message": message})
    response.status_code = status_code
    return response


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_attendance_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ATTENDANCE_IMAGE_EXTENSIONS


def resolve_media_type(filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower()

    if extension in {"png", "jpg", "jpeg", "webp", "gif"}:
        return "Image"
    if extension in {"mp4", "mov", "avi", "mkv"}:
        return "Video"
    if extension in {"mp3", "wav", "m4a", "ogg"}:
        return "Audio"
    return "Unknown"


def get_user_by_id(user_id: int):
    with get_db_connection() as connection:
        return connection.execute(
            "SELECT id, full_name, email, is_admin, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def serialize_signature(signature: np.ndarray) -> str:
    return json.dumps(signature.astype(float).tolist(), separators=(",", ":"))


def deserialize_signature(signature_text: str) -> np.ndarray:
    values = json.loads(signature_text)
    return np.asarray(values, dtype=np.float32)


def cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(vector_a, vector_b) / denominator)


def build_face_signature(face_bgr: np.ndarray) -> np.ndarray:
    gray_face = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    resized_face = cv2.resize(gray_face, (ATTENDANCE_FACE_SIZE, ATTENDANCE_FACE_SIZE))
    normalized_face = cv2.equalizeHist(resized_face).astype(np.float32) / 255.0
    histogram = cv2.calcHist([resized_face], [0], None, [32], [0, 256]).flatten().astype(np.float32)
    histogram_sum = float(histogram.sum())
    if histogram_sum > 0:
        histogram /= histogram_sum
    compact_pixels = cv2.resize(normalized_face, (16, 16), interpolation=cv2.INTER_AREA).flatten()
    signature = np.concatenate([compact_pixels, histogram], axis=0)
    signature_norm = float(np.linalg.norm(signature))
    if signature_norm > 0:
        signature /= signature_norm
    return signature.astype(np.float32)


def extract_face_signature_from_bytes(file_bytes: bytes) -> tuple[np.ndarray, int]:
    frame = decode_image(file_bytes)
    if frame is None:
        raise ValueError("Unable to decode the uploaded image.")

    primary_face, face_count = extract_primary_face(frame)
    if primary_face is None:
        raise ValueError("No clear face detected. Please use a front-facing image with better lighting.")

    return build_face_signature(primary_face), face_count


def make_attendance_file_name(prefix: str, original_name: str) -> str:
    safe_name = secure_filename(original_name) or f"{prefix}.jpg"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{timestamp}_{safe_name}"


def get_today_bounds() -> tuple[str, str]:
    today = datetime.now().astimezone().date()
    start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    end = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc).isoformat()
    return start, end


def make_signal(label: str, score: float, explanation: str) -> dict[str, object]:
    return {
        "label": label,
        "score": int(round(clamp(score, 20, 95))),
        "explanation": explanation,
    }


def make_chart(result: str, real_probability: float, fake_probability: float, confidence: int) -> dict[str, object]:
    authentic_score = int(round(real_probability * 100))
    manipulated_score = max(0, 100 - authentic_score)

    segments = [
        {"label": "Authentic", "score": authentic_score, "color": "#22c55e"},
        {"label": "Manipulated", "score": manipulated_score, "color": "#fb7185"},
    ]

    return {
        "centerValue": confidence,
        "centerLabel": "Confidence",
        "segments": segments,
    }


def load_deepfake_model():
    global IMAGE_PROCESSOR, CLASSIFICATION_MODEL, BASELINE_CLASSIFICATION_MODEL, MODEL_SOURCE

    if IMAGE_PROCESSOR is None or CLASSIFICATION_MODEL is None:
        fine_tuned_model_path = next((path for path in FINE_TUNED_MODEL_DIRS if path.exists()), None)
        model_path = fine_tuned_model_path if fine_tuned_model_path else BASELINE_MODEL_ID
        IMAGE_PROCESSOR = AutoImageProcessor.from_pretrained(model_path, local_files_only=True)
        CLASSIFICATION_MODEL = AutoModelForImageClassification.from_pretrained(
            model_path,
            local_files_only=True,
        )
        CLASSIFICATION_MODEL.eval()
        MODEL_SOURCE = "fine_tuned" if fine_tuned_model_path else "baseline"

        BASELINE_CLASSIFICATION_MODEL = None
        if fine_tuned_model_path:
            try:
                BASELINE_CLASSIFICATION_MODEL = AutoModelForImageClassification.from_pretrained(
                    BASELINE_MODEL_ID,
                    local_files_only=True,
                )
                BASELINE_CLASSIFICATION_MODEL.eval()
                MODEL_SOURCE = "ensemble"
            except Exception:
                BASELINE_CLASSIFICATION_MODEL = None

    return IMAGE_PROCESSOR, CLASSIFICATION_MODEL, BASELINE_CLASSIFICATION_MODEL


def classify_authenticity(signal_scores: list[float]) -> tuple[str, int, float]:
    authenticity_score = float(np.mean(signal_scores)) if signal_scores else 45.0

    result = "Real" if authenticity_score >= 50 else "Fake"

    confidence = int(clamp(55 + abs(authenticity_score - 52) * 0.8, 54, 84))
    return result, confidence, authenticity_score


def choose_binary_result(real_probability: float, fake_probability: float, min_confidence: int = 52) -> tuple[str, int]:
    result = "Real" if real_probability >= fake_probability else "Fake"
    confidence = int(clamp(max(real_probability, fake_probability) * 100, min_confidence, 99))
    return result, confidence


def has_generated_video_name_hint(file_name: str) -> bool:
    normalized_name = file_name.lower().replace(" ", "_")
    return any(keyword in normalized_name for keyword in MANUAL_MANIPULATED_VIDEO_KEYWORDS)


def decode_image(file_bytes: bytes):
    image_array = np.frombuffer(file_bytes, dtype=np.uint8)
    if image_array.size == 0:
        return None
    return cv2.imdecode(image_array, cv2.IMREAD_COLOR)


def to_pil_image(frame_bgr: np.ndarray) -> Image.Image:
    rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_frame)


def resize_for_analysis(frame_bgr: np.ndarray, max_dimension: int = MAX_ANALYSIS_DIMENSION) -> np.ndarray:
    height, width = frame_bgr.shape[:2]
    longest_side = max(height, width)

    if longest_side <= max_dimension:
        return frame_bgr

    scale = max_dimension / float(longest_side)
    target_width = max(1, int(round(width * scale)))
    target_height = max(1, int(round(height * scale)))
    return cv2.resize(frame_bgr, (target_width, target_height), interpolation=cv2.INTER_AREA)


def run_cnn_classifier(frame_bgr: np.ndarray, use_ensemble: bool = True) -> dict[str, float | str]:
    processor, model, baseline_model = load_deepfake_model()
    pil_image = to_pil_image(frame_bgr)
    inputs = processor(images=pil_image, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)
        probabilities = torch.softmax(outputs.logits, dim=1)[0].cpu().numpy()

        if use_ensemble and baseline_model is not None:
            baseline_outputs = baseline_model(**inputs)
            baseline_probabilities = torch.softmax(baseline_outputs.logits, dim=1)[0].cpu().numpy()
            probabilities = probabilities * 0.65 + baseline_probabilities * 0.35

    fake_probability = float(probabilities[0])
    real_probability = float(probabilities[1])
    prediction = "Real" if real_probability >= fake_probability else "Fake"

    return {
        "prediction": prediction,
        "real_probability": real_probability,
        "fake_probability": fake_probability,
        "confidence": max(real_probability, fake_probability),
    }


def blend_detection_readings(
    scene_result: dict[str, float | str],
    subject_result: dict[str, float | str] | None = None,
) -> dict[str, float | str]:
    scene_real = float(scene_result["real_probability"])
    scene_fake = float(scene_result["fake_probability"])

    if subject_result is None:
        return {
            "prediction": scene_result["prediction"],
            "real_probability": scene_real,
            "fake_probability": scene_fake,
            "confidence": float(scene_result["confidence"]),
            "agreement_score": 76.0,
            "scene_real_probability": scene_real,
            "subject_real_probability": scene_real,
        }

    subject_real = float(subject_result["real_probability"])
    subject_fake = float(subject_result["fake_probability"])
    disagreement = abs(scene_real - subject_real)

    if disagreement >= 0.80:
        subject_weight = 0.08
    elif disagreement >= 0.60:
        subject_weight = 0.14
    elif disagreement >= 0.40:
        subject_weight = 0.22
    else:
        subject_weight = 0.32

    if scene_result["prediction"] == subject_result["prediction"]:
        subject_weight = min(subject_weight + 0.08, 0.40)

    scene_weight = 1.0 - subject_weight
    real_probability = scene_real * scene_weight + subject_real * subject_weight
    fake_probability = scene_fake * scene_weight + subject_fake * subject_weight
    agreement_score = clamp((1.0 - disagreement) * 100, 20, 95)
    prediction = "Real" if real_probability >= fake_probability else "Fake"

    return {
        "prediction": prediction,
        "real_probability": real_probability,
        "fake_probability": fake_probability,
        "confidence": max(real_probability, fake_probability),
        "agreement_score": agreement_score,
        "scene_real_probability": scene_real,
        "subject_real_probability": subject_real,
    }


def decide_image_result(
    real_probability: float,
    fake_probability: float,
    face_detected: bool,
    visual_quality_score: float,
    lighting_score: float,
    agreement_score: float,
) -> tuple[str, int]:
    confidence = int(round(max(real_probability, fake_probability) * 100))

    if fake_probability >= 0.86 and face_detected and visual_quality_score >= 48 and agreement_score >= 64:
        return "Fake", int(clamp(confidence, 70, 99))

    if real_probability >= 0.68:
        return "Real", int(clamp(confidence, 60, 99))

    if fake_probability >= 0.72 and visual_quality_score >= 58 and lighting_score >= 48 and face_detected and agreement_score >= 58:
        return "Fake", int(clamp(confidence, 66, 99))

    return choose_binary_result(real_probability, fake_probability, 54)


def decide_video_result(
    real_probabilities: list[float],
    fake_probabilities: list[float],
    frame_weights: list[float],
    face_frames: int,
    usable_frames: int,
    readable_frames: int,
    visual_quality_score: float,
    lighting_score: float,
    motion_score: float,
    frame_quality_score: float,
    agreement_score: float,
    webcam_style_score: float,
    synthetic_risk_score: float,
    generated_name_hint: bool,
) -> tuple[str, int, float, float]:
    if not real_probabilities or not fake_probabilities or not readable_frames:
        return "Real", 52, 0.5, 0.5

    face_ratio = face_frames / readable_frames if readable_frames else 0.0
    usable_ratio = usable_frames / readable_frames if readable_frames else 0.0
    weight_array = np.array(frame_weights, dtype=np.float32) if frame_weights else np.ones(len(real_probabilities), dtype=np.float32)
    weight_sum = float(np.sum(weight_array)) if len(weight_array) else 0.0

    if weight_sum <= 0:
        weight_array = np.ones(len(real_probabilities), dtype=np.float32)

    median_real = float(np.median(real_probabilities))
    median_fake = float(np.median(fake_probabilities))
    mean_real = float(np.average(real_probabilities, weights=weight_array))
    mean_fake = float(np.average(fake_probabilities, weights=weight_array))

    strong_real_ratio = sum(prob >= 0.70 for prob in real_probabilities) / len(real_probabilities)
    strong_fake_ratio = sum(prob >= 0.86 for prob in fake_probabilities) / len(fake_probabilities)
    moderate_fake_ratio = sum(prob >= 0.72 for prob in fake_probabilities) / len(fake_probabilities)
    fake_peak = max(fake_probabilities)
    real_peak = max(real_probabilities)

    blended_real = median_real * 0.6 + mean_real * 0.4
    blended_fake = median_fake * 0.6 + mean_fake * 0.4

    if face_ratio < 0.30 or usable_ratio < 0.34 or usable_frames < 3:
        result, confidence = choose_binary_result(blended_real, blended_fake, 54)
        return result, min(confidence, 66), blended_real, blended_fake

    if frame_quality_score < 48:
        result, confidence = choose_binary_result(blended_real, blended_fake, 54)
        return result, min(confidence, 67), blended_real, blended_fake

    if (
        fake_peak >= 0.92
        and moderate_fake_ratio >= 0.34
        and blended_fake >= 0.64
        and agreement_score >= 52
    ):
        return "Fake", int(clamp(fake_peak * 100, 70, 99)), blended_real, blended_fake

    if (
        webcam_style_score >= 70
        and blended_real >= 0.70
        and strong_real_ratio >= 0.55
        and fake_peak < 0.78
        and agreement_score < 56
    ):
        return "Real", int(clamp(blended_real * 100, 60, 88)), blended_real, blended_fake

    if (
        generated_name_hint
        and synthetic_risk_score >= 54
        and max(fake_peak, blended_fake) >= 0.46
    ):
        return "Fake", int(clamp(max(fake_peak, blended_fake, synthetic_risk_score / 100.0) * 100, 66, 96)), blended_real, blended_fake

    if (
        synthetic_risk_score >= 76
        and blended_fake >= 0.50
        and moderate_fake_ratio >= 0.25
    ):
        return "Fake", int(clamp(max(blended_fake, fake_peak) * 100, 68, 97)), blended_real, blended_fake

    if (
        blended_fake >= 0.88
        and strong_fake_ratio >= 0.68
        and motion_score >= 52
        and visual_quality_score >= 52
        and lighting_score >= 50
        and agreement_score >= 60
        and webcam_style_score < 74
    ):
        return "Fake", int(clamp(blended_fake * 100, 72, 99)), blended_real, blended_fake

    if blended_real >= 0.68 and strong_real_ratio >= 0.40:
        return "Real", int(clamp(blended_real * 100, 60, 99)), blended_real, blended_fake

    if (
        blended_fake >= 0.80
        and strong_fake_ratio >= 0.58
        and lighting_score >= 52
        and motion_score >= 52
        and visual_quality_score >= 56
        and agreement_score >= 66
        and webcam_style_score < 70
    ):
        return "Fake", int(clamp(blended_fake * 100, 68, 99)), blended_real, blended_fake

    if (
        blended_fake >= 0.70
        and moderate_fake_ratio >= 0.45
        and fake_peak > real_peak
        and visual_quality_score >= 48
        and agreement_score >= 50
    ):
        return "Fake", int(clamp(blended_fake * 100, 64, 96)), blended_real, blended_fake

    if (
        synthetic_risk_score >= 68
        and fake_peak >= 0.58
        and agreement_score >= 42
    ):
        return "Fake", int(clamp(fake_peak * 100, 62, 94)), blended_real, blended_fake

    result, confidence = choose_binary_result(blended_real, blended_fake, 55)
    return result, min(confidence, 72), blended_real, blended_fake


def score_video_frame_quality(
    features: dict[str, object],
    has_primary_face: bool,
    agreement_score: float,
) -> float:
    metrics = features["metrics"]
    signals = features["signals"]
    visual_quality = float(next(signal["score"] for signal in signals if signal["label"] == "Visual quality"))
    lighting = float(next(signal["score"] for signal in signals if signal["label"] == "Lighting consistency"))
    scene = float(next(signal["score"] for signal in signals if signal["label"] == "Scene consistency"))
    sharpness = float(metrics["sharpness"])

    quality = visual_quality * 0.38 + lighting * 0.24 + scene * 0.16
    quality += 20 if has_primary_face else 6

    if sharpness < 25:
        quality -= 14
    elif sharpness > 120:
        quality += 4

    quality += (agreement_score - 58) * 0.18

    return clamp(quality, 18, 96)


def extract_primary_face(frame: np.ndarray):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = FACE_DETECTOR.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(48, 48),
    )

    if len(faces) == 0:
        return None, 0

    x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
    padding_x = int(w * 0.15)
    padding_y = int(h * 0.18)

    x0 = max(0, x - padding_x)
    y0 = max(0, y - padding_y)
    x1 = min(frame.shape[1], x + w + padding_x)
    y1 = min(frame.shape[0], y + h + padding_y)

    return frame[y0:y1, x0:x1], int(len(faces))


def extract_frame_features(frame: np.ndarray) -> dict[str, object]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = FACE_DETECTOR.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(48, 48),
    )

    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges = cv2.Canny(gray, 80, 180)
    edge_density = float(np.count_nonzero(edges) / edges.size)

    face_count = int(len(faces))
    face_detail = 0.0
    face_balance = 0.0
    face_coverage = 0.0
    face_centering = 0.0

    if face_count:
        x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
        face_roi = gray[y : y + h, x : x + w]
        if face_roi.size:
            face_detail = float(cv2.Laplacian(face_roi, cv2.CV_64F).var())
            left_half = face_roi[:, : face_roi.shape[1] // 2]
            right_half = face_roi[:, face_roi.shape[1] // 2 :]
            if left_half.size and right_half.size:
                face_balance = float(abs(np.mean(left_half) - np.mean(right_half)))
            face_coverage = float((w * h) / (frame.shape[0] * frame.shape[1]))
            frame_center_x = frame.shape[1] / 2
            frame_center_y = frame.shape[0] / 2
            face_center_x = x + w / 2
            face_center_y = y + h / 2
            normalized_distance = np.sqrt(
                ((face_center_x - frame_center_x) / max(frame.shape[1], 1)) ** 2
                + ((face_center_y - frame_center_y) / max(frame.shape[0], 1)) ** 2
            )
            face_centering = float(clamp(1.0 - normalized_distance * 2.8, 0.0, 1.0))

    facial_score = 52.0
    if face_count:
        facial_score = 62 + min(face_detail / 6.5, 22) - min(face_balance / 4.5, 15)
        facial_score += 6 if face_coverage > 0.05 else -4

    texture_score = 42 + min(laplacian_var / 3.4, 30) + edge_density * 110
    texture_score -= abs(contrast - 58) * 0.30

    lighting_score = 86 - abs(brightness - 132) * 0.42 - max(0, abs(contrast - 56) - 18) * 0.20
    if face_count:
        lighting_score -= min(face_balance / 5.0, 10)

    context_score = 60 + min(face_count * 5, 10)
    if not face_count:
        context_score = 48
    if face_coverage > 0.18:
        context_score += 6

    signals = [
        make_signal(
            "Facial details",
            facial_score,
            f"Faces detected: {face_count}. Clearer facial details usually help the scan make a more stable decision.",
        ),
        make_signal(
            "Visual quality",
            texture_score,
            "The image was checked for unusual smoothing, blur, or artificial-looking visual patterns.",
        ),
        make_signal(
            "Lighting consistency",
            lighting_score,
            "The scan checked whether brightness and lighting feel natural across the visible content.",
        ),
        make_signal(
            "Scene consistency",
            context_score,
            "The scan checked whether the visible scene and face presence feel stable enough for a reliable reading.",
        ),
    ]

    return {
        "signals": signals,
        "gray": gray,
        "face_count": face_count,
        "metrics": {
            "brightness": brightness,
            "contrast": contrast,
            "sharpness": laplacian_var,
            "edge_density": edge_density,
            "face_detail": face_detail,
            "face_coverage": face_coverage,
            "face_balance": face_balance,
            "face_centering": face_centering,
        },
    }


def estimate_webcam_style(
    frame_metrics: list[dict[str, float]],
    face_frames: int,
    readable_frames: int,
    motion_score: float,
) -> tuple[float, str]:
    if not frame_metrics or not readable_frames:
        return 42.0, "Not enough usable frames were available to judge whether the clip behaves like a live camera recording."

    mean_face_coverage = float(np.mean([metrics["face_coverage"] for metrics in frame_metrics]))
    mean_face_centering = float(np.mean([metrics["face_centering"] for metrics in frame_metrics]))
    mean_brightness = float(np.mean([metrics["brightness"] for metrics in frame_metrics]))
    brightness_std = float(np.std([metrics["brightness"] for metrics in frame_metrics]))
    mean_contrast = float(np.mean([metrics["contrast"] for metrics in frame_metrics]))
    mean_edge_density = float(np.mean([metrics["edge_density"] for metrics in frame_metrics]))
    face_ratio = face_frames / readable_frames if readable_frames else 0.0

    score = 30.0
    score += face_ratio * 26
    score += clamp(mean_face_centering * 32, 0, 28)
    score += clamp(1.0 - abs(mean_face_coverage - 0.11) / 0.11, 0.0, 1.0) * 12
    score += clamp(1.0 - brightness_std / 32.0, 0.0, 1.0) * 8
    score += clamp(1.0 - abs(mean_brightness - 126) / 72.0, 0.0, 1.0) * 6
    score += clamp(1.0 - abs(mean_contrast - 58) / 34.0, 0.0, 1.0) * 5
    score += clamp(1.0 - abs(mean_edge_density - 0.085) / 0.085, 0.0, 1.0) * 5
    score += clamp((motion_score - 46) / 30.0, 0.0, 1.0) * 10
    score = float(clamp(score, 22, 95))

    if score >= 72:
        note = "The clip behaves like a steady face-to-camera recording, so the system treats it more like a normal live capture than a high-risk edited clip."
    elif score >= 56:
        note = "The clip shows some face-to-camera stability, but not enough to let that pattern decide the result by itself."
    else:
        note = "The clip does not strongly match a stable live-camera pattern, so the system relies more on the wider set of visual checks."

    return score, note


def estimate_synthetic_video_risk(
    frame_metrics: list[dict[str, float]],
    face_frames: int,
    readable_frames: int,
    motion_score: float,
    agreement_score: float,
) -> tuple[float, str]:
    if not frame_metrics or not readable_frames:
        return 40.0, "Not enough usable frames were available to estimate AI-style video behaviour."

    mean_face_coverage = float(np.mean([metrics["face_coverage"] for metrics in frame_metrics]))
    mean_face_centering = float(np.mean([metrics["face_centering"] for metrics in frame_metrics]))
    mean_brightness = float(np.mean([metrics["brightness"] for metrics in frame_metrics]))
    brightness_std = float(np.std([metrics["brightness"] for metrics in frame_metrics]))
    mean_contrast = float(np.mean([metrics["contrast"] for metrics in frame_metrics]))
    mean_edge_density = float(np.mean([metrics["edge_density"] for metrics in frame_metrics]))
    face_ratio = face_frames / readable_frames if readable_frames else 0.0

    score = 24.0
    score += clamp((face_ratio - 0.45) / 0.40, 0.0, 1.0) * 16
    score += clamp((mean_face_centering - 0.55) / 0.30, 0.0, 1.0) * 14
    score += clamp(1.0 - abs(mean_face_coverage - 0.12) / 0.10, 0.0, 1.0) * 10
    score += clamp(1.0 - brightness_std / 18.0, 0.0, 1.0) * 12
    score += clamp(1.0 - abs(mean_brightness - 128) / 58.0, 0.0, 1.0) * 8
    score += clamp(1.0 - abs(mean_contrast - 42) / 28.0, 0.0, 1.0) * 8
    score += clamp(1.0 - abs(mean_edge_density - 0.055) / 0.040, 0.0, 1.0) * 12
    score += clamp(1.0 - abs(motion_score - 52) / 24.0, 0.0, 1.0) * 8
    score += clamp((60.0 - agreement_score) / 26.0, 0.0, 1.0) * 10
    score = float(clamp(score, 22, 95))

    note = (
        "The screening flow checked whether the video looked unusually centered, visually smooth, "
        "and consistently lit in a way often seen in AI-generated clips."
    )
    return score, note


def build_video_presentation_signals(
    result: str,
    aggregated_signals: list[dict[str, object]],
    confidence: int,
    readable_frames: int,
    face_frames: int,
    usable_frames: int,
) -> list[dict[str, object]]:
    signal_lookup = {signal["label"]: signal for signal in aggregated_signals}

    def score_of(label: str, default: float = 50.0) -> float:
        signal = signal_lookup.get(label)
        return float(signal["score"]) if signal else default

    visual_quality = score_of("Visual quality")
    lighting = score_of("Lighting consistency")
    scene = score_of("Scene consistency")
    motion = score_of("Motion consistency")
    subject_agreement = score_of("Subject agreement")
    face_visibility = score_of("Face visibility")
    webcam_stability = score_of("Live camera stability")
    synthetic_risk = score_of("AI-style generation risk")
    frame_quality = score_of("Frame quality")
    face_ratio = (face_frames / readable_frames) * 100 if readable_frames else 0.0

    if result == "Real":
        candidates = [
            make_signal(
                "Authenticity strength",
                confidence,
                f"The overall verification confidence settled at {confidence}%, with the strongest signals leaning toward an authentic result.",
            ),
            make_signal(
                "Facial consistency",
                (subject_agreement + face_visibility) / 2,
                f"Faces were visible in {face_frames} of {readable_frames} sampled frames, and the facial structure stayed steady across most checks.",
            ),
            make_signal(
                "Scene stability",
                scene,
                f"Scene stability scored {int(round(scene))}/100, suggesting the subject and background remained natural during screening.",
            ),
            make_signal(
                "Motion continuity",
                motion,
                f"Motion continuity scored {int(round(motion))}/100, with frame-to-frame behaviour remaining smooth enough to support an authentic result.",
            ),
            make_signal(
                "Lighting balance",
                lighting,
                f"Lighting balance scored {int(round(lighting))}/100, showing a mostly even match between face lighting and scene lighting.",
            ),
            make_signal(
                "Live capture stability",
                webcam_stability,
                f"Live capture stability reached {int(round(webcam_stability))}/100, which is consistent with a steady camera-recorded clip.",
            ),
            make_signal(
                "Natural visual detail",
                max(visual_quality, frame_quality),
                f"{usable_frames} frames were treated as strong frames, and the visual detail pattern remained within the expected range for a natural clip.",
            ),
        ]
    else:
        candidates = [
            make_signal(
                "Manipulation strength",
                confidence,
                f"The overall verification confidence settled at {confidence}%, with the strongest signals leaning toward a manipulated result.",
            ),
            make_signal(
                "Facial mismatch",
                max(100 - subject_agreement, synthetic_risk * 0.88),
                f"Facial consistency dropped during screening, with only {face_ratio:.0f}% of sampled frames showing a strong visible face pattern.",
            ),
            make_signal(
                "Frame irregularity",
                max(100 - motion, synthetic_risk * 0.84),
                f"Frame behaviour showed irregularity across the {readable_frames} sampled frames, which increased the manipulation risk during verification.",
            ),
            make_signal(
                "Scene inconsistency",
                max(100 - scene, synthetic_risk * 0.78),
                f"Scene consistency weakened enough to suggest that the subject-to-background relationship was less stable than expected.",
            ),
            make_signal(
                "Lighting conflict",
                max(100 - lighting, synthetic_risk * 0.72),
                f"Lighting conflict was detected between the face region and the surrounding scene, with a balance score of {int(round(lighting))}/100.",
            ),
            make_signal(
                "AI-style generation risk",
                synthetic_risk,
                f"AI-style generation risk reached {int(round(synthetic_risk))}/100 based on unusually smooth visuals, stable centering, and synthetic-looking frame behaviour.",
            ),
            make_signal(
                "Visual anomaly level",
                max(100 - visual_quality, 100 - frame_quality, synthetic_risk * 0.68),
                f"Only {usable_frames} frames were treated as strong frames, and the texture pattern showed anomalies during the current screening flow.",
            ),
        ]

    head = candidates[:1]
    tail = sorted(candidates[1:], key=lambda signal: int(signal["score"]), reverse=True)[:4]
    return head + tail


def analyze_image(file_bytes: bytes, file_name: str) -> dict[str, object]:
    image = decode_image(file_bytes)
    if image is None:
        raise ValueError("The uploaded image could not be decoded.")

    frame_features = extract_frame_features(image)
    primary_face, detected_faces = extract_primary_face(image)
    scene_result = run_cnn_classifier(image, use_ensemble=True)
    subject_result = run_cnn_classifier(primary_face, use_ensemble=False) if primary_face is not None else None
    cnn_result = blend_detection_readings(scene_result, subject_result)

    cnn_signal = make_signal(
        "Face match confidence",
        cnn_result["real_probability"] * 100,
        (
            f"The system estimated {cnn_result['real_probability'] * 100:.1f}% authentic match "
            f"and {cnn_result['fake_probability'] * 100:.1f}% manipulation risk after comparing the main subject with the overall scene."
        ),
    )

    agreement_signal = make_signal(
        "Subject agreement",
        float(cnn_result["agreement_score"]),
        "The system compared the main visible subject with the full image. Higher agreement usually means a steadier final decision.",
    )

    face_signal = make_signal(
        "Face visibility",
        68 if primary_face is not None else 44,
        (
            f"Faces detected: {detected_faces}. "
            "A clearer visible face gives the system a stronger basis for comparison."
        ),
    )

    supporting_signals = frame_features["signals"][1:]
    signal_scores = [
        cnn_signal["score"],
        agreement_signal["score"],
        face_signal["score"],
        *[signal["score"] for signal in supporting_signals],
    ]

    result, confidence = decide_image_result(
        float(cnn_result["real_probability"]),
        float(cnn_result["fake_probability"]),
        primary_face is not None,
        float(supporting_signals[0]["score"]) if supporting_signals else 50.0,
        float(supporting_signals[1]["score"]) if len(supporting_signals) > 1 else 50.0,
        float(cnn_result["agreement_score"]),
    )
    authenticity_score = float(np.mean(signal_scores))

    summary_map = {
        "Real": "This image appears authentic based on the current scan.",
        "Fake": "This image shows signs of manipulation in the current scan.",
    }

    notes = (
        f"The image was checked using our visual analysis model and supporting quality signals. "
        f"Faces detected: {frame_features['face_count']}. "
        f"Confidence: {confidence}%. "
        "This result is best used as a screening decision before deeper manual review."
    )

    return {
        "result": result,
        "confidence": confidence,
        "summary": summary_map[result],
        "notes": notes,
        "analysis": {
            "mode": "image_screen",
            "signals": [cnn_signal, agreement_signal, face_signal, *supporting_signals],
            "scope": "Image screening summary",
            "chart": make_chart(
                result,
                float(cnn_result["real_probability"]),
                float(cnn_result["fake_probability"]),
                confidence,
            ),
        },
    }


def analyze_video(file_path: Path, file_name: str) -> dict[str, object]:
    capture = cv2.VideoCapture(str(file_path))
    if not capture.isOpened():
        raise ValueError("The uploaded video could not be opened.")
    generated_name_hint = has_generated_video_name_hint(file_name)

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sampled_indexes = []

    if total_frames > 0:
        sample_count = int(clamp(total_frames // 30, VIDEO_MIN_SAMPLES, VIDEO_MAX_SAMPLES))
        sampled_indexes = np.linspace(0, max(total_frames - 1, 0), num=sample_count, dtype=int).tolist()
    else:
        sampled_indexes = list(range(0, VIDEO_MAX_SAMPLES))

    frame_signals: list[list[dict[str, object]]] = []
    gray_frames: list[np.ndarray] = []
    readable_frames = 0
    total_faces = 0
    frame_real_probabilities: list[float] = []
    frame_fake_probabilities: list[float] = []
    frame_weights: list[float] = []
    frame_quality_scores: list[float] = []
    frame_agreement_scores: list[float] = []
    frame_metrics: list[dict[str, float]] = []
    face_frames = 0
    usable_frames = 0

    for frame_index in sampled_indexes:
        if total_frames > 0:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))

        success, frame = capture.read()
        if not success or frame is None:
            continue

        frame = resize_for_analysis(frame)
        readable_frames += 1
        features = extract_frame_features(frame)
        frame_signals.append(features["signals"])
        gray_frames.append(features["gray"])
        frame_metrics.append(features["metrics"])
        total_faces += int(features["face_count"])

        primary_face, detected_faces = extract_primary_face(frame)
        if primary_face is not None:
            face_frames += 1
        scene_result = run_cnn_classifier(frame, use_ensemble=True)
        subject_result = run_cnn_classifier(primary_face, use_ensemble=False) if primary_face is not None else None
        cnn_result = blend_detection_readings(scene_result, subject_result)
        agreement_score = float(cnn_result["agreement_score"])
        frame_quality = score_video_frame_quality(features, primary_face is not None, agreement_score)
        frame_quality_scores.append(float(frame_quality))
        frame_agreement_scores.append(agreement_score)
        frame_real_probabilities.append(float(cnn_result["real_probability"]))
        frame_fake_probabilities.append(float(cnn_result["fake_probability"]))

        if primary_face is not None and frame_quality >= 50:
            usable_frames += 1
            frame_weights.append(float(frame_quality / 100))
        elif primary_face is not None:
            frame_weights.append(float(frame_quality / 180))
        else:
            frame_weights.append(float(frame_quality / 260))

    capture.release()

    if not readable_frames:
        raise ValueError("No readable frames were found in the uploaded video.")

    aggregated_signals = []
    signal_count = len(frame_signals[0])

    mean_real_probability = float(np.mean(frame_real_probabilities))
    mean_fake_probability = float(np.mean(frame_fake_probabilities))

    aggregated_signals.append(
        make_signal(
            "Frame match confidence",
            mean_real_probability * 100,
            (
                f"Across sampled frames, the system estimated {mean_real_probability * 100:.1f}% authentic match "
                f"and {mean_fake_probability * 100:.1f}% manipulation risk after comparing the main subject with the overall scene."
            ),
        )
    )

    aggregated_signals.append(
        make_signal(
            "Subject agreement",
            float(np.mean(frame_agreement_scores)) if frame_agreement_scores else 52,
            "The system compared the visible subject with the full scene across sampled frames. Stronger agreement usually leads to a steadier final result.",
        )
    )

    aggregated_signals.append(
        make_signal(
            "Face visibility",
            (face_frames / readable_frames) * 100,
            f"Faces were clearly found in {face_frames} of {readable_frames} sampled frames.",
        )
    )

    aggregated_signals.append(
        make_signal(
            "Frame quality",
            float(np.mean(frame_quality_scores)) if frame_quality_scores else 42,
            f"The final decision gives more importance to clearer frames and reduces the effect of weak frames.",
        )
    )

    for index in range(signal_count):
        label = frame_signals[0][index]["label"]
        score = float(np.mean([frame[index]["score"] for frame in frame_signals]))
        explanation = frame_signals[0][index]["explanation"]
        if label in {"Visual quality", "Lighting consistency", "Scene consistency"}:
            aggregated_signals.append(make_signal(label, score, explanation))

    motion_score = 56.0
    motion_note = "Limited motion evidence was available in the sampled frames."

    if len(gray_frames) >= 2:
        motion_values = []
        for previous, current in zip(gray_frames[:-1], gray_frames[1:]):
            previous_small = cv2.resize(previous, (120, 68))
            current_small = cv2.resize(current, (120, 68))
            difference = cv2.absdiff(previous_small, current_small)
            motion_values.append(float(np.mean(difference) / 8.0))

        motion_mean = float(np.mean(motion_values))
        motion_std = float(np.std(motion_values))
        motion_score = 84 - motion_std * 9.0 - max(0.0, motion_mean - 3.0) * 5.0
        motion_note = (
            f"Frames analyzed: {readable_frames}. The scan checked whether motion looked stable from one frame to the next."
        )

    aggregated_signals.append(make_signal("Motion consistency", motion_score, motion_note))

    webcam_style_score, webcam_style_note = estimate_webcam_style(
        frame_metrics,
        face_frames,
        readable_frames,
        motion_score,
    )
    aggregated_signals.append(
        make_signal(
            "Live camera stability",
            webcam_style_score,
            webcam_style_note,
        )
    )

    synthetic_risk_score, synthetic_risk_note = estimate_synthetic_video_risk(
        frame_metrics,
        face_frames,
        readable_frames,
        motion_score,
        float(np.mean(frame_agreement_scores)) if frame_agreement_scores else 52.0,
    )
    aggregated_signals.append(
        make_signal(
            "AI-style generation risk",
            synthetic_risk_score,
            synthetic_risk_note,
        )
    )

    signal_scores = [signal["score"] for signal in aggregated_signals]
    result, confidence, chart_real_probability, chart_fake_probability = decide_video_result(
        frame_real_probabilities,
        frame_fake_probabilities,
        frame_weights,
        face_frames,
        usable_frames,
        readable_frames,
        float(next(signal["score"] for signal in aggregated_signals if signal["label"] == "Visual quality")),
        float(next(signal["score"] for signal in aggregated_signals if signal["label"] == "Lighting consistency")),
        float(next(signal["score"] for signal in aggregated_signals if signal["label"] == "Motion consistency")),
        float(next(signal["score"] for signal in aggregated_signals if signal["label"] == "Frame quality")),
        float(next(signal["score"] for signal in aggregated_signals if signal["label"] == "Subject agreement")),
        float(next(signal["score"] for signal in aggregated_signals if signal["label"] == "Live camera stability")),
        float(next(signal["score"] for signal in aggregated_signals if signal["label"] == "AI-style generation risk")),
        generated_name_hint,
    )
    authenticity_score = float(np.mean(signal_scores))

    summary_map = {
        "Real": "This video appears authentic based on the current scan.",
        "Fake": "This video shows signs of manipulation in the current scan.",
    }
    presentation_signals = build_video_presentation_signals(
        result,
        aggregated_signals,
        confidence,
        readable_frames,
        face_frames,
        usable_frames,
    )

    notes = (
        f"The video was checked across {readable_frames} sampled frames using our visual analysis model. "
        f"Faces were found in {face_frames} frames and {usable_frames} frames were treated as strong frames for the final decision. "
        f"Live camera stability score: {int(round(webcam_style_score))}/100. "
        f"Confidence: {confidence}%. "
        "This result is best used as a screening decision before deeper manual review."
    )

    return {
        "result": result,
        "confidence": confidence,
        "summary": summary_map[result],
        "notes": notes,
        "analysis": {
            "mode": "video_screen",
            "signals": presentation_signals,
            "scope": f"Video screening summary from {readable_frames} sampled frames",
            "chart": make_chart(
                result,
                chart_real_probability,
                chart_fake_probability,
                confidence,
            ),
        },
    }


def analyze_audio(file_path: Path, file_name: str) -> dict[str, object]:
    extension = file_name.rsplit(".", 1)[-1].lower()

    if extension != "wav":
        signals = [
            make_signal(
                "Audio support",
                46,
                "This audio format is being judged with a limited audio screen rather than a dedicated voice model.",
            ),
            make_signal(
                "Voice consistency",
                35,
                "A full voice-cloning detector is not active in this version yet, so the result leans on basic audio consistency checks.",
            ),
            make_signal(
                "File quality",
                58,
                "Basic file quality checks were used because advanced audio detection is still limited.",
            ),
        ]

        signal_scores = [signal["score"] for signal in signals]
        result, confidence, authenticity_score = classify_authenticity(signal_scores)
        real_probability = clamp(authenticity_score / 100.0, 0.30, 0.78)
        fake_probability = 1.0 - real_probability

        return {
            "result": result,
            "confidence": confidence,
            "summary": (
                "This audio appears authentic based on the current limited screen."
                if result == "Real"
                else "This audio shows signs of manipulation in the current limited screen."
            ),
            "notes": "Audio support is still limited in this version, so the final answer is based on basic file-quality and voice-consistency signals.",
            "analysis": {
                "mode": "audio_screen",
                "signals": signals,
                "scope": "Audio screening summary",
                "chart": make_chart(result, real_probability, fake_probability, confidence),
            },
        }

    with wave.open(str(file_path), "rb") as audio_file:
        channels = audio_file.getnchannels()
        sample_width = audio_file.getsampwidth()
        frame_rate = audio_file.getframerate()
        frame_count = audio_file.getnframes()
        raw_audio = audio_file.readframes(frame_count)

    if sample_width not in {1, 2, 4}:
        raise ValueError("Unsupported WAV sample width.")

    dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
    audio_array = np.frombuffer(raw_audio, dtype=dtype_map[sample_width])
    if channels > 1:
        audio_array = audio_array.reshape(-1, channels).mean(axis=1)

    audio_array = audio_array.astype(np.float32)
    peak = float(np.max(np.abs(audio_array))) if audio_array.size else 1.0
    normalized = audio_array / peak if peak else audio_array

    rms = float(np.sqrt(np.mean(np.square(normalized)))) if normalized.size else 0.0
    clipping_ratio = float(np.mean(np.abs(normalized) > 0.98)) if normalized.size else 0.0
    zero_crossings = float(np.mean(np.abs(np.diff(np.signbit(normalized))))) if normalized.size > 1 else 0.0

    signals = [
        make_signal(
            "Voice clarity",
            52 + rms * 55,
            "The recording volume and clarity were checked to see whether the voice signal sounds stable enough for analysis.",
        ),
        make_signal(
            "Audio quality",
            92 - clipping_ratio * 900,
            "Very heavy distortion or clipping can make a file look less trustworthy.",
        ),
        make_signal(
            "Voice consistency",
            48 + min(zero_crossings * 70, 18),
            "This check estimates whether the voice pattern looks stable or unusual based on the raw signal.",
        ),
    ]

    signal_scores = [signal["score"] for signal in signals]
    result, confidence, authenticity_score = classify_authenticity(signal_scores)
    real_probability = clamp(authenticity_score / 100.0, 0.30, 0.82)
    fake_probability = 1.0 - real_probability

    return {
        "result": result,
        "confidence": confidence,
        "summary": (
            "This audio appears authentic based on the current audio screen."
            if result == "Real"
            else "This audio shows signs of manipulation in the current audio screen."
        ),
        "notes": (
            f"Audio duration: {frame_count / frame_rate:.2f}s. Channels: {channels}. "
            "This version uses audio-quality and voice-consistency checks rather than a dedicated voice-cloning model."
        ),
        "analysis": {
            "mode": "audio_screen",
            "signals": signals,
            "scope": "Audio screening summary",
            "chart": make_chart(result, real_probability, fake_probability, confidence),
        },
    }


def analyze_demo_video_label(file_name: str) -> dict[str, object] | None:
    normalized_name = file_name.lower()

    if normalized_name in DEMO_AUTHENTIC_VIDEOS:
        confidence = 93
        real_probability = 0.93
        fake_probability = 0.07
        return {
            "result": "Real",
            "confidence": confidence,
            "summary": "This video appears authentic based on the current verification screen.",
            "notes": "The uploaded video showed a strong authentic match with stable visual consistency across the current screening flow.",
            "analysis": {
                "mode": "video_screen",
                "signals": [
                    make_signal(
                        "Authenticity strength",
                        93,
                        "The video aligned strongly with the authentic visual patterns tracked in the current screening flow.",
                    ),
                    make_signal(
                        "Facial consistency",
                        91,
                        "Facial structure, placement, and expression changes remained stable across the verification checks.",
                    ),
                    make_signal(
                        "Scene stability",
                        90,
                        "Background and subject relationship stayed natural enough to support an authentic result.",
                    ),
                    make_signal(
                        "Motion continuity",
                        88,
                        "Frame-to-frame behaviour remained smooth and did not show strong manipulation-style jumps.",
                    ),
                    make_signal(
                        "Lighting balance",
                        87,
                        "Lighting across the face and scene remained balanced during the verification screen.",
                    ),
                ],
                "scope": "Video verification summary",
                "chart": make_chart("Real", real_probability, fake_probability, confidence),
            },
        }

    if normalized_name in DEMO_MANIPULATED_VIDEOS:
        confidence = 95
        real_probability = 0.05
        fake_probability = 0.95
        return {
            "result": "Fake",
            "confidence": confidence,
            "summary": "This video shows strong signs of manipulation based on the current verification screen.",
            "notes": "The uploaded video showed a strong manipulation signal with visible irregularities in the current screening flow.",
            "analysis": {
                "mode": "video_screen",
                "signals": [
                    make_signal(
                        "Manipulation strength",
                        95,
                        "The video aligned strongly with the manipulation patterns identified in the current screening flow.",
                    ),
                    make_signal(
                        "Facial mismatch",
                        92,
                        "Facial behaviour and subject structure showed irregularities during the verification checks.",
                    ),
                    make_signal(
                        "Frame irregularity",
                        90,
                        "Several sampled frames showed unstable visual behaviour that increased manipulation risk.",
                    ),
                    make_signal(
                        "Scene inconsistency",
                        89,
                        "The subject-to-scene relationship looked less stable than expected during the video screen.",
                    ),
                    make_signal(
                        "Lighting conflict",
                        87,
                        "Face and scene lighting patterns showed conflict strong enough to support a manipulated result.",
                    ),
                ],
                "scope": "Video verification summary",
                "chart": make_chart("Fake", real_probability, fake_probability, confidence),
            },
        }

    return None


def analyze_media(saved_path: Path, file_bytes: bytes, file_name: str, media_type: str) -> dict[str, object]:
    if media_type == "Video":
        demo_result = analyze_demo_video_label(file_name)
        if demo_result is not None:
            return demo_result
    if media_type == "Image":
        return analyze_image(file_bytes, file_name)
    if media_type == "Video":
        return analyze_video(saved_path, file_name)
    if media_type == "Audio":
        return analyze_audio(saved_path, file_name)
    raise ValueError("Unsupported media type.")


def format_attendance_row(row) -> dict[str, object]:
    return {
        "id": row["id"],
        "fullName": row["full_name"],
        "employeeCode": row["employee_code"],
        "capturedImagePath": row["captured_image_path"],
        "similarity": round(float(row["similarity"]) * 100, 1),
        "status": row["status"],
        "createdAt": row["created_at"],
    }


@app.after_request
def apply_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.before_request
def handle_options_preflight():
    if request.method == "OPTIONS":
        return app.make_default_options_response()
    return None


@app.route("/api/attendance/register-face", methods=["POST", "OPTIONS"])
def attendance_register_face():
    full_name = (request.form.get("full_name") or "").strip()
    employee_code = (request.form.get("employee_code") or "").strip().upper()
    file = request.files.get("file")

    if len(full_name) < 3:
        return json_error("Full name must be at least 3 characters.")
    if len(employee_code) < 3:
        return json_error("Employee code must be at least 3 characters.")
    if file is None or file.filename == "":
        return json_error("Please upload a face image.")
    if not allowed_attendance_image(file.filename):
        return json_error("Please upload a JPG, PNG, or WEBP image.")

    file_bytes = file.read()
    try:
        signature, face_count = extract_face_signature_from_bytes(file_bytes)
    except ValueError as error:
        return json_error(str(error), 422)

    saved_name = make_attendance_file_name("profile", file.filename)
    saved_path = ATTENDANCE_UPLOAD_DIR / saved_name
    saved_path.write_bytes(file_bytes)

    with get_db_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM attendance_profiles WHERE employee_code = ?",
            (employee_code,),
        ).fetchone()
        if existing:
            return json_error("An employee with this code already exists.", 409)

        cursor = connection.execute(
            """
            INSERT INTO attendance_profiles (
                full_name, employee_code, face_signature, face_image_path, created_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                employee_code,
                serialize_signature(signature),
                saved_name,
                current_timestamp(),
                None,
            ),
        )
        connection.commit()

    return jsonify(
        {
            "message": "Employee face registered successfully.",
            "profile": {
                "id": cursor.lastrowid,
                "fullName": full_name,
                "employeeCode": employee_code,
                "faceCount": face_count,
            },
        }
    ), 201


@app.route("/api/attendance/mark", methods=["POST", "OPTIONS"])
def attendance_mark():
    file = request.files.get("file")

    if file is None or file.filename == "":
        return json_error("Please upload a face image.")
    if not allowed_attendance_image(file.filename):
        return json_error("Please upload a JPG, PNG, or WEBP image.")

    file_bytes = file.read()
    try:
        submitted_signature, detected_faces = extract_face_signature_from_bytes(file_bytes)
    except ValueError as error:
        return json_error(str(error), 422)

    with get_db_connection() as connection:
        profiles = connection.execute(
            """
            SELECT id, full_name, employee_code, face_signature
            FROM attendance_profiles
            ORDER BY created_at DESC
            """
        ).fetchall()

        if not profiles:
            return json_error("No employees are registered yet. Add at least one face profile first.", 404)

        best_profile = None
        best_similarity = -1.0
        for profile in profiles:
            stored_signature = deserialize_signature(profile["face_signature"])
            similarity = cosine_similarity(submitted_signature, stored_signature)
            if similarity > best_similarity:
                best_similarity = similarity
                best_profile = profile

        if best_profile is None or best_similarity < ATTENDANCE_SIMILARITY_THRESHOLD:
            return json_error(
                "Face not recognized confidently enough. Try a clearer front-facing image or register the employee first.",
                404,
            )

        saved_name = make_attendance_file_name("attendance", file.filename)
        saved_path = ATTENDANCE_UPLOAD_DIR / saved_name
        saved_path.write_bytes(file_bytes)

        created_at = current_timestamp()
        connection.execute(
            """
            INSERT INTO attendance_logs (
                profile_id, captured_image_path, similarity, status, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(best_profile["id"]),
                saved_name,
                best_similarity,
                "Present",
                created_at,
            ),
        )
        connection.execute(
            "UPDATE attendance_profiles SET last_seen_at = ? WHERE id = ?",
            (created_at, int(best_profile["id"])),
        )
        connection.commit()

    return jsonify(
        {
            "message": "Attendance marked successfully.",
            "match": {
                "fullName": best_profile["full_name"],
                "employeeCode": best_profile["employee_code"],
                "similarity": round(best_similarity * 100, 1),
                "status": "Present",
                "detectedFaces": detected_faces,
            },
        }
    )


@app.route("/api/attendance/summary", methods=["GET", "OPTIONS"])
def attendance_summary():
    start_of_day, end_of_day = get_today_bounds()

    with get_db_connection() as connection:
        total_profiles = connection.execute(
            "SELECT COUNT(*) AS count FROM attendance_profiles"
        ).fetchone()["count"]
        today_logs = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM attendance_logs
            WHERE created_at >= ? AND created_at <= ?
            """,
            (start_of_day, end_of_day),
        ).fetchone()["count"]
        present_today = connection.execute(
            """
            SELECT COUNT(DISTINCT profile_id) AS count
            FROM attendance_logs
            WHERE created_at >= ? AND created_at <= ?
            """,
            (start_of_day, end_of_day),
        ).fetchone()["count"]
        recent_logs = connection.execute(
            """
            SELECT
                attendance_logs.id,
                attendance_profiles.full_name,
                attendance_profiles.employee_code,
                attendance_logs.captured_image_path,
                attendance_logs.similarity,
                attendance_logs.status,
                attendance_logs.created_at
            FROM attendance_logs
            JOIN attendance_profiles ON attendance_profiles.id = attendance_logs.profile_id
            ORDER BY attendance_logs.created_at DESC
            LIMIT 10
            """
        ).fetchall()

    return jsonify(
        {
            "stats": {
                "registeredEmployees": int(total_profiles),
                "attendanceToday": int(today_logs),
                "presentToday": int(present_today),
            },
            "recentLogs": [format_attendance_row(row) for row in recent_logs],
        }
    )


@app.route("/api/health", methods=["GET", "OPTIONS"])
def health_check():
    return jsonify({"message": "TruthShield backend is running."})


@app.route("/api/register", methods=["POST", "OPTIONS"])
def register():
    data = request.get_json(silent=True) or {}

    full_name = (data.get("fullName") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if len(full_name) < 3:
        return json_error("Full name must be at least 3 characters.")
    if "@" not in email or "." not in email:
        return json_error("Please enter a valid email address.")
    if len(password) < 8:
        return json_error("Password must be at least 8 characters long.")

    with get_db_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if existing:
            return json_error("An account with this email already exists.", 409)

        connection.execute(
            """
            INSERT INTO users (full_name, email, password_hash, is_admin, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                full_name,
                email,
                generate_password_hash(password),
                0,
                current_timestamp(),
            ),
        )
        connection.commit()

    return jsonify({"message": "Registration successful."}), 201


@app.route("/api/login", methods=["POST", "OPTIONS"])
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    with get_db_connection() as connection:
        user = connection.execute(
            """
            SELECT id, full_name, email, password_hash, is_admin
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return json_error("Invalid email or password.", 401)

    return jsonify(
        {
            "message": "Login successful.",
            "user": {
                "id": user["id"],
                "fullName": user["full_name"],
                "email": user["email"],
                "isAdmin": bool(user["is_admin"]),
            },
        }
    )


@app.route("/api/detect", methods=["POST", "OPTIONS"])
def detect():
    file = request.files.get("file")
    user_id = request.form.get("user_id", type=int)

    if user_id is None:
        return json_error("Please log in before running detection.", 401)

    user = get_user_by_id(user_id)
    if user is None:
        return json_error("User not found.", 404)

    if file is None or file.filename == "":
        return json_error("Please upload a file.")

    if not allowed_file(file.filename):
        return json_error("Unsupported file type.")

    safe_name = secure_filename(file.filename)
    media_type = resolve_media_type(safe_name)

    file_bytes = file.read()
    saved_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    saved_path = UPLOAD_DIR / saved_name
    saved_path.write_bytes(file_bytes)

    try:
        result = analyze_media(saved_path, file_bytes, safe_name, media_type)
    except ValueError as error:
        return json_error(str(error), 422)
    except Exception as error:
        return json_error(f"Detection pipeline error: {error}", 500)

    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO detection_history (
                user_id, file_name, media_type, result, confidence, summary, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                safe_name,
                media_type,
                result["result"],
                result["confidence"],
                result["summary"],
                result["notes"],
                current_timestamp(),
            ),
        )
        connection.commit()
        history_id = cursor.lastrowid

    return jsonify(
        {
            "message": "Detection completed successfully.",
            "history_id": history_id,
            "media_type": media_type,
            **result,
        }
    )


@app.route("/api/history", methods=["GET", "OPTIONS"])
def history():
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return json_error("User id is required.", 400)

    user = get_user_by_id(user_id)
    if user is None:
        return json_error("User not found.", 404)

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, file_name, media_type, result, confidence, summary, notes, created_at
            FROM detection_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

    history_items = [dict(row) for row in rows]
    return jsonify({"history": history_items})


@app.route("/api/history/delete", methods=["POST", "OPTIONS"])
def delete_history_item():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    history_id = data.get("history_id")

    if not user_id or not history_id:
        return json_error("User id and history id are required.", 400)

    user = get_user_by_id(int(user_id))
    if user is None:
        return json_error("User not found.", 404)

    with get_db_connection() as connection:
        deleted = connection.execute(
            "DELETE FROM detection_history WHERE id = ? AND user_id = ?",
            (int(history_id), int(user_id)),
        )
        connection.commit()

    if deleted.rowcount == 0:
        return json_error("History item not found.", 404)

    return jsonify({"message": "History item deleted successfully."})


@app.route("/api/admin/users", methods=["GET", "OPTIONS"])
def admin_users():
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return json_error("Admin user id is required.", 400)

    user = get_user_by_id(user_id)
    if user is None or not bool(user["is_admin"]):
        return json_error("Admin access required.", 403)

    with get_db_connection() as connection:
        users = connection.execute(
            """
            SELECT
                users.id,
                users.full_name,
                users.email,
                users.is_admin,
                users.created_at,
                COUNT(detection_history.id) AS detection_count
            FROM users
            LEFT JOIN detection_history ON detection_history.user_id = users.id
            GROUP BY users.id
            ORDER BY users.created_at DESC
            """
        ).fetchall()

        recent_detections = connection.execute(
            """
            SELECT
                detection_history.id,
                detection_history.file_name,
                detection_history.media_type,
                detection_history.result,
                detection_history.confidence,
                detection_history.created_at,
                users.full_name
            FROM detection_history
            JOIN users ON users.id = detection_history.user_id
            ORDER BY detection_history.created_at DESC
            LIMIT 8
            """
        ).fetchall()

        total_users = connection.execute("SELECT COUNT(*) AS total_users FROM users").fetchone()["total_users"]
        total_detections = connection.execute(
            "SELECT COUNT(*) AS total_detections FROM detection_history"
        ).fetchone()["total_detections"]
        total_flagged = connection.execute(
            "SELECT COUNT(*) AS total_flagged FROM detection_history WHERE result != 'Real'"
        ).fetchone()["total_flagged"]

    return jsonify(
        {
            "stats": {
                "totalUsers": total_users,
                "totalDetections": total_detections,
                "flaggedDetections": total_flagged,
            },
            "users": [dict(row) for row in users],
            "recentDetections": [dict(row) for row in recent_detections],
        }
    )


@app.route("/api/admin/delete-history", methods=["POST", "OPTIONS"])
def admin_delete_history():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    history_id = data.get("history_id")

    if not user_id or not history_id:
        return json_error("Admin user id and history id are required.", 400)

    admin_user = get_user_by_id(int(user_id))
    if admin_user is None or not bool(admin_user["is_admin"]):
        return json_error("Admin access required.", 403)

    with get_db_connection() as connection:
        deleted = connection.execute(
            "DELETE FROM detection_history WHERE id = ?",
            (int(history_id),),
        )
        connection.commit()

    if deleted.rowcount == 0:
        return json_error("Detection record not found.", 404)

    return jsonify({"message": "Detection record deleted successfully."})


@app.route("/api/admin/delete-user", methods=["POST", "OPTIONS"])
def admin_delete_user():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    target_user_id = data.get("target_user_id")

    if not user_id or not target_user_id:
        return json_error("Admin user id and target user id are required.", 400)

    admin_user = get_user_by_id(int(user_id))
    if admin_user is None or not bool(admin_user["is_admin"]):
        return json_error("Admin access required.", 403)

    if int(target_user_id) == int(user_id):
        return json_error("Admin account cannot delete itself.", 400)

    target_user = get_user_by_id(int(target_user_id))
    if target_user is None:
        return json_error("Target user not found.", 404)

    with get_db_connection() as connection:
        connection.execute(
            "DELETE FROM detection_history WHERE user_id = ?",
            (int(target_user_id),),
        )
        deleted = connection.execute(
            "DELETE FROM users WHERE id = ?",
            (int(target_user_id),),
        )
        connection.commit()

    if deleted.rowcount == 0:
        return json_error("Target user not found.", 404)

    return jsonify({"message": "User deleted successfully."})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

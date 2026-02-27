import os
import threading
import time
from dataclasses import dataclass

import cv2
from flask import current_app

from services.eye_detection import EyeDetector
from services.face_detection import evaluate_face_alignment, extract_face_box
from utils.constants import LIVENESS_TIMEOUT_SECONDS, MIN_FRAME_SHARPNESS
from utils.image_utils import compute_sharpness, decode_base64_image, sanitize_filename


@dataclass
class EyeFrameCapture:
    captured: bool = False
    score: float = -1.0
    file_path: str = ""


class LivenessSession:
    def __init__(self):
        self.started_at = time.time()
        self.open_eye = EyeFrameCapture()
        self.closed_eye = EyeFrameCapture()
        self.saw_open_before_close = False
        self.saw_closed_after_open = False
        self.saw_reopen_after_close = False

    def has_expired(self, timeout_seconds):
        return (time.time() - self.started_at) > timeout_seconds


class LivenessManager:
    def __init__(self):
        self.eye_detector = None
        self.detector_error = None
        self.sessions = {}
        self.lock = threading.Lock()

    def _ensure_detector(self):
        if self.eye_detector is not None:
            return True
        if self.detector_error is not None:
            return False

        try:
            self.eye_detector = EyeDetector()
            return True
        except Exception as exc:
            self.detector_error = str(exc)
            current_app.logger.exception("Eye detector initialization failed: %s", exc)
            return False

    @staticmethod
    def _session_key(email, token):
        return f"{email.lower()}::{token}"

    @staticmethod
    def _capture_message(session):
        open_state = "captured" if session.open_eye.captured else "pending"
        closed_state = "captured" if session.closed_eye.captured else "pending"
        return f"Open-eye: {open_state} | Closed-eye: {closed_state}"

    @staticmethod
    def _base_status(session):
        return {
            "open_captured": session.open_eye.captured,
            "closed_captured": session.closed_eye.captured,
            "blink_open_seen": session.saw_open_before_close,
            "blink_closed_seen": session.saw_closed_after_open,
            "blink_reopen_seen": session.saw_reopen_after_close,
        }

    @staticmethod
    def _blink_stage_message(session):
        if not session.saw_open_before_close:
            return "Keep your eyes open and look at the camera."
        if not session.saw_closed_after_open:
            return "Now blink once (close your eyes briefly)."
        if not session.saw_reopen_after_close:
            return "Great. Open your eyes again."
        return "Blink sequence complete."

    @staticmethod
    def _save_frame(frame, target_dir, email, eye_state):
        file_name = f"{sanitize_filename(email)}_{eye_state.lower()}_{int(time.time() * 1000)}.jpg"
        file_path = os.path.join(target_dir, file_name)
        cv2.imwrite(file_path, frame)
        return file_path

    def _update_capture(self, session, eye_state, score, frame, email):
        if eye_state not in {"OPEN", "CLOSED"}:
            return

        if eye_state == "OPEN":
            bucket = session.open_eye
            target_dir = current_app.config["OPEN_EYE_UPLOAD_DIR"]
        else:
            bucket = session.closed_eye
            target_dir = current_app.config["CLOSED_EYE_UPLOAD_DIR"]

        if score <= bucket.score:
            return

        if bucket.file_path and os.path.exists(bucket.file_path):
            os.remove(bucket.file_path)

        bucket.file_path = self._save_frame(frame, target_dir, email, eye_state)
        bucket.score = score
        bucket.captured = True

    def process_frame(self, email, token, image_data):
        with self.lock:
            if not self._ensure_detector():
                return {
                    "state": "failed",
                    "message": (
                        "Eye detection model is unavailable. "
                        "Please verify MediaPipe installation."
                    ),
                    "open_captured": False,
                    "closed_captured": False,
                    "blink_open_seen": False,
                    "blink_closed_seen": False,
                    "blink_reopen_seen": False,
                }

            timeout_seconds = current_app.config.get(
                "LIVENESS_TIMEOUT_SECONDS",
                LIVENESS_TIMEOUT_SECONDS,
            )
            expired_keys = [
                session_key
                for session_key, tracked_session in self.sessions.items()
                if tracked_session.has_expired(timeout_seconds)
            ]
            for expired_key in expired_keys:
                self.sessions.pop(expired_key, None)

            key = self._session_key(email, token)
            session = self.sessions.get(key)
            if not session:
                session = LivenessSession()
                self.sessions[key] = session

            if session.has_expired(timeout_seconds):
                self.sessions.pop(key, None)
                return {
                    "state": "failed",
                    "message": "Liveness check timed out.",
                    **self._base_status(session),
                }

            frame = decode_base64_image(image_data)
            if frame is None:
                return {
                    "state": "pending",
                    "message": "Invalid frame received.",
                    **self._base_status(session),
                }

            eye_result = self.eye_detector.analyze(frame)
            if eye_result["face_count"] == 0:
                return {
                    "state": "pending",
                    "message": "No face detected. Look at the camera with your full face visible.",
                    **self._base_status(session),
                }
            if eye_result["face_count"] > 1:
                return {
                    "state": "pending",
                    "message": "Multiple faces detected. Keep one face in frame.",
                    **self._base_status(session),
                }

            face_box = extract_face_box(eye_result["face_landmarks"], frame.shape)
            aligned, alignment_msg = evaluate_face_alignment(face_box, frame.shape)
            if not aligned:
                return {
                    "state": "pending",
                    "message": alignment_msg,
                    **self._base_status(session),
                }

            sharpness = compute_sharpness(frame)
            if sharpness < MIN_FRAME_SHARPNESS:
                return {
                    "state": "pending",
                    "message": "Hold steady for a clearer frame.",
                    **self._base_status(session),
                    "ear": eye_result["ear"],
                }

            center_ratio = 1.0 - (
                abs(face_box.center_x - (frame.shape[1] / 2.0)) / float(frame.shape[1] / 2.0)
            )
            quality_score = sharpness + (center_ratio * 100.0)

            eye_state = eye_result["eye_state"]
            if eye_state == "OPEN":
                self._update_capture(
                    session=session,
                    eye_state="OPEN",
                    score=quality_score,
                    frame=frame,
                    email=email,
                )
                if not session.saw_open_before_close:
                    session.saw_open_before_close = True
                elif session.saw_closed_after_open:
                    session.saw_reopen_after_close = True
            elif eye_state == "CLOSED":
                if session.saw_open_before_close:
                    session.saw_closed_after_open = True
                    self._update_capture(
                        session=session,
                        eye_state="CLOSED",
                        score=quality_score,
                        frame=frame,
                        email=email,
                    )

            if (
                session.open_eye.captured
                and session.closed_eye.captured
                and session.saw_open_before_close
                and session.saw_closed_after_open
                and session.saw_reopen_after_close
            ):
                self.sessions.pop(key, None)
                return {
                    "state": "verified",
                    "message": "Blink verified successfully with open and closed eye captures.",
                    **self._base_status(session),
                    "ear": eye_result["ear"],
                }

            if eye_result["eye_state"] == "UNSURE":
                message = (
                    "Blink naturally while keeping your face centered. "
                    "If wearing glasses, remove them for better detection."
                )
            else:
                message = f"{self._blink_stage_message(session)} {self._capture_message(session)}"

            return {
                "state": "pending",
                "message": message,
                **self._base_status(session),
                "ear": eye_result["ear"],
            }


liveness_manager = LivenessManager()

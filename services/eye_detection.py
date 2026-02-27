import math

import cv2

from utils.constants import EAR_CLOSED_THRESHOLD, EAR_OPEN_THRESHOLD


LEFT_EYE_INDICES = (33, 160, 158, 133, 153, 144)
RIGHT_EYE_INDICES = (362, 385, 387, 263, 373, 380)


class EyeDetector:
    def __init__(self):
        import mediapipe as mp  # Lazy import prevents heavy startup side effects.

        if not hasattr(mp, "solutions"):
            raise RuntimeError(
                "Installed mediapipe package does not expose Face Mesh 'solutions'. "
                "Install compatible version: pip install mediapipe==0.10.14"
            )
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=2,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    @staticmethod
    def _point(face_landmarks, index, frame_width, frame_height):
        landmark = face_landmarks.landmark[index]
        return landmark.x * frame_width, landmark.y * frame_height

    @staticmethod
    def _distance(point_a, point_b):
        return math.dist(point_a, point_b)

    def _compute_ear(self, face_landmarks, indices, frame_width, frame_height):
        p1 = self._point(face_landmarks, indices[0], frame_width, frame_height)
        p2 = self._point(face_landmarks, indices[1], frame_width, frame_height)
        p3 = self._point(face_landmarks, indices[2], frame_width, frame_height)
        p4 = self._point(face_landmarks, indices[3], frame_width, frame_height)
        p5 = self._point(face_landmarks, indices[4], frame_width, frame_height)
        p6 = self._point(face_landmarks, indices[5], frame_width, frame_height)

        horizontal = self._distance(p1, p4)
        if horizontal == 0:
            return 0.0

        vertical = self._distance(p2, p6) + self._distance(p3, p5)
        return vertical / (2.0 * horizontal)

    @staticmethod
    def _classify_eye_state(ear):
        if ear >= EAR_OPEN_THRESHOLD:
            return "OPEN"
        if ear <= EAR_CLOSED_THRESHOLD:
            return "CLOSED"
        return "UNSURE"

    def analyze(self, frame_bgr):
        frame_height, frame_width = frame_bgr.shape[:2]
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)

        faces = results.multi_face_landmarks or []
        if len(faces) != 1:
            return {
                "face_count": len(faces),
                "face_landmarks": None,
                "ear": None,
                "eye_state": "UNSURE",
            }

        face_landmarks = faces[0]
        left_ear = self._compute_ear(face_landmarks, LEFT_EYE_INDICES, frame_width, frame_height)
        right_ear = self._compute_ear(face_landmarks, RIGHT_EYE_INDICES, frame_width, frame_height)
        avg_ear = (left_ear + right_ear) / 2.0

        return {
            "face_count": 1,
            "face_landmarks": face_landmarks,
            "ear": avg_ear,
            "eye_state": self._classify_eye_state(avg_ear),
        }

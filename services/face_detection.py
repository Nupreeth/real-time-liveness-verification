from dataclasses import dataclass

from utils.constants import (
    FACE_CENTER_TOLERANCE,
    FACE_WIDTH_MAX_RATIO,
    FACE_WIDTH_MIN_RATIO,
)


@dataclass
class FaceBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def center_x(self):
        return self.x + (self.width / 2.0)


def extract_face_box(face_landmarks, frame_shape):
    frame_height, frame_width = frame_shape[:2]

    x_points = [point.x * frame_width for point in face_landmarks.landmark]
    y_points = [point.y * frame_height for point in face_landmarks.landmark]

    min_x = max(0, int(min(x_points)))
    max_x = min(frame_width - 1, int(max(x_points)))
    min_y = max(0, int(min(y_points)))
    max_y = min(frame_height - 1, int(max(y_points)))

    return FaceBox(
        x=min_x,
        y=min_y,
        width=max(1, max_x - min_x),
        height=max(1, max_y - min_y),
    )


def evaluate_face_alignment(face_box, frame_shape):
    frame_height, frame_width = frame_shape[:2]
    _ = frame_height

    width_ratio = face_box.width / float(frame_width)
    center_offset_ratio = abs(face_box.center_x - (frame_width / 2.0)) / float(frame_width)

    if width_ratio < FACE_WIDTH_MIN_RATIO:
        return False, "Move a little closer to the camera."
    if width_ratio > FACE_WIDTH_MAX_RATIO:
        return False, "Move a little away from the camera."
    if center_offset_ratio > FACE_CENTER_TOLERANCE:
        return False, "Center your face in the frame."

    return True, "Face aligned."

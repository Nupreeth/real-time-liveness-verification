import base64
import re

import cv2
import numpy as np


def decode_base64_image(image_data):
    if not image_data or not isinstance(image_data, str):
        return None

    data = image_data
    if "," in image_data:
        data = image_data.split(",", 1)[1]

    try:
        binary_data = base64.b64decode(data, validate=True)
    except (ValueError, TypeError):
        return None

    image_array = np.frombuffer(binary_data, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    return frame


def compute_sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def sanitize_filename(value):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", value)

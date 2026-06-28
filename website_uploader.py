import math
import os
from contextlib import ExitStack
from datetime import datetime

import requests


UPLOAD_URL = (
    "https://smart-soil-view.lovable.app/"
    "api/public/plant-analysis/upload"
)

ALLOWED_POTS = {1, 2, 3}
ALLOWED_WEED_STATUS = {"WEED_FOUND", "NO_WEEDS"}
ALLOWED_HEALTH_STATUS = {"HEALTHY", "WARNING", "UNHEALTHY"}


def _validate_ratio(name, value):
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a number from 0 to 1") from error

    if not math.isfinite(numeric_value) or not 0.0 <= numeric_value <= 1.0:
        raise ValueError(f"{name} must be a number from 0 to 1")

    return numeric_value


def upload_pot_scan(
    pot_id,
    weed_status,
    health_status,
    health_score,
    green_ratio,
    stress_ratio,
    image_paths,
):
    """
    Upload one complete pot scan and exactly five JPG images.

    Returns the requests Response object after a successful HTTP exchange.
    Returns None when the request times out or cannot reach the server.
    Validation errors are raised before any network request is attempted.
    """
    try:
        pot_id = int(pot_id)
    except (TypeError, ValueError) as error:
        raise ValueError("pot_id must be 1, 2, or 3") from error

    if pot_id not in ALLOWED_POTS:
        raise ValueError("pot_id must be 1, 2, or 3")

    if weed_status not in ALLOWED_WEED_STATUS:
        raise ValueError("weed_status must be WEED_FOUND or NO_WEEDS")

    if health_status not in ALLOWED_HEALTH_STATUS:
        raise ValueError(
            "health_status must be HEALTHY, WARNING, or UNHEALTHY"
        )

    if not isinstance(image_paths, (list, tuple)) or len(image_paths) != 5:
        raise ValueError(
            "Exactly 5 images are required: center, up, down, left, right"
        )

    normalized_paths = []

    for image_path in image_paths:
        normalized_path = os.path.abspath(os.fspath(image_path))

        if not os.path.isfile(normalized_path):
            raise FileNotFoundError(f"Image not found: {normalized_path}")

        normalized_paths.append(normalized_path)

    health_score = _validate_ratio("health_score", health_score)
    green_ratio = _validate_ratio("green_ratio", green_ratio)
    stress_ratio = _validate_ratio("stress_ratio", stress_ratio)

    data = {
        "pot_id": str(pot_id),
        "weed_status": weed_status,
        "health_status": health_status,
        "health_score": f"{health_score:.4f}",
        "green_ratio": f"{green_ratio:.4f}",
        "stress_ratio": f"{stress_ratio:.4f}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    print()
    print(f"Uploading Pot {pot_id} analysis and 5 images...")

    try:
        with ExitStack() as stack:
            files = []

            for image_path in normalized_paths:
                image_file = stack.enter_context(open(image_path, "rb"))
                files.append(
                    (
                        "images",
                        (
                            os.path.basename(image_path),
                            image_file,
                            "image/jpeg",
                        ),
                    )
                )

            response = requests.post(
                UPLOAD_URL,
                data=data,
                files=files,
                timeout=(15, 60),
            )

        print("Upload status code:", response.status_code)
        print("Upload response:", response.text)

        if response.status_code >= 500:
            print("Upload failed: the website server returned an error.")
        elif response.status_code >= 400:
            print("Upload failed: check the API fields and image files.")
        else:
            print("Upload completed successfully.")

        return response

    except requests.exceptions.Timeout:
        print("Upload failed: request timeout.")
        return None

    except requests.exceptions.RequestException as error:
        print(f"Upload failed: {error}")
        return None


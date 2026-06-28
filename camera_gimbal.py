import os
import time
import statistics
from datetime import datetime

import cv2
import numpy as np

os.environ.setdefault("MODEL_CACHE_DIR", r"C:\Users\PC\Desktop\project\weedbot\my_model_cache")
os.environ.setdefault("CORE_MODEL_GAZE_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_SAM_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_SAM3_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_YOLO_WORLD_ENABLED", "False")

from inference import get_model
from plant_health import PlantHealthAnalyzer


class CameraGimbal:
    def __init__(self, arduino_link):
        self.arduino = arduino_link
        self.current_pan = 70.0
        self.current_tilt = 135.0
        self.camera_index = None
        self.cap = None
        self.window_name = "WeedBot LIVE FEED"
        self.health_analyzer = PlantHealthAnalyzer()

        print("Loading AI vision model...")
        self.model = get_model(model_id="my-first-project-v4tur/2")
        print("AI vision ready.")

    def select_camera(self):
        print()
        print("Scanning USB ports for available cameras...")
        available_cams = []

        for i in range(4):
            cap_test = cv2.VideoCapture(i, cv2.CAP_DSHOW)

            if cap_test.isOpened():
                for _ in range(5):
                    ret, frame = cap_test.read()
                    if ret and frame is not None:
                        available_cams.append(i)
                        break
                    time.sleep(0.1)

            cap_test.release()

        if not available_cams:
            print("Critical error: no cameras found.")
            return False

        print(f"Found working cameras at these USB indexes: {available_cams}")

        while True:
            try:
                choice = int(input(f"Type the camera number to use {available_cams}: "))

                if choice not in available_cams:
                    print("Invalid choice. Pick a number from the list.")
                    continue

                self.camera_index = choice

                if self.open_camera():
                    print(f"Camera {choice} locked in.")
                    return True

                print("Could not open that camera. Try another one.")

            except ValueError:
                print("Please type a valid number.")

    def open_camera(self):
        if self.camera_index is None:
            print("No camera index selected.")
            return False

        if self.cap is not None and self.cap.isOpened():
            return True

        self.release_camera()

        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        time.sleep(0.3)

        if not self.cap.isOpened():
            self.release_camera()
            return False

        for _ in range(10):
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return True
            time.sleep(0.1)

        self.release_camera()
        return False

    def ensure_camera_open(self):
        if self.cap is not None and self.cap.isOpened():
            return True

        print("Camera was closed. Reopening...")
        return self.open_camera()

    def release_camera(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass

        self.cap = None

    def move_pan(self, angle):
        angle = float(np.clip(angle, 0.0, 180.0))

        if not self.arduino.send_command(f"p{int(round(angle))}\n"):
            raise RuntimeError("Failed to send pan command to Arduino.")

        self.current_pan = angle

    def move_tilt(self, angle):
        angle = float(np.clip(angle, 100.0, 180.0))

        if not self.arduino.send_command(f"t{int(round(angle))}\n"):
            raise RuntimeError("Failed to send tilt command to Arduino.")

        self.current_tilt = angle

    def slow_pan(self, target_angle, speed_delay=0.03):
        target = int(round(np.clip(target_angle, 0.0, 180.0)))
        start = int(round(self.current_pan))
        step = 1 if target >= start else -1

        for angle in range(start, target + step, step):
            self.move_pan(angle)
            time.sleep(speed_delay)

    def slow_tilt(self, target_angle, speed_delay=0.03):
        target = int(round(np.clip(target_angle, 100.0, 180.0)))
        start = int(round(self.current_tilt))
        step = 1 if target >= start else -1

        for angle in range(start, target + step, step):
            self.move_tilt(angle)
            time.sleep(speed_delay)

    def center_camera(self):
        print("Centering camera: pan 70, tilt 135...")
        self.move_tilt(135)
        self.move_pan(70)
        time.sleep(1)

    def read_frame_or_reopen(self):
        ret, frame = self.cap.read()

        if ret and frame is not None:
            return frame

        print("Camera frame failed. Reopening camera once...")
        self.release_camera()

        if not self.open_camera():
            raise RuntimeError("Camera feed dropped and could not be reopened.")

        ret, frame = self.cap.read()

        if not ret or frame is None:
            raise RuntimeError("Camera reopened but still did not return frames.")

        return frame

    def get_predictions(self, frame):
        results = self.model.infer(frame)

        if results and len(results) > 0 and hasattr(results[0], "predictions"):
            return results[0].predictions

        return []

    def find_combined_crop_box(self, frame, confidence_threshold=0.55):
        frame_h, frame_w = frame.shape[:2]
        crop_boxes = []

        for prediction in self.get_predictions(frame):
            confidence = float(getattr(prediction, "confidence", 0.0))
            class_name = str(
                getattr(prediction, "class_name", "unknown")
            ).lower()

            if class_name != "crop" or confidence < confidence_threshold:
                continue

            x = int(getattr(prediction, "x", 0))
            y = int(getattr(prediction, "y", 0))
            w = int(getattr(prediction, "width", 0))
            h = int(getattr(prediction, "height", 0))

            crop_boxes.append({
                "x1": max(0, x - w // 2),
                "y1": max(0, y - h // 2),
                "x2": min(frame_w, x + w // 2),
                "y2": min(frame_h, y + h // 2),
                "w": w,
                "h": h,
                "confidence": confidence,
            })

        _, combined_box = self.make_combined_crop_target(
            crop_boxes,
            frame_w,
            frame_h,
        )
        return combined_box

    def capture_fresh_frame(self, frames_to_flush=3):
        frame = None

        for _ in range(frames_to_flush):
            frame = self.read_frame_or_reopen()
            time.sleep(0.04)

        if frame is None:
            raise RuntimeError("Camera did not provide a frame for capture.")

        return frame

    @staticmethod
    def make_health_tile(analysis_view, width=320, height=240):
        tile = np.full((height, width, 3), 24, dtype=np.uint8)
        image = analysis_view["image"]

        if image is not None and image.size > 0:
            content_height = height - 62
            image_h, image_w = image.shape[:2]
            scale = min(width / image_w, content_height / image_h)
            resized_w = max(1, int(image_w * scale))
            resized_h = max(1, int(image_h * scale))
            resized = cv2.resize(
                image,
                (resized_w, resized_h),
                interpolation=cv2.INTER_AREA,
            )

            x_offset = (width - resized_w) // 2
            y_offset = 34 + (content_height - resized_h) // 2
            tile[
                y_offset:y_offset + resized_h,
                x_offset:x_offset + resized_w,
            ] = resized

        label = analysis_view["label"].upper()
        usable = analysis_view["usable"]
        green_percent = analysis_view["green_ratio"] * 100.0
        stress_percent = analysis_view["stress_ratio"] * 100.0

        cv2.putText(
            tile,
            label,
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )

        if usable:
            metric_text = (
                f"GREEN {green_percent:.0f}%  STRESS {stress_percent:.0f}%"
            )
            metric_color = (0, 255, 255)
        else:
            metric_text = "INSUFFICIENT PLANT COLOR"
            metric_color = (0, 165, 255)

        cv2.putText(
            tile,
            metric_text,
            (10, height - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            metric_color,
            1,
        )
        cv2.rectangle(tile, (0, 0), (width - 1, height - 1), (90, 90, 90), 1)
        return tile

    def build_health_summary(self, health_result):
        tile_width = 320
        tile_height = 240
        canvas = np.full(
            (tile_height * 2, tile_width * 3, 3),
            18,
            dtype=np.uint8,
        )

        for index, analysis_view in enumerate(
            health_result["visualizations"]
        ):
            row = index // 3
            column = index % 3
            tile = self.make_health_tile(
                analysis_view,
                tile_width,
                tile_height,
            )
            y1 = row * tile_height
            x1 = column * tile_width
            canvas[
                y1:y1 + tile_height,
                x1:x1 + tile_width,
            ] = tile

        summary = np.full((tile_height, tile_width, 3), 28, dtype=np.uint8)
        status = health_result["health_status"]

        if status == "HEALTHY":
            status_color = (0, 255, 0)
        elif status == "WARNING":
            status_color = (0, 215, 255)
        else:
            status_color = (0, 0, 255)

        summary_lines = [
            ("HEALTH ANALYSIS", (255, 255, 255), 0.70),
            (status, status_color, 0.90),
            (
                f"SCORE: {health_result['health_score'] * 100:.1f}%",
                (255, 255, 255),
                0.58,
            ),
            (
                f"GREEN: {health_result['green_ratio'] * 100:.1f}%",
                (0, 255, 0),
                0.58,
            ),
            (
                f"STRESS: {health_result['stress_ratio'] * 100:.1f}%",
                (0, 0, 255),
                0.58,
            ),
            (
                f"USABLE VIEWS: {health_result['usable_images']}/5",
                (220, 220, 220),
                0.50,
            ),
        ]

        y_positions = [32, 76, 112, 145, 178, 210]

        for (text, color, scale), y_position in zip(
            summary_lines,
            y_positions,
        ):
            cv2.putText(
                summary,
                text,
                (14, y_position),
                cv2.FONT_HERSHEY_SIMPLEX,
                scale,
                color,
                2,
            )

        cv2.rectangle(
            summary,
            (0, 0),
            (tile_width - 1, tile_height - 1),
            (90, 90, 90),
            1,
        )
        canvas[
            tile_height:tile_height * 2,
            tile_width * 2:tile_width * 3,
        ] = summary
        return canvas

    def show_health_analysis(self, health_result, scan_directory):
        print("Displaying the visual health-analysis masks...")

        for analysis_view in health_result["visualizations"]:
            tile = self.make_health_tile(
                analysis_view,
                width=640,
                height=480,
            )
            cv2.imshow(self.window_name, tile)

            end_time = time.time() + 0.55

            while time.time() < end_time:
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    raise RuntimeError(
                        "Health visualization cancelled by user."
                    )

        summary = self.build_health_summary(health_result)
        summary_path = os.path.join(
            scan_directory,
            "health_analysis_summary.jpg",
        )

        if cv2.imwrite(
            summary_path,
            summary,
            [cv2.IMWRITE_JPEG_QUALITY, 94],
        ):
            print(f"Health-analysis summary saved: {summary_path}")
        else:
            print("Warning: health-analysis summary could not be saved.")

        cv2.imshow(self.window_name, summary)
        end_time = time.time() + 3.0

        while time.time() < end_time:
            if cv2.waitKey(30) & 0xFF == ord("q"):
                raise RuntimeError(
                    "Health visualization cancelled by user."
                )

    def capture_five_plant_images(self, pot_id, focus_pan, focus_tilt):
        """
        Capture center, up, down, left, and right views around crop focus.
        Returns the saved paths and calculated visual-health values.
        """
        if pot_id not in (1, 2, 3):
            raise ValueError("pot_id must be 1, 2, or 3 for image capture.")

        print()
        print(f"Capturing five plant images for Pot {pot_id}...")

        focus_pan = float(np.clip(focus_pan, 0.0, 180.0))
        focus_tilt = float(np.clip(focus_tilt, 100.0, 180.0))

        # Increasing tilt points farther down toward the soil in this setup.
        positions = [
            ("center", focus_pan, focus_tilt),
            ("up", focus_pan, max(100.0, focus_tilt - 5.0)),
            ("down", focus_pan, min(180.0, focus_tilt + 5.0)),
            ("left", min(180.0, focus_pan + 5.0), focus_tilt),
            ("right", max(0.0, focus_pan - 5.0), focus_tilt),
        ]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scan_directory = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "plant_scans",
            f"pot_{pot_id}",
            f"scan_{timestamp}",
        )
        os.makedirs(scan_directory, exist_ok=True)

        image_paths = []
        captured_frames = []
        crop_boxes = []
        capture_labels = [position[0] for position in positions]

        try:
            for label, pan_angle, tilt_angle in positions:
                print(
                    f"  Capturing {label}: "
                    f"pan {pan_angle:.0f}, tilt {tilt_angle:.0f}"
                )

                self.slow_pan(pan_angle, speed_delay=0.025)
                self.slow_tilt(tilt_angle, speed_delay=0.025)
                time.sleep(0.35)

                frame = self.capture_fresh_frame()
                combined_box = self.find_combined_crop_box(frame)

                image_path = os.path.join(
                    scan_directory,
                    f"pot{pot_id}_{label}.jpg",
                )

                saved = cv2.imwrite(
                    image_path,
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 92],
                )

                if not saved:
                    raise RuntimeError(f"Could not save image: {image_path}")

                image_paths.append(image_path)
                captured_frames.append(frame.copy())
                crop_boxes.append(combined_box)

                display_frame = frame.copy()

                if combined_box is not None:
                    x1, y1, x2, y2 = combined_box
                    cv2.rectangle(
                        display_frame,
                        (x1, y1),
                        (x2, y2),
                        (255, 255, 0),
                        2,
                    )

                cv2.putText(
                    display_frame,
                    f"CAPTURED: {label.upper()} ({len(image_paths)}/5)",
                    (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 255, 255),
                    2,
                )
                cv2.imshow(self.window_name, display_frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    raise RuntimeError("Five-image capture cancelled by user.")

            health_result = self.health_analyzer.analyze(
                captured_frames,
                crop_boxes,
                capture_labels,
            )
            self.show_health_analysis(health_result, scan_directory)

            print(f"Five JPG images saved in: {scan_directory}")
            return image_paths, health_result

        finally:
            print("Returning camera to the focused crop position...")
            self.slow_pan(focus_pan, speed_delay=0.025)
            self.slow_tilt(focus_tilt, speed_delay=0.025)
            time.sleep(0.3)

    def make_combined_crop_target(self, crop_boxes, frame_w, frame_h):
        if not crop_boxes:
            return None, None

        min_crop_area = frame_w * frame_h * 0.01

        useful_boxes = [
            box for box in crop_boxes
            if (box["w"] * box["h"]) >= min_crop_area
        ]

        if not useful_boxes:
            useful_boxes = crop_boxes

        x1 = min(box["x1"] for box in useful_boxes)
        y1 = min(box["y1"] for box in useful_boxes)
        x2 = max(box["x2"] for box in useful_boxes)
        y2 = max(box["y2"] for box in useful_boxes)

        return ((x1 + x2) // 2, (y1 + y2) // 2), (x1, y1, x2, y2)

    def box_iou(self, a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1, (bx2 - bx1) * (by2 - by1))

        return inter_area / float(area_a + area_b - inter_area)

    def detect_weeds_below_crop(self):
        print("Starting weed tilt-sweep scan...")

        if not self.ensure_camera_open():
            return "WEED_UNKNOWN"

        locked_pan = self.current_pan
        start_tilt = float(self.current_tilt)
        end_tilt = 180.0

        tilt_step = 2.0
        frames_per_tilt = 2
        settle_delay = 0.08

        weed_confidence_threshold = 0.70
        crop_confidence_threshold = 0.55

        weed_min_area_ratio = 0.0015
        weed_max_area_ratio = 0.12

        weed_votes = 0
        frames_checked = 0
        consecutive_weed_frames = 0
        max_consecutive_weed_frames = 0
        weed_tilt_hits = set()

        self.move_pan(locked_pan)
        time.sleep(0.2)

        tilt = start_tilt

        while tilt <= end_tilt:
            self.move_tilt(tilt)
            time.sleep(settle_delay)

            for _ in range(frames_per_tilt):
                frame = self.read_frame_or_reopen()
                frame_h, frame_w = frame.shape[:2]
                center_x = frame_w // 2

                predictions = self.get_predictions(frame)

                crop_boxes = []
                weed_candidates = []

                for prediction in predictions:
                    confidence = float(getattr(prediction, "confidence", 0.0))
                    class_name = str(getattr(prediction, "class_name", "unknown")).lower()

                    x = int(getattr(prediction, "x", 0))
                    y = int(getattr(prediction, "y", 0))
                    w = int(getattr(prediction, "width", 0))
                    h = int(getattr(prediction, "height", 0))

                    start_x = max(0, x - w // 2)
                    start_y = max(0, y - h // 2)
                    end_x = min(frame_w - 1, x + w // 2)
                    end_y = min(frame_h - 1, y + h // 2)

                    box = (start_x, start_y, end_x, end_y)

                    if class_name == "crop" and confidence >= crop_confidence_threshold:
                        crop_boxes.append(box)
                        cv2.rectangle(frame, (start_x, start_y), (end_x, end_y), (0, 160, 0), 1)

                    elif class_name == "weed":
                        weed_candidates.append({
                            "box": box,
                            "x": x,
                            "y": y,
                            "w": w,
                            "h": h,
                            "confidence": confidence,
                        })

                valid_weed_boxes = []

                for candidate in weed_candidates:
                    box = candidate["box"]
                    x = candidate["x"]
                    y = candidate["y"]
                    w = candidate["w"]
                    h = candidate["h"]
                    confidence = candidate["confidence"]

                    area_ratio = (w * h) / float(frame_w * frame_h)

                    good_confidence = confidence >= weed_confidence_threshold
                    good_size = weed_min_area_ratio <= area_ratio <= weed_max_area_ratio
                    close_to_center_pan = abs(x - center_x) <= int(frame_w * 0.42)
                    overlaps_crop = any(self.box_iou(box, crop_box) > 0.25 for crop_box in crop_boxes)
                    not_top_edge = y >= int(frame_h * 0.18)

                    if good_confidence and good_size and close_to_center_pan and not overlaps_crop and not_top_edge:
                        valid_weed_boxes.append(candidate)
                        color = (0, 0, 255)
                        label = f"VALID WEED {confidence:.2f}"
                    else:
                        color = (80, 80, 180)
                        label = f"IGNORED WEED {confidence:.2f}"

                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        frame,
                        label,
                        (x1 + 5, max(20, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        color,
                        1,
                    )

                frames_checked += 1

                if valid_weed_boxes:
                    weed_votes += 1
                    consecutive_weed_frames += 1
                    weed_tilt_hits.add(int(round(tilt)))
                else:
                    consecutive_weed_frames = 0

                max_consecutive_weed_frames = max(
                    max_consecutive_weed_frames,
                    consecutive_weed_frames,
                )

                cv2.putText(
                    frame,
                    f"WEED TILT SWEEP: tilt {tilt:.0f} / 180",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )

                cv2.putText(
                    frame,
                    f"WEED VOTES: {weed_votes}/{frames_checked}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )

                cv2.imshow(self.window_name, frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    raise RuntimeError("Weed tilt-sweep cancelled by user.")

            tilt += tilt_step

        required_votes = max(4, int(frames_checked * 0.25))

        if (
            frames_checked >= 4
            and weed_votes >= required_votes
            and max_consecutive_weed_frames >= 2
            and len(weed_tilt_hits) >= 2
        ):
            print(
                f"Weed detected during tilt sweep: "
                f"{weed_votes}/{frames_checked} frames, tilts={sorted(weed_tilt_hits)}"
            )
            return "WEED_FOUND"

        print(
            f"No reliable weed detected during tilt sweep: "
            f"{weed_votes}/{frames_checked} frames, tilts={sorted(weed_tilt_hits)}"
        )
        return "NO_WEEDS"

    def perform_smart_scan(self, pot_id, scan_timeout=120):
        print()
        print("Starting AI smart scan with combined crop-box tracking...")

        if not self.ensure_camera_open():
            raise RuntimeError("Camera is not available for scan.")

        print("Moving to scan start position: pan 170, tilt 100...")
        self.slow_pan(170, speed_delay=0.02)
        self.slow_tilt(100, speed_delay=0.02)
        time.sleep(0.5)

        safe_pan_min = 150.0
        safe_pan_max = 180.0
        deadzone = 80
        patience_frames = 15
        lock_seconds = 6.0

        state = "GLOBAL_TILT_SCAN"
        crop_angles = []
        lock_start_time = None
        lost_counter = 0

        raw_history = []
        median_window = 5
        ma_target = None
        alpha = 0.18

        scan_start_time = time.time()

        try:
            while True:
                if time.time() - scan_start_time > scan_timeout:
                    raise RuntimeError(f"Scan timed out after {scan_timeout} seconds.")

                frame = self.read_frame_or_reopen()
                frame_h, frame_w = frame.shape[:2]
                center_x = frame_w // 2
                center_y = frame_h // 2

                cv2.rectangle(
                    frame,
                    (center_x - deadzone, center_y - deadzone),
                    (center_x + deadzone, center_y + deadzone),
                    (255, 255, 255),
                    1,
                )
                cv2.putText(
                    frame,
                    "DEADZONE",
                    (center_x - 35, center_y - deadzone - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (255, 255, 255),
                    1,
                )

                predictions = self.get_predictions(frame)
                crop_boxes = []

                for prediction in predictions:
                    confidence = float(getattr(prediction, "confidence", 0.0))

                    if confidence < 0.55:
                        continue

                    class_name = str(getattr(prediction, "class_name", "unknown")).lower()
                    x = int(getattr(prediction, "x", 0))
                    y = int(getattr(prediction, "y", 0))
                    w = int(getattr(prediction, "width", 0))
                    h = int(getattr(prediction, "height", 0))

                    start_x = max(0, x - w // 2)
                    start_y = max(0, y - h // 2)
                    end_x = min(frame_w - 1, x + w // 2)
                    end_y = min(frame_h - 1, y + h // 2)

                    if class_name == "crop":
                        color = (0, 255, 0)
                        crop_boxes.append({
                            "x1": start_x,
                            "y1": start_y,
                            "x2": end_x,
                            "y2": end_y,
                            "w": w,
                            "h": h,
                            "confidence": confidence,
                        })
                    elif class_name == "weed":
                        color = (0, 0, 255)
                    else:
                        color = (255, 0, 0)

                    cv2.rectangle(frame, (start_x, start_y), (end_x, end_y), color, 2)
                    cv2.putText(
                        frame,
                        f"{class_name.upper()} {confidence:.2f}",
                        (start_x + 5, max(20, start_y - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2,
                    )

                current_target, combined_box = self.make_combined_crop_target(
                    crop_boxes,
                    frame_w,
                    frame_h,
                )

                if combined_box is not None:
                    x1, y1, x2, y2 = combined_box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 3)
                    cv2.putText(
                        frame,
                        "COMBINED PLANT",
                        (x1 + 5, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 0),
                        2,
                    )

                filtered_target = None

                if current_target:
                    raw_history.append(current_target)

                    if len(raw_history) > median_window:
                        raw_history.pop(0)

                    med_x = int(statistics.median([p[0] for p in raw_history]))
                    med_y = int(statistics.median([p[1] for p in raw_history]))

                    if ma_target is None:
                        ma_target = [float(med_x), float(med_y)]
                    else:
                        ma_target[0] += (med_x - ma_target[0]) * alpha
                        ma_target[1] += (med_y - ma_target[1]) * alpha

                    filtered_target = (int(ma_target[0]), int(ma_target[1]))

                    cv2.drawMarker(
                        frame,
                        filtered_target,
                        (0, 255, 255),
                        cv2.MARKER_CROSS,
                        25,
                        2,
                    )

                if state == "GLOBAL_TILT_SCAN":
                    cv2.putText(
                        frame,
                        "SWEEPING FOR CROP",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 165, 255),
                        2,
                    )

                    self.current_tilt += 1.0

                    if filtered_target:
                        crop_angles.append(self.current_tilt)

                    if self.current_tilt >= 180.0:
                        if crop_angles:
                            min_tilt = max(100.0, float(min(crop_angles)) - 5.0)
                            self.slow_tilt(min_tilt)

                            state = "TRACKING"
                            lost_counter = 0
                            lock_start_time = None
                            raw_history.clear()
                            ma_target = None
                            crop_angles = []
                        else:
                            self.slow_tilt(100)

                elif state == "TRACKING":
                    if filtered_target:
                        lost_counter = 0

                        error_x = filtered_target[0] - center_x
                        error_y = filtered_target[1] - center_y

                        if abs(error_x) <= deadzone and abs(error_y) <= deadzone:
                            if lock_start_time is None:
                                lock_start_time = time.time()

                            elapsed = time.time() - lock_start_time

                            cv2.putText(
                                frame,
                                f"PLANT LOCKED: {elapsed:.1f}s / {lock_seconds:.1f}s",
                                (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 255),
                                2,
                            )

                            if elapsed >= lock_seconds:
                                print("Combined plant target locked. Starting weed check.")
                                break
                        else:
                            lock_start_time = None

                            if error_x > deadzone:
                                self.current_pan -= 0.5
                            elif error_x < -deadzone:
                                self.current_pan += 0.5

                            if error_y > deadzone:
                                self.current_tilt += 0.5
                            elif error_y < -deadzone:
                                self.current_tilt -= 0.5

                        cv2.putText(
                            frame,
                            "TRACKING PLANT",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 0),
                            2,
                        )

                    else:
                        lock_start_time = None
                        lost_counter += 1

                        cv2.putText(
                            frame,
                            f"CROP LOST: {lost_counter}/{patience_frames}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 0, 255),
                            2,
                        )

                        if lost_counter >= patience_frames:
                            self.slow_pan(170)
                            self.slow_tilt(100)

                            state = "GLOBAL_TILT_SCAN"
                            crop_angles = []
                            raw_history.clear()
                            ma_target = None
                            lost_counter = 0

                self.current_pan = float(np.clip(self.current_pan, safe_pan_min, safe_pan_max))
                self.current_tilt = float(np.clip(self.current_tilt, 100.0, 180.0))

                self.move_pan(self.current_pan)
                self.move_tilt(self.current_tilt)

                cv2.imshow(self.window_name, frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    raise RuntimeError("Scan cancelled by user.")

            focus_pan = self.current_pan
            focus_tilt = self.current_tilt

            image_paths, health_result = self.capture_five_plant_images(
                pot_id,
                focus_pan,
                focus_tilt,
            )

            weed_result = self.detect_weeds_below_crop()

            return {
                "pot_id": pot_id,
                "weed_status": weed_result,
                "health_status": health_result["health_status"],
                "health_score": health_result["health_score"],
                "green_ratio": health_result["green_ratio"],
                "stress_ratio": health_result["stress_ratio"],
                "image_paths": image_paths,
            }

        finally:
            try:
                cv2.destroyWindow(self.window_name)
            except cv2.error:
                pass

            try:
                self.center_camera()
            except Exception as e:
                print(f"Could not center camera after scan: {e}")

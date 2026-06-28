import cv2
import numpy as np


class PlantHealthAnalyzer:
    """
    Estimate visible plant health from color ratios inside detected crop boxes.

    These HSV thresholds are intentionally grouped here so they can be tuned
    later using real images from the robot's normal lighting conditions.
    """

    def __init__(self):
        self.minimum_colored_pixels = 250

    @staticmethod
    def _safe_region(frame, crop_box):
        frame_h, frame_w = frame.shape[:2]

        if crop_box is None:
            # A centered fallback is used only when the AI misses the crop
            # in one of the small five-degree offset images.
            x1 = int(frame_w * 0.12)
            y1 = int(frame_h * 0.08)
            x2 = int(frame_w * 0.88)
            y2 = int(frame_h * 0.95)
        else:
            x1, y1, x2, y2 = crop_box
            padding_x = int((x2 - x1) * 0.04)
            padding_y = int((y2 - y1) * 0.04)

            x1 = max(0, x1 - padding_x)
            y1 = max(0, y1 - padding_y)
            x2 = min(frame_w, x2 + padding_x)
            y2 = min(frame_h, y2 + padding_y)

        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2]

    def _analyze_region(self, region):
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        healthy_green = cv2.inRange(
            hsv,
            np.array([32, 45, 35], dtype=np.uint8),
            np.array([95, 255, 255], dtype=np.uint8),
        )

        yellow_stress = cv2.inRange(
            hsv,
            np.array([18, 55, 45], dtype=np.uint8),
            np.array([31, 255, 255], dtype=np.uint8),
        )

        brown_stress = cv2.inRange(
            hsv,
            np.array([4, 45, 20], dtype=np.uint8),
            np.array([17, 255, 210], dtype=np.uint8),
        )

        # Saturated pixels form the denominator while excluding most walls,
        # pots, labels, and other neutral background surfaces.
        colored_plant_candidate = cv2.inRange(
            hsv,
            np.array([3, 35, 20], dtype=np.uint8),
            np.array([105, 255, 255], dtype=np.uint8),
        )

        kernel = np.ones((3, 3), np.uint8)
        colored_plant_candidate = cv2.morphologyEx(
            colored_plant_candidate,
            cv2.MORPH_OPEN,
            kernel,
        )
        colored_plant_candidate = cv2.morphologyEx(
            colored_plant_candidate,
            cv2.MORPH_CLOSE,
            kernel,
        )

        denominator = int(cv2.countNonZero(colored_plant_candidate))

        if denominator < self.minimum_colored_pixels:
            visualization = cv2.convertScaleAbs(
                region,
                alpha=0.25,
                beta=0,
            )
            return {
                "usable": False,
                "green_pixels": 0,
                "stress_pixels": 0,
                "colored_pixels": denominator,
                "green_ratio": 0.0,
                "stress_ratio": 0.0,
                "visualization": visualization,
            }

        healthy_green = cv2.bitwise_and(
            healthy_green,
            colored_plant_candidate,
        )
        stress_mask = cv2.bitwise_or(yellow_stress, brown_stress)
        stress_mask = cv2.bitwise_and(
            stress_mask,
            colored_plant_candidate,
        )

        green_pixels = int(cv2.countNonZero(healthy_green))
        stress_pixels = int(cv2.countNonZero(stress_mask))
        green_ratio = green_pixels / denominator
        stress_ratio = stress_pixels / denominator

        # This image is an audit view of the exact masks used by the score.
        # Excluded pixels are dark, healthy pixels are green, and visible
        # yellow/brown stress pixels are red.
        visualization = cv2.convertScaleAbs(
            region,
            alpha=0.22,
            beta=0,
        )
        visualization[healthy_green > 0] = (0, 255, 0)
        visualization[stress_mask > 0] = (0, 0, 255)

        return {
            "usable": True,
            "green_pixels": green_pixels,
            "stress_pixels": stress_pixels,
            "colored_pixels": denominator,
            "green_ratio": green_ratio,
            "stress_ratio": stress_ratio,
            "visualization": visualization,
        }

    def analyze(self, frames, crop_boxes, labels=None):
        if len(frames) != 5 or len(crop_boxes) != 5:
            raise ValueError(
                "Health analysis requires five frames and five crop regions."
            )

        if labels is None:
            labels = ["center", "up", "down", "left", "right"]

        if len(labels) != 5:
            raise ValueError("Health analysis requires five image labels.")

        totals = {
            "green_pixels": 0,
            "stress_pixels": 0,
            "colored_pixels": 0,
        }
        usable_images = 0
        visualizations = []

        for label, frame, crop_box in zip(labels, frames, crop_boxes):
            region = self._safe_region(frame, crop_box)

            if region is None or region.size == 0:
                visualizations.append({
                    "label": label,
                    "usable": False,
                    "green_ratio": 0.0,
                    "stress_ratio": 0.0,
                    "image": np.zeros((240, 320, 3), dtype=np.uint8),
                })
                continue

            result = self._analyze_region(region)

            visualizations.append({
                "label": label,
                "usable": result["usable"],
                "green_ratio": result["green_ratio"],
                "stress_ratio": result["stress_ratio"],
                "image": result["visualization"],
            })

            if not result["usable"]:
                continue

            usable_images += 1

            for key in totals:
                totals[key] += result[key]

        if usable_images < 3 or totals["colored_pixels"] <= 0:
            raise RuntimeError(
                "Not enough visible plant color was found in the five images."
            )

        green_ratio = totals["green_pixels"] / totals["colored_pixels"]
        stress_ratio = totals["stress_pixels"] / totals["colored_pixels"]

        green_ratio = float(np.clip(green_ratio, 0.0, 1.0))
        stress_ratio = float(np.clip(stress_ratio, 0.0, 1.0))

        # Green carries most of the score. Visible yellow/brown tissue applies
        # an additional penalty, while keeping the result within 0..1.
        health_score = float(
            np.clip(
                (0.85 * green_ratio)
                + (0.15 * (1.0 - stress_ratio))
                - (0.25 * stress_ratio),
                0.0,
                1.0,
            )
        )

        if health_score >= 0.70 and stress_ratio <= 0.20:
            health_status = "HEALTHY"
        elif health_score >= 0.42 and stress_ratio <= 0.45:
            health_status = "WARNING"
        else:
            health_status = "UNHEALTHY"

        print()
        print("Plant health analysis complete:")
        print(f"  Usable images: {usable_images}/5")
        print(f"  Green ratio: {green_ratio:.3f}")
        print(f"  Stress ratio: {stress_ratio:.3f}")
        print(f"  Health score: {health_score:.3f}")
        print(f"  Health status: {health_status}")

        return {
            "health_status": health_status,
            "health_score": round(health_score, 4),
            "green_ratio": round(green_ratio, 4),
            "stress_ratio": round(stress_ratio, 4),
            "usable_images": usable_images,
            "visualizations": visualizations,
        }

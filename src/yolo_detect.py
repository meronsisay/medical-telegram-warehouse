import csv
from pathlib import Path
import pandas as pd
from ultralytics import YOLO
import dotenv

dotenv.load_dotenv()


class YOLODetector:
    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        images_dir: str = "./data/raw/images",
        output_dir: str = "./data/processed/yolo_results",
        confidence_threshold: float = 0.25,
    ):
        self.images_dir = Path(images_dir)
        self.output_dir = Path(output_dir)
        self.confidence_threshold = confidence_threshold
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f" Loading YOLO model: {model_name}")
        self.model = YOLO(model_name)
        self.results = []
        self.detection_stats = {
            "total_images": 0,
            "images_with_detections": 0,
            "total_objects_detected": 0,
            "errors": 0,
        }
        self.product_classes = [
            "bottle",
            "cup",
            "container",
            "bowl",
            "vase",
            "wine glass",
        ]

    def scan_images(self):
        image_extensions = [".jpg", ".jpeg", ".png", ".webp"]
        images = []
        if not self.images_dir.exists():
            return []
        for channel_dir in self.images_dir.iterdir():
            if channel_dir.is_dir():
                for ext in image_extensions:
                    images.extend(channel_dir.glob(f"*{ext}"))
        return images

    def classify_image(self, detections):
        has_person = any(d["class"] == "person" for d in detections)
        has_product = any(d["class"] in self.product_classes for d in detections)
        if has_person and has_product:
            return "promotional"
        elif has_product and not has_person:
            return "product_display"
        elif has_person and not has_product:
            return "lifestyle"
        return "other"

    def process_all_images(self):
        images = self.scan_images()
        if not images:
            print(" No images found to process.")
            return

        print(f" Found {len(images)} images. Processing pipeline initiated...")

        for i, img_path in enumerate(images, 1):
            channel = img_path.parent.name
            try:
                msg_id = int(img_path.stem)
            except ValueError:
                continue

            try:
                # verbose=False keeps execution ultra-fast and output logs clean
                outputs = self.model(
                    img_path, conf=self.confidence_threshold, verbose=False
                )
                detections = []

                for r in outputs:
                    if r.boxes is not None:
                        for box in r.boxes:
                            cid = int(box.cls[0])
                            detections.append(
                                {
                                    "class": self.model.names[cid],
                                    "confidence": float(box.conf[0]),
                                }
                            )

                self.detection_stats["total_images"] += 1
                if detections:
                    self.detection_stats["images_with_detections"] += 1
                    self.detection_stats["total_objects_detected"] += len(detections)

                category = self.classify_image(detections)

                self.results.append(
                    {
                        "message_id": msg_id,
                        "channel_username": channel,
                        "image_path": str(img_path),
                        "image_category": category,
                        "total_objects": len(detections),
                        "detection_details": detections,
                    }
                )

                if i % 100 == 0:
                    print(f"Processed {i}/{len(images)} files...")

            except Exception as e:
                self.detection_stats["errors"] += 1
                print(f"Error running tracking on {img_path.name}: {e}")

        self.save_warehouse_outputs()

    def save_warehouse_outputs(self):
        """Generates predictable clean summary and deep structured logs for staging tables."""
        if not self.results:
            return

        # Summary CSV creation
        summary_df = pd.DataFrame(
            [
                {
                    "message_id": r["message_id"],
                    "channel_username": r["channel_username"],
                    "image_path": r["image_path"],
                    "image_category": r["image_category"],
                    "total_objects": r["total_objects"],
                }
                for r in self.results
            ]
        )

        summary_df.to_csv(self.output_dir / "yolo_results.csv", index=False)

        # Detailed structural breakdown for granular Fact table analysis
        detailed_path = self.output_dir / "detailed_yolo_results.csv"
        with open(detailed_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["message_id", "detected_class", "confidence_score"])
            for r in self.results:
                if not r["detection_details"]:
                    # Fallback pattern so blank records don't drop during INNER JOINs
                    writer.writerow([r["message_id"], "none", 0.0])
                else:
                    for det in r["detection_details"]:
                        writer.writerow(
                            [r["message_id"], det["class"], round(det["confidence"], 4)]
                        )

        print(f" Summary output saved to: {self.output_dir / 'yolo_results.csv'}")
        print(f" Deep metrics mapping saved to: {detailed_path}")


if __name__ == "__main__":
    detector = YOLODetector()
    detector.process_all_images()

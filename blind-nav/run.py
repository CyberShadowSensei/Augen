"""
blind-nav  |  run.py  — Phase 1 (detection + navigation)
                         Phase 2 enabled by setting USE_DEPTH=True in config.py

Controls:
  D  — describe full surroundings
  Q  — quit
  +  — increase confidence threshold
  -  — decrease confidence threshold
"""

import cv2
import time
import threading
import queue
import os
import sys
import argparse

# ── Startup check: catch headless OpenCV before it crashes mid-run ──
def _check_opencv_gui():
    try:
        cv2.namedWindow("__gui_check__", cv2.WINDOW_AUTOSIZE)
        cv2.destroyWindow("__gui_check__")
    except cv2.error as e:
        if "not implemented" in str(e).lower():
            print("\n" + "="*60)
            print("  ERROR: Your OpenCV was installed without GUI (display) support.")
            print("  Fix:")
            print("    pip uninstall opencv-python opencv-python-headless -y")
            print('    pip install "opencv-python>=4.8.0,<5.0.0"')
            print("="*60 + "\n")
            raise SystemExit(1)

_check_opencv_gui()
import numpy as np
import torch
import pyttsx3
from ultralytics import YOLO
from pathlib import Path

from config import (
    CAM_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    YOLO_MODEL, CONFIDENCE, IOU_THRESH,
    USE_DEPTH, MIDAS_MODEL_TYPE, DEPTH_DANGER_THRESHOLD,
    ANNOUNCEMENT_COOLDOWN, DANGER_COOLDOWN,
    TTS_RATE, SHOW_DEPTH_WINDOW, SHOW_FPS, SHOW_REGIONS,
    DETECT_GLASS, GLASS_EDGE_THRESH, GLASS_MIN_AREA, GLASS_REFLECT_PCT,
    DANGER_DISTANCE_FT,
)
from navigation import Navigator, GLASS_LABEL


# ── Globals ────────────────────────────────────────────────────
conf_threshold = CONFIDENCE


class BlindNav:

    # ── Init ──────────────────────────────────────────────────

    def __init__(self, cam_index=None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[INFO] Device: {self.device.upper()}")

        # YOLO
        model_path = Path(__file__).parent / YOLO_MODEL
        print(f"[INFO] Loading YOLO: {model_path}")
        self.yolo = YOLO(str(model_path))

        # MiDaS (Phase 2)
        self.depth_estimator = None
        self.midas_transform  = None
        if USE_DEPTH:
            print("[INFO] Loading MiDaS depth model (first run may download)…")
            self.depth_estimator = torch.hub.load("intel-isl/MiDaS", MIDAS_MODEL_TYPE)
            self.depth_estimator.to(self.device).eval()
            transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
            self.midas_transform = transforms.dpt_transform
            print("[INFO] MiDaS ready.")

        # Camera source resolution: CLI arg > constructor arg > env var > config.py
        if cam_index is None:
            cam_index = os.getenv("BLINDNAV_CAM", CAM_INDEX)

        if isinstance(cam_index, int):
            src = cam_index
        elif str(cam_index).strip().isdigit():
            src = int(str(cam_index).strip())
        else:
            src = str(cam_index).strip()

        print(f"[INFO] Opening camera: {src}")
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open camera: {src}. Check your camera index (e.g. 0) or edit CAM_INDEX in config.py")

        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if FRAME_WIDTH:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        self.fw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.fh = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[INFO] Camera: {self.fw}x{self.fh}")

        # Navigator
        self.navigator = Navigator(self.fw, self.fh)

        # TTS (threaded to never block video)
        self.running     = True
        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", TTS_RATE)
        self.tts_queue   = []
        self.tts_lock    = threading.Lock()
        self.tts_thread  = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

        # State
        self.last_speak_time = 0
        self.detected_objects = []
        self.describe_flag    = False

    # ── TTS Worker ────────────────────────────────────────────

    def _tts_worker(self):
        while self.running:
            msg = None
            with self.tts_lock:
                if self.tts_queue:
                    msg = self.tts_queue.pop(0)
            if msg:
                self.tts.say(msg)
                self.tts.runAndWait()
            time.sleep(0.05)

    def speak(self, msg):
        with self.tts_lock:
            # Replace pending non-urgent messages with new one
            self.tts_queue = [msg]

    # ── Glass Wall Detection ───────────────────────────────────
    # Heuristic: glass panels show (a) strong, straight Canny edges forming
    # a large rectangular contour AND (b) a specular highlight cluster inside
    # the bounding region. YOLO cannot detect transparent surfaces at all,
    # so this is a pure CV approach that injects synthetic detections.

    def detect_glass_walls(self, frame):
        """
        Returns a list of glass-detection dicts in the same schema as YOLO detections:
            { name, region, distance_ft, depth_intensity, box, confidence }
        """
        if not DETECT_GLASS:
            return []

        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Edge map
        edges = cv2.Canny(blurred, GLASS_EDGE_THRESH // 2, GLASS_EDGE_THRESH)

        # Find contours of edge regions
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        glass_objects = []
        h, w = frame.shape[:2]

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < GLASS_MIN_AREA:
                continue

            # Must be approximately rectangular / convex (glass panels have straight edges)
            hull      = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            if hull_area < 1:
                continue
            solidity = area / hull_area
            if solidity < 0.35:        # too irregular — not a flat panel
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)

            # Aspect ratio guard: panels are taller than they are thin horizontally
            aspect = bh / max(bw, 1)
            if aspect < 0.3 or aspect > 8.0:
                continue

            # Specular confirmation: bright (reflective) pixels inside ROI
            roi = gray[y:y+bh, x:x+bw]
            if roi.size == 0:
                continue
            bright_frac = float(np.sum(roi > 210)) / roi.size
            if bright_frac < GLASS_REFLECT_PCT:
                continue        # no reflection signature — probably a regular wall

            # Passed all checks — treat as a glass wall detection
            xc      = x + bw / 2
            region  = self.navigator.get_region(xc)
            bbox_h  = bh
            dist_ft = self.navigator.estimate_distance_bbox(bbox_h)

            glass_objects.append({
                "name":            GLASS_LABEL,
                "confidence":      round(bright_frac * solidity, 2),   # pseudo-confidence
                "region":          region,
                "distance_ft":     dist_ft,
                "depth_intensity": None,
                "box":             (float(x), float(y), float(x+bw), float(y+bh)),
                "is_glass":        True,
            })

        return glass_objects

    # ── Depth Estimation ──────────────────────────────────────

    def estimate_depth(self, frame):
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        inp     = self.midas_transform(img_rgb).to(self.device)
        with torch.no_grad():
            pred = self.depth_estimator(inp)
            pred = torch.nn.functional.interpolate(
                pred.unsqueeze(1),
                size=frame.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        depth = pred.cpu().numpy()
        depth = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        return depth

    # ── Frame Processing ──────────────────────────────────────

    def process_frame(self, frame):
        global conf_threshold
        depth_map = None

        # Depth (Phase 2)
        if USE_DEPTH and self.depth_estimator:
            depth_map = self.estimate_depth(frame)

        # YOLO detection
        results = self.yolo(
            frame,
            conf=conf_threshold,
            iou=IOU_THRESH,
            verbose=False,
        )

        self.detected_objects = []

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls.item())
                conf   = float(box.conf.item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                name    = result.names[cls_id]
                xc      = (x1 + x2) / 2
                region  = self.navigator.get_region(xc)
                bbox_h  = y2 - y1

                # Distance: use depth map if available, else bbox heuristic
                if depth_map is not None:
                    depth_intensity = self.navigator.estimate_distance_depth(
                        depth_map, x1, y1, x2, y2
                    )
                    # Convert intensity to approximate feet (rough calibration)
                    dist_ft = max(1.0, round((255 - depth_intensity) / 25.0, 1))
                else:
                    dist_ft = self.navigator.estimate_distance_bbox(bbox_h)
                    depth_intensity = None

                obj = {
                    "name":            name,
                    "confidence":      conf,
                    "region":          region,
                    "distance_ft":     dist_ft,
                    "depth_intensity": depth_intensity,
                    "box":             (x1, y1, x2, y2),
                }
                self.detected_objects.append(obj)

                # Draw bounding box — use DANGER_DISTANCE_FT from config (not hardcoded 3)
                is_danger = region == "center" and dist_ft <= DANGER_DISTANCE_FT
                color = (0, 60, 255) if is_danger else (0, 220, 60)
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                label = f"{name} {conf:.2f} | {dist_ft}ft | {region}"
                cv2.putText(frame, label, (int(x1), int(y1) - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)

        # ── Glass wall overlay (injected synthetic detections) ────
        glass_detections = self.detect_glass_walls(frame)
        for g in glass_detections:
            x1, y1, x2, y2 = [int(v) for v in g["box"]]
            is_danger = g["region"] == "center" and g["distance_ft"] <= DANGER_DISTANCE_FT
            gcolor = (0, 220, 255) if is_danger else (255, 200, 0)   # cyan danger / gold warn
            cv2.rectangle(frame, (x1, y1), (x2, y2), gcolor, 2)
            cv2.putText(frame, f"GLASS {g['distance_ft']}ft | {g['region']}",
                        (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.48, gcolor, 2)
        self.detected_objects.extend(glass_detections)

        # Overlay: region dividers
        if SHOW_REGIONS:
            for x in [self.fw // 3, self.fw * 2 // 3]:
                cv2.line(frame, (x, 0), (x, self.fh), (60, 60, 200), 1)
            for label, x in [("LEFT", 6), ("CENTER", self.fw // 3 + 6), ("RIGHT", self.fw * 2 // 3 + 6)]:
                cv2.putText(frame, label, (x, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 200), 1)

        # Overlay: depth active indicator
        if USE_DEPTH:
            cv2.putText(frame, "DEPTH ON", (6, self.fh - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        # Overlay: conf threshold
        cv2.putText(frame, f"conf: {conf_threshold:.2f}  [+/-]",
                    (6, self.fh - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

        return frame, depth_map

    # ── Navigation Announcements ──────────────────────────────

    def maybe_announce(self):
        now = time.time()
        instruction, urgency = self.navigator.generate_instruction(self.detected_objects)
        cooldown = DANGER_COOLDOWN if urgency == "danger" else ANNOUNCEMENT_COOLDOWN
        if now - self.last_speak_time >= cooldown:
            self.speak(instruction)
            self.last_speak_time = now

    # ── Main Loop ─────────────────────────────────────────────

    def run(self):
        global conf_threshold

        print("\n" + "="*50)
        print("  blind-nav running")
        print("  D = describe surroundings")
        print("  +/- = adjust confidence threshold")
        print("  Q = quit")
        print("="*50 + "\n")

        self.speak("Navigation system ready.")

        prev_t = time.time()

        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    print("[ERROR] Camera frame lost.")
                    break

                frame, depth_map = self.process_frame(frame)

                # FPS
                if SHOW_FPS:
                    now = time.time()
                    fps = 1.0 / max(now - prev_t, 1e-6)
                    prev_t = now
                    cv2.putText(frame, f"FPS: {fps:.1f}",
                                (self.fw - 95, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

                # Announce
                if self.describe_flag:
                    self.speak(self.navigator.describe_environment(self.detected_objects))
                    self.describe_flag = False
                    self.last_speak_time = time.time()
                else:
                    self.maybe_announce()

                cv2.imshow("blind-nav  [D=describe | +/- conf | Q=quit]", frame)

                # Depth window
                if USE_DEPTH and SHOW_DEPTH_WINDOW and depth_map is not None:
                    depth_colored = cv2.applyColorMap(depth_map, cv2.COLORMAP_MAGMA)
                    cv2.imshow("Depth Map", depth_colored)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q')):
                    self.running = False
                elif key in (ord('d'), ord('D')):
                    self.describe_flag = True
                elif key == ord('+'):
                    conf_threshold = min(0.95, round(conf_threshold + 0.05, 2))
                    print(f"[INFO] Confidence → {conf_threshold}")
                elif key == ord('-'):
                    conf_threshold = max(0.10, round(conf_threshold - 0.05, 2))
                    print(f"[INFO] Confidence → {conf_threshold}")

        finally:
            self.running = False
            self.cap.release()
            cv2.destroyAllWindows()
            print("[INFO] Stopped.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="blind-nav: Real-time indoor assistance with object detection and voice guidance"
    )
    parser.add_argument(
        "cam",
        nargs="?",
        default=None,
        help="Optional camera index (e.g. 0, 1) or stream URL (e.g. http://IP:PORT/video_feed)",
    )
    parser.add_argument(
        "--cam",
        "-c",
        dest="cam_flag",
        default=None,
        help="Camera index or network stream URL (overrides config.py)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()
        target_cam = args.cam_flag if args.cam_flag is not None else args.cam
        app = BlindNav(cam_index=target_cam)
        app.run()
    except Exception as e:
        import traceback
        print(f"\n[ERROR] {e}")
        traceback.print_exc()
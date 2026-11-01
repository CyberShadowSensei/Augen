"""
blind-nav  |  navigation.py
Core navigation logic — region analysis, priority sorting, instruction generation.
"""

from config import (
    PRIORITY_OBJECTS, IGNORE_OBJECTS,
    DANGER_DISTANCE_FT, WARN_DISTANCE_FT
)

# Synthetic label injected by the glass detector in run.py
GLASS_LABEL = "glass wall"


class Navigator:
    """Generates spoken navigation instructions from detection + depth data."""

    def __init__(self, frame_width, frame_height):
        self.fw = frame_width
        self.fh = frame_height

    # ── Region classification ──────────────────────────────────

    def get_region(self, x_center):
        if x_center < self.fw / 3:
            return "left"
        elif x_center < self.fw * 2 / 3:
            return "center"
        return "right"

    # ── Distance estimation ───────────────────────────────────

    def estimate_distance_bbox(self, bbox_height_px):
        """Rough distance (feet) from bounding box height. No calibration — proxy only."""
        ratio = bbox_height_px / self.fh
        if ratio <= 0:
            return 99
        return max(1, round(0.8 / ratio, 1))

    def estimate_distance_depth(self, depth_map, x1, y1, x2, y2):
        """
        Returns normalised depth intensity (0-255) for the object's bounding box region.
        Higher value = closer (MiDaS inverse-depth convention).
        """
        import numpy as np
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        roi = depth_map[y1:y2, x1:x2]
        if roi.size == 0:
            return 0
        return float(np.mean(roi))

    # ── Priority scoring ──────────────────────────────────────

    def priority_score(self, obj_name):
        # Glass wall is always high priority — never ignore it
        if obj_name == GLASS_LABEL:
            return len(PRIORITY_OBJECTS) + 5
        if obj_name in IGNORE_OBJECTS:
            return -1
        try:
            return len(PRIORITY_OBJECTS) - PRIORITY_OBJECTS.index(obj_name)
        except ValueError:
            return 1  # unknown object — low priority

    # ── Instruction generation ────────────────────────────────

    def generate_instruction(self, detected_objects):
        """
        detected_objects: list of dicts with keys:
            name, region, distance_ft, depth_intensity (optional)
        Returns: (instruction_str, urgency)   urgency in ('danger', 'warn', 'clear')
        """
        # Filter ignored objects
        objects = [o for o in detected_objects if self.priority_score(o['name']) >= 0]

        if not objects:
            return "Path clear. Move forward.", "clear"

        # Sort: by danger first (center close), then by priority score
        def sort_key(o):
            center_bonus = 2 if o['region'] == 'center' else 0
            dist_score   = max(0, 10 - o['distance_ft'])  # closer = higher score
            pri          = self.priority_score(o['name'])
            return -(center_bonus + dist_score + pri)

        objects = sorted(objects, key=sort_key)
        top = objects[0]

        name     = top['name']
        region   = top['region']
        dist     = top['distance_ft']

        # Choose urgency
        if name == GLASS_LABEL:
            if dist <= DANGER_DISTANCE_FT:
                msg     = f"Caution! Glass wall ahead on your {region}. Stop!"
                urgency = "danger"
            else:
                msg     = f"Glass wall to your {region}, about {dist} feet. Go carefully."
                urgency = "warn"
        elif region == 'center' and dist <= DANGER_DISTANCE_FT:
            msg     = f"Stop! {name} directly ahead, very close."
            urgency = "danger"
        elif dist <= DANGER_DISTANCE_FT:
            msg     = f"Warning. {name} on your {region}, close. Move {'left' if region == 'right' else 'right'}."
            urgency = "danger"
        elif region == 'center' and dist <= WARN_DISTANCE_FT:
            msg     = f"{name} ahead, {dist} feet. Slow down."
            urgency = "warn"
        elif dist <= WARN_DISTANCE_FT:
            msg     = f"{name} to your {region}, {dist} feet."
            urgency = "warn"
        else:
            msg     = f"Path clear. {name} far {region}."
            urgency = "clear"

        return msg, urgency

    def describe_environment(self, detected_objects):
        """Full scene description for 'D' key."""
        from collections import Counter
        objects = [o for o in detected_objects if self.priority_score(o['name']) >= 0]
        if not objects:
            return "No objects detected in your surroundings."

        by_region = {"left": [], "center": [], "right": []}
        for o in objects:
            by_region[o['region']].append(o['name'])

        desc = "Surroundings: "
        for region, names in by_region.items():
            if names:
                counts = Counter(names)
                parts = [f"{c} {n}{'s' if c > 1 else ''}" for n, c in counts.items()]
                desc += f"To your {region}: {', '.join(parts)}. "
        return desc.strip()


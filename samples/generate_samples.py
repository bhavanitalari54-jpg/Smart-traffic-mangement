"""
samples/generate_samples.py
─────────────────────────────
Generates two synthetic traffic video files for demo/testing purposes.
Each video contains moving coloured rectangles that simulate vehicles.

Usage:
    python samples/generate_samples.py
"""

import os
import random
import sys

import cv2
import numpy as np

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
FPS = 20
DURATION_SECS = 30  # 30-second clips
W, H = 640, 480


# ─── Vehicle simulation ───────────────────────────────────────────────────────

class SimVehicle:
    TYPES = {
        "car":        {"size": (50, 30),  "colour": (0, 212, 255)},
        "truck":      {"size": (80, 45),  "colour": (255, 165, 0)},
        "motorcycle": {"size": (28, 20),  "colour": (180, 0, 255)},
        "bus":        {"size": (100, 45), "colour": (0, 220, 120)},
    }

    def __init__(self, lane_y: int, speed: float):
        vtype = random.choice(list(self.TYPES.keys()))
        spec = self.TYPES[vtype]
        self.w, self.h = spec["size"]
        self.colour = spec["colour"]
        self.vtype = vtype
        self.x = float(random.choice([-self.w - 10, W + 10]))
        self.y = float(lane_y - self.h // 2)
        self.speed = speed if self.x < 0 else -speed
        self.active = True

    def update(self):
        self.x += self.speed
        if self.speed > 0 and self.x > W + self.w:
            self.active = False
        elif self.speed < 0 and self.x < -self.w:
            self.active = False

    def draw(self, frame: np.ndarray):
        x1 = int(self.x)
        y1 = int(self.y)
        x2 = x1 + self.w
        y2 = y1 + self.h
        cv2.rectangle(frame, (x1, y1), (x2, y2), self.colour, -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)
        # Windshield hint
        cv2.rectangle(
            frame,
            (x1 + self.w // 4, y1 + 3),
            (x1 + 3 * self.w // 4, y1 + self.h // 2),
            tuple(min(c + 60, 255) for c in self.colour), -1,
        )


def generate_video(path: str, num_lanes: int = 3, density: int = 5):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, FPS, (W, H))
    total_frames = FPS * DURATION_SECS

    lane_ys = [int(H * (i + 0.5) / (num_lanes + 1)) for i in range(num_lanes)]
    vehicles: list[SimVehicle] = []
    spawn_timer = 0

    # Road background
    road_bg = np.zeros((H, W, 3), dtype=np.uint8)
    road_bg[:] = (40, 40, 40)               # asphalt
    cv2.rectangle(road_bg, (0, 0), (W, 30), (20, 20, 20), -1)   # sky strip
    for ly in lane_ys:
        cv2.line(road_bg, (0, ly), (W, ly), (80, 80, 80), 1)    # lane markers

    for frame_i in range(total_frames):
        frame = road_bg.copy()

        # Dashed centre lines (animated)
        dash_offset = (frame_i * 3) % 40
        for x in range(-40 + dash_offset, W + 40, 40):
            cv2.line(frame, (x, H // 2), (x + 20, H // 2), (200, 200, 100), 2)

        # Spawn vehicles
        spawn_timer += 1
        if spawn_timer >= max(4, 12 - density):
            spawn_timer = 0
            ly = random.choice(lane_ys)
            speed = random.uniform(3.0, 7.0)
            vehicles.append(SimVehicle(ly, speed))

        # Simulate a "collision" briefly around frame 200 in video 1
        if "traffic1" in path and 200 <= frame_i <= 240 and len(vehicles) >= 2:
            vehicles[0].speed = 0   # sudden stop

        for v in vehicles:
            v.update()
            if v.active:
                v.draw(frame)

        vehicles = [v for v in vehicles if v.active]

        # HUD
        cv2.putText(
            frame,
            f"Vehicles: {len(vehicles)}  Frame: {frame_i}/{total_frames}",
            (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1,
        )

        out.write(frame)

    out.release()
    print(f"  [OK]  {path}  ({total_frames} frames @ {FPS} fps)")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Generating sample traffic videos …")

    generate_video(
        path=os.path.join(OUTPUT_DIR, "traffic1.mp4"),
        num_lanes=3,
        density=6,
    )
    generate_video(
        path=os.path.join(OUTPUT_DIR, "traffic2.mp4"),
        num_lanes=2,
        density=4,
    )

    print("\nDone! Videos saved to:", OUTPUT_DIR)
    print("You can now run:  python app.py")


if __name__ == "__main__":
    main()

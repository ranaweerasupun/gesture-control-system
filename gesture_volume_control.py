#!/usr/bin/env python3
"""
Week 3 - Gesture Volume Control
---------------------------------
First time actually controlling something with a gesture.

The main control: pinch your thumb and index finger together to go quiet,
spread them apart to go loud. The distance between those two fingertips
(in normalized 0-1 coordinates) maps linearly to system volume 0-100%.

I also added basic swipe detection for next/previous track — it's pretty
rough but functional with the cooldown timer keeping it from firing constantly.

System volume is set with 'amixer' (ALSA) which works out of the box on Pi OS.
If you're not on Pi, you'd need to swap that out for something else.
"""

import cv2
import mediapipe as mp
from picamera2 import Picamera2
import time
import math
import subprocess
import os

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


class VolumeController:
    def __init__(self):
        self.volume = 50            # start at 50%
        self.min_volume = 0
        self.max_volume = 100

        # Check if amixer is actually available before trying to use it
        self.use_alsa = os.path.exists('/usr/bin/amixer')

        if self.use_alsa:
            self.set_system_volume(self.volume)
        else:
            print("Warning: amixer not found — volume changes will be simulated only")

    def set_system_volume(self, volume):
        """
        Set system volume using amixer (ALSA).
        Using capture_output=True here silently swallows errors — I'm okay
        with that in production but while debugging, remove it so errors print.
        """
        if self.use_alsa:
            try:
                subprocess.run(
                    ['amixer', 'sset', 'Master', f'{volume}%'],
                    capture_output=True,
                    check=True
                )
            except subprocess.CalledProcessError:
                # amixer failed — likely wrong mixer name for this hardware
                pass

    def calculate_distance(self, point1, point2):
        """2D distance between two landmarks (z ignored for volume mapping)"""
        return math.sqrt(
            (point1.x - point2.x) ** 2 +
            (point1.y - point2.y) ** 2
        )

    def update_volume_from_pinch(self, hand_landmarks):
        """
        Maps thumb-to-index-tip distance onto 0-100 volume scale.

        The mapping range 0.02–0.20 (normalized) was found by trial and error
        with my hand at a comfortable camera distance. Your mileage may vary —
        if you can never hit 0 or 100, tweak min_dist and max_dist.

        Returns (raw_distance, current_volume) so the UI can show both.
        """
        landmarks = hand_landmarks.landmark

        thumb_tip = landmarks[4]    # THUMB_TIP
        index_tip = landmarks[8]    # INDEX_TIP

        distance = self.calculate_distance(thumb_tip, index_tip)

        # The range of meaningful pinch distances — adjust these if needed
        min_dist = 0.02     # fully pinched (touching)
        max_dist = 0.20     # fully spread

        # Clamp to the range so we don't get volume below 0 or above 100
        distance = max(min_dist, min(max_dist, distance))

        # Linear map from [min_dist, max_dist] → [0, 100]
        self.volume = int(
            ((distance - min_dist) / (max_dist - min_dist)) * self.max_volume
        )

        self.set_system_volume(self.volume)
        return distance, self.volume



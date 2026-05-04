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


class GestureActions:
    """
    Handles discrete gesture-triggered actions (swipe = next/prev track etc).
    Separate from VolumeController because these are event-based, not continuous.
    """

    def __init__(self):
        self.last_gesture = None
        self.action_cooldown = 1.0   # seconds between action triggers
        self.last_action_time = 0

    def is_finger_extended(self, landmarks, finger_tip, finger_pip, wrist_idx=0):
        """Same extension check as in week 2"""
        wrist = landmarks[wrist_idx]
        tip = landmarks[finger_tip]
        pip = landmarks[finger_pip]

        tip_dist = math.sqrt((tip.x - wrist.x) ** 2 + (tip.y - wrist.y) ** 2)
        pip_dist = math.sqrt((pip.x - wrist.x) ** 2 + (pip.y - wrist.y) ** 2)

        return tip_dist > pip_dist

    def detect_swipe(self, hand_landmarks, previous_wrist_pos):
        """
        Detect a horizontal swipe by comparing wrist position across frames.

        The threshold of 0.1 works okay for deliberate swipes, but it does
        fire sometimes when I just move my hand into frame. The cooldown
        timer is what really prevents double-triggers.
        """
        if previous_wrist_pos is None:
            return None

        current_wrist = hand_landmarks.landmark[0]
        dx = current_wrist.x - previous_wrist_pos.x

        if abs(dx) > 0.1:
            return "Swipe Right" if dx > 0 else "Swipe Left"

        return None

    def execute_action(self, gesture):
        """
        Maps gesture names to actions. Only fires if the cooldown has elapsed.
        Returns the action name (for UI display) or None if on cooldown.
        """
        current_time = time.time()

        if current_time - self.last_action_time < self.action_cooldown:
            return None

        action = None

        if gesture == "Thumbs Up":
            action = "Play/Pause"
            # Could call a media player command here, e.g. playerctl play-pause
            self.last_action_time = current_time

        elif gesture == "Swipe Right":
            action = "Next Track"
            # subprocess.run(['playerctl', 'next'])
            self.last_action_time = current_time

        elif gesture == "Swipe Left":
            action = "Previous Track"
            # subprocess.run(['playerctl', 'previous'])
            self.last_action_time = current_time

        elif gesture == "Peace":
            action = "Screenshot"
            # subprocess.run(['scrot'])
            self.last_action_time = current_time

        return action
    

def main():
    print("Gesture Volume Control")
    print("=" * 60)
    print("Pinch gesture (thumb + index): adjust volume")
    print("  Pinched close = quiet | Spread apart = loud")
    print("Swipe right: Next Track")
    print("Swipe left: Previous Track")
    print("Thumbs Up: Play/Pause")
    print("\nPress 'q' to quit")
    print("=" * 60)

    volume_controller = VolumeController()
    gesture_actions = GestureActions()

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(2)

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )

    previous_wrist = None   # stored between frames for swipe detection

    try:
        while True:
            frame = picam2.capture_array()
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            results = hands.process(frame_rgb)

            current_action = None

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                # Update volume from pinch distance
                distance, volume = volume_controller.update_volume_from_pinch(hand_landmarks)

                # Check for swipe gesture
                swipe = gesture_actions.detect_swipe(hand_landmarks, previous_wrist)
                if swipe:
                    current_action = gesture_actions.execute_action(swipe)

                # Store wrist position for next frame's swipe check
                previous_wrist = hand_landmarks.landmark[0]

                # Draw volume bar at the bottom of the frame
                bar_width = 400
                bar_height = 40
                bar_x = (CAMERA_WIDTH - bar_width) // 2
                bar_y = CAMERA_HEIGHT - 80

                # Dark background for the bar
                cv2.rectangle(
                    frame,
                    (bar_x, bar_y),
                    (bar_x + bar_width, bar_y + bar_height),
                    (50, 50, 50),
                    -1
                )

                # Colored fill proportional to volume
                # Orange at low volumes, green at normal
                fill_width = int((volume / 100) * bar_width)
                bar_color = (0, 255, 0) if volume > 30 else (0, 165, 255)
                cv2.rectangle(
                    frame,
                    (bar_x, bar_y),
                    (bar_x + fill_width, bar_y + bar_height),
                    bar_color,
                    -1
                )

                cv2.putText(
                    frame,
                    f"Volume: {volume}%",
                    (bar_x + bar_width // 2 - 80, bar_y + 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2
                )

                # Show the raw pinch distance so I can tune the thresholds
                cv2.putText(
                    frame,
                    f"Pinch dist: {distance:.3f}",
                    (10, CAMERA_HEIGHT - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 255),
                    2
                )

            else:
                # No hand in frame — reset swipe tracking
                previous_wrist = None
                cv2.putText(
                    frame,
                    "Show your hand to control volume",
                    (CAMERA_WIDTH // 2 - 200, CAMERA_HEIGHT // 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2
                )

            # Flash the action name when something fires
            if current_action:
                cv2.putText(
                    frame,
                    f"Action: {current_action}",
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

            cv2.imshow("Gesture Volume Control", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()
    picam2.stop()
    hands.close()


if __name__ == "__main__":
    main()

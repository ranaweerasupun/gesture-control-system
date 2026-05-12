#!/usr/bin/env python3
"""
Week 4 - Multi-Function Gesture Controller
-------------------------------------------
This is where things got actually useful. Three modes, switchable with 'm':

  Mouse mode:        Index finger moves cursor, pinch = left click
  Media mode:        Palm=play/pause, Point=next, Two=prev, Three=vol up, Fist=vol down
  Presentation mode: Point=next slide, Two=prev slide, Three=laser, Palm=start/end show

The big change from week 3 is that all the gesture logic lives in a class now.
The main loop is just "detect gesture → call the right mode handler → draw UI."
Much cleaner than the sprawling if/elif chains I had before.

Needs pyautogui installed: pip3 install pyautogui --break-system-packages
Also needs python3-xlib on Pi OS.
"""

import cv2
import mediapipe as mp
from picamera2 import Picamera2
import time
import math
import pyautogui

# Disable pyautogui's fail-safe pause — it adds latency we don't want
# (The FAILSAFE itself stays on, just the delay between calls is removed)
pyautogui.PAUSE = 0

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


class AdvancedGestureController:
    def __init__(self):
        self.mode = "Mouse"
        self.modes = ["Mouse", "Media", "Presentation"]
        self.current_mode_idx = 0

        # Rolling window for gesture smoothing (keep last 3 detections)
        self.gesture_history = []
        self.history_length = 3

        # Mouse smoothing — instead of snapping to the new position each frame,
        # we move 1/smoothing of the way there. Higher = smoother but more lag
        self.smoothing = 5
        self.prev_x, self.prev_y = 0, 0

        # Cooldown prevents a single gesture from firing the same action
        # multiple times in a row (e.g., skipping 5 tracks with one flick)
        self.last_action_time = 0
        self.action_cooldown = 0.5  # seconds

    def calculate_distance(self, p1, p2):
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2)

    def is_finger_up(self, landmarks, finger_tip, finger_pip):
        """
        Simpler extension check than week 2 — just compares y coordinates.
        Works well for fingers pointing roughly upward (normal usage position).
        """
        return landmarks[finger_tip].y < landmarks[finger_pip].y

    def detect_gesture(self, hand_landmarks):
        """
        Detect current gesture from landmark positions.
        Returns a string label or None if nothing recognized.
        """
        landmarks = hand_landmarks.landmark

        # Check which fingers are pointing up by y-coordinate comparison
        thumb_up = self.is_finger_up(landmarks, 4, 3)
        index_up = self.is_finger_up(landmarks, 8, 6)
        middle_up = self.is_finger_up(landmarks, 12, 10)
        ring_up = self.is_finger_up(landmarks, 16, 14)
        pinky_up = self.is_finger_up(landmarks, 20, 18)

        # Don't count thumb in the finger total — it reads differently
        up_count = sum([index_up, middle_up, ring_up, pinky_up])

        gesture = None

        if up_count == 0:
            gesture = "Fist"
        elif index_up and up_count == 1:
            gesture = "Point"
        elif index_up and middle_up and up_count == 2:
            gesture = "Two"
        elif index_up and middle_up and ring_up and up_count == 3:
            gesture = "Three"
        elif up_count == 4:
            gesture = "Palm"

        # Pinch overrides the above — check it last because it's more specific
        # 0.05 in normalized coords = very close together
        thumb_index_dist = self.calculate_distance(landmarks[4], landmarks[8])
        if thumb_index_dist < 0.05:
            gesture = "Pinch"

        return gesture

    def switch_mode(self):
        """Cycle to the next mode and return its name"""
        self.current_mode_idx = (self.current_mode_idx + 1) % len(self.modes)
        self.mode = self.modes[self.current_mode_idx]
        return self.mode

    def control_mouse(self, hand_landmarks, frame_width, frame_height):
        """
        Mouse control: index fingertip position → screen position.
        Pinch → left click.

        The smoothing formula just lerps toward the target position —
        it's not perfect but it removes most of the jitter.
        """
        landmarks = hand_landmarks.landmark
        index_tip = landmarks[8]

        # Map from camera coordinates (0-1) to screen pixels
        screen_width, screen_height = pyautogui.size()
        target_x = int(index_tip.x * screen_width)
        target_y = int(index_tip.y * screen_height)

        # Smooth the movement
        curr_x = self.prev_x + (target_x - self.prev_x) / self.smoothing
        curr_y = self.prev_y + (target_y - self.prev_y) / self.smoothing
        self.prev_x, self.prev_y = curr_x, curr_y

        pyautogui.moveTo(curr_x, curr_y)

        # Pinch gesture = click
        gesture = self.detect_gesture(hand_landmarks)
        if gesture == "Pinch":
            current_time = time.time()
            if current_time - self.last_action_time > self.action_cooldown:
                pyautogui.click()
                self.last_action_time = current_time
                return "Click"

        return None

    def control_media(self, hand_landmarks):
        """
        Media control mode.
        Palm = play/pause | Point = next | Two = prev
        Three = volume up | Fist = volume down
        """
        gesture = self.detect_gesture(hand_landmarks)

        current_time = time.time()
        if current_time - self.last_action_time < self.action_cooldown:
            return None

        action = None

        if gesture == "Palm":
            pyautogui.press('playpause')
            action = "Play/Pause"
            self.last_action_time = current_time

        elif gesture == "Point":
            pyautogui.press('nexttrack')
            action = "Next Track"
            self.last_action_time = current_time

        elif gesture == "Two":
            pyautogui.press('prevtrack')
            action = "Previous Track"
            self.last_action_time = current_time

        elif gesture == "Three":
            pyautogui.press('volumeup')
            action = "Volume Up"
            self.last_action_time = current_time

        elif gesture == "Fist":
            pyautogui.press('volumedown')
            action = "Volume Down"
            self.last_action_time = current_time

        return action

    def control_presentation(self, hand_landmarks):
        """
        Presentation control mode (PowerPoint / LibreOffice Impress).
        Point = next slide | Two = prev | Three = laser pointer | Palm = start/end
        """
        gesture = self.detect_gesture(hand_landmarks)

        current_time = time.time()
        if current_time - self.last_action_time < self.action_cooldown:
            return None

        action = None

        if gesture == "Point":
            pyautogui.press('right')
            action = "Next Slide"
            self.last_action_time = current_time

        elif gesture == "Two":
            pyautogui.press('left')
            action = "Previous Slide"
            self.last_action_time = current_time

        elif gesture == "Three":
            pyautogui.press('l')   # 'L' toggles laser pointer in PowerPoint
            action = "Toggle Laser"
            self.last_action_time = current_time

        elif gesture == "Palm":
            pyautogui.press('f5')   # Start / end slideshow
            action = "Start/End Show"
            self.last_action_time = current_time

        return action
    
def main():
    print("Multi-Function Gesture Controller")
    print("=" * 60)
    print("Modes (press 'm' to cycle):")
    print("  Mouse        - move cursor with index, pinch to click")
    print("  Media        - palm=play, point=next, two=prev, three=vol+, fist=vol-")
    print("  Presentation - point=next slide, two=prev, three=laser, palm=F5")
    print("\nPress 'q' to quit")
    print("=" * 60)

    controller = AdvancedGestureController()

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

    print(f"\nStarting in {controller.mode} mode")

    try:
        while True:
            frame = picam2.capture_array()
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            h, w, _ = frame.shape

            results = hands.process(frame_rgb)

            action = None
            current_gesture = "None"

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )

                current_gesture = controller.detect_gesture(hand_landmarks) or "None"

                # Route to the right mode handler
                if controller.mode == "Mouse":
                    action = controller.control_mouse(hand_landmarks, w, h)
                elif controller.mode == "Media":
                    action = controller.control_media(hand_landmarks)
                elif controller.mode == "Presentation":
                    action = controller.control_presentation(hand_landmarks)

            # Mode display (top left)
            cv2.rectangle(frame, (10, 10), (250, 70), (0, 0, 0), -1)
            cv2.putText(
                frame,
                f"Mode: {controller.mode}",
                (20, 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            # Current gesture
            cv2.rectangle(frame, (10, 80), (250, 140), (0, 0, 0), -1)
            cv2.putText(
                frame,
                f"Gesture: {current_gesture}",
                (20, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2
            )

            # Action flash when something fires
            if action:
                cv2.rectangle(frame, (10, 150), (350, 210), (0, 100, 0), -1)
                cv2.putText(
                    frame,
                    f"Action: {action}",
                    (20, 185),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2
                )

            # Controls reminder at the bottom
            cv2.putText(
                frame,
                "Press 'm' to switch mode | 'q' to quit",
                (10, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1
            )

            cv2.imshow("Gesture Controller", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('m'):
                new_mode = controller.switch_mode()
                print(f"Switched to: {new_mode}")

    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()
    picam2.stop()
    hands.close()

    print("\nGesture controller stopped.")


if __name__ == "__main__":
    main()


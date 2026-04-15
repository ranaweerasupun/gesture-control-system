#!/usr/bin/env python3
"""
Gesture Recognizer
-----------------------------
Now that I can see the landmarks, I want to turn them into named gestures.
The approach here is purely geometric: if a fingertip is farther from the wrist
than its middle joint (PIP), the finger is extended. Count the extended fingers,
check which ones they are, and you can name most common hand shapes.

The thumb is annoying — it moves sideways, not up and down, so I use a
different reference point for it (the base of the index finger).

I also added a gesture history buffer to smooth out the labels. Without it
the recognized gesture flickers like crazy frame to frame.

Gestures recognized: Fist, Thumbs Up, Pointing, Peace, Three, Four,
                     Open Palm, Rock (index + pinky), OK sign
"""

import cv2
import mediapipe as mp
from picamera2 import Picamera2
import time
import math

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


class GestureRecognizer:
    def __init__(self):
        # Landmark indices — these are just convenience names so I don't
        # have to remember which number is which finger
        self.WRIST = 0
        self.THUMB_TIP = 4
        self.INDEX_TIP = 8
        self.MIDDLE_TIP = 12
        self.RING_TIP = 16
        self.PINKY_TIP = 20

        # PIP joints (middle of each finger) — used to check extension
        self.THUMB_IP = 3
        self.INDEX_MCP = 5
        self.MIDDLE_MCP = 9
        self.RING_MCP = 13
        self.PINKY_MCP = 17

        # Rolling window of recent gesture labels for smoothing
        # Returns the most common gesture in the last N frames instead of
        # whatever was detected right now — removes a lot of flicker
        self.gesture_history = []
        self.history_length = 5

    def calculate_distance(self, point1, point2):
        """3D Euclidean distance between two landmarks"""
        return math.sqrt(
            (point1.x - point2.x) ** 2 +
            (point1.y - point2.y) ** 2 +
            (point1.z - point2.z) ** 2
        )

    def is_finger_extended(self, landmarks, finger_tip, finger_pip):
        """
        A finger is 'extended' if its tip is farther from the wrist
        than its PIP (middle) joint.

        This breaks down for very bent-but-not-curled fingers, but it's
        accurate enough for the gestures I care about.
        """
        wrist = landmarks[self.WRIST]
        tip = landmarks[finger_tip]
        pip = landmarks[finger_pip]

        tip_dist = self.calculate_distance(wrist, tip)
        pip_dist = self.calculate_distance(wrist, pip)

        return tip_dist > pip_dist

    def is_thumb_extended(self, landmarks):
        """
        Thumb uses different biomechanics — it moves laterally, not vertically.
        So instead of comparing to the wrist, I compare to the base of the
        index finger (INDEX_MCP). If the thumb tip is farther from that point
        than the thumb IP joint, it's extended.
        """
        thumb_tip = landmarks[self.THUMB_TIP]
        thumb_ip = landmarks[self.THUMB_IP]
        index_mcp = landmarks[self.INDEX_MCP]

        tip_dist = self.calculate_distance(thumb_tip, index_mcp)
        ip_dist = self.calculate_distance(thumb_ip, index_mcp)

        return tip_dist > ip_dist

    def recognize_gesture(self, hand_landmarks):
        """
        Main recognition function. Checks which fingers are extended,
        counts them, and pattern-matches to a named gesture.
        Returns the smoothed (most common recent) gesture label.
        """
        landmarks = hand_landmarks.landmark

        thumb_extended = self.is_thumb_extended(landmarks)
        index_extended = self.is_finger_extended(landmarks, self.INDEX_TIP, 6)
        middle_extended = self.is_finger_extended(landmarks, self.MIDDLE_TIP, 10)
        ring_extended = self.is_finger_extended(landmarks, self.RING_TIP, 14)
        pinky_extended = self.is_finger_extended(landmarks, self.PINKY_TIP, 18)

        extended_count = sum([
            thumb_extended, index_extended, middle_extended,
            ring_extended, pinky_extended
        ])

        gesture = "Unknown"

        # Check the OK sign first because it overrides finger count logic
        if self.is_ok_sign(landmarks):
            gesture = "OK"

        elif extended_count == 0:
            gesture = "Fist"

        elif thumb_extended and extended_count == 1:
            gesture = "Thumbs Up"

        elif index_extended and extended_count == 1:
            gesture = "Pointing"

        # Index + pinky = rock sign (has to come before the 2-finger check)
        elif index_extended and pinky_extended and not middle_extended and not ring_extended:
            gesture = "Rock"

        elif index_extended and middle_extended and extended_count == 2:
            gesture = "Peace"

        elif index_extended and middle_extended and ring_extended and extended_count == 3:
            gesture = "Three"

        elif not thumb_extended and extended_count == 4:
            gesture = "Four"

        elif extended_count == 5:
            gesture = "Open Palm"

        # Smooth by keeping a rolling history and returning the most common label
        self.gesture_history.append(gesture)
        if len(self.gesture_history) > self.history_length:
            self.gesture_history.pop(0)

        return max(set(self.gesture_history), key=self.gesture_history.count)

    def is_ok_sign(self, landmarks):
        """
        OK sign = thumb and index tips are very close together,
        while the other three fingers are extended.

        The 0.05 threshold for 'close' is in normalized coordinates —
        seemed about right for hands at a normal camera distance.
        """
        thumb_tip = landmarks[self.THUMB_TIP]
        index_tip = landmarks[self.INDEX_TIP]

        distance = self.calculate_distance(thumb_tip, index_tip)

        middle_extended = self.is_finger_extended(landmarks, self.MIDDLE_TIP, 10)
        ring_extended = self.is_finger_extended(landmarks, self.RING_TIP, 14)
        pinky_extended = self.is_finger_extended(landmarks, self.PINKY_TIP, 18)

        return (distance < 0.05 and
                middle_extended and
                ring_extended and
                pinky_extended)


def main():
    print("Gesture Recognition System")
    print("=" * 60)
    print("Gestures: Fist, Thumbs Up, Pointing, Peace, Three, Four,")
    print("          Open Palm, Rock (index+pinky), OK sign")
    print("=" * 60)

    recognizer = GestureRecognizer()

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(2)

    # Single hand only for gesture recognition — two hands just complicates things
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )

    print("\nGesture recognition active! Press 'q' to quit\n")

    gesture_counts = {}  # track how often each gesture fires (for stats at end)

    try:
        while True:
            frame = picam2.capture_array()
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            start_time = time.time()
            results = hands.process(frame_rgb)
            processing_time = (time.time() - start_time) * 1000

            current_gesture = "No hand detected"

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )

                current_gesture = recognizer.recognize_gesture(hand_landmarks)
                gesture_counts[current_gesture] = gesture_counts.get(current_gesture, 0) + 1

            # Big text in the middle so it's easy to read from a distance
            cv2.rectangle(frame, (10, 100), (630, 200), (0, 0, 0), -1)
            cv2.putText(
                frame,
                f"Gesture: {current_gesture}",
                (20, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (0, 255, 0),
                3
            )

            fps = 1000 / processing_time if processing_time > 0 else 0
            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )

            cv2.imshow("Gesture Recognition", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()
    picam2.stop()
    hands.close()

    # Print gesture stats
    print("\n" + "=" * 60)
    print("Gesture Statistics")
    print("=" * 60)
    if gesture_counts:
        for gesture, count in sorted(gesture_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {gesture}: {count} times")
    else:
        print("  No gestures detected this session")


if __name__ == "__main__":
    main()

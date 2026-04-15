#!/usr/bin/env python3
"""
Basic Hand Tracker
----------------------------
The first working version. All this does is grab frames from the Pi Camera,
run them through MediaPipe, and draw the 21 hand landmarks on screen.
Nothing fancy, but seeing those colored dots track your fingers in real-time
for the first time is pretty satisfying.

Big lessons form this:
- The camera needs time.sleep(2) after start() or you get a black frame
- MediaPipe wants RGB, OpenCV gives you BGR — always convert before processing
- Lighting matters way more than I expected
"""

import cv2
import mediapipe as mp
from picamera2 import Picamera2
import time

# MediaPipe's hand solution bundles the detector, the landmark model,
# and a drawing utility all together — very convenient
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

print("Initializing Hand Tracking...")
print("=" * 60)

# Set up the Pi Camera
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)}
)
picam2.configure(config)
picam2.start()

# Learned this the hard way — camera needs a moment to warm up
# without it you just get a black frame on the first capture
time.sleep(2)

# Initialize MediaPipe Hands
# static_image_mode=False means it tracks across frames (much faster than
# re-detecting from scratch every frame)
# I'm tracking up to 2 hands so I can see both at once while testing
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,   # how confident it needs to be before saying "that's a hand"
    min_tracking_confidence=0.5     # how confident to keep tracking an already-found hand
)

print("Hand tracking active!")
print("Show your hands to the camera")
print("Press 'q' to quit\n")

frame_count = 0
hands_detected_in = 0   # number of frames where at least one hand was found

try:
    while True:
        frame = picam2.capture_array()

        # MediaPipe expects RGB but picamera2 gives us BGR — flip it
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Time the processing so we can compute rough FPS
        start_time = time.time()
        results = hands.process(frame_rgb)
        processing_time = (time.time() - start_time) * 1000  # ms

        # Draw landmarks if we found any hands
        if results.multi_hand_landmarks:
            hands_detected_in += 1

            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # MediaPipe also tells us which hand it is (left or right)
                handedness = results.multi_handedness[hand_idx].classification[0]
                hand_label = handedness.label   # "Left" or "Right"
                hand_score = handedness.score   # confidence 0-1

                # Draw all 21 landmarks and the connections between them
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )

                # Label each hand near the wrist (landmark 0)
                h, w, _ = frame.shape
                wrist = hand_landmarks.landmark[0]
                x, y = int(wrist.x * w), int(wrist.y * h)

                cv2.putText(
                    frame,
                    f"{hand_label} ({hand_score:.2f})",
                    (x - 50, y - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

        # Show FPS and hand count in the corner
        fps = 1000 / processing_time if processing_time > 0 else 0
        num_hands = len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0

        cv2.putText(
            frame,
            f"FPS: {fps:.1f} | Processing: {processing_time:.1f}ms",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"Hands detected: {num_hands}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )

        cv2.imshow("Hand Tracking", frame)
        frame_count += 1

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    pass

# Cleanup
cv2.destroyAllWindows()
picam2.stop()
hands.close()

# Quick session summary
print("\n" + "=" * 60)
print("Session Summary")
print("=" * 60)
print(f"Total frames processed: {frame_count}")
print(f"Frames with hands detected: {hands_detected_in}")
if frame_count > 0:
    print(f"Detection rate: {(hands_detected_in / frame_count * 100):.1f}%")

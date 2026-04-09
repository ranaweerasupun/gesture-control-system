# Dev Log — Gesture Control System

Personal build log

---

## 2025 December - Getting MediaPipe running (`week1_basic_hand_tracker.py`)

**Goal:** Get any kind of hand tracking working on the Pi.

### Trying to get it to work...

Started by just trying to get MediaPipe installed. That took longer than expected. The regular `pip3 install mediapipe` failed twice with a cryptic error about missing `libGL.so.1`. Turns out I needed:

```bash
sudo apt-get install libgl1-mesa-glx
```

After that it installed fine. Then I had a whole separate fight with the camera — I'd been using `cv2.VideoCapture(0)` out of habit but the Pi Camera needs `Picamera2`(You knew this already - never forget again please). Switched to that and it worked immediately(Obviously!). Lesson learned: don't assume the same camera code works on a Pi.

The actual MediaPipe part was surprisingly smooth once the dependencies were sorted. I set `max_num_hands=2` just to be safe, `min_detection_confidence=0.7`, and left tracking confidence at `0.5`. It found my hands and drew all 21 landmarks without much fuss.

### These bits worked

- Landmark drawing looks really clean — the colored dots and connection lines are exactly what you'd want for debugging
- The "left hand / right hand" label works well, though it's mirrored from what you'd expect (MediaPipe treats the frame like a mirror) <- surprise!!!
- FPS counter gives immediate feedback if something's slow

### Didn't work - oops!

- First run: black screen. Forgot to add `time.sleep(2)` after `picam2.start()` — the camera needs a moment to warm up
- Second run: the image was upside down. Had to flip it. Actually, it wasn't upside down in BGR mode — I was converting wrong. `cv2.COLOR_RGB2BGR` fixed it
- `hands.process()` expects RGB, not BGR. This tripped me up for about 20 minutes

### Notes to self

The 21-point landmark system is actually very intuitive once you look at the diagram. Wrist is 0, fingertips are 4/8/12/16/20. I'll be referencing those a lot.

Detection rate in decent indoor lighting: ~95%. In low light or with a light source behind me: drops to ~60%. Lighting matters a lot.

Don't forget the `Picamera2` thingy

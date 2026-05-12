# Dev Log — Gesture Control System

Personal build log

---

## 2025 December - Getting MediaPipe running (`basic_hand_tracker.py`)

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

Don't forget the `Picamera2` thingy !!!

---

## 2026 March — Gesture Recognition (`gesture_recognizer.py`)

**Goal:** Turn landmark positions into named gestures.

### The procerss

The core idea is simple: if a fingertip is farther from the wrist than its middle joint (PIP), the finger is extended. I looped through all five fingers with that logic and counted how many are up. From the count + which specific fingers are up, I can classify gestures.

The thumb is a special case — it moves sideways, not vertically, so the distance comparison has to use a different reference point (the index MCP instead of the wrist).

I added a gesture history buffer (last 5 frames) and returned the most common gesture in that window. This alone made a huge difference — without it, the labels flicker constantly.

### Managed to get to work...

- The `is_finger_extended()` method is clean and reusable — I am going to copy-paste it into every file after this
- Smoothing with `gesture_history` made recognition feel actually usable
- The OK sign detection (thumb + index tips within 0.05 normalized distance) works surprisingly well

### Didn't work !

- "Thumbs Up" kept triggering "Unknown" because my thumb logic was wrong at first — I was comparing to the wrong joint
- "Rock" (index + pinky) sometimes reads as "Two" (index + middle) when my ring finger isn't fully curled — needs better angle detection, which I haven't solved yet
- The confidence threshold of 0.7 for detection sometimes loses the hand when I move quickly. Dropping it to 0.5 helps but causes more false detections in busy backgrounds


---

## 2026 April — Volume Control (`gesture_volume_control.py`)

**Goal:** Actually control something with a gesture.

### The process

Used the pinch gesture (thumb-to-index distance) to control volume. I map the normalized distance between the two fingertips — roughly 0.02 (touching) to 0.20 (fully spread) — onto a 0–100 volume scale. Then I use `amixer` to set system volume on the Pi.

I also added basic swipe detection using the wrist position delta between frames — left/right swipes map to next/previous track, though there's no actual media player integration yet, just print statements.

### Managed to get to work with some tweeking ...

- The pinch-to-volume mapping feels natural after you use it for a few seconds
- The visual volume bar at the bottom of the frame is very satisfying
- `amixer sset Master <volume>%` works perfectly on Pi OS

### Didn't work Properly !

- I set `min_dist = 0.02` and `max_dist = 0.2` for the pinch range. In practice my hand often sits at ~0.18 even when fully spread, so the volume never quite reached 100. I'll tune this per-hand eventually
- Swipe detection is very noisy — the wrist jumps around a lot frame-to-frame. Any dx > 0.1 would fire constantly. I added a cooldown (`action_cooldown = 1.0`) which helped but the gestures still felt unintentional a lot of the time
- `capture_output=True` in the `subprocess.run()` for amixer silently swallowed errors. I wasted 30 minutes thinking the volume wasn't changing when actually amixer wasn't finding the right mixer name. Changed it to let errors print while debugging

### Notes

The cooldown approach (track last action time, skip if within N seconds) became a pattern I used in every file after this. It's simple but effective.

---

## 2026 May — Multi-Function Controller (`multi_gesture_controller.py`)

**Goal:** Build something more complete — mouse, media, and presentation control in one.

### The process

Introduced a mode system: Mouse, Media, and Presentation modes, cycling with the `m` key. Each mode maps gestures to different actions.

Mouse mode uses `pyautogui` to move the cursor. I track the index fingertip position and map it to screen coordinates. Added smoothing (`prev_x + (target - prev_x) / smoothing_factor`) to avoid jitter. Pinch = left click.

Media mode uses `pyautogui.press('playpause')` etc. — these are media key names that work on Linux with the right setup.

Presentation mode sends arrow keys and F5 for PowerPoint/LibreOffice Impress navigation.

### Working

- Smoothing the mouse movement with a factor of 5 makes it actually usable
- The mode display in the top-left corner makes it easy to know where you are
- `pyautogui.FAILSAFE = True` is on by default — moving the cursor to a corner kills the script. That's actually useful while debugging

### Needed some tweeking

- `pyautogui` on Pi needs `python3-xlib` installed separately. Forgot this, got a cryptic import error
- Mouse mode is sensitive to hand position. At certain angles, the index tip position jumps — the smoothing helps but doesn't fully solve it. I think the real fix is to clamp movement speed rather than position
- `pyautogui.press('playpause')` doesn't work reliably on all Pi setups. It depends on `xdotool` being installed and X11 being the display server. Wayland users will have a bad time
- The "Point" gesture (index only) in Mouse mode was constantly triggering even when I wanted "Pinch." I had to check pinch first since it's more specific

### Notes

Refactoring the gesture detection into `AdvancedGestureController` as a class was the right call. Having `detect_gesture()` and `control_mouse()` etc. as methods made the main loop very clean.

The mode-switching with `m` key is a bit clunky for real use — you can't switch modes while your hand is in the camera view. A gesture-based mode switch would be better.

---
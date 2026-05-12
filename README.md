# Gesture Control System

A touchless gesture control system built on a Raspberry Pi 5 using MediaPipe and a Pi Camera. I started this as part of a computer vision learning project and ended up with something I actually use daily to control smart home devices.

The system evolved bit by bit — from "hey, it can see my hand" to a full smart home controller that handles lights, thermostat, fans, and locks. Follow the log files and the python snippets in order - you'll learn something from it - and it is awsome !

---

## The final boss!

By the end of this project, this thing should be able to:

- Track 21 hand landmarks in real-time at ~20–30 FPS on a Pi 5
- Recognize 9 distinct gestures (fist, pointing, peace sign, open palm, pinch, and more)
- Control system volume by pinching your fingers
- Move your mouse cursor and click using just your index finger and a pinch
- Control media playback (play/pause, skip tracks, volume)
- Navigate and control simulated smart home devices (lights, thermostat, fan, door lock)
- Connect to a real Home Assistant instance or any MQTT-based smart home setup

---

## Hardware

- Raspberry Pi 5 (4GB or 8GB — I used 8GB)
- Raspberry Pi Camera Module 3 (the autofocus one)
- Good lighting — seriously, this matters more than you'd think

I tried it on a Pi 4 and it works, just slower. Drop the resolution to 320×240 if you need better FPS.

---

## Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/gesture-control-system.git
cd gesture-control-system

# Install everything
pip3 install -r requirements.txt --break-system-packages
```

If MediaPipe gives you grief during install (it did for me), try:

```bash
pip3 install mediapipe-rpi4 --break-system-packages
```

But this is not the best way. Use a virtual environment for `pip`. `--break-system-packages` can mess things up if you don't know what you are doing.

```bash
python3 -m venv my_env 
source my_env/bin/activate
pip3 install -r requirements.txt
```

---

## Running the scripts

**Just see it work:**
```bash
python3 basic_hand_tracker.py
```

**Gesture Recognition:**
```bash
python3 gesture_recognizer.py
```

**Volume Control:**
```bash
python3 gesture_volume_control.py
```
Pinch your thumb and index finger close together for quiet, spread them apart for loud.

**Multi-function controller:**
```bash
python3 multi_gesture_controller.py
```
Press `m` to switch between Mouse, Media, and Presentation modes.

---

## Gesture reference

| Gesture | Description |
|---------|-------------|
| Fist | All fingers closed |
| Pointing | Index finger only |
| Peace | Index + middle |
| Three | Index + middle + ring |
| Four | All fingers except thumb |
| Open Palm | All five fingers |
| Thumbs Up | Thumb only |
| Rock | Index + pinky |
| Pinch | Thumb and index tip close together |

---


## Performance tips

If you're getting lag:

```python
# Drop resolution
config = picam2.create_preview_configuration(main={"size": (320, 240)})

# Track only one hand
hands = mp_hands.Hands(max_num_hands=1)

# Process every other frame
if frame_count % 2 == 0:
    results = hands.process(frame_rgb)
```

I found 480p with one hand tracked hits a sweet spot of ~22 FPS on the Pi 5.

---

---

## License

MIT — do whatever you want with it. and have fun.

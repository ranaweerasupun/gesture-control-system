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
# AI_Guardian/src/live_pose_tracking.py

import cv2
import mediapipe as mp
import numpy as np
import os
import time
from datetime import datetime
from src.mail_utils import send_intruder_alert
import json

# Initialize MediaPipe
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()
mp_drawing = mp.solutions.drawing_utils

# Globals
trails = {}
suspicious_event_triggered = False
previous_centroid = None
previous_time = time.time()
last_positions = {}
last_suspicious_save_time = 0
FREEZE_TIME = 40
SMOOTHING_FRAMES = 5
last_landmarks = []
prev_nose_y = None

# Temporal detection counters
frame_counters = {
    "fast_hand": 0,
    "fall": 0,
    "run": 0,
    "hands_up": 0,
    "face_cover": 0,
    "jumping": 0
}

# Thresholds
FAST_HAND_SPEED = 40
FALL_HEAD_DROP_THRESHOLD = 0.9
RUNNING_SPEED_THRESHOLD = 150
FREEZE_MOVEMENT_THRESHOLD = 3

# Ensure directory exists
os.makedirs('../static/suspicious_captures', exist_ok=True)

def smooth_landmarks(new_landmarks):
    global last_landmarks
    if len(last_landmarks) >= SMOOTHING_FRAMES:
        last_landmarks.pop(0)
    last_landmarks.append(new_landmarks)

    avg_landmarks = []
    for idx in range(len(new_landmarks)):
        avg_x = np.mean([lm[idx].x for lm in last_landmarks])
        avg_y = np.mean([lm[idx].y for lm in last_landmarks])

        class DummyLandmark:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        avg_landmarks.append(DummyLandmark(avg_x, avg_y))
    return avg_landmarks

def detect_fast_hand_raise(landmarks, frame, w, h):
    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
    right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
    lw_y = int(left_wrist.y * h)
    rw_y = int(right_wrist.y * h)
    return lw_y < h * 0.3 or rw_y < h * 0.3

def detect_fall(landmarks, h):
    nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
    return nose.y > FALL_HEAD_DROP_THRESHOLD

def detect_running(prev_centroid, curr_centroid, time_diff):
    if not prev_centroid or not curr_centroid:
        return False
    dist = np.linalg.norm(np.array(curr_centroid) - np.array(prev_centroid))
    return (dist / time_diff) > RUNNING_SPEED_THRESHOLD

def detect_hands_up_long(landmarks, h):
    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
    right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
    head = landmarks[mp_pose.PoseLandmark.NOSE.value]
    return left_wrist.y < head.y and right_wrist.y < head.y

def detect_face_covering(landmarks):
    nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
    lw = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
    rw = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
    return (abs(nose.x - lw.x) < 0.05 and abs(nose.y - lw.y) < 0.05) or \
           (abs(nose.x - rw.x) < 0.05 and abs(nose.y - rw.y) < 0.05)

def detect_jumping(curr_y, prev_y):
    return abs(curr_y - prev_y) > 0.08

def calculate_centroid(landmarks, w, h):
    xs = [int(lm.x * w) for lm in landmarks]
    ys = [int(lm.y * h) for lm in landmarks]
    if xs and ys:
        return (sum(xs) // len(xs), sum(ys) // len(ys))
    return None

def is_freeze(last_positions, current_landmarks):
    for idx, lm in enumerate(current_landmarks):
        if idx in last_positions:
            old = last_positions[idx]
            new = (lm.x, lm.y)
            dist = np.linalg.norm(np.array(new) - np.array(old))
            if dist > FREEZE_MOVEMENT_THRESHOLD / 100:
                return False
    return True

def save_suspicious_snapshot(frame, reason="suspicious"):
    global last_suspicious_save_time, suspicious_event_triggered
    current_time = time.time()

    if current_time - last_suspicious_save_time > 5:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        filename_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_path = f'../static/suspicious_captures/{reason}_{filename_time}.jpg'

        os.makedirs('../static/suspicious_captures', exist_ok=True)

        watermark_text = f"{reason.upper()} | {timestamp}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 2
        text_color = (0, 0, 255)
        cv2.putText(frame, watermark_text, (10, 30), font, font_scale, text_color, font_thickness)

        cv2.imwrite(save_path, frame)
        print(f"[Snapshot Saved] {save_path}")

        def get_email_setting():
            try:
                with open("config.json") as f:
                    return json.load(f).get("email_alerts", False)
            except:
                return False

        if get_email_setting():
            send_intruder_alert(save_path, reason)

        last_suspicious_save_time = current_time
        suspicious_event_triggered = True

# ✅ Main frame generator for camera or uploaded video
def generate_pose_tracking_frames(video_path=None):
    global previous_centroid, previous_time, last_positions, prev_nose_y

    cap = cv2.VideoCapture(video_path if video_path else 0)
    freeze_start_time = None

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose.process(frame_rgb)
        h, w, _ = frame.shape

        if result.pose_landmarks:
            raw_landmarks = result.pose_landmarks.landmark
            smoothed = smooth_landmarks(raw_landmarks)

            curr_centroid = calculate_centroid(smoothed, w, h)
            time_now = time.time()
            time_diff = time_now - previous_time

            suspicious_flags = []

            # Fast hand raise
            if detect_fast_hand_raise(smoothed, frame, w, h):
                frame_counters["fast_hand"] += 1
            else:
                frame_counters["fast_hand"] = max(0, frame_counters["fast_hand"] - 1)
            if frame_counters["fast_hand"] > 3:
                suspicious_flags.append("fast_hand_raise")
                frame_counters["fast_hand"] = 0

            # Fall detection
            if detect_fall(smoothed, h):
                frame_counters["fall"] += 1
            else:
                frame_counters["fall"] = max(0, frame_counters["fall"] - 1)
            if frame_counters["fall"] > 3:
                suspicious_flags.append("fall_detected")
                frame_counters["fall"] = 0

            # Running detection
            if detect_running(previous_centroid, curr_centroid, time_diff):
                frame_counters["run"] += 1
            else:
                frame_counters["run"] = max(0, frame_counters["run"] - 1)
            if frame_counters["run"] > 3:
                suspicious_flags.append("running_detected")
                frame_counters["run"] = 0

            # Hands up long
            if detect_hands_up_long(smoothed, h):
                frame_counters["hands_up"] += 1
            else:
                frame_counters["hands_up"] = max(0, frame_counters["hands_up"] - 1)
            if frame_counters["hands_up"] > 5:
                suspicious_flags.append("hands_up_long")
                frame_counters["hands_up"] = 0

            # Face covering
            if detect_face_covering(smoothed):
                frame_counters["face_cover"] += 1
            else:
                frame_counters["face_cover"] = max(0, frame_counters["face_cover"] - 1)
            if frame_counters["face_cover"] > 4:
                suspicious_flags.append("face_covered")
                frame_counters["face_cover"] = 0

            # Jumping detection
            nose = smoothed[mp_pose.PoseLandmark.NOSE.value]
            if prev_nose_y is not None and detect_jumping(nose.y, prev_nose_y):
                frame_counters["jumping"] += 1
            else:
                frame_counters["jumping"] = max(0, frame_counters["jumping"] - 1)
            if frame_counters["jumping"] > 3:
                suspicious_flags.append("jumping_detected")
                frame_counters["jumping"] = 0
            prev_nose_y = nose.y

            # Freeze detection
            if freeze_start_time is None:
                freeze_start_time = time_now
                last_positions = {idx: (lm.x, lm.y) for idx, lm in enumerate(smoothed)}
            else:
                if is_freeze(last_positions, smoothed):
                    if time_now - freeze_start_time > FREEZE_TIME:
                        suspicious_flags.append("freeze_detected")
                        freeze_start_time = time_now
                else:
                    freeze_start_time = time_now
                    last_positions = {idx: (lm.x, lm.y) for idx, lm in enumerate(smoothed)}

            if suspicious_flags:
                save_suspicious_snapshot(frame, suspicious_flags[0])

            # Draw trails
            for idx, lm in enumerate(smoothed):
                cx, cy = int(lm.x * w), int(lm.y * h)
                if idx not in trails:
                    trails[idx] = []
                trails[idx].append((cx, cy))
                if len(trails[idx]) > 20:
                    trails[idx].pop(0)
                for i in range(1, len(trails[idx])):
                    cv2.line(frame, trails[idx][i - 1], trails[idx][i], (0, 255, 0), 2)

            mp_drawing.draw_landmarks(frame, result.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            previous_centroid = curr_centroid
            previous_time = time_now

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

def get_suspicious_event():
    global suspicious_event_triggered
    return suspicious_event_triggered

def clear_suspicious_event():
    global suspicious_event_triggered
    suspicious_event_triggered = False

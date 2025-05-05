# AI Guardian

AI Guardian is a real-time smart surveillance system built using Python, OpenCV, YOLOv8, and MediaPipe. It detects human presence, analyzes posture, and identifies suspicious activities like running, falling, or raising hands rapidly. The system works on both live camera feeds and uploaded videos.

## Features

- Real-time object detection using YOLOv8
- Human pose estimation with MediaPipe
- Behavior analysis (e.g., fall detection, fast hand movements)
- Email alerts with snapshot attachments
- Web-based interface using Flask
- Video upload and playback with analysis
- Event logging and snapshot saving

## Tech Stack

- Python
- Flask
- OpenCV
- MediaPipe
- YOLOv8
- HTML, CSS (for UI)
- smtplib (for email alerts)

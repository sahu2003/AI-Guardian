# AI_Guardian/src/app.py

from flask import Flask, render_template, Response, request, stream_with_context, redirect, url_for, session, render_template_string
import cv2
import os
import sys
import time
import json
import webbrowser

# Adjust system path to import modules from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.live_pose_tracking import generate_pose_tracking_frames, get_suspicious_event, clear_suspicious_event

# Initialize Flask app
app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = 'supersecretkey'  # Change this in production

# Load/save email alert config
def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except:
        return {"email_alerts": False}

def save_config(config):
    with open("config.json", "w") as f:
        json.dump(config, f)

# ---------------- ROUTES ----------------

# Route: Home Page
@app.route('/')
def index():
    return render_template('index.html')

# Route: Upload Video File
@app.route('/upload_video', methods=['POST'])
def upload_video():
    video = request.files.get('video')
    if video:
        save_path = os.path.join(app.static_folder, "uploaded_video.mp4")
        video.save(save_path)
    return ('', 204)

# Route: Video Feed (camera or uploaded)
@app.route('/video_feed')
def video_feed():
    source = request.args.get('source', 'camera')
    upload_path = os.path.join(app.static_folder, "uploaded_video.mp4")

    if source == 'upload' and os.path.exists(upload_path):
        return Response(generate_pose_tracking_frames(video_path=upload_path),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return Response(generate_pose_tracking_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')


# Route: Real-Time Suspicious Feed for JS
@app.route('/suspicious_feed')
def suspicious_feed():
    def event_stream():
        while True:
            if get_suspicious_event():
                yield 'data: suspicious\n\n'
                clear_suspicious_event()
            time.sleep(1)
    return Response(stream_with_context(event_stream()), content_type='text/event-stream')

# ---------------- ADMIN PANEL ----------------

# Route: Admin Login / Config
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = load_config()

    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'admin123':  # Change this to your secure password
            session['admin'] = True
        else:
            return "Unauthorized", 403

    if not session.get('admin'):
        return '''
            <form method="POST">
                <h3>Admin Login</h3>
                <input type="password" name="password" placeholder="Enter Admin Password" required>
                <button type="submit">Login</button>
            </form>
        '''

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
        <title>Admin - Configurations</title>
    </head>
    <body class="light-mode">
        <div class="admin-container">
            <h2>Configurations</h2>

            <form method="POST" action="/toggle_email">
                <label>Email Alerts:</label>
                <input type="checkbox" name="email_alerts" value="true" {{'checked' if email_alerts else ''}}>
                <br><br>
                <button type="submit">Save</button>
            </form>

            <hr>

            <h3>Upload Video for Detection</h3>
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" name="video" accept="video/*" required>
                <button type="button" onclick="uploadVideo()">Upload</button>
            </form>

            <div style="margin-top:20px;">
                <h4>▶️ Video Playback (original)</h4>
                <video id="adminVideoPlayer" width="100%" height="auto" controls>
                    <source src="/static/uploaded_video.mp4" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
            
            <div style="margin-top:20px;">
                <button onclick="replayVideo()">🔁 Replay Detection</button>
            </div>


            <div style="margin-top:30px;">
                <h4>🧠 Detection Visualization</h4>
                <img id="detectionFeed" src="/video_feed?source=upload" style="width:100%;max-width:800px;border-radius:12px;box-shadow:0 0 12px rgba(0,0,0,0.2);" />
            </div>

            <a href="/">← Back to Dashboard</a>
        </div>

        <script>
            function uploadVideo() {
                const form = document.getElementById('uploadForm');
                const formData = new FormData(form);

                fetch('/upload_video', {
                    method: 'POST',
                    body: formData
                }).then(response => {
                    if (response.ok) {
                        alert('Upload successful!');
                        document.getElementById('adminVideoPlayer').src = '/static/uploaded_video.mp4?' + new Date().getTime();
                        document.getElementById('detectionFeed').src = '/video_feed?source=upload&' + new Date().getTime();
                    } else {
                        alert('Upload failed!');
                    }
                });
            }
            
            function replayVideo() {
                const video = document.getElementById('adminVideoPlayer');
                video.currentTime = 0;
                video.play();

                // Refresh detection feed (force reload)
                const detectionFeed = document.getElementById('detectionFeed');
                detectionFeed.src = '/video_feed?source=upload&' + new Date().getTime();
            }

        </script>
    </body>
    </html>
    """, email_alerts=config.get('email_alerts', False))


# Route: Toggle Email Alerts Setting
@app.route('/toggle_email', methods=['POST'])
def toggle_email():
    if not session.get('admin'):
        return redirect(url_for('admin'))
    config = load_config()
    config['email_alerts'] = 'email_alerts' in request.form
    save_config(config)
    return redirect(url_for('admin'))

# Main Entry Point
if __name__ == '__main__':
    print("Flask server starting...")
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)

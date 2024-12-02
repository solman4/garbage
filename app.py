from flask import Flask, Response, render_template, jsonify, send_from_directory, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_login import login_user, logout_user, login_required, current_user, LoginManager, UserMixin
import cv2
import threading
import time
import os
import uuid
from f5 import process_frame, set_violation_callback

# Khởi tạo Flask app với thư mục static và templates
app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

CORS(app)

# Cấu hình secret key cho session và bảo mật
app.secret_key = '2'

# Khởi tạo SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Khởi tạo LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'

# Đường dẫn video
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = r'D:\garbage\videos\1.mp4'

# Biến global
global_frame = None
is_processing = False
violations = []

# User class cho đăng nhập
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

# Mock database users
users = {
    'admin': User('1', 'admin', 'admin123'),
    'user': User('2', 'user', 'user123')
}

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user.id == user_id:
            return user
    return None

# Thêm cấu hình đường dẫn lưu ảnh vi phạm
app.config['VIOLATIONS_DIR'] = os.path.join(app.static_folder, 'violations')

def violation_callback(data):
    # Đảm bảo URL ảnh đúng format
    image_url = data.get('image_url', '')
    if image_url.startswith('/static/'):
        data['image_url'] = url_for('static', filename=image_url[8:])
    
    violations.append({
        'timestamp': time.time(),
        'violation': str(data),
        'image_url': data['image_url']
    })
    socketio.emit('violation_update', data)

set_violation_callback(violation_callback)

# Routes
@app.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('landing.html')

@app.route('/index')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in users and users[username].password == password:
            login_user(users[username])
            next_page = request.args.get('next')
            flash('Đăng nhập thành công!', 'success')
            return redirect(next_page if next_page else url_for('index'))
        
        flash('Tên đăng nhập hoặc mật khẩu không đúng', 'error')
        return redirect(url_for('landing'))
    
    return redirect(url_for('landing'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        if username in users:
            flash('Tên đăng nhập đã tồn tại', 'error')
            return redirect(url_for('landing'))
            
        new_user_id = str(len(users) + 1)
        users[username] = User(new_user_id, username, password)
        
        login_user(users[username])
        flash('Đăng ký thành công!', 'success')
        return redirect(url_for('index'))
    
    return redirect(url_for('landing'))

@app.route('/logout')
@login_required 
def logout():
    logout_user()
    flash('Đăng xuất thành công!', 'info')
    return redirect(url_for('landing'))

@app.route('/violations_page') 
@login_required
def violations_page():
    return render_template('violations.html')

@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html')

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/static/violations/<path:filename>')
def serve_violation_image(filename):
    return send_from_directory(app.config['VIOLATIONS_DIR'], filename)

# API endpoints
@app.route('/api/violations')
def get_violations():
    formatted_violations = []
    for v in violations:
        violation_data = {
            'timestamp': v['timestamp'],
            'violation': v['violation'],
            'image_url': v.get('image_url', ''),
            'id': str(uuid.uuid4())
        }
        formatted_violations.append(violation_data)
    return jsonify(formatted_violations)

@app.route('/api/person/<person_id>')
def get_person_details(person_id):
    person_details = {
        'id': person_id,
        'name': f'Người vi phạm {person_id}', 
        'position': 'Nhân viên',
        'department': 'Phòng A',
        'face_image': '/static/faces/person1.jpg',
        'violation_count': 1
    }
    return jsonify(person_details)

# Video processing functions
def update_frame():
    global global_frame, is_processing
    cap = cv2.VideoCapture(VIDEO_PATH)
    
    if not cap.isOpened():
        print(f"Error: Không thể mở video tại {VIDEO_PATH}")
        return
    print("Video successfully opened")
    
    while cap.isOpened():
        if is_processing:
            ret, frame = cap.read()
            if not ret:
                print("Kết thúc video.")
                break
            processed_frame = process_frame(frame)
            global_frame = processed_frame
            time.sleep(0.03)
        else:
            time.sleep(0.1)
    cap.release()
    print("Đã giải phóng tài nguyên video.")

@app.route('/video_feed')
def video_feed():
    def generate():
        cap = cv2.VideoCapture(VIDEO_PATH)
        if not cap.isOpened():
            print(f"Error: Không thể mở video tại {VIDEO_PATH}")
            return
            
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print(f"[DEBUG] End of video or error reading frame at count {frame_count}")
                break
                
            processed_frame = process_frame(frame)
            _, buffer = cv2.imencode('.jpg', processed_frame)
            frame_bytes = buffer.tobytes()
            frame_count += 1
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
        cap.release()
        print("[DEBUG] Released video capture")
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Video control routes
@app.route('/start_video', methods=['POST'])
def start_video():
    global is_processing
    is_processing = True
    print("Video processing started")
    return "Video started", 200

@app.route('/stop_video', methods=['POST'])
def stop_video():
    global is_processing
    is_processing = False
    print("Video processing stopped")
    return "Video stopped", 200

@app.route('/reset_video', methods=['POST'])
def reset_video():
    global is_processing, frame_thread
    is_processing = False
    print("Video reset started")
    
    global_frame = None
    frame_thread = threading.Thread(target=update_frame)
    frame_thread.daemon = True
    frame_thread.start()
    
    time.sleep(1)
    is_processing = True
    return "Video reset and started", 200

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    print(f"Violations: {violations}")
    violations_data = [
        {'timestamp': v['timestamp'], 'violation': str(v['violation'])} 
        for v in violations
    ]
    emit('violation_history', violations_data)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('toggle_processing')
def handle_toggle_processing(data):
    global is_processing
    status = data.get('status', True)
    is_processing = status
    state = 'started' if is_processing else 'stopped'
    print(f"Processing has been {state}.")
    emit('processing_status', {'status': is_processing}, broadcast=True)

if __name__ == '__main__':
    violations_dir = app.config['VIOLATIONS_DIR']
    os.makedirs(violations_dir, exist_ok=True)
    
    frame_thread = threading.Thread(target=update_frame)
    frame_thread.daemon = True
    frame_thread.start()
    
    socketio.run(app, host='0.0.0.0', port=5005, debug=True, use_reloader=False)
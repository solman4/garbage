import yolov5
import cv2
import torch
from deep_sort_realtime.deepsort_tracker import DeepSort
import datetime
import os
import uuid
import warnings
import math
import time
from face_utils import load_known_faces, recognize_faces_in_frame
import threading
import queue

warnings.filterwarnings("ignore", category=FutureWarning)

VIDEO_PATH = r'D:\garbage\videos\1.mp4'
YOLO_MODEL_PATH = r'D:\garbage\yolov5\runs\train\exp\weights\best.pt'
KNOWN_FACES_DIR = r'D:\garbage\data\mat_cua_ai'
CACHE_PATH = r'D:\garbage\known_faces.pkl'

if not os.path.exists(VIDEO_PATH):
    print(f"Error: Video file not found tại {VIDEO_PATH}")
    exit()

if not os.path.exists(YOLO_MODEL_PATH):
    print(f"Error: Model file not found tại {YOLO_MODEL_PATH}")
    exit()

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Sử dụng thiết bị: {device}")

print("Đang tải mô hình YOLOv5...")
model = torch.hub.load('ultralytics/yolov5', 'custom', path=YOLO_MODEL_PATH, force_reload=True).to(device)
print("Mô hình đã được tải thành công.")
model = yolov5.load(YOLO_MODEL_PATH)
model.to(device)
PERSON_CLASS_ID = 0
GARBAGE_CLASS_ID = 80

tracker = DeepSort(max_age=70, nn_budget=200, n_init=3)
garbage_tracker = DeepSort(max_age=9, n_init=6, nn_budget=50)

print("Đang tải dữ liệu khuôn mặt đã biết...")
known_face_encodings, known_face_names = load_known_faces(KNOWN_FACES_DIR, CACHE_PATH)
print(f"Đã tải {len(known_face_names)} khuôn mặt đã biết.")

distance_history = {}
photo_captured = {}

frame_queue = queue.Queue()
result_queue = queue.Queue()

# Thêm biến callback để gửi thông báo vi phạm
violation_callback = None

def set_violation_callback(callback):
    """Đặt callback để gửi thông báo vi phạm."""
    global violation_callback
    violation_callback = callback

def detect_objects(frame):
    img = [frame]
    results = model(img, size=640)
    results = results.xyxy[0].cpu().numpy()
    people = []
    garbage = []
    confidence_threshold = 0.5  # ngưỡng độ tin cậy

    for detection in results:
        x1, y1, x2, y2, conf, cls = detection
        if conf < confidence_threshold:
            continue
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        cls = int(cls)
        label = model.names[cls]
        if cls == PERSON_CLASS_ID:
            people.append((x1, y1, x2, y2, conf))
        elif cls == GARBAGE_CLASS_ID:
            box_area = (x2 - x1) * (y2 - y1)
            min_box_area = 500
            max_box_area = 20000
            if box_area < min_box_area or box_area > max_box_area:
                continue
            garbage.append((x1, y1, x2, y2, conf))
    return people, garbage

def track_people(detections, frame):
    converted_detections = [([x1, y1, x2 - x1, y2 - y1], conf, 'person') for (x1, y1, x2, y2, conf) in detections]
    tracks = tracker.update_tracks(converted_detections, frame=frame)
    return [(track.track_id, track.to_ltrb()) for track in tracks if track.is_confirmed()]

def track_garbage(detections, frame):
    converted_detections = [([x1, y1, x2 - x1, y2 - y1], conf, 'garbage') for (x1, y1, x2, y2, conf) in detections]
    tracks = garbage_tracker.update_tracks(converted_detections, frame=frame)
    return [(track.track_id, track.to_ltrb()) for track in tracks if track.is_confirmed()]

def detect_violation(tracked_people, tracked_garbage, garbage_owner, distance_threshold=120, movement_threshold=1, history_length=3, photo_distance_threshold=100, ground_distance_threshold=200):
    global distance_history, photo_captured
    violations = []
    for person in tracked_people:
        person_id, (px1, py1, px2, py2) = person
        person_center = ((px1 + px2) / 2, (py1 + py2) / 2)
        for garb in tracked_garbage:
            garbage_id, (gx1, gy1, gx2, gy2) = garb
            # Chỉ xét rác thuộc về người này
            if garbage_owner.get(garbage_id) != person_id:
                continue
            garbage_center = ((gx1 + gx2) / 2, (gy1 + gy2) / 2)
            distance = math.hypot(person_center[0] - garbage_center[0], person_center[1] - garbage_center[1])

            key = (person_id, garbage_id)

            if key not in photo_captured:
                photo_captured[key] = {"photo_near": False, "second_photo": False, "first_violation_time": None}

            if key not in distance_history:
                distance_history[key] = []
            distance_history[key].append(distance)
            if len(distance_history[key]) > history_length:
                distance_history[key].pop(0)

            if len(distance_history[key]) == history_length:
                is_increasing = all(earlier < later for earlier, later in zip(distance_history[key], distance_history[key][1:]))
                total_movement = distance_history[key][-1] - distance_history[key][0]

                # In ra giá trị để gỡ lỗi
                print(f"Kiểm tra vi phạm cho người {person_id} và rác {garbage_id}:")
                print(f"Khoảng cách hiện tại: {distance}")
                print(f"Lịch sử khoảng cách: {distance_history[key]}")
                print(f"is_increasing: {is_increasing}, total_movement: {total_movement}")

                if is_increasing and total_movement > movement_threshold:
                    if distance > photo_distance_threshold and not photo_captured[key]["photo_near"]:
                        violations.append((person_id, garbage_id, (px1, py1, px2, py2)))
                        photo_captured[key]["photo_near"] = True
                        photo_captured[key]["first_violation_time"] = time.time()
                    elif photo_captured[key]["photo_near"] and not photo_captured[key]["second_photo"]:
                        current_time = time.time()
                        time_since_first_violation = current_time - photo_captured[key]["first_violation_time"]
                        if time_since_first_violation >= 2:
                            violations.append((person_id, garbage_id, (px1, py1, px2, py2)))
                            photo_captured[key]["second_photo"] = True
    # Sau khi phát hiện vi phạm, gửi thông báo qua callback
    for violation in violations:
        person_id, garbage_id, bbox = violation
        # Giả sử bạn có cách để lấy thông tin vi phạm chi tiết, bao gồm thời gian và URL ảnh
        violation_data = {
            'person_id': person_id,
            'garbage_id': garbage_id,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'image_url': f"/static/violations/violation_person_{person_id}_photo_near_{int(time.time())}.jpg"
        }
        if violation_callback:
            violation_callback(violation_data)
    return violations

def log_violation(person_id, bbox, name):
    with open("D:/garbage/data/violation_log.txt", "a") as log:
        log.write(f"Violation by ID {person_id} ({name}) at {datetime.datetime.now()} with bounding box {bbox}\n")

# Thay đổi đường dẫn violations_dir
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIOLATIONS_DIR = os.path.join('static', 'violations')

def save_violation_image(frame, person_id, bbox, suffix="", known_face_encodings=None, known_face_names=None):
    # Sử dụng UUID để tạo tên tệp độc nhất
    unique_id = uuid.uuid4().hex
    filename = f"violation_person_{person_id}_{suffix}_{unique_id}.jpg"
    filepath = os.path.join(VIOLATIONS_DIR, filename)
    os.makedirs(VIOLATIONS_DIR, exist_ok=True)

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    face_locations, face_names = recognize_faces_in_frame(frame_rgb, known_face_encodings, known_face_names)

    for face_location, name in zip(face_locations, face_names):
        top, right, bottom, left = face_location
        if name != "Unknown":
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            log_violation(person_id, bbox, name)
        else:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.putText(frame, "Unknown", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            log_violation(person_id, bbox, "Unknown")

    if not face_locations:
        log_violation(person_id, bbox, "Unknown")

    cv2.imwrite(filepath, frame)
    print(f"Đã lưu ảnh vi phạm tại {filepath}")

    # Cập nhật image_url đúng đường dẫn
    image_url = f"/static/violations/{filename}"
    violation_data = {
        'person_id': person_id,
        'garbage_id': bbox,  # Có thể cần chỉnh lại nếu `garbage_id` khác
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'image_url': image_url
    }

    if violation_callback:
        violation_callback(violation_data)

def process_frame(frame):
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    people, garbage = detect_objects(frame_rgb)

    # Lọc bỏ các phát hiện rác ở quá xa người
    filtered_garbage = []
    for gx1, gy1, gx2, gy2, g_conf in garbage:
        garbage_center = ((gx1 + gx2) / 2, (gy1 + gy2) / 2)
        min_distance_to_person = float('inf')
        for px1, py1, px2, py2, p_conf in people:
            person_center = ((px1 + px2) / 2, (py1 + py2) / 2)
            distance = math.hypot(garbage_center[0] - person_center[0], garbage_center[1] - person_center[1])
            if distance < min_distance_to_person:
                min_distance_to_person = distance
        if min_distance_to_person < 200:
            filtered_garbage.append((gx1, gy1, gx2, gy2, g_conf))
    garbage = filtered_garbage

    tracked_people = track_people(people, frame_rgb)
    tracked_garbage = track_garbage(garbage, frame_rgb)

    # Khởi tạo garbage_owner
    garbage_owner = {}

    # Gán rác cho người gần nhất khi rác được phát hiện lần đầu
    for garbage_item in tracked_garbage:
        garbage_id, (gx1, gy1, gx2, gy2) = garbage_item
        garbage_center = ((gx1 + gx2) / 2, (gy1 + gy2) / 2)

        min_distance = float('inf')
        owner_id = None

        for person in tracked_people:
            person_id, (px1, py1, px2, py2) = person
            person_center = ((px1 + px2) / 2, (py1 + py2) / 2)
            distance = math.hypot(garbage_center[0] - person_center[0], garbage_center[1] - person_center[1])

            if distance < min_distance:
                min_distance = distance
                owner_id = person_id

        # Gán chủ sở hữu nếu chưa có và khoảng cách nhỏ hơn ngưỡng
        if min_distance < 150:
            garbage_owner[garbage_id] = owner_id
            # In ra thông tin gán rác cho người
            print(f"Garbage {garbage_id} được gán cho người {owner_id}")

    violations = detect_violation(
        tracked_people,
        tracked_garbage,
        garbage_owner,
        distance_threshold=120,
        movement_threshold=1,
        history_length=3,
        photo_distance_threshold=100,
        ground_distance_threshold=200
    )

    # Vẽ bounding boxes cho người được theo dõi
    for person in tracked_people:
        person_id, (px1, py1, px2, py2) = person
        cv2.rectangle(frame, (int(px1), int(py1)), (int(px2), int(py2)), (0, 255, 0), 2)
        cv2.putText(frame, f'Person ID: {person_id}', (int(px1), int(py1) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Vẽ bounding boxes cho rác được theo dõi
    for garbage_item in tracked_garbage:
        garbage_id, (gx1, gy1, gx2, gy2) = garbage_item
        cv2.rectangle(frame, (int(gx1), int(gy1)), (int(gx2), int(gy2)), (255, 0, 0), 2)
        cv2.putText(frame, f'Garbage ID: {garbage_id}', (int(gx1), int(gy1) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        owner_id = garbage_owner.get(garbage_id)
        if owner_id is not None:
            cv2.putText(frame, f'Owner ID: {owner_id}', (int(gx1), int(gy1) - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    # Hiển thị kết quả và ghi log
    for violation in violations:
        person_id, garbage_id, bbox = violation
        px1, py1, px2, py2 = bbox
        key = (person_id, garbage_id)

        # Vẽ bounding box cho người vi phạm
        cv2.rectangle(frame, (int(px1), int(py1)), (int(px2), int(py2)), (0, 0, 255), 2)
        # Viết thông tin vi phạm
        cv2.putText(frame, f'Violation by Person ID: {person_id}', (int(px1), int(py1) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Ghi log và chụp ảnh vi phạm
        if photo_captured[key]["photo_near"] and not photo_captured[key]["second_photo"]:
            save_violation_image(frame.copy(), person_id, bbox, "photo_near", known_face_encodings, known_face_names)
            log_violation(person_id, (px1, py1, px2, py2), "photo_near")

        if photo_captured[key]["second_photo"]:
            save_violation_image(frame.copy(), person_id, bbox, "photo_2s_later", known_face_encodings, known_face_names)
            log_violation(person_id, (px1, py1, px2, py2), "photo_2s_later")

    return frame


def frame_reader(cap):
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Kết thúc video.")
            break
        frame_queue.put(frame)
    cap.release()
    print("Đã giải phóng tài nguyên video.")

def frame_processor():
    while True:
        if not frame_queue.empty():
            frame = frame_queue.get()
            processed_frame = process_frame(frame)
            result_queue.put(processed_frame)
        else:
            if not reader_thread.is_alive() and frame_queue.empty():
                print("Không còn khung hình để xử lý.")
                break
            time.sleep(0.01)

def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("Error: Không thể mở video.")
        return

    global reader_thread
    reader_thread = threading.Thread(target=frame_reader, args=(cap,))
    global processor_thread
    processor_thread = threading.Thread(target=frame_processor)

    reader_thread.start()
    processor_thread.start()

    while True:
        if not result_queue.empty():
            frame = result_queue.get()
            cv2.imshow('Garbage Violation Detection', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            if not processor_thread.is_alive() and result_queue.empty():
                print("Không còn khung hình để hiển thị.")
                break
            time.sleep(0.01)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

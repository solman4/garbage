# face_utils.py
import os
import face_recognition
import pickle
import cv2

def load_known_faces(known_faces_dir, cache_path='known_faces.pkl'):
    """
    Tải các khuôn mặt đã biết từ thư mục hoặc từ tệp cache.

    Args:
        known_faces_dir (str): Đường dẫn tới thư mục chứa các khuôn mặt đã biết.
        cache_path (str): Đường dẫn tới tệp cache để lưu trữ dữ liệu khuôn mặt.

    Returns:
        tuple: (known_face_encodings, known_face_names)
    """
    if os.path.exists(cache_path):
        print("Đang tải dữ liệu khuôn mặt từ cache...")
        with open(cache_path, 'rb') as f:
            known_face_encodings, known_face_names = pickle.load(f)
        print(f"Đã tải {len(known_face_names)} khuôn mặt đã biết từ cache.")
    else:
        print("Đang tải dữ liệu khuôn mặt đã biết từ thư mục...")
        known_face_encodings = []
        known_face_names = []

        for entry in os.listdir(known_faces_dir):
            entry_path = os.path.join(known_faces_dir, entry)
            if os.path.isdir(entry_path):
                # Nếu là thư mục con, lấy tên người từ tên thư mục
                name = entry
                for filename in os.listdir(entry_path):
                    filepath = os.path.join(entry_path, filename)
                    if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        continue
                    image = face_recognition.load_image_file(filepath)
                    encodings = face_recognition.face_encodings(image)
                    if encodings:
                        known_face_encodings.append(encodings[0])
                        known_face_names.append(name)
                        print(f"Loaded encoding for {name} from {filename}")
                    else:
                        print(f"Warning: Không tìm thấy khuôn mặt trong hình ảnh {filepath}.")
            else:
                # Nếu là file ảnh trực tiếp, lấy tên người từ tên file (giả sử tên file chứa tên người)
                filename = entry
                name = os.path.splitext(filename)[0]  # Lấy tên file mà không có đuôi
                filepath = entry_path
                if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                image = face_recognition.load_image_file(filepath)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    known_face_encodings.append(encodings[0])
                    known_face_names.append(name)
                    print(f"Loaded encoding for {name} from {filename}")
                else:
                    print(f"Warning: Không tìm thấy khuôn mặt trong hình ảnh {filepath}.")

        # Lưu dữ liệu vào cache
        print(f"Đã tải {len(known_face_names)} khuôn mặt đã biết từ thư mục. Đang lưu vào cache...")
        with open(cache_path, 'wb') as f:
            pickle.dump((known_face_encodings, known_face_names), f)
        print("Đã lưu dữ liệu khuôn mặt vào cache.")
    
    return known_face_encodings, known_face_names

def recognize_faces_in_frame(frame, known_face_encodings, known_face_names):
    """
    Nhận diện khuôn mặt trong một khung hình cụ thể.

    Args:
        frame (numpy.ndarray): Khung hình video hiện tại (BGR).
        known_face_encodings (list): Danh sách các mã hóa khuôn mặt đã biết.
        known_face_names (list): Danh sách các tên tương ứng với các mã hóa khuôn mặt.

    Returns:
        tuple: (face_locations, face_names)
    """
    # Chuyển đổi hình ảnh từ BGR sang RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    face_names = []
    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"

        # Tính khoảng cách và tìm kết quả tốt nhất
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = face_distances.argmin() if len(face_distances) > 0 else None
        if best_match_index is not None and matches[best_match_index]:
            name = known_face_names[best_match_index]

        face_names.append(name)

    return face_locations, face_names

def update_cache(known_faces_dir, cache_path='known_faces.pkl'):
    """
    Cập nhật tệp cache với dữ liệu khuôn mặt mới.

    Args:
        known_faces_dir (str): Đường dẫn tới thư mục chứa các khuôn mặt đã biết.
        cache_path (str): Đường dẫn tới tệp cache để lưu trữ dữ liệu khuôn mặt.

    Returns:
        tuple: (known_face_encodings, known_face_names)
    """
    print("Đang cập nhật cache với các khuôn mặt mới...")
    known_face_encodings = []
    known_face_names = []

    for entry in os.listdir(known_faces_dir):
        entry_path = os.path.join(known_faces_dir, entry)
        if os.path.isdir(entry_path):
            # Nếu là thư mục con, lấy tên người từ tên thư mục
            name = entry
            for filename in os.listdir(entry_path):
                filepath = os.path.join(entry_path, filename)
                if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                image = face_recognition.load_image_file(filepath)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    known_face_encodings.append(encodings[0])
                    known_face_names.append(name)
                    print(f"Loaded encoding for {name} from {filename}")
                else:
                    print(f"Warning: Không tìm thấy khuôn mặt trong hình ảnh {filepath}.")
        else:
            # Nếu là file ảnh trực tiếp, lấy tên người từ tên file (giả sử tên file chứa tên người)
            filename = entry
            name = os.path.splitext(filename)[0]  # Lấy tên file mà không có đuôi
            filepath = entry_path
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            image = face_recognition.load_image_file(filepath)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                known_face_encodings.append(encodings[0])
                known_face_names.append(name)
                print(f"Loaded encoding for {name} from {filename}")
            else:
                print(f"Warning: Không tìm thấy khuôn mặt trong hình ảnh {filepath}.")

    # Lưu dữ liệu vào cache
    with open(cache_path, 'wb') as f:
        pickle.dump((known_face_encodings, known_face_names), f)
    print("Đã cập nhật dữ liệu khuôn mặt vào cache.")

    return known_face_encodings, known_face_names

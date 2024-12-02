# face_recognition_test.py
import os
import face_recognition
import cv2
from face_utils import load_known_faces, recognize_faces_in_frame

def test_face_recognition():
    # Đường dẫn tới thư mục chứa các khuôn mặt đã biết
    KNOWN_FACES_DIR = 'D:/garbage/mat_cua_ai'

    # Đường dẫn tới tệp cache
    CACHE_PATH = 'known_faces.pkl'

    # Đường dẫn tới hình ảnh thử nghiệm
    TEST_IMAGE_PATH = 'D:/garbage/4.png'  # Thay đổi đường dẫn này thành hình ảnh bạn muốn thử

    # Tải các khuôn mặt đã biết (từ cache nếu có)
    print("Đang tải dữ liệu khuôn mặt đã biết...")
    known_face_encodings, known_face_names = load_known_faces(KNOWN_FACES_DIR, CACHE_PATH)
    print(f"Đã tải {len(known_face_names)} khuôn mặt đã biết.")

    # Kiểm tra nhận diện khuôn mặt trên hình ảnh thử nghiệm
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"Error: Hình ảnh thử nghiệm không tồn tại tại {TEST_IMAGE_PATH}")
        return

    print(f"Đang kiểm tra nhận diện khuôn mặt trên hình ảnh: {TEST_IMAGE_PATH}")
    test_image = cv2.imread(TEST_IMAGE_PATH)
    if test_image is None:
        print(f"Error: Không thể tải hình ảnh {TEST_IMAGE_PATH}")
        return

    face_locations, face_names = recognize_faces_in_frame(test_image, known_face_encodings, known_face_names)

    for (top, right, bottom, left), name in zip(face_locations, face_names):
        if name != "Unknown":
            # Vẽ hình chữ nhật và tên lên hình ảnh
            cv2.rectangle(test_image, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(test_image, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            print(f"Đã nhận diện: {name}")
        else:
            # Nếu không nhận diện được, ghi với tên "Unknown"
            cv2.rectangle(test_image, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.putText(test_image, "Unknown", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            print("Đã nhận diện: Unknown")

    # Hiển thị hình ảnh đã nhận diện
    cv2.imshow('Face Recognition Test', test_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_face_recognition()

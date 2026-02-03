
import cv2
import pickle
import os
import sys

# Color constants
GREEN = (0, 255, 0)
RED = (0, 0, 255)
BLUE = (255, 0, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX

def enroll_face(filename="sentry_auth.pkl"):
    print("[INIT] Launching Biometric Enrollment...")
    
    try:
        import face_recognition
    except ImportError:
        print("[ERROR] 'face_recognition' library missing. Waiting for installation...")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Camera not accessible.")
        return

    print("[INFO] look at the camera and press 'SPACE' to register your face.")
    print("[INFO] Press 'Q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # Face detection for UI feedback (using fast cv2 method for preview)
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small = small_frame[:, :, ::-1] # BGR to RGB
        
        # Detect faces (using face_recognition for accuracy check)
        face_locations = face_recognition.face_locations(rgb_small)
        
        # Draw box
        for (top, right, bottom, left) in face_locations:
            top *= 2; right *= 2; bottom *= 2; left *= 2
            cv2.rectangle(frame, (left, top), (right, bottom), GREEN, 2)
            cv2.putText(frame, "TARGET LOCKED", (left, top-10), FONT, 0.8, GREEN, 2)

        status_text = f"Faces Visible: {len(face_locations)}"
        cv2.putText(frame, status_text, (10, 30), FONT, 0.7, BLUE, 2)
        cv2.putText(frame, "Press SPACE to Enroll", (10, 60), FONT, 0.7, GREEN, 2)

        cv2.imshow('J.A.R.V.I.S. Biometric Enrollment', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == 32: # SPACE
            if len(face_locations) == 1:
                print("[PROCESS] Analyzing biometric signature...")
                # Get encoding
                encodings = face_recognition.face_encodings(frame)
                if encodings:
                    auth_data = {"name": "Boss", "encoding": encodings[0]}
                    with open(filename, 'wb') as f:
                        pickle.dump(auth_data, f)
                    print("[SUCCESS] Face Registered Successfully!")
                    print(f"[SECURE] Saved to {filename}")
                    break
                else:
                    print("[FAIL] Could not encode face. Try better lighting.")
            elif len(face_locations) == 0:
                print("[FAIL] No face detected.")
            else:
                print("[FAIL] Multiple faces detected. Alone, please.")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    enroll_face()


import cv2
import os
import numpy as np
import pickle
import time
import logging

# Paths
DATA_DIR = "sentry_data"
MODEL_FILE = "sentry_model.yml"
LABELS_FILE = "sentry_labels.pkl"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_camera():
    # Try different indices if 0 fails
    for i in range(2):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) # CAP_DSHOW is faster on Windows
        if cap.isOpened():
            return cap
    return None

def detect_face(img, face_cascade):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0:
        return None, None
    
    # Assume the largest face is the target
    (x, y, w, h) = max(faces, key=lambda rect: rect[2] * rect[3])
    return gray[y:y+w, x:x+h], (x, y, w, h)

def enroll_silent(user_id="boss", num_samples=30):
    """Silently captures face samples for enrollment."""
    print(f"[SENTRY] Enrolling '{user_id}' silently...")
    
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = get_camera()
    
    if not cap:
        return {"status": "error", "message": "Camera unavailable"}
    
    samples = []
    start_time = time.time()
    
    while len(samples) < num_samples:
        ret, frame = cap.read()
        if not ret: break
        
        # Timeout after 20 seconds
        if time.time() - start_time > 20:
            break
            
        face_roi, _ = detect_face(frame, face_cascade)
        if face_roi is not None:
            # Resize to standard
            face_roi = cv2.resize(face_roi, (200, 200))
            samples.append(face_roi)
            time.sleep(0.1) # Small delay
            
    cap.release()
    
    if len(samples) < 10:
        return {"status": "error", "message": f"Insufficient data ({len(samples)} samples). Low light or no face?"}
        
    # Train immediately
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(samples, np.array([0] * len(samples))) # Label 0 for Boss
        recognizer.save(MODEL_FILE)
        
        # Save label map
        with open(LABELS_FILE, 'wb') as f:
            pickle.dump({0: user_id}, f)
            
        return {"status": "success", "samples": len(samples)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def authenticate_current_user():
    """Captures a frame and verifies if it matches the enrolled user."""
    if not os.path.exists(MODEL_FILE):
        return {"status": "error", "message": "No model trained."}
        
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(MODEL_FILE)
    
    cap = get_camera()
    if not cap: return {"status": "error", "message": "Camera unavailable"}
    
    # Take a few frames to let auto-exposure settle
    for _ in range(10): cap.read()
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret: return {"status": "error", "message": "Capture failed"}
    
    face_roi, rect = detect_face(frame, face_cascade)
    
    if face_roi is not None:
        face_roi = cv2.resize(face_roi, (200, 200))
        label, confidence = recognizer.predict(face_roi)
        
        # LBPH Confidence: Lower is better (distance). < 50 is good match.
        is_match = confidence < 60 
        
        return {
            "status": "success",
            "match": is_match,
            "confidence": confidence,
            "frame": frame # Return frame for sending evidence if needed
        }
    else:
        # Save frame to verify why face wasn't found
        debug_path = "debug_no_face.jpg"
        cv2.imwrite(debug_path, frame)
        return {"status": "no_face", "frame": frame}

if __name__ == "__main__":
    # Test enrollment if run directly
    print(enroll_silent())

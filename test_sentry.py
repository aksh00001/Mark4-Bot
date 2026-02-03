
from sentry_mode import authenticate_current_user
import cv2
import os

print("Testing Sentry Authentication (Scan)...")
result = authenticate_current_user()
print(f"Status: {result.get('status')}")
if result.get('status') == 'success':
    print(f"Match: {result.get('match')}")
    print(f"Confidence: {result.get('confidence')}")
    cv2.imwrite("test_scan_result.jpg", result.get('frame'))
    print("Frame saved to test_scan_result.jpg")
elif result.get('status') == 'no_face':
    print("No face detected.")
    cv2.imwrite("test_scan_noface.jpg", result.get('frame'))
else:
    print(f"Error: {result.get('message')}")

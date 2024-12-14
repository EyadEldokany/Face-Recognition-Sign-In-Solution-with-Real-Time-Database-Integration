from flask import Flask, render_template, Response, request, jsonify
import cv2
import face_recognition
import numpy as np
import mysql.connector
import pickle
from datetime import datetime
import base64

app = Flask(__name__)
# camera = cv2.VideoCapture(0)
# Connect to MySQL database
db = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="",
    database="face_recognition"
)
cursor = db.cursor()

# Fetch known faces from the database
def fetch_known_faces():
    cursor.execute("SELECT id, name, face_encoding FROM users")
    results = cursor.fetchall()
    known_face_encodings = []
    known_face_names = []
    user_ids = []
    for user_id, name, encoding in results:
        known_face_encodings.append(pickle.loads(encoding))  # Decode the binary face encoding
        known_face_names.append(name)
        user_ids.append(user_id)
    return known_face_encodings, known_face_names, user_ids

# Log user actions into the database
def log_user_sign_in(user_id):
    sign_in_time = datetime.now()
    cursor.execute("INSERT INTO sign_in_logs (user_id, sign_in_time) VALUES (%s, %s)", (user_id, sign_in_time))
    db.commit()

# Register a new user by capturing their face
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']  # Get the user's name from the form
        
        # Try to open the camera
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            return jsonify({"error": "Unable to access the camera. Please ensure it is not in use by another application."})

        import time
        time.sleep(2)

        success = False
        for _ in range(5):
            success, frame = camera.read()
            if success:
                break
        camera.release()

        if not success:
            return jsonify({"error": "Failed to capture face. Please try again."})

        # Process the captured frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        if face_locations:
            # If faces are detected, extract face encodings
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            # Debug: Check the size of the encodings
            print(f"Number of face encodings: {len(face_encodings)}")

            if len(face_encodings) > 0:
                encoded_data = pickle.dumps(face_encodings[0])  # Serialize face encoding
                
                # Insert the name and face encoding into the database
                try:
                    cursor.execute("INSERT INTO users (name, face_encoding) VALUES (%s, %s)", (name, encoded_data))
                    db.commit()
                    return render_template('register_result.html', name=f"User {name} registered successfully!")
                except mysql.connector.Error as err:
                    return render_template('register_result.html', name=f"Error inserting data into database : {err}", image_file=None)
            else:
                return render_template('register_result.html', name= "No Face Detected", image_file=None)
        else:
            return render_template('register_result.html', name="No face detected", image_file=None)
    
    return render_template('register.html')  # Render the registration form



# Sign in by recognizing the user's face
@app.route('/sign-in', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        known_face_encodings, known_face_names, user_ids = fetch_known_faces()

        # Start the webcam
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            print("Error: Could not access the camera.")
            return "Unable to access the camera. Please ensure it is not in use by another application."

        # Allow camera to warm up
        import time
        time.sleep(2)

        # Capture multiple frames
        success = False
        for _ in range(5):
            success, frame = camera.read()
            if success:
                break
        camera.release()

        if not success:
            print("Error: Failed to capture frame.")
            return "Failed to capture face. Please try again."

        # Process the captured frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)

        if face_locations:
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            for face_encoding, (top, right, bottom, left) in zip(face_encodings, face_locations):
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                name = "Unknown"

                if matches[best_match_index]:
                    name = known_face_names[best_match_index]
                    user_id = user_ids[best_match_index]
                    log_user_sign_in(user_id)  # Log sign-in action

                # Draw a rectangle around the face
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

                # Display the name label
                cv2.rectangle(frame, (left, bottom + 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, name, (left + 6, bottom + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Save the image with the rectangle and label
            cv2.imwrite("static/detected_face.jpg", frame)

            # Render the image with rectangles
            return render_template('sign_in_result.html', name=name, image_file="static/detected_face.jpg")
        
        else:
            return render_template('sign_in_result.html', name="No face Detected", image_file=None)

    return render_template('sign_in.html')



# Home route
@app.route('/')
def index():
    return render_template('index.html')

# # Function to convert an OpenCV image to base64
# def encode_image_to_base64(image):
#     _, buffer = cv2.imencode('.png', image)
#     return base64.b64encode(buffer).decode('utf-8')

# Video feed route for live webcam
# def gen_frames():
#     camera = cv2.VideoCapture(0)
#     while True:
#         success, frame = camera.read()  # Read the camera frame
#         if not success:
#             break
#         else:
#             # Convert the frame to JPEG format
#             ret, buffer = cv2.imencode('.jpg', frame)
#             if not ret:
#                 continue

#             # Convert the frame to bytes and yield it
#             frame = buffer.tobytes()
#             yield (b'--frame\r\n'
#                     b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# @app.route('/video_feed')
# def video_feed():
#     return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)

import os
import base64
import numpy as np
import cv2
import face_recognition
from flask import Flask, render_template, request, jsonify
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue, PayloadSchemaType
)
from datetime import datetime
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# ---------------------------------------------------------------------------
# Qdrant setup
# ---------------------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "face_encodings"
VECTOR_SIZE = 128  # face_recognition always outputs 128-d vectors

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def ensure_collection():
    """Create the Qdrant collection if it doesn't exist."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


ensure_collection()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def decode_image(b64_string: str) -> np.ndarray:
    """Decode a base64 image (from browser) to an OpenCV BGR array."""
    if "," in b64_string:
        b64_string = b64_string.split(",")[1]
    img_bytes = base64.b64decode(b64_string)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return frame


def get_face_encoding(frame: np.ndarray):
    """Return the first face encoding found in frame, or None."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb)
    if not locations:
        return None, None
    encodings = face_recognition.face_encodings(rgb, locations)
    return encodings[0] if encodings else None, locations[0]


def search_face(encoding: np.ndarray, threshold: float = 0.55):
    """
    Search Qdrant for the closest matching face.
    Returns (name, user_id) or ("Unknown", None).
    Cosine distance in Qdrant: score=1 means identical, score<threshold means no match.
    """
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=encoding.tolist(),
        limit=1,
        with_payload=True,
    )
    if results and results[0].score >= threshold:
        payload = results[0].payload
        return payload["name"], payload["user_id"]
    return "Unknown", None


def log_sign_in(user_id: str, name: str):
    """Store a sign-in event as a point in a separate Qdrant collection."""
    LOG_COLLECTION = "sign_in_logs"
    existing = [c.name for c in client.get_collections().collections]
    if LOG_COLLECTION not in existing:
        # Dummy 1-d vector collection just for log payloads
        client.create_collection(
            collection_name=LOG_COLLECTION,
            vectors_config=VectorParams(size=1, distance=Distance.COSINE),
        )
    client.upsert(
        collection_name=LOG_COLLECTION,
        points=[PointStruct(
            id=str(uuid.uuid4()),
            vector=[0.0],
            payload={
                "user_id": user_id,
                "name": name,
                "sign_in_time": datetime.utcnow().isoformat(),
            }
        )]
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    return render_template("register.html")


@app.route("/api/register", methods=["POST"])
def api_register():
    """
    Receive JSON: { "name": "Alice", "image": "<base64 data URL>" }
    Returns JSON: { "success": true/false, "message": "..." }
    """
    data = request.get_json()
    name = data.get("name", "").strip()
    image_b64 = data.get("image", "")

    if not name:
        return jsonify({"success": False, "message": "Name is required."})
    if not image_b64:
        return jsonify({"success": False, "message": "No image received."})

    frame = decode_image(image_b64)
    encoding, _ = get_face_encoding(frame)

    if encoding is None:
        return jsonify({"success": False, "message": "No face detected. Please try again."})

    user_id = str(uuid.uuid4())
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(
            id=user_id,
            vector=encoding.tolist(),
            payload={"name": name, "user_id": user_id},
        )]
    )
    return jsonify({"success": True, "message": f"User '{name}' registered successfully!"})


@app.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    return render_template("sign_in.html")


@app.route("/api/sign-in", methods=["POST"])
def api_sign_in():
    """
    Receive JSON: { "image": "<base64 data URL>" }
    Returns JSON: { "success": true/false, "name": "...", "message": "..." }
    """
    data = request.get_json()
    image_b64 = data.get("image", "")

    if not image_b64:
        return jsonify({"success": False, "name": "Unknown", "message": "No image received."})

    frame = decode_image(image_b64)
    encoding, location = get_face_encoding(frame)

    if encoding is None:
        return jsonify({"success": False, "name": "Unknown", "message": "No face detected."})

    name, user_id = search_face(encoding)

    if name != "Unknown":
        # Draw rectangle on the frame
        top, right, bottom, left = location
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.rectangle(frame, (left, bottom + 35), (right, bottom), (0, 255, 0), cv2.FILLED)
        cv2.putText(frame, name, (left + 6, bottom + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Encode annotated image back to base64 to send to browser
        _, buffer = cv2.imencode(".jpg", frame)
        img_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")

        log_sign_in(user_id, name)
        return jsonify({"success": True, "name": name, "image": img_b64,
                        "message": f"Welcome back, {name}!"})
    else:
        return jsonify({"success": False, "name": "Unknown",
                        "message": "Face not recognized. Please register first."})


if __name__ == "__main__":

    app.run(debug=True)

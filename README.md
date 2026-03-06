# Face Recognition Web App

A Flask web application for face registration and sign-in using browser-based camera capture, Qdrant vector database, and deployed on Railway.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [1. Set Up Qdrant Cloud](#1-set-up-qdrant-cloud)
- [2. Environment Variables](#2-environment-variables)
- [3. Local Development](#3-local-development)
- [4. Deploy to Railway](#4-deploy-to-railway)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## Architecture

| Layer | Technology |
|-------|-----------|
| Frontend | HTML + WebRTC (browser camera capture) |
| Backend | Flask + face_recognition + OpenCV |
| Database | Qdrant Cloud (128-d face vector storage) |
| Hosting | Railway (Docker, auto HTTPS) |

**Registration flow:** Browser captures photo → base64 sent to `/api/register` → face encoding extracted → stored in Qdrant

**Sign-in flow:** Browser captures photo → base64 sent to `/api/sign-in` → Qdrant similarity search → match returned with annotated image

---

## Project Structure

```
your-repo/
├── app.py                  # Flask app
├── Dockerfile              # Production container
├── railway.toml            # Railway config
├── requirements.txt        # Python dependencies
├── .env.example            # Env variable template
├── .gitignore
├── static/                 # Auto-created at runtime
└── templates/
    ├── index.html
    ├── register.html       # Browser camera capture
    └── sign_in.html        # Browser camera capture
```

---

## Prerequisites

- Python 3.10+
- Git
- A webcam (for local testing)
- Accounts on: [GitHub](https://github.com), [Qdrant Cloud](https://cloud.qdrant.io), [Railway](https://railway.app)

---

## 1. Set Up Qdrant Cloud

1. Go to [cloud.qdrant.io](https://cloud.qdrant.io) and create a free account
2. Click **New Cluster** → select **Free tier** → choose a region → **Create**
3. Once ready, open the cluster and copy your **Cluster URL**:
   ```
   https://xxxx-xxxx.us-east4-0.gcp.cloud.qdrant.io
   ```
4. Go to the **API Keys** tab → **Create API Key** → copy it immediately (shown only once)

> ⚠️ Save both the Cluster URL and API Key — you'll need them in the next step.

---

## 2. Environment Variables

Your app needs these three variables. **Never commit them to GitHub.**

| Variable | Description |
|----------|-------------|
| `QDRANT_URL` | Your Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | Your Qdrant API key |
| `FLASK_SECRET_KEY` | A long random string for session security |

**Generate a secret key:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**For local development**, create a `.env` file in the project root:
```env
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_api_key_here
FLASK_SECRET_KEY=your_generated_secret_here
```

Make sure `.env` is in your `.gitignore`:
```
.env
__pycache__/
*.pyc
static/detected_face.jpg
```

---

## 3. Local Development

```bash
# Clone the repo
git clone https://github.com/your-username/your-repo.git
cd your-repo

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
# Visit http://localhost:5000
```

> 📷 Camera access via `getUserMedia` only works on `localhost` or HTTPS. Railway provides HTTPS automatically.

**Optional — run Qdrant locally with Docker:**
```bash
docker run -p 6333:6333 qdrant/qdrant
# Then set QDRANT_URL=http://localhost:6333 in your .env
```

---

## 4. Deploy to Railway

### Step 1 — Push to GitHub
```bash
git add .
git commit -m "production-ready app"
git push origin main
```

### Step 2 — Create Railway Project
1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your repository
3. Railway auto-detects the `Dockerfile` — no extra config needed

### Step 3 — Fix Service Name (if needed)
If Railway shows a naming error, go to **Service → Settings → Service Name** and rename it to something like:
```
face-recognition-app
```
Names must be lowercase, letters, numbers, and hyphens only.

### Step 4 — Set Root Directory (if code is in a subfolder)
If your Flask files are not in the repo root, go to **Service → Settings → Root Directory** and enter the subfolder name, e.g.:
```
Register_page_with_face_recognition_API
```

### Step 5 — Add Environment Variables
Go to your service → **Variables** tab → add:

| Variable | Value |
|----------|-------|
| `QDRANT_URL` | `https://your-cluster.qdrant.io` |
| `QDRANT_API_KEY` | `your_api_key` |
| `FLASK_SECRET_KEY` | `your_generated_secret` |

### Step 6 — Generate a Public URL
Go to **Service → Settings → Networking → Generate Domain**

Your app will be live at:
```
https://your-app-name.up.railway.app
```

> ⏱️ The first build takes 5–10 minutes because `dlib` compiles from source. Subsequent builds are faster due to Docker layer caching.

---

## API Reference

### `POST /api/register`
Registers a new user by storing their face encoding in Qdrant.

**Request:**
```json
{
  "name": "Alice",
  "image": "data:image/jpeg;base64,/9j/4AAQ..."
}
```

**Response:**
```json
{ "success": true, "message": "User 'Alice' registered successfully!" }
```

---

### `POST /api/sign-in`
Recognizes a face via Qdrant similarity search and logs the sign-in.

**Request:**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQ..."
}
```

**Response:**
```json
{
  "success": true,
  "name": "Alice",
  "image": "data:image/jpeg;base64,...",
  "message": "Welcome back, Alice!"
}
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Camera blocked in browser | Must use HTTPS — Railway provides this automatically |
| `libgl1-mesa-glx` not found | Replace with `libgl1` in Dockerfile (Debian Trixie renamed it) |
| Service name invalid on Railway | Use lowercase + hyphens only, e.g. `face-recognition-app` |
| Railpack can't find app | Set **Root Directory** in Railway service Settings |
| Register button reloads the page | You're using the old `register.html` — replace it with the version that uses JS camera capture (no `<form method="POST">`) |
| No face detected | Ensure good lighting and face is centered in the frame |
| Qdrant connection error | Double-check `QDRANT_URL` and `QDRANT_API_KEY` in Railway Variables |
| First build times out | Normal — `dlib` takes 5–10 min to compile. Retry the build. |

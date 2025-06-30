# Project Setup Guide

This guide provides instructions for running the application using both Docker and a local development environment.

## Prerequisites

- **Docker**: You must have Docker installed. [Download Docker](https://www.docker.com/products/docker-desktop)
- **Docker Compose**: Included with Docker Desktop for Windows and Mac. For Linux, you may need to install it separately.

---

## 🚀 Running with Docker (Recommended)

This is the easiest way to get the entire application running.

### 1. Start the Application

Launch all services (backend, frontend, and Ollama) in the background.

```bash
docker-compose up -d
```

### 2. One-Time Model Setup

The first time you run this project, you need to download the `mistral` model. This command executes inside the `ollama` container and saves the model to a shared volume, so you only need to do this once.

```bash
docker-compose exec ollama ollama run mistral
```

Wait for the download to complete.

### 3. Access the Application

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Stopping the Application

To stop all running services and remove the containers, run:

```bash
docker-compose down
```

---

## 💻 Local Development Setup

If you prefer to run the services manually without Docker, follow these steps.

### Prerequisites

- Python 3.11+ and `venv`
- Node.js 20+ and `npm`
- Ollama installed and running locally. [Download Ollama](https://ollama.ai/)

### 1. Start Ollama

Make sure your local Ollama application is running and that you have already pulled the `mistral` model:

```bash
ollama run mistral
```

### 2. Backend Setup

From the project root directory:

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python run_server.py
```

The backend will be available at `http://localhost:8000`.

### 3. Frontend Setup

In a new terminal, navigate to the `frontend` directory:

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`. 
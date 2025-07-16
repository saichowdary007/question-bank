# Question Bank Processor

A sophisticated PDF processing system that extracts questions from educational materials and converts them into structured question banks using AI.

## 🚀 Quick Start

### Option 1: Docker (Recommended)

1. **Start all services:**
   ```bash
   docker-compose up --build
   ```

2. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Option 2: Local Development

1. **Setup environment:**
   ```bash
   python setup_local.py
   ```

2. **Start the server:**
   ```bash
   python run_server.py
   ```

## 🛠️ Prerequisites

### For Docker:
- Docker and Docker Compose installed

### For Local Development:
- Python 3.8+
- Ollama installed ([Download here](https://ollama.ai/))
- MongoDB (local installation or Docker)

## 📋 Features

- **PDF Text Extraction**: Advanced PDF processing with page-by-page extraction
- **AI-Powered Question Generation**: Uses Mistral LLM for intelligent question extraction
- **Duplicate Detection**: Automatic deduplication using semantic similarity
- **Real-time Monitoring**: Beautiful logging and progress tracking
- **Export Functionality**: Export questions as JSON
- **Web Interface**: Modern React frontend for easy interaction

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │    Database     │
│   (React)       │────│   (FastAPI)     │────│   (MongoDB)     │
│   Port: 3000    │    │   Port: 8000    │    │   Port: 27017   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                       ┌─────────────────┐
                       │     Ollama      │
                       │   (Mistral AI)  │
                       │   Port: 11434   │
                       └─────────────────┘
```

## 🐳 Docker Setup Details

The Docker setup includes:
- **Backend**: FastAPI application with all dependencies
- **Frontend**: React application with modern UI
- **MongoDB**: Database for storing questions
- **Ollama**: AI service with Mistral model pre-installed
- **Automatic Model Setup**: Mistral model is automatically pulled on first run

### Docker Commands

```bash
# Start all services
docker-compose up --build

# Start in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild specific service
docker-compose build backend
```

## 🖥️ Local Development Setup

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Ollama (if not already installed)
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows - Download from https://ollama.ai/
```

### 2. Setup Services

```bash
# Run the automated setup
python setup_local.py
```

This script will:
- Check Python dependencies
- Start Ollama service
- Install Mistral model
- Verify MongoDB connection

### 3. Manual Setup (if needed)

```bash
# Start Ollama
ollama serve

# Pull Mistral model
ollama pull mistral

# Start MongoDB (if using Docker)
docker run -d -p 27017:27017 mongo:7

# Start the application
python run_server.py
```

## 📖 Usage

### 1. Upload PDF
- Access the frontend at http://localhost:3000
- Upload a PDF file with educational content
- Specify grade, subject, and topic information

### 2. Monitor Processing
- Real-time logs show processing progress
- Progress bars indicate extraction status
- Color-coded messages for different stages

### 3. Download Results
- Questions are automatically exported as JSON
- Download button appears when processing completes
- Questions include multiple-choice options and correct answers

## 🔧 Configuration

### Environment Variables

```bash
# Ollama Configuration
OLLAMA_HOST=localhost          # For local: localhost, For Docker: ollama

# MongoDB Configuration  
MONGODB_URI=mongodb://localhost:27017/    # Local
MONGODB_URI=mongodb://mongo:27017/        # Docker

# Application Settings
CONCURRENT_REQUESTS=4          # Number of parallel AI requests
```

### File Structure

```
question-bank/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── llm_ollama.py        # AI integration
│   ├── db.py                # Database operations
│   ├── pdf_utils.py         # PDF processing
│   └── deduplication.py     # Duplicate detection
├── frontend/
│   └── src/                 # React application
├── docker-compose.yml       # Docker orchestration
├── setup_local.py          # Local setup script
└── run_server.py           # Enhanced server startup
```

## 🎨 Enhanced Features

### Real-time Logging
- Color-coded console output
- Progress bars for long operations
- Timing information for performance monitoring
- Visual separators for different processing stages

### Error Handling
- Comprehensive error catching and logging
- Automatic retry mechanisms
- Graceful degradation when services are unavailable
- Detailed error messages for debugging

### Performance Optimizations
- Concurrent PDF page processing
- Asynchronous AI calls
- Database connection pooling
- Efficient duplicate detection algorithms

## 🚨 Troubleshooting

### Common Issues

1. **Ollama 404 Errors**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Restart Ollama
   ollama serve
   
   # For Docker: ensure model is pulled
   docker exec questionbank-ollama-1 ollama pull mistral
   ```

2. **Questions.json Directory Error**
   - Fixed automatically by the updated code
   - Removes any conflicting directories before file creation

3. **Port Conflicts**
   ```bash
   # Check what's running on ports
   lsof -i :8000  # Backend
   lsof -i :3000  # Frontend
   lsof -i :11434 # Ollama
   lsof -i :27017 # MongoDB
   ```

4. **MongoDB Connection Issues**
   ```bash
   # For local development
   brew services start mongodb-community
   
   # For Docker
   docker run -d -p 27017:27017 mongo:7
   ```

### Log Monitoring

```bash
# View application logs
tail -f app.log

# Enhanced log viewer
python log_viewer.py

# Docker logs
docker-compose logs -f backend
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test both local and Docker setups
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support


1. Check the troubleshooting section above
2. Review the logs for error details
3. Ensure all prerequisites are installed
4. Verify service connectivity using the provided curl commands 
# Audio Transcription API

A powerful Flask-based API for transcribing audio and video files using the Faster Whisper model. This service provides multiple transcription modes, including standard, streaming, and search-based transcription.

## Features

- **Multiple Transcription Modes**:
  - **Standard Transcription**: Get the complete transcription in a single response
  - **Streaming Transcription**: Receive transcription segments in real-time as they're processed
  - **Search-based Transcription**: Find specific terms or phrases within audio content

- **High-Quality Speech Recognition**:
  - Powered by Faster Whisper (medium model)
  - GPU acceleration with CUDA support
  - Multi-language detection and transcription

- **User-Friendly Web Interface**:
  - Drag-and-drop file uploading
  - Real-time progress updates
  - Segment-based results with timestamps
  - Full text view with copy functionality

- **Developer-Friendly API**:
  - RESTful endpoints
  - Structured JSON responses
  - Streaming response support
  - Comprehensive error handling

## Installation

### Prerequisites

- Python 3.8 or higher
- CUDA-compatible GPU (for optimal performance)
- FFmpeg (for audio processing)

### Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd InnovDigital
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Make sure the uploads directory exists:
   ```
   mkdir -p uploads
   ```

5. Run the application:
   ```
   python backend.py
   ```

The server will start on http://0.0.0.0:5000

## API Endpoints

### 1. Root Endpoint

- **URL**: `/`
- **Method**: `GET`
- **Description**: Serves the web interface for the transcription service
- **Response**: HTML page

### 2. Standard Transcription

- **URL**: `/transcribe`
- **Method**: `POST`
- **Description**: Transcribes the complete audio/video file and returns the full result
- **Parameters**:
  - `file` (required): Audio or video file (MP3, MP4, WAV, OGG, M4A)
- **Response Format**: JSON
  ```json
  {
    "language": "en",
    "language_probability": 0.9892,
    "processing_time": 12.45,
    "segments": [
      {
        "start": 0.0,
        "end": 4.5,
        "text": "This is the transcribed text of the first segment."
      },
      ...
    ],
    "full_text": "This is the transcribed text of the first segment. ..."
  }
  ```
- **Error Responses**:
  - 400 Bad Request: Missing file, empty filename, or unsupported file type
  - 500 Internal Server Error: Transcription processing errors

### 3. Streaming Transcription

- **URL**: `/stream-transcribe`
- **Method**: `POST`
- **Description**: Transcribes the file and streams results as they become available
- **Parameters**:
  - `file` (required): Audio or video file (MP3, MP4, WAV, OGG, M4A)
- **Response Format**: Event stream (text/event-stream)
  ```
  {"type": "info", "message": "Transcription started", "filename": "example.mp3"}
  {"type": "language", "language": "en", "language_probability": 0.9892}
  {"type": "segment", "segment": {"id": 0, "start": 0.0, "end": 4.5, "text": "This is the transcribed text."}}
  ...
  {"type": "complete", "processing_time": 12.45, "segment_count": 42}
  ```
- **Error Responses**: Same as standard transcription, plus streaming-specific errors

### 4. Search Transcription

- **URL**: `/search`
- **Method**: `POST`
- **Description**: Transcribes the file while searching for a specific term, stops when found
- **Parameters**:
  - `file` (required): Audio or video file (MP3, MP4, WAV, OGG, M4A)
  - `searchTerm` (required): The word or phrase to search for in the transcription
- **Response Format**: Event stream (text/event-stream)
  ```
  {"type": "info", "message": "Search transcription started", "filename": "example.mp3", "searchTerm": "keyword"}
  {"type": "language", "language": "en", "language_probability": 0.9892}
  {"type": "segment", "segment": {"id": 0, "start": 0.0, "end": 4.5, "text": "This is the transcribed text."}}
  ...
  {"type": "match", "match": {...}, "context": {...}}
  {"type": "complete", "status": "found", "processing_time": 8.32, "segment_count": 17}
  ```
- **Error Responses**: Same as standard transcription, plus search-specific errors

## Usage Examples

### cURL Examples

#### Standard Transcription

```bash
curl -X POST -F "file=@/path/to/audio.mp3" http://localhost:5000/transcribe
```

#### Streaming Transcription

```bash
curl -X POST -F "file=@/path/to/audio.mp3" http://localhost:5000/stream-transcribe
```

#### Search Transcription

```bash
curl -X POST -F "file=@/path/to/audio.mp3" -F "searchTerm=important concept" http://localhost:5000/search
```

### Python Example

```python
import requests

# Standard transcription
def transcribe_file(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post('http://localhost:5000/transcribe', files=files)
        
    if response.status_code == 200:
        result = response.json()
        print(f"Transcription complete. Language: {result['language']}")
        print(f"Full text: {result['full_text']}")
        return result
    else:
        print(f"Error: {response.json()['error']}")
        return None

# Usage
transcribe_file('audio_sample.mp3')
```

### JavaScript Example

```javascript
// Using fetch API for standard transcription
function transcribeFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    return fetch('http://localhost:5000/transcribe', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Transcription failed');
            });
        }
        return response.json();
    });
}

// Using XHR for streaming transcription
function streamTranscribe(file, onSegment, onComplete, onError) {
    const formData = new FormData();
    formData.append('file', file);
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://localhost:5000/stream-transcribe', true);
    
    let buffer = '';
    
    xhr.onprogress = function() {
        const newResponse = xhr.responseText.substring(buffer.length);
        buffer = xhr.responseText;
        
        const lines = newResponse.split('\n');
        lines.forEach(line => {
            if (!line.trim()) return;
            
            try {
                const data = JSON.parse(line);
                
                switch(data.type) {
                    case 'segment':
                        onSegment && onSegment(data.segment);
                        break;
                    case 'complete':
                        onComplete && onComplete(data);
                        break;
                    case 'error':
                        onError && onError(data.error);
                        break;
                }
            } catch (e) {
                console.error('Error parsing streaming response:', e);
            }
        });
    };
    
    xhr.onerror = function() {
        onError && onError('Network error');
    };
    
    xhr.send(formData);
}
```

## Configuration

The application can be configured by modifying the following settings in `backend.py`:

```python
# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'mp3', 'mp4', 'wav', 'ogg', 'm4a'}
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Limit file size to 50MB

# Model configuration
model_size = "Systran/faster-whisper-medium"
model = WhisperModel(model_size, device="cuda", compute_type="int8")
```

## Model Details

The service uses Systran's Faster Whisper implementation, which significantly improves transcription speed compared to OpenAI's original Whisper model while maintaining comparable accuracy.

- **Model**: `Systran/faster-whisper-medium`
- **Compute Type**: `int8` (for optimal performance)
- **Device**: `cuda` (GPU acceleration)

## Performance Considerations

- **File Size**: Larger files require more processing time
- **Audio Quality**: Clear audio with minimal background noise yields better results
- **GPU Memory**: The medium model requires approximately 2-3GB of GPU memory
- **Concurrent Requests**: Heavy concurrent usage may affect performance

## Error Handling

The API provides detailed error messages for various scenarios:

- Missing file in request
- Empty or invalid filename
- Unsupported file extensions
- File size exceeds maximum limit
- Transcription processing errors

Each error response includes an error message and appropriate HTTP status code.

## License

[MIT License](LICENSE)

## Acknowledgements

- [Faster Whisper](https://github.com/guillaumekln/faster-whisper) by Systran
- [OpenAI Whisper](https://github.com/openai/whisper) by OpenAI
- [Flask](https://flask.palletsprojects.com/) web framework
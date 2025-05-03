from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from werkzeug.utils import secure_filename
from faster_whisper import WhisperModel
import os
import time
import json
import uuid
import logging
from flask_cors import CORS
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'mp3', 'mp4', 'wav', 'ogg', 'm4a'}
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Limit file size to 50MB

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
logger.info(f"Upload folder created/confirmed at: {os.path.abspath(app.config['UPLOAD_FOLDER'])}")

# Load the whisper model
model_size = "Systran/faster-whisper-medium"
logger.info(f"Loading model: {model_size}")
model = WhisperModel(model_size, device="cuda", compute_type="int8")
logger.info("Model loaded successfully")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    logger.info("Homepage accessed")
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe_file():
    """Standard transcription endpoint that returns the complete transcription at once"""
    logger.info("Transcription request received")
    client_ip = request.remote_addr
    logger.info(f"Request from IP: {client_ip}")
    
    # Check if a file was uploaded
    if 'file' not in request.files:
        logger.warning("No file part in the request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # Check if the file is empty
    if file.filename == '':
        logger.warning("Empty filename submitted")
        return jsonify({'error': 'No file selected'}), 400
    
    logger.info(f"File submitted: {file.filename}")
    
    # Check if the file extension is allowed
    if not allowed_file(file.filename):
        logger.warning(f"File type not allowed: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Generate a unique filename to avoid collisions
    unique_filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    logger.info(f"Saving file as: {unique_filename}")
    
    try:
        # Save the file
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        logger.info(f"File saved successfully. Size: {file_size/1024/1024:.2f} MB")
        
        # Transcribe the file
        logger.info("Starting transcription process")
        start_time = time.time()
        segments, info = model.transcribe(file_path, beam_size=5)
        
        # Process the transcription
        transcript_data = []
        full_text = ""
        segment_count = 0
        
        for segment in segments:
            segment_data = {
                'start': segment.start,
                'end': segment.end,
                'text': segment.text
            }
            transcript_data.append(segment_data)
            full_text += segment.text + " "
            segment_count += 1
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"Transcription completed in {processing_time:.2f} seconds")
        logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.4f})")
        logger.info(f"Generated {segment_count} segments, total text length: {len(full_text)} characters")
        
        # Return the result
        result = {
            'language': info.language,
            'language_probability': info.language_probability,
            'processing_time': processing_time,
            'segments': transcript_data,
            'full_text': full_text.strip()
        }
        
        # Clean up the uploaded file
        os.remove(file_path)
        logger.info(f"Temporary file deleted: {unique_filename}")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        # Clean up in case of error
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Temporary file deleted after error: {unique_filename}")
        return jsonify({'error': str(e)}), 500

@app.route('/stream-transcribe', methods=['POST'])
def stream_transcribe():
    """Streaming transcription endpoint that returns segments as they're processed"""
    logger.info("Streaming transcription request received")
    client_ip = request.remote_addr
    logger.info(f"Request from IP: {client_ip}")
    
    # Check if a file was uploaded
    if 'file' not in request.files:
        logger.warning("No file part in the request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # Check if the file is empty
    if file.filename == '':
        logger.warning("Empty filename submitted")
        return jsonify({'error': 'No file selected'}), 400
    
    logger.info(f"File submitted: {file.filename}")
    
    # Check if the file extension is allowed
    if not allowed_file(file.filename):
        logger.warning(f"File type not allowed: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Generate a unique filename to avoid collisions
    unique_filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    logger.info(f"Saving file as: {unique_filename}")
    
    try:
        # Save the file
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        logger.info(f"File saved successfully. Size: {file_size/1024/1024:.2f} MB")
        
        @stream_with_context
        def generate():
            """Generator function to stream transcription results"""
            try:
                # Send initial metadata
                yield json.dumps({
                    'type': 'info',
                    'message': 'Transcription started',
                    'filename': file.filename
                }) + '\n'
                
                # Start transcription
                logger.info("Starting streaming transcription process")
                start_time = time.time()
                segments_generator = model.transcribe(file_path, beam_size=5)
                
                # Get the language info from the generator
                segments, info = segments_generator
                
                # Send language info
                yield json.dumps({
                    'type': 'language',
                    'language': info.language,
                    'language_probability': info.language_probability
                }) + '\n'
                
                # Process and send each segment as it becomes available
                segment_count = 0
                for segment in segments:
                    segment_data = {
                        'type': 'segment',
                        'segment': {
                            'id': segment_count,
                            'start': segment.start,
                            'end': segment.end,
                            'text': segment.text
                        }
                    }
                    segment_count += 1
                    logger.info(f"Streaming segment {segment_count}: {segment.text[:30]}...")
                    yield json.dumps(segment_data) + '\n'
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Send completion message
                yield json.dumps({
                    'type': 'complete',
                    'processing_time': processing_time,
                    'segment_count': segment_count
                }) + '\n'
                
                logger.info(f"Streaming transcription completed in {processing_time:.2f} seconds")
                logger.info(f"Streamed {segment_count} segments")
                
            except Exception as e:
                logger.error(f"Error in streaming: {str(e)}", exc_info=True)
                yield json.dumps({
                    'type': 'error',
                    'error': str(e)
                }) + '\n'
            finally:
                # Clean up the uploaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Temporary file deleted after streaming: {unique_filename}")
        
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        logger.error(f"Error processing file for streaming: {str(e)}", exc_info=True)
        # Clean up in case of error
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Temporary file deleted after error: {unique_filename}")
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['POST'])
def search_transcribe():
    """Transcription endpoint that searches for specific text and stops when found"""
    logger.info("Search transcription request received")
    client_ip = request.remote_addr
    logger.info(f"Request from IP: {client_ip}")
    
    # Check if a file was uploaded
    if 'file' not in request.files:
        logger.warning("No file part in the request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # Check if the file is empty
    if file.filename == '':
        logger.warning("Empty filename submitted")
        return jsonify({'error': 'No file selected'}), 400
    
    # Get the search term
    search_term = request.form.get('searchTerm', '').strip().lower()
    if not search_term:
        logger.warning("No search term provided")
        return jsonify({'error': 'No search term provided'}), 400
    
    logger.info(f"File submitted: {file.filename}")
    logger.info(f"Search term: {search_term}")
    
    # Check if the file extension is allowed
    if not allowed_file(file.filename):
        logger.warning(f"File type not allowed: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Generate a unique filename to avoid collisions
    unique_filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    logger.info(f"Saving file as: {unique_filename}")
    
    try:
        # Save the file
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        logger.info(f"File saved successfully. Size: {file_size/1024/1024:.2f} MB")
        
        @stream_with_context
        def generate():
            """Generator function to stream transcription results and search for target text"""
            try:
                # Send initial metadata
                yield json.dumps({
                    'type': 'info',
                    'message': 'Search transcription started',
                    'filename': file.filename,
                    'searchTerm': search_term
                }) + '\n'
                
                # Start transcription
                logger.info("Starting search-based transcription process")
                start_time = time.time()
                
                # Process the audio file for transcription
                segments, info = model.transcribe(file_path, beam_size=5)
                
                # Send language info
                yield json.dumps({
                    'type': 'language',
                    'language': info.language,
                    'language_probability': info.language_probability
                }) + '\n'
                
                # Process and send each segment while searching for target text
                segment_count = 0
                processed_segments = []
                target_found = False
                
                # Process segments one by one
                for segment in segments:
                    segment_data = {
                        'id': segment_count,
                        'start': segment.start,
                        'end': segment.end,
                        'text': segment.text
                    }
                    processed_segments.append(segment_data)
                    
                    # Send the segment to the client
                    yield json.dumps({
                        'type': 'segment',
                        'segment': segment_data
                    }) + '\n'
                    
                    # Check if the search term is in this segment
                    if not target_found and search_term in segment.text.lower():
                        logger.info(f"Search term '{search_term}' found in segment {segment_count}")
                        target_found = True
                        match_index = segment_count
                        
                        # We found a match, but keep processing for a bit more context
                        # Don't break out of the loop, just mark we found it and continue
                        # We'll process a few more segments for additional context
                        after_match_count = 0
                        max_after_match = 3  # Number of segments to process after match
                    
                    # If we already found a match, count how many additional segments we've processed
                    if target_found:
                        after_match_count += 1
                        # Once we've processed enough segments after the match, we can stop
                        if after_match_count > max_after_match:
                            logger.info(f"Processed {after_match_count-1} segments after match, stopping")
                            break
                    
                    segment_count += 1
                
                # If we found a match, send the match with context
                if target_found:
                    # Get the context for the match
                    match_segment = processed_segments[match_index]
                    context = get_context(processed_segments, match_index)
                    
                    # Send the match info with context
                    yield json.dumps({
                        'type': 'match',
                        'match': match_segment,
                        'context': context
                    }) + '\n'
                    
                    logger.info(f"Match sent with context - {len(context['before'])} segments before and {len(context['after'])} segments after")
                else:
                    # If no match was found, inform the client
                    logger.info("No match found, processed all segments")
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Send completion message
                result_status = 'found' if target_found else 'not_found'
                yield json.dumps({
                    'type': 'complete',
                    'status': result_status,
                    'processing_time': processing_time,
                    'segment_count': segment_count
                }) + '\n'
                
                logger.info(f"Search transcription completed in {processing_time:.2f} seconds")
                logger.info(f"Processed {segment_count} segments, search term {result_status}")
                
            except Exception as e:
                logger.error(f"Error in search transcription: {str(e)}", exc_info=True)
                yield json.dumps({
                    'type': 'error',
                    'error': str(e)
                }) + '\n'
            finally:
                # Clean up the uploaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Temporary file deleted after search: {unique_filename}")
        
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        logger.error(f"Error processing file for search: {str(e)}", exc_info=True)
        # Clean up in case of error
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Temporary file deleted after error: {unique_filename}")
        return jsonify({'error': str(e)}), 500

def get_context(segments, current_index, context_size=2):
    """Get segments before and after the matched segment for context"""
    # Get segments before the match (up to context_size)
    start_idx = max(0, current_index - context_size)
    before_segments = segments[start_idx:current_index]
    
    # Get segments after the match (up to context_size)
    end_idx = min(len(segments), current_index + context_size + 1)
    after_segments = segments[current_index+1:end_idx]
    
    # Compile the context
    context = {
        'before': before_segments,
        'current': segments[current_index],
        'after': after_segments
    }
    
    # Calculate the full context as a paragraph
    full_segments = before_segments + [segments[current_index]] + after_segments
    context_text = " ".join([seg['text'] for seg in full_segments])
    
    context['full_text'] = context_text.strip()
    
    # Add timestamp range for the entire context
    context['timestamp_start'] = full_segments[0]['start'] if full_segments else 0
    context['timestamp_end'] = full_segments[-1]['end'] if full_segments else 0
    
    return context

if __name__ == '__main__':
    logger.info("Starting Flask server")
    app.run(debug=True, host='0.0.0.0', port=5000)
    logger.info("Flask server stopped")
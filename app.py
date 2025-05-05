from flask import Flask, request, jsonify, render_template, send_file, abort
import os
import tempfile
import re
import subprocess
import json
import sys

app = Flask(__name__)

@app.route('/')
def home_page():
    return render_template('index.html')

@app.route('/download')
def download_file():
    file_path = request.args.get('path')
    
    if not file_path or not os.path.exists(file_path):
        abort(404)
    
    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data['url']
    
    # Validate URL
    if not re.match(r'https?://(www\.)?(instagram\.com|youtube\.com|youtu\.be)/.*', url):
        return jsonify({"error": "Invalid URL. This tool supports Instagram and YouTube only."}), 400
    
    return download_with_ytdlp(url)

def download_with_ytdlp(url):
    """Download video using yt-dlp"""
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({"error": "yt-dlp is not found. Please install it first."}), 500
            
        # Get video info first
        info_cmd = [ytdlp_path, '--dump-json', url]
        result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
        # Download the video
        download_cmd = [ytdlp_path, '-o', output_template, url]
        subprocess.run(download_cmd, capture_output=True, check=True)
        
        # Find the downloaded file
        video_path = None
        for file in os.listdir(temp_dir):
            if file.endswith(('.mp4', '.mov', '.webm', '.mkv')):
                video_path = os.path.join(temp_dir, file)
                break
        
        if not video_path:
            return jsonify({"error": "Failed to download video with yt-dlp"}), 500
        
        # Get video size
        video_size = os.path.getsize(video_path)
        
        # Determine the platform (Instagram or YouTube)
        platform = "Instagram" if "instagram" in url.lower() else "YouTube"
        
        return jsonify({
            "success": True,
            "video_info": {
                "filename": os.path.basename(video_path),
                "size_bytes": video_size,
                "size_mb": round(video_size / (1024 * 1024), 2),
                "local_path": video_path,
                "caption": video_info.get('description', ''),
                "owner": video_info.get('uploader', ''),
                "platform": platform,
                "title": video_info.get('title', '')
            }
        })
            
    except subprocess.CalledProcessError as e:
        error_message = str(e.stderr) if hasattr(e, 'stderr') else str(e)
        return jsonify({"error": f"yt-dlp error: {error_message}"}), 500
    
    except Exception as e:
        return jsonify({"error": f"Error using yt-dlp: {str(e)}"}), 500

@app.route('/api/get-info', methods=['POST'])
def get_info():
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data['url']
    
    # Validate URL
    if not re.match(r'https?://(www\.)?(instagram\.com|youtube\.com|youtu\.be)/.*', url):
        return jsonify({"error": "Invalid URL. This tool supports Instagram and YouTube only."}), 400
    
    try:
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({"error": "yt-dlp is not found. Please install it first."}), 500
            
        # Get video info
        info_cmd = [ytdlp_path, '--dump-json', url]
        result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
        # Determine platform
        platform = "Instagram" if "instagram" in url.lower() else "YouTube"
        
        return jsonify({
            "success": True,
            "video_info": {
                "title": video_info.get('title', 'Unknown'),
                "uploader": video_info.get('uploader', 'Unknown'),
                "duration": video_info.get('duration', 0),
                "view_count": video_info.get('view_count', 0),
                "like_count": video_info.get('like_count', 0),
                "upload_date": video_info.get('upload_date', ''),
                "description": video_info.get('description', ''),
                "platform": platform
            }
        })
    
    except subprocess.CalledProcessError as e:
        error_message = str(e.stderr) if hasattr(e, 'stderr') else str(e)
        return jsonify({"error": f"yt-dlp error: {error_message}"}), 500
    
    except Exception as e:
        return jsonify({"error": f"Error using yt-dlp: {str(e)}"}), 500

@app.route('/api/test-ytdlp', methods=['GET'])
def test_ytdlp():
    """Endpoint to test if yt-dlp is working."""
    try:
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({
                "success": False,
                "error": "yt-dlp is not found in your system",
                "installation_guide": "Please install yt-dlp using 'pip install yt-dlp'"
            }), 404
        
        # Get yt-dlp version
        version_cmd = [ytdlp_path, '--version']
        result = subprocess.run(version_cmd, capture_output=True, text=True, check=True)
        version = result.stdout.strip()
        
        return jsonify({
            "success": True,
            "yt_dlp_version": version,
            "yt_dlp_path": ytdlp_path,
            "python_version": sys.version
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error testing yt-dlp: {str(e)}",
            "python_version": sys.version
        }), 500

def find_ytdlp_path():
    """Find the path to yt-dlp executable"""
    ytdlp_path = None
    
    try:
        # Try to use where/which command first
        if os.name == 'nt':  # Windows
            result = subprocess.run(['where', 'yt-dlp'], capture_output=True, text=True, check=True)
            paths = result.stdout.strip().split('\n')
            if paths:
                ytdlp_path = paths[0]
        else:  # Linux/Mac
            result = subprocess.run(['which', 'yt-dlp'], capture_output=True, text=True, check=True)
            ytdlp_path = result.stdout.strip()
    except subprocess.CalledProcessError:
        # If where/which command fails, try other methods
        pass
    
    if not ytdlp_path:
        # Python executable path
        python_dir = os.path.dirname(sys.executable)
        
        # List of possible paths
        possible_paths = [
            os.path.join(python_dir, 'Scripts', 'yt-dlp.exe'),  # Windows
            os.path.join(python_dir, 'bin', 'yt-dlp'),          # Linux/Mac
            'yt-dlp'                                            # System path
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, '--version'], capture_output=True, check=True)
                ytdlp_path = path
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    
    return ytdlp_path

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Check if yt-dlp is installed
    ytdlp_path = find_ytdlp_path()
    if not ytdlp_path:
        print("Warning: yt-dlp is not found in your system")
        print("Please install yt-dlp using 'pip install yt-dlp'")
    else:
        version_cmd = [ytdlp_path, '--version']
        try:
            result = subprocess.run(version_cmd, capture_output=True, text=True, check=True)
            print(f"Found yt-dlp version: {result.stdout.strip()}")
        except Exception as e:
            print(f"Error checking yt-dlp version: {e}")
    
    print("Starting the Video Downloader web application...")
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 
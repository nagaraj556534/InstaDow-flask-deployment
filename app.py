from flask import Flask, request, jsonify, render_template, send_file, abort
import os
import tempfile
import re
import subprocess
import json
import sys
import uuid

app = Flask(__name__)

# Constants
COOKIE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies')

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
    """Download video using yt-dlp with cookie support"""
    try:
        # Create temporary directory with unique name
        temp_dir = tempfile.mkdtemp(prefix='ytdlp_')
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({"error": "yt-dlp is not found. Please install it first."}), 500
            
        # Determine platform and set up cookie parameters
        cookie_params = []
        platform = "Instagram" if "instagram" in url.lower() else "YouTube"
        
        # Ensure cookie directory exists
        os.makedirs(COOKIE_DIR, exist_ok=True)
        
        # Add extra parameters to help avoid bot detection
        extra_params = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            '--add-header', 'Accept-Language:en-US,en;q=0.9',
            '--no-check-certificates',
            '--extractor-retries', '3'
        ]
        
        # Add specific parameters for Instagram to bypass login
        if platform == "Instagram":
            extra_params.extend([
                '--no-check-certificate',
                '--ignore-errors',
                '--no-warnings',
                '--no-progress',
                '--extract-audio',
                '--add-header', 'User-Agent:Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US; 138226743)'
            ])
            cookie_path = os.path.join(COOKIE_DIR, "instagram_cookies.txt")
            if os.path.exists(cookie_path):
                cookie_params = ['--cookies', cookie_path]
        else:  # YouTube
            cookie_path = os.path.join(COOKIE_DIR, "youtube_cookies.txt")
            if os.path.exists(cookie_path):
                cookie_params = ['--cookies', cookie_path]
        
        try:
            # Get video info first
            info_cmd = [ytdlp_path, '--dump-json'] + cookie_params + extra_params + [url]
            result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
            video_info = json.loads(result.stdout)
            
            # Download the video
            download_cmd = [ytdlp_path, '-o', output_template] + cookie_params + extra_params + [url]
            subprocess.run(download_cmd, capture_output=True, text=True, check=True)
            
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
            error_output = e.stderr if e.stderr else str(e)
            
            # For Instagram, try an alternative method if login is required
            if platform == "Instagram" and ("login required" in error_output or "Requested content is not available" in error_output):
                try:
                    # Try alternative approach with different parameters
                    alt_params = [
                        '--no-check-certificate',
                        '--ignore-errors',
                        '--no-warnings',
                        '--force-generic-extractor',
                        '--add-header', 'User-Agent:Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118'
                    ]
                    
                    # Check if we have credentials available
                    credentials = get_credentials('instagram')
                    if credentials and credentials.get('username') and credentials.get('password'):
                        alt_params.extend([
                            '--username', credentials['username'],
                            '--password', credentials['password']
                        ])
                    
                    # Download with alternative parameters
                    alt_cmd = [ytdlp_path, '-o', output_template] + alt_params + [url]
                    subprocess.run(alt_cmd, capture_output=True, text=True, check=True)
                    
                    # Find the downloaded file
                    video_path = None
                    for file in os.listdir(temp_dir):
                        if file.endswith(('.mp4', '.mov', '.webm', '.mkv')):
                            video_path = os.path.join(temp_dir, file)
                            break
                    
                    if not video_path:
                        return jsonify({"error": "Failed to download Instagram video"}), 500
                    
                    # Get video size
                    video_size = os.path.getsize(video_path)
                    
                    return jsonify({
                        "success": True,
                        "video_info": {
                            "filename": os.path.basename(video_path),
                            "size_bytes": video_size,
                            "size_mb": round(video_size / (1024 * 1024), 2),
                            "local_path": video_path,
                            "platform": "Instagram",
                            "title": os.path.basename(video_path).split('.')[0]
                        }
                    })
                    
                except Exception as alt_err:
                    credentials_exist = get_credentials('instagram') is not None
                    return jsonify({
                        "error": "Instagram login required and alternative method failed",
                        "details": str(alt_err),
                        "solution": "Try uploading Instagram cookies from a logged-in browser session",
                        "has_credentials": credentials_exist
                    }), 403
            
            # Provide more specific and helpful error messages for other cases
            if "Sign in to confirm you're not a bot" in error_output:
                return jsonify({
                    "error": "YouTube requires authentication to verify you're not a bot",
                    "solution": "Upload YouTube cookies from a logged-in browser session",
                    "has_cookies": os.path.exists(os.path.join(COOKIE_DIR, "youtube_cookies.txt"))
                }), 403
            elif "login required" in error_output or "Requested content is not available" in error_output:
                return jsonify({
                    "error": "Instagram login required",
                    "solution": "Upload Instagram cookies from a logged-in browser session",
                    "has_cookies": os.path.exists(os.path.join(COOKIE_DIR, "instagram_cookies.txt"))
                }), 403
            else:
                return jsonify({"error": f"yt-dlp error: {error_output}"}), 500
    
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
        
        # Determine platform and set up cookie parameters
        cookie_params = []
        platform = "Instagram" if "instagram" in url.lower() else "YouTube"
        
        # Add extra parameters to help avoid bot detection
        extra_params = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            '--add-header', 'Accept-Language:en-US,en;q=0.9',
            '--no-check-certificates',
            '--extractor-retries', '3'
        ]
        
        # Add specific parameters for Instagram to bypass login
        if platform == "Instagram":
            extra_params.extend([
                '--no-check-certificate',
                '--ignore-errors',
                '--no-warnings',
                '--no-progress',
                '--add-header', 'User-Agent:Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US; 138226743)'
            ])
            cookie_path = os.path.join(COOKIE_DIR, "instagram_cookies.txt")
            if os.path.exists(cookie_path):
                cookie_params = ['--cookies', cookie_path]
        else:  # YouTube
            cookie_path = os.path.join(COOKIE_DIR, "youtube_cookies.txt")
            if os.path.exists(cookie_path):
                cookie_params = ['--cookies', cookie_path]
            
        # Get video info
        info_cmd = [ytdlp_path, '--dump-json'] + cookie_params + extra_params + [url]
        result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
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
        error_output = e.stderr if e.stderr else str(e)
        
        # For Instagram, try an alternative method if login is required
        if platform == "Instagram" and ("login required" in error_output or "Requested content is not available" in error_output):
            try:
                # Try alternative approach with different parameters
                alt_params = [
                    '--no-check-certificate',
                    '--ignore-errors',
                    '--no-warnings',
                    '--force-generic-extractor',
                    '--add-header', 'User-Agent:Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118'
                ]
                
                # Check if we have credentials available
                credentials = get_credentials('instagram')
                if credentials and credentials.get('username') and credentials.get('password'):
                    alt_params.extend([
                        '--username', credentials['username'],
                        '--password', credentials['password']
                    ])
                
                # Get info with alternative parameters
                alt_cmd = [ytdlp_path, '--dump-json'] + alt_params + [url]
                result = subprocess.run(alt_cmd, capture_output=True, text=True, check=True)
                video_info = json.loads(result.stdout)
                
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
                        "platform": "Instagram"
                    }
                })
                
            except Exception as alt_err:
                credentials_exist = get_credentials('instagram') is not None
                return jsonify({
                    "error": "Instagram login required and alternative method failed",
                    "details": str(alt_err),
                    "solution": "Try uploading Instagram cookies from a logged-in browser session",
                    "has_credentials": credentials_exist
                }), 403
        
        # Provide more specific and helpful error messages for other cases
        if "Sign in to confirm you're not a bot" in error_output:
            return jsonify({
                "error": "YouTube requires authentication to verify you're not a bot",
                "solution": "Upload YouTube cookies from a logged-in browser session",
                "has_cookies": os.path.exists(os.path.join(COOKIE_DIR, "youtube_cookies.txt"))
            }), 403
        elif "login required" in error_output or "Requested content is not available" in error_output:
            return jsonify({
                "error": "Instagram login required",
                "solution": "Upload Instagram cookies from a logged-in browser session",
                "has_cookies": os.path.exists(os.path.join(COOKIE_DIR, "instagram_cookies.txt"))
            }), 403
        else:
            return jsonify({"error": f"yt-dlp error: {error_output}"}), 500
    
    except Exception as e:
        return jsonify({"error": f"Error using yt-dlp: {str(e)}"}), 500

@app.route('/api/upload-cookies', methods=['POST'])
def upload_cookies():
    """Endpoint to upload cookies file"""
    if 'cookie_file' not in request.files:
        return jsonify({"error": "No cookie file provided"}), 400
        
    file = request.files['cookie_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    platform = request.form.get('platform', '').lower()
    if platform not in ['youtube', 'instagram']:
        return jsonify({"error": "Invalid platform. Must be 'youtube' or 'instagram'"}), 400
    
    try:
        # Ensure cookie directory exists
        os.makedirs(COOKIE_DIR, exist_ok=True)
        
        # Save the file
        filename = f"{platform}_cookies.txt"
        file_path = os.path.join(COOKIE_DIR, filename)
        file.save(file_path)
        
        return jsonify({
            "success": True,
            "message": f"Cookies for {platform} uploaded successfully"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to save cookie file: {str(e)}"}), 500

@app.route('/api/set-credentials', methods=['POST'])
def set_credentials():
    """Endpoint to save Instagram or YouTube credentials"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No credentials data provided"}), 400
            
        platform = data.get('platform', '').lower()
        if platform not in ['youtube', 'instagram']:
            return jsonify({"error": "Invalid platform. Must be 'youtube' or 'instagram'"}), 400
            
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
            
        # Ensure cookie directory exists
        os.makedirs(COOKIE_DIR, exist_ok=True)
        
        # Create credential file
        cred_file = os.path.join(COOKIE_DIR, f"{platform}_credentials.json")
        
        # Save credentials as JSON
        with open(cred_file, 'w') as f:
            json.dump({
                "username": username,
                "password": password,
                "saved_at": str(uuid.uuid4())  # Add a unique ID as timestamp
            }, f)
            
        # Try to generate cookies file using yt-dlp with credentials
        ytdlp_path = find_ytdlp_path()
        
        if ytdlp_path:
            # Create cookies file from credentials
            cookie_file = os.path.join(COOKIE_DIR, f"{platform}_cookies.txt")
            
            if platform == "instagram":
                test_url = "https://www.instagram.com/instagram/"
            else:  # youtube
                test_url = "https://www.youtube.com/feed/trending"
                
            try:
                # Use yt-dlp to authenticate and save cookies
                auth_cmd = [
                    ytdlp_path,
                    '--username', username,
                    '--password', password,
                    '--cookies', cookie_file,
                    '--mark-watched',
                    '--no-check-certificate',
                    '--ignore-errors',
                    '--no-warnings',
                    '--no-download',
                    '--quiet',
                    test_url
                ]
                
                subprocess.run(auth_cmd, capture_output=True, text=True, timeout=30)
                
                # Check if cookies file was created
                if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 0:
                    return jsonify({
                        "success": True,
                        "message": f"{platform.capitalize()} credentials saved successfully and cookies generated",
                        "has_cookies": True
                    })
            except Exception as e:
                # Log error but continue - we'll return success for credentials even if cookie generation fails
                print(f"Error generating cookies: {str(e)}")
        
        # Return success for saving credentials even if cookie generation fails
        return jsonify({
            "success": True,
            "message": f"{platform.capitalize()} credentials saved successfully",
            "has_cookies": False
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to save credentials: {str(e)}"}), 500

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
        
        # Check if cookie files exist
        youtube_cookies_exist = os.path.exists(os.path.join(COOKIE_DIR, "youtube_cookies.txt"))
        instagram_cookies_exist = os.path.exists(os.path.join(COOKIE_DIR, "instagram_cookies.txt"))
        
        # Check if credential files exist
        youtube_credentials_exist = get_credentials('youtube') is not None
        instagram_credentials_exist = get_credentials('instagram') is not None
        
        return jsonify({
            "success": True,
            "yt_dlp_version": version,
            "yt_dlp_path": ytdlp_path,
            "python_version": sys.version,
            "cookies": {
                "youtube": youtube_cookies_exist,
                "instagram": instagram_cookies_exist
            },
            "credentials": {
                "youtube": youtube_credentials_exist,
                "instagram": instagram_credentials_exist
            }
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

def get_credentials(platform):
    """Get saved credentials for a platform if they exist"""
    cred_file = os.path.join(COOKIE_DIR, f"{platform.lower()}_credentials.json")
    
    if os.path.exists(cred_file):
        try:
            with open(cred_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    return None

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create cookies directory if it doesn't exist
    os.makedirs(COOKIE_DIR, exist_ok=True)
    
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

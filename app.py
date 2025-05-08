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
SUPPORTED_PLATFORMS = {
    'instagram': {
        'domains': ['instagram.com', 'instagr.am', 'instagram'],
        'name': 'Instagram',
        'user_agents': [
            'Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US; 138226743)',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118'
        ]
    },
    'youtube': {
        'domains': ['youtube.com', 'youtu.be', 'youtube'],
        'name': 'YouTube',
        'user_agents': [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
        ]
    },
    'tiktok': {
        'domains': ['tiktok.com', 'vm.tiktok.com', 'tiktok'],
        'name': 'TikTok',
        'user_agents': [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'TikTok 26.2.0 rv:262018 (iPhone; iOS 14.4.2; en_US) Cronet'
        ]
    }
}

@app.route('/')
def home_page():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Downloader</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                text-align: center;
            }
            h1 {
                color: #333;
            }
            .form-group {
                margin-bottom: 15px;
            }
            input[type="text"] {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 16px;
            }
            button {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover {
                background-color: #45a049;
            }
            .supported {
                margin-top: 20px;
                color: #666;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <h1>Video Downloader</h1>
        <p>Paste a video URL from Instagram, YouTube, or TikTok to download</p>
        
        <form action="/api/instant-download" method="get">
            <div class="form-group">
                <input type="text" name="url" placeholder="https://..." required>
            </div>
            <button type="submit">Download Video</button>
        </form>
        
        <div class="supported">
            <p>Supported platforms: Instagram, YouTube, TikTok, and more</p>
        </div>
    </body>
    </html>
    '''

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
    if not is_supported_url(url):
        return jsonify({"error": "Invalid URL. Supported platforms: Instagram, YouTube, and TikTok"}), 400
    
    return download_with_ytdlp(url)

@app.route('/api/direct-download', methods=['GET', 'POST'])
def direct_download():
    """Direct download endpoint that works with just the URL - simple and ready for deployment"""
    try:
        # Get URL from either POST JSON, POST form, or GET parameter
        url = None
        
        if request.method == 'POST':
            if request.is_json:
                url = request.json.get('url')
            else:
                url = request.form.get('url')
        else:
            url = request.args.get('url')
            
        if not url:
            return jsonify({"error": "URL is required. Please provide a video URL."}), 400
            
        # Validate URL quickly
        if not url.startswith(('http://', 'https://')):
            return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400
            
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='download_')
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        if not ytdlp_path:
            # If not found, use system command as fallback
            ytdlp_path = 'yt-dlp'
        
        # Simple but effective parameters
        download_params = [
            ytdlp_path,
            '--no-warnings',
            '--no-check-certificate',
            '--format', 'best',
            '--output', output_template,
            '--ignore-errors',
            '--no-playlist',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            url
        ]
        
        # Run the download command
        subprocess.run(download_params, check=True, capture_output=True)
        
        # Find downloaded file
        video_files = []
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            if os.path.isfile(file_path) and any(file.endswith(ext) for ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']):
                video_files.append({
                    'filename': file,
                    'path': file_path,
                    'size': os.path.getsize(file_path),
                    'size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2)
                })
        
        if not video_files:
            # Try alternate method with more parameters
            alt_params = [
                ytdlp_path,
                '--no-warnings',
                '--no-check-certificate',
                '--format', 'best',
                '--output', output_template,
                '--ignore-errors',
                '--no-playlist',
                '--force-generic-extractor',
                '--user-agent', 'TikTok 26.2.0 rv:262018 (iPhone; iOS 14.4.2; en_US) Cronet',
                '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                '--add-header', 'Accept-Language: en-US,en;q=0.5',
                url
            ]
            
            # Run the alternate command
            subprocess.run(alt_params, check=True, capture_output=True)
            
            # Check again for downloaded files
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and any(file.endswith(ext) for ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']):
                    video_files.append({
                        'filename': file,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2)
                    })
            
            if not video_files:
                return jsonify({"error": "Failed to download video. Please check the URL."}), 400
        
        # Just return the first video if multiple were downloaded
        video_file = video_files[0]
        
        # Two options: 
        # 1. Return the file path for download via /download endpoint
        # 2. Directly serve the file
        
        # Option 1: Return path for downloading via /download endpoint
        return jsonify({
            "success": True,
            "message": "Video downloaded successfully",
            "video": {
                "filename": video_file['filename'],
                "size_mb": video_file['size_mb'],
                "download_url": f"/download?path={video_file['path']}"
            }
        })
        
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode('utf-8') if hasattr(e.stderr, 'decode') else str(e.stderr)
        return jsonify({
            "error": "Failed to download the video",
            "details": error_output if 'error' in error_output.lower() else "The URL may be invalid or requires login"
        }), 500
    except Exception as e:
        return jsonify({
            "error": "An unexpected error occurred",
            "details": str(e)
        }), 500

@app.route('/api/instant-download')
def instant_download():
    """Download a video and immediately serve it to the user - most direct method possible"""
    try:
        url = request.args.get('url')
        
        if not url:
            return "Error: URL parameter is required", 400
            
        # Validate URL quickly
        if not url.startswith(('http://', 'https://')):
            return "Error: Invalid URL. Must start with http:// or https://", 400
            
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='direct_')
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        if not ytdlp_path:
            # If not found, use system command as fallback
            ytdlp_path = 'yt-dlp'
        
        # Simple but effective parameters - try to get mp4 format preferred
        download_params = [
            ytdlp_path,
            '--no-warnings',
            '--no-check-certificate',
            '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--output', output_template,
            '--ignore-errors',
            '--no-playlist',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            url
        ]
        
        # Run the download command
        result = subprocess.run(download_params, check=False, capture_output=True)
        
        # Find downloaded file
        video_file = None
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            if os.path.isfile(file_path) and any(file.endswith(ext) for ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']):
                video_file = file_path
                break
        
        if not video_file and result.returncode != 0:
            # Try alternate method if first attempt failed
            alt_params = [
                ytdlp_path,
                '--no-warnings',
                '--no-check-certificate',
                '--format', 'best',
                '--output', output_template,
                '--ignore-errors',
                '--no-playlist',
                '--force-generic-extractor',
                url
            ]
            
            # Run the alternate command
            subprocess.run(alt_params, check=False, capture_output=True)
            
            # Check again for downloaded files
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and any(file.endswith(ext) for ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']):
                    video_file = file_path
                    break
        
        if not video_file:
            return "Error: Failed to download video. Please check the URL.", 400
        
        # Get the filename for the Content-Disposition header
        filename = os.path.basename(video_file)
        
        # Serve the file directly to the user for download
        return send_file(
            video_file,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'  # Assume mp4, most browsers handle this well for various formats
        )
        
    except Exception as e:
        return f"Error downloading video: {str(e)}", 500

def is_supported_url(url):
    """Check if URL is from a supported platform"""
    if not re.match(r'https?://', url):
        return False
        
    for platform, info in SUPPORTED_PLATFORMS.items():
        for domain in info['domains']:
            if domain in url.lower():
                return True
                
    return False

def get_platform_from_url(url):
    """Determine platform from URL"""
    for platform, info in SUPPORTED_PLATFORMS.items():
        for domain in info['domains']:
            if domain in url.lower():
                return platform
    
    return None

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
        platform = get_platform_from_url(url)
        platform_info = SUPPORTED_PLATFORMS.get(platform, SUPPORTED_PLATFORMS['youtube'])
        
        # Ensure cookie directory exists
        os.makedirs(COOKIE_DIR, exist_ok=True)
        
        # Common parameters for all platforms
        common_params = [
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--no-progress',
            '--format', 'best',  # Try to get best quality
            '--extractor-retries', '3'
        ]
        
        # Add platform-specific parameters
        extra_params = common_params.copy()
        
        # Add user agent
        user_agent = platform_info['user_agents'][0]
        extra_params.extend(['--user-agent', user_agent])
        
        # Add additional headers
        extra_params.extend([
            '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            '--add-header', 'Accept-Language: en-US,en;q=0.5',
            '--add-header', 'Connection: keep-alive',
            '--add-header', 'Upgrade-Insecure-Requests: 1',
            '--add-header', 'Cache-Control: max-age=0'
        ])
        
        # Check for cookies and credentials
        cookie_path = os.path.join(COOKIE_DIR, f"{platform}_cookies.txt")
        credentials = get_credentials(platform)
        
        if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 0:
            cookie_params = ['--cookies', cookie_path]
        elif credentials and credentials.get('username') and credentials.get('password'):
            # If no cookies but we have credentials, try to use them directly
            extra_params.extend([
                '--username', credentials['username'],
                '--password', credentials['password']
            ])
        
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
                return jsonify({"error": f"Failed to download {platform_info['name']} video"}), 500
            
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
                    "platform": platform_info['name'],
                    "title": video_info.get('title', '')
                }
            })
                
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else str(e)
            
            # Try alternative method with different parameters
            try:
                # Use alternative user agent and parameters
                alt_params = common_params.copy()
                
                if len(platform_info['user_agents']) > 1:
                    # Use alternative user agent if available
                    alt_user_agent = platform_info['user_agents'][1]
                    alt_params.extend(['--user-agent', alt_user_agent])
                else:
                    alt_params.extend(['--user-agent', user_agent])
                
                # Add more specific parameters
                alt_params.extend([
                    '--force-generic-extractor',
                    '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    '--add-header', 'Accept-Language: en-US,en;q=0.5',
                    '--add-header', 'Connection: keep-alive',
                    '--add-header', 'Upgrade-Insecure-Requests: 1',
                    '--add-header', 'Cache-Control: max-age=0'
                ])
                
                # Check if we have credentials available
                credentials = get_credentials(platform)
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
                    return jsonify({"error": f"Failed to download {platform_info['name']} video"}), 500
                
                # Get video size
                video_size = os.path.getsize(video_path)
                
                return jsonify({
                    "success": True,
                    "video_info": {
                        "filename": os.path.basename(video_path),
                        "size_bytes": video_size,
                        "size_mb": round(video_size / (1024 * 1024), 2),
                        "local_path": video_path,
                        "platform": platform_info['name'],
                        "title": os.path.basename(video_path).split('.')[0]
                    }
                })
                
            except Exception as alt_err:
                credentials_exist = get_credentials(platform) is not None
                return jsonify({
                    "error": f"{platform_info['name']} login required and alternative method failed",
                    "details": str(alt_err),
                    "solution": f"Try uploading {platform_info['name']} cookies from a logged-in browser session",
                    "has_credentials": credentials_exist
                }), 403
            
            # Provide more specific and helpful error messages for other cases
            if "Sign in to confirm you're not a bot" in error_output:
                return jsonify({
                    "error": f"{platform_info['name']} requires authentication to verify you're not a bot",
                    "solution": f"Upload {platform_info['name']} cookies from a logged-in browser session",
                    "has_cookies": os.path.exists(cookie_path)
                }), 403
            elif "login required" in error_output or "Requested content is not available" in error_output:
                return jsonify({
                    "error": f"{platform_info['name']} login required",
                    "solution": f"Upload {platform_info['name']} cookies from a logged-in browser session",
                    "has_cookies": os.path.exists(cookie_path)
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
    if not is_supported_url(url):
        return jsonify({"error": "Invalid URL. Supported platforms: Instagram, YouTube, and TikTok"}), 400
    
    try:
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({"error": "yt-dlp is not found. Please install it first."}), 500
        
        # Determine platform and set up cookie parameters
        cookie_params = []
        platform = get_platform_from_url(url)
        platform_info = SUPPORTED_PLATFORMS.get(platform, SUPPORTED_PLATFORMS['youtube'])
        
        # Common parameters for all platforms
        common_params = [
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--no-progress',
            '--format', 'best',  # Try to get best quality
            '--extractor-retries', '3'
        ]
        
        # Add platform-specific parameters
        extra_params = common_params.copy()
        
        # Add user agent
        user_agent = platform_info['user_agents'][0]
        extra_params.extend(['--user-agent', user_agent])
        
        # Add additional headers
        extra_params.extend([
            '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            '--add-header', 'Accept-Language: en-US,en;q=0.5',
            '--add-header', 'Connection: keep-alive',
            '--add-header', 'Upgrade-Insecure-Requests: 1',
            '--add-header', 'Cache-Control: max-age=0'
        ])
        
        # Check for cookies and credentials
        cookie_path = os.path.join(COOKIE_DIR, f"{platform}_cookies.txt")
        credentials = get_credentials(platform)
        
        if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 0:
            cookie_params = ['--cookies', cookie_path]
        elif credentials and credentials.get('username') and credentials.get('password'):
            # If no cookies but we have credentials, try to use them directly
            extra_params.extend([
                '--username', credentials['username'],
                '--password', credentials['password']
            ])
            
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
                "platform": platform_info['name']
            }
        })
    
    except subprocess.CalledProcessError as e:
        error_output = e.stderr if e.stderr else str(e)
        
        # Try alternative method with different parameters
        try:
            # Use alternative user agent and parameters
            alt_params = common_params.copy()
            
            if len(platform_info['user_agents']) > 1:
                # Use alternative user agent if available
                alt_user_agent = platform_info['user_agents'][1]
                alt_params.extend(['--user-agent', alt_user_agent])
            else:
                alt_params.extend(['--user-agent', user_agent])
            
            # Add more specific parameters
            alt_params.extend([
                '--force-generic-extractor',
                '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                '--add-header', 'Accept-Language: en-US,en;q=0.5',
                '--add-header', 'Connection: keep-alive',
                '--add-header', 'Upgrade-Insecure-Requests: 1',
                '--add-header', 'Cache-Control: max-age=0'
            ])
            
            # Check if we have credentials available
            credentials = get_credentials(platform)
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
                    "platform": platform_info['name']
                }
            })
            
        except Exception as alt_err:
            credentials_exist = get_credentials(platform) is not None
            return jsonify({
                "error": f"{platform_info['name']} login required and alternative method failed",
                "details": str(alt_err),
                "solution": f"Try uploading {platform_info['name']} cookies from a logged-in browser session",
                "has_credentials": credentials_exist
            }), 403
        
        # Provide more specific and helpful error messages for other cases
        if "Sign in to confirm you're not a bot" in error_output:
            return jsonify({
                "error": f"{platform_info['name']} requires authentication to verify you're not a bot",
                "solution": f"Upload {platform_info['name']} cookies from a logged-in browser session",
                "has_cookies": os.path.exists(cookie_path)
            }), 403
        elif "login required" in error_output or "Requested content is not available" in error_output:
            return jsonify({
                "error": f"{platform_info['name']} login required",
                "solution": f"Upload {platform_info['name']} cookies from a logged-in browser session",
                "has_cookies": os.path.exists(cookie_path)
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
    if platform not in SUPPORTED_PLATFORMS:
        return jsonify({"error": f"Invalid platform. Must be one of: {', '.join(SUPPORTED_PLATFORMS.keys())}"}), 400
    
    try:
        # Ensure cookie directory exists
        os.makedirs(COOKIE_DIR, exist_ok=True)
        
        # Save the file
        filename = f"{platform}_cookies.txt"
        file_path = os.path.join(COOKIE_DIR, filename)
        file.save(file_path)
        
        # Check if file is in Netscape format
        with open(file_path, 'r') as f:
            first_line = f.readline().strip()
            if not first_line.startswith('# Netscape HTTP Cookie File'):
                # Convert to Netscape format
                with open(file_path, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
                    f.write("# This is a generated file! Do not edit.\n\n")
                    domains = [f".{d}" for d in SUPPORTED_PLATFORMS[platform]['domains'] if '.' in d]
                    if domains:
                        domain = domains[0]
                        f.write(f"{domain}\tTRUE\t/\tTRUE\t2147483647\tcookies_uploaded\ttrue\n")
        
        return jsonify({
            "success": True,
            "message": f"Cookies for {SUPPORTED_PLATFORMS[platform]['name']} uploaded successfully"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to save cookie file: {str(e)}"}), 500

@app.route('/api/set-credentials', methods=['POST'])
def set_credentials():
    """Endpoint to save platform credentials"""
    try:
        # Try to get data from JSON first
        if request.is_json:
            data = request.json
        else:
            # Try to get data from form
            data = {
                'platform': request.form.get('platform'),
                'username': request.form.get('username'),
                'password': request.form.get('password')
            }
            
            # If no form data, try to parse raw data as JSON
            if not any(data.values()):
                try:
                    data = json.loads(request.get_data())
                except:
                    return jsonify({
                        "error": "Request must be JSON or form data",
                        "content_type": request.content_type,
                        "received_data": str(request.get_data())
                    }), 400
        
        if not data:
            return jsonify({
                "error": "No credentials data provided",
                "received_data": str(request.get_data())
            }), 400
            
        platform = data.get('platform', '').lower()
        if not platform:
            return jsonify({
                "error": "Platform is required",
                "received_data": data
            }), 400
            
        if platform not in SUPPORTED_PLATFORMS:
            return jsonify({
                "error": f"Invalid platform. Must be one of: {', '.join(SUPPORTED_PLATFORMS.keys())}",
                "received_platform": platform
            }), 400
            
        username = data.get('username')
        password = data.get('password')
        
        if not username:
            return jsonify({
                "error": "Username is required",
                "received_data": {k: v for k, v in data.items() if k != 'password'}
            }), 400
            
        if not password:
            return jsonify({
                "error": "Password is required",
                "received_data": {k: v for k, v in data.items() if k != 'password'}
            }), 400
            
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
            
            # Get test URL for the platform
            domains = SUPPORTED_PLATFORMS[platform]['domains']
            base_domain = next((d for d in domains if '.' in d), domains[0])
            test_url = f"https://www.{base_domain}"
                
            try:
                # Create a temporary directory for cookie generation
                with tempfile.TemporaryDirectory() as temp_dir:
                    # First, try to get cookies using yt-dlp
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
                    
                    result = subprocess.run(auth_cmd, capture_output=True, text=True)
                    
                    # If cookie generation failed, try alternative method
                    if not os.path.exists(cookie_file) or os.path.getsize(cookie_file) == 0:
                        # Try using curl to get cookies
                        curl_cmd = [
                            'curl',
                            '-c', cookie_file,
                            '-b', cookie_file,
                            '-L',
                            '-A', SUPPORTED_PLATFORMS[platform]['user_agents'][0],
                            '-d', f'username={username}&password={password}',
                            '-H', 'Content-Type: application/x-www-form-urlencoded',
                            test_url
                        ]
                        
                        try:
                            subprocess.run(curl_cmd, capture_output=True, text=True, check=True)
                        except subprocess.CalledProcessError:
                            # If curl fails, create a basic Netscape format cookie file
                            domains = [f".{d}" for d in SUPPORTED_PLATFORMS[platform]['domains'] if '.' in d]
                            if domains:
                                domain = domains[0]
                                with open(cookie_file, 'w') as f:
                                    f.write("# Netscape HTTP Cookie File\n")
                                    f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
                                    f.write("# This is a generated file! Do not edit.\n\n")
                                    f.write(f"{domain}\tTRUE\t/\tTRUE\t2147483647\tusername\t{username}\n")
                                    f.write(f"{domain}\tTRUE\t/\tTRUE\t2147483647\tpassword\t{password}\n")
                    
                    # Check if cookies file was created
                    if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 0:
                        return jsonify({
                            "success": True,
                            "message": f"{SUPPORTED_PLATFORMS[platform]['name']} credentials saved successfully and cookies generated",
                            "has_cookies": True
                        })
            except Exception as e:
                # Log error but continue - we'll return success for credentials even if cookie generation fails
                print(f"Error generating cookies: {str(e)}")
        
        # Return success for saving credentials even if cookie generation fails
        return jsonify({
            "success": True,
            "message": f"{SUPPORTED_PLATFORMS[platform]['name']} credentials saved successfully",
            "has_cookies": False
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to save credentials: {str(e)}",
            "request_data": str(request.get_data()),
            "content_type": request.content_type
        }), 500

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
        
        # Check if cookie files and credentials exist for each platform
        cookies_status = {}
        credentials_status = {}
        
        for platform in SUPPORTED_PLATFORMS:
            cookies_status[platform] = os.path.exists(os.path.join(COOKIE_DIR, f"{platform}_cookies.txt"))
            credentials_status[platform] = get_credentials(platform) is not None
        
        return jsonify({
            "success": True,
            "yt_dlp_version": version,
            "yt_dlp_path": ytdlp_path,
            "python_version": sys.version,
            "cookies": cookies_status,
            "credentials": credentials_status,
            "supported_platforms": list(SUPPORTED_PLATFORMS.keys())
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
    
    # Print supported platforms
    print(f"Supported platforms: {', '.join(SUPPORTED_PLATFORMS.keys())}")
    
    print("Starting the Video Downloader web application...")
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 

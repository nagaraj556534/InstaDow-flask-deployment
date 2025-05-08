from flask import Flask, request, jsonify, render_template, send_file, abort
import os
import tempfile
import re
import subprocess
import json
import sys
import uuid
import logging
import shutil
import traceback

app = Flask(__name__)

# Constants
COOKIE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies')
DOWNLOAD_DIRS = {
    'instagram': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instagram_files'),
    'youtube': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'youtube_files'),
    'tiktok': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tiktok_files')
}
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
                margin: 5px;
            }
            button:hover {
                background-color: #45a049;
            }
            .supported {
                margin-top: 20px;
                color: #666;
                font-size: 14px;
            }
            .download-options {
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                margin-top: 10px;
            }
            .separator {
                margin: 20px 0;
                border-top: 1px solid #ddd;
            }
            .error-message {
                color: #f44336;
                margin: 10px 0;
                font-size: 14px;
                display: none;
            }
            .instagram-button {
                background-color: #C13584;
            }
            .instagram-button:hover {
                background-color: #a52e70;
            }
            .debug-button {
                background-color: #3498db;
                margin-top: 10px;
                font-size: 14px;
                padding: 8px 16px;
            }
            .debug-button:hover {
                background-color: #2980b9;
            }
            .tooltips {
                margin-top: 15px;
                font-size: 13px;
                color: #666;
                text-align: left;
                background-color: #f9f9f9;
                padding: 10px;
                border-radius: 4px;
            }
            .tooltips h3 {
                font-size: 15px;
                margin: 5px 0;
            }
            .tooltips ul {
                margin: 5px 0;
                padding-left: 20px;
            }
        </style>
    </head>
    <body>
        <h1>Video Downloader</h1>
        <p>Paste a video URL from Instagram, YouTube, or TikTok to download</p>
        
        <form id="downloadForm">
            <div class="form-group">
                <input type="text" id="videoUrl" name="url" placeholder="https://..." required>
            </div>
            
            <div class="download-options">
                <button type="button" onclick="downloadVideo('instant')">Download Video</button>
                <button type="button" onclick="downloadVideo('instagram')" class="instagram-button">Instagram Standard</button>
                <button type="button" onclick="downloadVideo('robust')" class="instagram-button" style="background-color: #8a3ab9;">Instagram Robust</button>
            </div>
            
            <div id="errorMessage" class="error-message"></div>
            
            <button type="button" id="debugButton" onclick="debugInstagram()" class="debug-button" style="display: none;">Debug Instagram URL</button>
        </form>
        
        <div class="separator"></div>
        
        <div class="supported">
            <p>Supported platforms: Instagram, YouTube, TikTok, and more</p>
            <p><small>If standard methods don't work for Instagram, try the robust option</small></p>
        </div>
        
        <div class="tooltips">
            <h3>Which download method should I use?</h3>
            <ul>
                <li><strong>Download Video:</strong> Works for most YouTube and TikTok videos</li>
                <li><strong>Instagram Standard:</strong> Fast method for public Instagram posts</li>
                <li><strong>Instagram Robust:</strong> Advanced method that works with private content (requires login)</li>
            </ul>
            <p><small>For Instagram login, go to /api/upload-cookies or /api/set-credentials</small></p>
        </div>
        
        <script>
            function downloadVideo(method) {
                const urlInput = document.getElementById('videoUrl');
                const errorMsg = document.getElementById('errorMessage');
                const debugBtn = document.getElementById('debugButton');
                const url = urlInput.value.trim();
                
                if (!url) {
                    errorMsg.textContent = "Please enter a URL";
                    errorMsg.style.display = "block";
                    return;
                }
                
                if (!url.startsWith('http://') && !url.startsWith('https://')) {
                    errorMsg.textContent = "URL must start with http:// or https://";
                    errorMsg.style.display = "block";
                    return;
                }
                
                errorMsg.style.display = "none";
                
                // Show debug button for Instagram URLs
                if (url.includes('instagram.com')) {
                    debugBtn.style.display = "inline-block";
                } else {
                    debugBtn.style.display = "none";
                }
                
                // Choose endpoint based on method and platform
                let endpoint = '/api/instant-download';
                
                if (method === 'instagram' && url.includes('instagram.com')) {
                    endpoint = '/api/instagram-download';
                } else if (method === 'robust' && url.includes('instagram.com')) {
                    endpoint = '/api/instagram-download-robust';
                } else if (url.includes('instagram.com') && method === 'instant') {
                    endpoint = '/api/instagram-download';
                }
                
                // Redirect to download endpoint
                window.location.href = `${endpoint}?url=${encodeURIComponent(url)}`;
            }
            
            function debugInstagram() {
                const urlInput = document.getElementById('videoUrl');
                const url = urlInput.value.trim();
                
                if (url && url.includes('instagram.com')) {
                    window.open(`/api/debug-instagram?url=${encodeURIComponent(url)}`, '_blank');
                }
            }
            
            // Check URL on input to show/hide debug button
            document.getElementById('videoUrl').addEventListener('input', function() {
                const debugBtn = document.getElementById('debugButton');
                if (this.value.includes('instagram.com')) {
                    debugBtn.style.display = "inline-block";
                } else {
                    debugBtn.style.display = "none";
                }
            });
        </script>
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
        # Validate request
        if not request.args:
            return "Error: No parameters provided", 400
            
        url = request.args.get('url')
        if not url:
            return "Error: URL parameter is required", 400
            
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            return "Error: Invalid URL. Must start with http:// or https://", 400
            
        # Validate URL length
        if len(url) > 2048:  # Reasonable max length for URLs
            return "Error: URL is too long", 400
            
        # Create temporary directory with unique name
        temp_dir = tempfile.mkdtemp(prefix='direct_')
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Find yt-dlp executable path and test it
        ytdlp_path = find_ytdlp_path()
        
        # Test if yt-dlp works by checking its version
        ytdlp_works = False
        try:
            version_cmd = [ytdlp_path, '--version']
            result = subprocess.run(version_cmd, capture_output=True, text=True, timeout=5)
            ytdlp_works = (result.returncode == 0)
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            try:
                # Try pip install as a fallback if not working
                subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'], 
                              capture_output=True, check=False, timeout=60)
                # Test again after installation
                try:
                    version_cmd = [ytdlp_path, '--version']
                    result = subprocess.run(version_cmd, capture_output=True, text=True, timeout=5)
                    ytdlp_works = (result.returncode == 0)
                except:
                    ytdlp_works = False
            except:
                ytdlp_works = False
        
        # Determine platform and set up specific parameters
        platform = get_platform_from_url(url)
        if not platform:
            return "Error: Unsupported platform. Please provide a valid Instagram, YouTube, or TikTok URL.", 400
            
        platform_info = SUPPORTED_PLATFORMS.get(platform)
        
        # Special handling for Instagram URLs - use Python requests as fallback if needed
        if platform == 'instagram' and not ytdlp_works:
            try:
                # Extract video ID from Instagram URL
                video_id = None
                match = re.search(r'instagram\.com/(?:p|reel)/([^/?]+)', url)
                if match:
                    video_id = match.group(1)
                
                if not video_id:
                    return "Error: Could not extract video ID from Instagram URL", 400
                
                # Use requests to download the page
                headers = {
                    'User-Agent': platform_info['user_agents'][0],
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0'
                }
                
                # Try to download the page and extract video URL
                import requests
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    return f"Error: Instagram returned status code {response.status_code}", 400
                
                # Look for video URL in the page
                html_content = response.text
                
                # Save HTML content for debugging
                debug_html_path = os.path.join(temp_dir, "instagram_debug.html")
                with open(debug_html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                video_url = None
                
                # Match common video URL patterns
                video_patterns = [
                    r'(https://scontent[^"\']+\.mp4[^"\']*)',
                    r'(https://instagram\.[\w\.]+/v/[^"\']+)',
                    r'(https://[\w-]+\.cdninstagram\.com/v/[^"\']+\.mp4[^"\']*)',
                    r'video_url":"([^"]+)"',
                    r'"video_url":"([^"]+)"',
                    r'<meta property="og:video" content="([^"]+)"',
                    r'<meta property="og:video:secure_url" content="([^"]+)"',
                    r'<source src="([^"]+)" type="video/mp4"',
                    r'"contentUrl"\s*:\s*"([^"]+)"',
                    r'"playbackVideoUrl":"([^"]+)"',
                ]
                
                for pattern in video_patterns:
                    matches = re.findall(pattern, html_content)
                    if matches:
                        for match in matches:
                            cleaned_match = match.replace('\\u0026', '&').replace('\\/', '/')
                            if '.mp4' in cleaned_match or '/v/' in cleaned_match:
                                video_url = cleaned_match
                                break
                        if video_url:
                            break
                
                if not video_url:
                    # Try Instagram API URL format
                    api_url = f"https://www.instagram.com/p/{video_id}/?__a=1"
                    try:
                        api_response = requests.get(api_url, headers=headers, timeout=10)
                        if api_response.status_code == 200 and api_response.text:
                            try:
                                api_data = json.loads(api_response.text)
                                # Try to find video URL in API response
                                if 'graphql' in api_data and 'shortcode_media' in api_data['graphql']:
                                    media = api_data['graphql']['shortcode_media']
                                    if 'video_url' in media:
                                        video_url = media['video_url']
                            except json.JSONDecodeError:
                                pass
                    except:
                        pass
                
                if not video_url:
                    return f"Error: Could not find video URL in Instagram page. Check {debug_html_path} for details.", 400
                
                # Download the video
                video_filename = f"instagram_{video_id}.mp4"
                video_path = os.path.join(temp_dir, video_filename)
                
                video_response = requests.get(video_url, headers=headers, stream=True, timeout=30)
                
                if video_response.status_code != 200:
                    return f"Error: Failed to download video, status code: {video_response.status_code}", 400
                
                with open(video_path, 'wb') as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Check file size
                if os.path.getsize(video_path) < 1000:
                    return "Error: Downloaded file is too small, likely not a valid video", 400
                
                # Return the video file
                return send_file(
                    video_path,
                    as_attachment=True,
                    download_name=video_filename,
                    mimetype='video/mp4'
                )
                
            except Exception as e:
                return f"Error with Instagram download: {str(e)}", 500
        
        if not ytdlp_works:
            return "Error: yt-dlp is not working. Please install it manually. Try 'pip install yt-dlp'", 500
        
        # Base parameters for all platforms
        download_params = [
            ytdlp_path,
            '--no-warnings',
            '--no-check-certificate',
            '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--output', output_template,
            '--ignore-errors',
            '--no-playlist',
            '--user-agent', platform_info['user_agents'][0],
            '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            '--add-header', 'Accept-Language: en-US,en;q=0.5',
            '--add-header', 'Connection: keep-alive',
            '--add-header', 'Upgrade-Insecure-Requests: 1',
            '--add-header', 'Cache-Control: max-age=0'
        ]
        
        # Add platform-specific parameters
        if platform == 'instagram':
            download_params.extend([
                '--extractor-args', 'instagram:logged_in=true',
                '--add-header', 'X-IG-App-ID: 936619743392459',
                '--add-header', 'X-Requested-With: XMLHttpRequest'
            ])
            
            # Check for cookies or credentials
            cookie_path = os.path.join(COOKIE_DIR, f"{platform}_cookies.txt")
            credentials = get_credentials(platform)
            
            if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 0:
                download_params.extend(['--cookies', cookie_path])
            elif credentials and credentials.get('username') and credentials.get('password'):
                download_params.extend([
                    '--username', credentials['username'],
                    '--password', credentials['password']
                ])
        
        try:
            # Run the download command with timeout
            result = subprocess.run(
                download_params + [url],
                check=False,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Find downloaded file
            video_file = None
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and any(file.endswith(ext) for ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']):
                    video_file = file_path
                    break
            
            if not video_file:
                # If first attempt failed, try alternate method
                alt_params = [
                    ytdlp_path,
                    '--no-warnings',
                    '--no-check-certificate',
                    '--format', 'best',
                    '--output', output_template,
                    '--ignore-errors',
                    '--no-playlist',
                    '--force-generic-extractor',
                    '--user-agent', platform_info['user_agents'][0] if len(platform_info['user_agents']) == 1 else platform_info['user_agents'][1],
                    url
                ]
                
                # Run the alternate command with timeout
                subprocess.run(
                    alt_params,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30  # 30 second timeout
                )
                
                # Check again for downloaded files
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path) and any(file.endswith(ext) for ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']):
                        video_file = file_path
                        break
            
            if not video_file:
                error_msg = result.stderr if result.stderr else "Unknown error occurred"
                if "login required" in error_msg.lower():
                    return "Error: This content requires login. Please provide Instagram credentials.", 401
                elif "sign in" in error_msg.lower():
                    return "Error: Instagram requires authentication. Please provide credentials.", 401
                elif "not available" in error_msg.lower():
                    return "Error: This content is not available or has been removed.", 404
                else:
                    return f"Error downloading video: {error_msg}", 400
            
            # Get the filename for the Content-Disposition header
            filename = os.path.basename(video_file)
            
            # Serve the file directly to the user for download
            return send_file(
                video_file,
                as_attachment=True,
                download_name=filename,
                mimetype='video/mp4'  # Assume mp4, most browsers handle this well for various formats
            )
            
        except subprocess.TimeoutExpired:
            return "Error: Download timed out. Please try again.", 504
        except subprocess.CalledProcessError as e:
            return f"Error during download: {e.stderr if e.stderr else str(e)}", 500
        except Exception as e:
            return f"Error processing video: {str(e)}", 500
            
    except Exception as e:
        return f"Error: {str(e)}", 500
    finally:
        # Clean up temporary directory
        try:
            if 'temp_dir' in locals():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

@app.route('/api/instagram-download')
def instagram_download():
    """Special endpoint just for Instagram downloads that doesn't rely on yt-dlp"""
    try:
        # Validate request
        url = request.args.get('url')
        if not url:
            return "Error: URL parameter is required", 400
            
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            return "Error: Invalid URL. Must start with http:// or https://", 400
            
        # Check if it's an Instagram URL
        if 'instagram.com' not in url.lower():
            return "Error: This endpoint is only for Instagram URLs", 400
            
        # Extract video ID
        video_id = None
        match = re.search(r'instagram\.com/(?:p|reel)/([^/?]+)', url)
        if match:
            video_id = match.group(1)
        
        if not video_id:
            return "Error: Could not extract video ID from Instagram URL", 400
        
        # Create temporary directory and ensure the Instagram download directory exists
        temp_dir = tempfile.mkdtemp(prefix='insta_download_')
        download_dir = DOWNLOAD_DIRS.get('instagram')
        os.makedirs(download_dir, exist_ok=True)
        
        # Use enhanced browser-like headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Google Chrome";v="135", "Chromium";v="135", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://www.instagram.com/'
        }
        
        # Try different URL formats for Instagram
        instagram_urls = [
            url,
            f"https://www.instagram.com/reel/{video_id}/",
            f"https://www.instagram.com/p/{video_id}/",
            # Also try the embed page which sometimes has the video more accessible
            f"https://www.instagram.com/p/{video_id}/embed/",
            f"https://www.instagram.com/reel/{video_id}/embed/"
        ]
        
        import requests
        html_content = None
        response_url = None
        
        for instagram_url in instagram_urls:
            try:
                response = requests.get(instagram_url, headers=headers, timeout=15)
                if response.status_code == 200 and len(response.text) > 1000:  # Ensure we got a real page
                    html_content = response.text
                    response_url = instagram_url
                    break
            except Exception:
                continue
        
        if not html_content:
            return "Error: Could not fetch Instagram page. Please check if the URL is valid.", 400
        
        # Save HTML for debugging
        debug_html_path = os.path.join(temp_dir, f"{video_id}.html")
        with open(debug_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Improved video URL extraction
        video_url = None
        
        # First look for common video URL patterns in HTML
        video_patterns = [
            r'(https://scontent[^"\']+\.mp4[^"\']*)',
            r'(https://instagram\.[\w\.]+/v/[^"\']+)',
            r'(https://[\w-]+\.cdninstagram\.com/v/[^"\']+\.mp4[^"\']*)',
            r'video_url":"([^"]+)"',
            r'"video_url":"([^"]+)"',
            r'<meta property="og:video" content="([^"]+)"',
            r'<meta property="og:video:secure_url" content="([^"]+)"',
            r'<source src="([^"]+)" type="video/mp4"',
            r'"contentUrl"\s*:\s*"([^"]+)"',
            r'"playbackVideoUrl":"([^"]+)"',
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, html_content)
            if matches:
                for match in matches:
                    # Clean up URL (remove escapes)
                    cleaned_match = match.replace('\\u0026', '&').replace('\\/', '/')
                    # Only consider if it looks like a video URL
                    if ('.mp4' in cleaned_match or '/v/' in cleaned_match) and ('http' in cleaned_match):
                        video_url = cleaned_match
                        break
                if video_url:
                    break
        
        # If not found, try to extract from JSON data
        if not video_url:
            json_data_matches = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html_content, re.DOTALL)
            for json_match in json_data_matches:
                try:
                    json_data = json.loads(json_match)
                    
                    # Function to recursively search for video URL in JSON
                    def find_video_url(obj, path=""):
                        if isinstance(obj, dict):
                            # First check for fields that are commonly used for video URLs
                            for key in ['video_url', 'video_src', 'contentUrl', 'playbackVideoUrl', 'url']:
                                if key in obj and isinstance(obj[key], str):
                                    value = obj[key]
                                    if '.mp4' in value or '/v/' in value:
                                        return value
                            
                            # Then recursively search all fields
                            for key, value in obj.items():
                                result = find_video_url(value, f"{path}.{key}")
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for i, item in enumerate(obj):
                                result = find_video_url(item, f"{path}[{i}]")
                                if result:
                                    return result
                        return None
                    
                    potential_url = find_video_url(json_data)
                    if potential_url:
                        video_url = potential_url.replace('\\u0026', '&').replace('\\/', '/')
                        break
                except json.JSONDecodeError:
                    continue
        
        # If we still don't have a video URL and this is an embed page, try to look for iframe src
        if not video_url and '/embed/' in response_url:
            iframe_matches = re.findall(r'<iframe[^>]+src="([^"]+)"', html_content)
            for iframe_src in iframe_matches:
                if 'instagram.com' in iframe_src and video_id in iframe_src:
                    try:
                        iframe_response = requests.get(iframe_src, headers=headers, timeout=15)
                        if iframe_response.status_code == 200:
                            iframe_content = iframe_response.text
                            for pattern in video_patterns:
                                matches = re.findall(pattern, iframe_content)
                                if matches:
                                    for match in matches:
                                        cleaned_match = match.replace('\\u0026', '&').replace('\\/', '/')
                                        if '.mp4' in cleaned_match or '/v/' in cleaned_match:
                                            video_url = cleaned_match
                                            break
                                    if video_url:
                                        break
                    except:
                        continue
        
        # If still no video URL, try using the Instagram API format
        if not video_url:
            api_url = f"https://www.instagram.com/p/{video_id}/?__a=1"
            try:
                api_response = requests.get(api_url, headers=headers, timeout=10)
                if api_response.status_code == 200 and api_response.text:
                    try:
                        api_data = json.loads(api_response.text)
                        # Try to find video URL in API response
                        if 'graphql' in api_data and 'shortcode_media' in api_data['graphql']:
                            media = api_data['graphql']['shortcode_media']
                            if 'video_url' in media:
                                video_url = media['video_url']
                    except json.JSONDecodeError:
                        pass
            except:
                pass
        
        # Final attempt - if it's a reel, try the OEmbed API
        if not video_url and 'reel' in url:
            try:
                oembed_url = f"https://api.instagram.com/oembed/?url={url}"
                oembed_response = requests.get(oembed_url, headers=headers, timeout=10)
                if oembed_response.status_code == 200:
                    try:
                        oembed_data = json.loads(oembed_response.text)
                        if 'html' in oembed_data:
                            html_snippet = oembed_data['html']
                            for pattern in video_patterns:
                                matches = re.findall(pattern, html_snippet)
                                if matches:
                                    for match in matches:
                                        cleaned_match = match.replace('\\u0026', '&').replace('\\/', '/')
                                        if '.mp4' in cleaned_match or '/v/' in cleaned_match:
                                            video_url = cleaned_match
                                            break
                                    if video_url:
                                        break
                    except:
                        pass
            except:
                pass
        
        # If we still couldn't find the video URL
        if not video_url:
            return jsonify({
                "error": "Could not find video URL in Instagram page",
                "debug_file": debug_html_path,
                "video_id": video_id,
                "solution": "Try using the '/api/debug-instagram' endpoint with this URL for more details"
            }), 400
        
        # Download the video
        video_filename = f"instagram_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
        temp_video_path = os.path.join(temp_dir, video_filename)
        
        video_response = requests.get(video_url, headers=headers, stream=True, timeout=30)
        
        if video_response.status_code != 200:
            return f"Error: Failed to download video, status code: {video_response.status_code}", 400
        
        with open(temp_video_path, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify file size and type
        if os.path.getsize(temp_video_path) < 10000:  # Less than 10KB is probably not a valid video
            return "Error: Downloaded file is too small, likely not a valid video", 400
            
        # Move to final location
        final_path = os.path.join(download_dir, video_filename)
        shutil.move(temp_video_path, final_path)
        
        # Return the video file
        return send_file(
            final_path,
            as_attachment=True,
            download_name=video_filename,
            mimetype='video/mp4'
        )
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/instagram-download-robust')
def instagram_download_robust():
    """Even more robust Instagram download with multiple fallback methods"""
    try:
        # Validate request
        url = request.args.get('url')
        if not url:
            return "Error: URL parameter is required", 400
            
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            return "Error: Invalid URL. Must start with http:// or https://", 400
            
        # Check if it's an Instagram URL
        if 'instagram.com' not in url.lower():
            return "Error: This endpoint is only for Instagram URLs", 400
            
        # Extract video ID
        video_id = None
        match = re.search(r'instagram\.com/(?:p|reel)/([^/?]+)', url)
        if match:
            video_id = match.group(1)
        
        if not video_id:
            return "Error: Could not extract video ID from Instagram URL", 400
        
        # Create temporary directory and ensure the Instagram download directory exists
        temp_dir = tempfile.mkdtemp(prefix='insta_download_robust_')
        download_dir = DOWNLOAD_DIRS.get('instagram')
        os.makedirs(download_dir, exist_ok=True)
        
        # Track which methods we've tried
        tried_methods = []
        errors = {}
        
        # 1. Try to download with yt-dlp directly first (most reliable when it works)
        tried_methods.append("yt-dlp")
        try:
            # Use yt-dlp with special flags to help with extraction
            ytdlp_path = find_ytdlp_path()
            if ytdlp_path:
                video_filename = f"instagram_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                output_path = os.path.join(download_dir, video_filename)
                
                # Enhanced yt-dlp parameters specifically for Instagram
                yt_params = [
                    ytdlp_path,
                    '--no-warnings',
                    '--no-check-certificate',
                    '--ignore-errors',
                    '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    '-o', output_path,
                    '--user-agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 213.0.0.22.120',
                    '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    '--add-header', 'Accept-Language: en-US,en;q=0.9',
                    '--add-header', 'Connection: keep-alive',
                    '--add-header', 'Upgrade-Insecure-Requests: 1',
                    '--add-header', 'Sec-Fetch-Dest: document',
                    '--add-header', 'Sec-Fetch-Mode: navigate',
                    '--add-header', 'Sec-Fetch-Site: none',
                    '--add-header', 'Sec-Fetch-User: ?1',
                    '--add-header', 'Referer: https://www.instagram.com/',
                    '--add-header', 'X-IG-App-ID: 936619743392459',
                    '--add-header', 'X-Requested-With: XMLHttpRequest',
                    '--extractor-args', 'instagram:logged_in=true',
                    url
                ]
                
                # Try with cookies if available
                cookie_path = os.path.join(COOKIE_DIR, "instagram_cookies.txt")
                if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 0:
                    yt_params.extend(['--cookies', cookie_path])
                
                # Try with credentials if available
                credentials = get_credentials('instagram')
                if credentials and credentials.get('username') and credentials.get('password'):
                    yt_params.extend([
                        '--username', credentials['username'],
                        '--password', credentials['password']
                    ])
                
                # Run the command
                try:
                    logging.info(f"Attempting to download with yt-dlp robust method: {url}")
                    result = subprocess.run(yt_params, capture_output=True, text=True, timeout=60)
                    
                    # Check if the file was created and has content
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                        return send_file(
                            output_path,
                            as_attachment=True,
                            download_name=video_filename,
                            mimetype='video/mp4'
                        )
                    else:
                        errors["yt-dlp"] = {
                            "exit_code": result.returncode,
                            "stderr": result.stderr[:500] if result.stderr else "",
                            "stdout": result.stdout[:500] if result.stdout else ""
                        }
                except Exception as e:
                    errors["yt-dlp"] = str(e)
                    logging.error(f"Error in yt-dlp robust download: {str(e)}")
        except Exception as ytdlp_error:
            errors["yt-dlp"] = str(ytdlp_error)
            logging.error(f"Failed to use yt-dlp for robust download: {str(ytdlp_error)}")
        
        # 2. Try the embed URL method (often works when regular URLs don't)
        tried_methods.append("embed_url")
        try:
            embed_url = f"https://www.instagram.com/p/{video_id}/embed/"
            if 'reel' in url.lower():
                embed_url = f"https://www.instagram.com/reel/{video_id}/embed/"
                
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 213.0.0.22.120',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
                'Referer': 'https://www.instagram.com/'
            }
            
            import requests
            response = requests.get(embed_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                html_content = response.text
                
                # Look for video URL in the embed page
                video_patterns = [
                    r'(https://scontent[^"\']+\.mp4[^"\']*)',
                    r'(https://instagram\.[\w\.]+/v/[^"\']+)',
                    r'(https://[\w-]+\.cdninstagram\.com/v/[^"\']+\.mp4[^"\']*)',
                    r'video_url":"([^"]+)"',
                    r'"video_url":"([^"]+)"',
                    r'<meta property="og:video" content="([^"]+)"',
                    r'<meta property="og:video:secure_url" content="([^"]+)"',
                    r'<source src="([^"]+)" type="video/mp4"',
                    r'"contentUrl"\s*:\s*"([^"]+)"',
                    r'"playbackVideoUrl":"([^"]+)"'
                ]
                
                video_url = None
                for pattern in video_patterns:
                    matches = re.findall(pattern, html_content)
                    if matches:
                        for match in matches:
                            cleaned_match = match.replace('\\u0026', '&').replace('\\/', '/')
                            if '.mp4' in cleaned_match or '/v/' in cleaned_match:
                                video_url = cleaned_match
                                break
                        if video_url:
                            break
                
                if video_url:
                    # Download the video
                    video_filename = f"instagram_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = os.path.join(download_dir, video_filename)
                    
                    video_response = requests.get(video_url, headers=headers, stream=True, timeout=30)
                    
                    if video_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in video_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # Verify file size
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                            return send_file(
                                output_path,
                                as_attachment=True,
                                download_name=video_filename,
                                mimetype='video/mp4'
                            )
                    else:
                        errors["embed_url"] = f"Video response status code: {video_response.status_code}"
                else:
                    errors["embed_url"] = "No video URL found in embed page"
            else:
                errors["embed_url"] = f"Embed page response status code: {response.status_code}"
        except Exception as embed_error:
            errors["embed_url"] = str(embed_error)
            logging.error(f"Error using embed URL method: {str(embed_error)}")
        
        # 3. Try using instaloader (specialized Instagram tool)
        tried_methods.append("instaloader")
        try:
            # Check if instaloader is installed
            try:
                import importlib
                instaloader_spec = importlib.util.find_spec('instaloader')
                if instaloader_spec is None:
                    logging.info("Instaloader not found, attempting to install...")
                    subprocess.run([sys.executable, '-m', 'pip', 'install', 'instaloader'], 
                                  check=True, capture_output=True)
            except Exception as install_error:
                errors["instaloader_install"] = str(install_error)
                logging.error(f"Failed to install instaloader: {str(install_error)}")
            
            try:
                import instaloader
                
                # Create an instaloader instance
                L = instaloader.Instaloader(
                    download_pictures=False,
                    download_videos=True,
                    download_video_thumbnails=False,
                    download_geotags=False,
                    download_comments=False,
                    save_metadata=False,
                    compress_json=False,
                    post_metadata_txt_pattern='',
                    dirname_pattern=temp_dir
                )
                
                # Try to log in if credentials are available
                credentials = get_credentials('instagram')
                if credentials and credentials.get('username') and credentials.get('password'):
                    try:
                        L.login(credentials['username'], credentials['password'])
                    except Exception as login_error:
                        errors["instaloader_login"] = str(login_error)
                        logging.error(f"Instaloader login error: {str(login_error)}")
                
                # Download the post
                post = instaloader.Post.from_shortcode(L.context, video_id)
                L.download_post(post, target=None)
                
                # Find the downloaded video
                video_file = None
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path) and file.endswith('.mp4'):
                        video_file = file_path
                        break
                
                if video_file:
                    # Move to final location
                    video_filename = f"instagram_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                    final_path = os.path.join(download_dir, video_filename)
                    shutil.move(video_file, final_path)
                    
                    return send_file(
                        final_path,
                        as_attachment=True,
                        download_name=video_filename,
                        mimetype='video/mp4'
                    )
                else:
                    errors["instaloader"] = "No video file found after downloading with instaloader"
            except Exception as insta_error:
                errors["instaloader"] = str(insta_error)
                logging.error(f"Instaloader error: {str(insta_error)}")
        except Exception as e:
            errors["instaloader"] = str(e)
            logging.error(f"Failed to use instaloader: {str(e)}")
        
        # 4. Try using direct API approach
        tried_methods.append("instagram_api")
        try:
            import requests
            
            api_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 213.0.0.22.120',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'https://www.instagram.com/p/{video_id}/',
                'Origin': 'https://www.instagram.com',
                'Connection': 'keep-alive'
            }
            
            # Try to use cookies if available
            cookies = {}
            cookie_path = os.path.join(COOKIE_DIR, "instagram_cookies.txt")
            if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 0:
                try:
                    with open(cookie_path, 'r') as f:
                        cookie_content = f.read()
                        for line in cookie_content.split('\n'):
                            if line.strip() and not line.startswith('#'):
                                try:
                                    domain, _, path, secure, expires, name, value = line.split('\t')
                                    if '.instagram.com' in domain and name not in cookies:
                                        cookies[name] = value
                                except:
                                    continue
                except Exception as cookie_error:
                    errors["api_cookies"] = str(cookie_error)
            
            # Try different API endpoints
            api_urls = [
                f"https://www.instagram.com/p/{video_id}/?__a=1",
                f"https://www.instagram.com/reel/{video_id}/?__a=1",
                f"https://i.instagram.com/api/v1/media/{video_id}/info/"
            ]
            
            video_url = None
            for api_url in api_urls:
                try:
                    api_response = requests.get(api_url, headers=api_headers, cookies=cookies, timeout=15)
                    if api_response.status_code == 200 and api_response.text:
                        try:
                            data = json.loads(api_response.text)
                            
                            # Function to recursively search for video URL
                            def find_video_url(obj):
                                if isinstance(obj, dict):
                                    for key in ['video_url', 'video_versions']:
                                        if key in obj:
                                            if key == 'video_url' and isinstance(obj[key], str):
                                                return obj[key]
                                            elif key == 'video_versions' and isinstance(obj[key], list) and len(obj[key]) > 0:
                                                if 'url' in obj[key][0]:
                                                    return obj[key][0]['url']
                                    
                                    for value in obj.values():
                                        result = find_video_url(value)
                                        if result:
                                            return result
                                elif isinstance(obj, list):
                                    for item in obj:
                                        result = find_video_url(item)
                                        if result:
                                            return result
                                return None
                            
                            potential_url = find_video_url(data)
                            if potential_url:
                                video_url = potential_url
                                break
                        except json.JSONDecodeError:
                            errors["api_json"] = f"Invalid JSON from {api_url}"
                except Exception as api_error:
                    errors[f"api_{api_url}"] = str(api_error)
            
            if video_url:
                # Download the video
                video_filename = f"instagram_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                output_path = os.path.join(download_dir, video_filename)
                
                video_response = requests.get(video_url, headers=api_headers, stream=True, timeout=30)
                
                if video_response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in video_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # Verify file size
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                        return send_file(
                            output_path,
                            as_attachment=True,
                            download_name=video_filename,
                            mimetype='video/mp4'
                        )
                else:
                    errors["api_video_download"] = f"Video response status code: {video_response.status_code}"
            else:
                errors["instagram_api"] = "No video URL found in API responses"
        except Exception as api_error:
            errors["instagram_api"] = str(api_error)
            logging.error(f"Error using Instagram API method: {str(api_error)}")
        
        # If we reached this point, all methods failed
        # Try one last desperate attempt with a direct ffmpeg download
        tried_methods.append("ffmpeg")
        try:
            # Check if ffmpeg is installed
            try:
                if os.name == 'nt':  # Windows
                    ffmpeg_cmd = ['where', 'ffmpeg']
                else:  # Unix/Linux/Mac
                    ffmpeg_cmd = ['which', 'ffmpeg']
                    
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                ffmpeg_exists = result.returncode == 0
                
                if ffmpeg_exists:
                    video_url = f"https://www.instagram.com/p/{video_id}/"
                    if 'reel' in url.lower():
                        video_url = f"https://www.instagram.com/reel/{video_id}/"
                    
                    video_filename = f"instagram_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = os.path.join(download_dir, video_filename)
                    
                    user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 213.0.0.22.120'
                    
                    # Try to use ffmpeg to download directly
                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-user_agent', user_agent,
                        '-headers', 'Referer: https://www.instagram.com/\r\n',
                        '-i', video_url,
                        '-c', 'copy',
                        output_path
                    ]
                    
                    subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
                    
                    # Check if file was created
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                        return send_file(
                            output_path,
                            as_attachment=True,
                            download_name=video_filename,
                            mimetype='video/mp4'
                        )
                    else:
                        errors["ffmpeg"] = "ffmpeg failed to create a valid video file"
                else:
                    errors["ffmpeg"] = "ffmpeg not found on the system"
            except Exception as ffmpeg_error:
                errors["ffmpeg"] = str(ffmpeg_error)
                logging.error(f"Error using ffmpeg method: {str(ffmpeg_error)}")
        except Exception as e:
            errors["ffmpeg"] = str(e)
            logging.error(f"Failed to use ffmpeg: {str(e)}")
        
        # If all methods fail, return a detailed error
        return jsonify({
            "error": "All download methods failed for this Instagram URL",
            "video_id": video_id,
            "url": url,
            "methods_tried": tried_methods,
            "errors": errors,
            "next_steps": [
                "Try using the /api/debug-instagram endpoint for more details",
                "Upload Instagram cookies using /api/upload-cookies",
                "Set Instagram credentials using /api/set-credentials",
                "Try a different URL format (post URL instead of reel or vice versa)",
                "The content may be private and require authentication"
            ]
        }), 400
            
    except Exception as e:
        return jsonify({
            "error": f"Error: {str(e)}",
            "stack_trace": traceback.format_exc()
        }), 500

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
        # Determine platform
        platform = get_platform_from_url(url)
        if not platform:
            return jsonify({"error": "Unsupported platform"}), 400
            
        # Ensure download directory exists
        download_dir = DOWNLOAD_DIRS.get(platform)
        os.makedirs(download_dir, exist_ok=True)
        
        # Create temporary directory with unique name for processing
        temp_dir = tempfile.mkdtemp(prefix='ytdlp_')
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({"error": "yt-dlp is not found. Please install it first."}), 500
            
        # Set up cookie parameters
        cookie_params = []
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
            
            # Move to platform-specific directory
            final_filename = f"{platform}_{uuid.uuid4().hex[:8]}_{os.path.basename(video_path)}"
            final_path = os.path.join(download_dir, final_filename)
            shutil.move(video_path, final_path)
            
            # Get video size
            video_size = os.path.getsize(final_path)
            
            return jsonify({
                "success": True,
                "video_info": {
                    "filename": os.path.basename(final_path),
                    "size_bytes": video_size,
                    "size_mb": round(video_size / (1024 * 1024), 2),
                    "local_path": final_path,
                    "caption": video_info.get('description', ''),
                    "owner": video_info.get('uploader', ''),
                    "platform": platform_info['name'],
                    "title": video_info.get('title', ''),
                    "download_url": f"/download?path={final_path}"
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
                
                # Move to platform-specific directory
                final_filename = f"{platform}_{uuid.uuid4().hex[:8]}_{os.path.basename(video_path)}"
                final_path = os.path.join(download_dir, final_filename)
                shutil.move(video_path, final_path)
                
                # Get video size
                video_size = os.path.getsize(final_path)
                
                return jsonify({
                    "success": True,
                    "video_info": {
                        "filename": os.path.basename(final_path),
                        "size_bytes": video_size,
                        "size_mb": round(video_size / (1024 * 1024), 2),
                        "local_path": final_path,
                        "platform": platform_info['name'],
                        "title": os.path.basename(final_path).split('.')[0],
                        "download_url": f"/download?path={final_path}"
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
        
        # Check for cookies and credentials
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

@app.route('/api/debug-ytdlp')
def debug_ytdlp():
    """Endpoint for debugging yt-dlp status"""
    try:
        # Get system information
        system_info = {
            "os": os.name,
            "platform": sys.platform,
            "python_version": sys.version,
            "executable": sys.executable,
            "cwd": os.getcwd(),
            "env_vars": {k: v for k, v in os.environ.items() if k in ['PATH', 'PYTHONPATH', 'HOME', 'USER', 'VIRTUAL_ENV']}
        }
        
        # Check for yt-dlp
        ytdlp_info = {}
        ytdlp_path = find_ytdlp_path()
        ytdlp_info["path"] = ytdlp_path
        
        if ytdlp_path:
            try:
                # Check version
                version_cmd = [ytdlp_path, '--version']
                version_result = subprocess.run(version_cmd, capture_output=True, text=True, timeout=5)
                ytdlp_info["version"] = version_result.stdout.strip() if version_result.returncode == 0 else None
                ytdlp_info["version_error"] = version_result.stderr if version_result.returncode != 0 else None
                ytdlp_info["working"] = version_result.returncode == 0
                
                # Check help
                help_cmd = [ytdlp_path, '--help']
                help_result = subprocess.run(help_cmd, capture_output=True, text=True, timeout=5)
                ytdlp_info["help_working"] = help_result.returncode == 0
                
                # Try to run a simple info command
                test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # A popular video that should always work
                test_cmd = [ytdlp_path, '--dump-json', '--no-download', '--no-warnings', '--ignore-errors', test_url]
                test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=15)
                ytdlp_info["test_result"] = "success" if test_result.returncode == 0 else "failure"
                ytdlp_info["test_error"] = test_result.stderr if test_result.stderr else None
                
            except Exception as e:
                ytdlp_info["error"] = str(e)
                ytdlp_info["working"] = False
        else:
            ytdlp_info["working"] = False
            ytdlp_info["error"] = "yt-dlp not found"
            
        # Check for cookies and credentials
        cookies_info = {}
        credentials_info = {}
        
        for platform in SUPPORTED_PLATFORMS:
            cookies_path = os.path.join(COOKIE_DIR, f"{platform}_cookies.txt")
            cookies_info[platform] = {
                "exists": os.path.exists(cookies_path),
                "size": os.path.getsize(cookies_path) if os.path.exists(cookies_path) else 0,
                "readable": os.access(cookies_path, os.R_OK) if os.path.exists(cookies_path) else False
            }
            
            creds = get_credentials(platform)
            credentials_info[platform] = {
                "exists": creds is not None,
                "has_username": creds is not None and "username" in creds,
                "has_password": creds is not None and "password" in creds
            }
        
        # Collect directory information
        dir_info = {
            "cookie_dir": {
                "path": COOKIE_DIR,
                "exists": os.path.exists(COOKIE_DIR),
                "writable": os.access(COOKIE_DIR, os.W_OK) if os.path.exists(COOKIE_DIR) else False,
                "contents": os.listdir(COOKIE_DIR) if os.path.exists(COOKIE_DIR) else []
            },
            "current_dir": {
                "path": os.getcwd(),
                "writable": os.access(os.getcwd(), os.W_OK),
                "contents": os.listdir(os.getcwd())[:20]  # Limit to first 20 items
            }
        }
        
        # Try to create a test file
        file_test = {}
        test_file_path = os.path.join(tempfile.gettempdir(), f"ytdlp_test_{uuid.uuid4()}.txt")
        try:
            with open(test_file_path, 'w') as f:
                f.write("test")
            file_test["write_success"] = True
            os.remove(test_file_path)
            file_test["remove_success"] = True
        except Exception as e:
            file_test["error"] = str(e)
            file_test["write_success"] = False
        
        return jsonify({
            "system": system_info,
            "yt_dlp": ytdlp_info,
            "cookies": cookies_info,
            "credentials": credentials_info,
            "directories": dir_info,
            "file_test": file_test,
            "timestamp": str(uuid.uuid4())
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": str(sys.exc_info())
        }), 500

@app.route('/api/debug-instagram')
def debug_instagram():
    """Debug endpoint for Instagram video extraction"""
    try:
        url = request.args.get('url')
        
        if not url:
            return jsonify({"error": "URL parameter is required"}), 400
            
        # Validate URL
        if not is_supported_url(url) or 'instagram' not in url.lower():
            return jsonify({"error": "Not a valid Instagram URL"}), 400
            
        # Extract video ID
        video_id = None
        match = re.search(r'instagram\.com/(?:p|reel)/([^/?]+)', url)
        if match:
            video_id = match.group(1)
        
        if not video_id:
            return jsonify({"error": "Could not extract video ID from URL"}), 400
            
        # Create a temporary directory for debug files
        temp_dir = tempfile.mkdtemp(prefix='insta_debug_')
        
        # Use browser-like headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Google Chrome";v="135", "Chromium";v="135", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        
        # Try different URL formats for Instagram
        instagram_urls = [
            url,
            f"https://www.instagram.com/reel/{video_id}/",
            f"https://www.instagram.com/p/{video_id}/"
        ]
        
        results = []
        
        import requests
        for test_url in instagram_urls:
            result = {"url": test_url}
            
            try:
                response = requests.get(test_url, headers=headers, timeout=15)
                result["status_code"] = response.status_code
                
                if response.status_code == 200:
                    html_content = response.text
                    result["html_length"] = len(html_content)
                    
                    # Save HTML content
                    debug_file = os.path.join(temp_dir, f"{video_id}_{len(results)}.html")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    result["debug_file"] = debug_file
                    
                    # Look for video patterns
                    video_patterns = [
                        r'(https://scontent[^"\']+\.mp4[^"\']*)',
                        r'(https://instagram\.[\w\.]+/v/[^"\']+)',
                        r'(https://[\w-]+\.cdninstagram\.com/v/[^"\']+\.mp4[^"\']*)',
                        r'video_url":"([^"]+)"',
                        r'"video_url":"([^"]+)"',
                        r'<meta property="og:video" content="([^"]+)"',
                        r'<meta property="og:video:secure_url" content="([^"]+)"',
                        r'<source src="([^"]+)" type="video/mp4"',
                        r'"contentUrl"\s*:\s*"([^"]+)"',
                        r'"playbackVideoUrl":"([^"]+)"',
                    ]
                    
                    pattern_matches = {}
                    for pattern in video_patterns:
                        matches = re.findall(pattern, html_content)
                        if matches:
                            pattern_matches[pattern] = [
                                match.replace('\\u0026', '&').replace('\\/', '/') 
                                for match in matches[:3]  # Limit to first 3 matches
                            ]
                    
                    result["pattern_matches"] = pattern_matches
                    
                    # Look for JSON data
                    json_data_matches = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html_content, re.DOTALL)
                    result["json_blocks_found"] = len(json_data_matches)
                    
                    # Extract some sample JSON data (limited size)
                    if json_data_matches:
                        json_samples = []
                        for i, json_text in enumerate(json_data_matches[:2]):  # Only first 2 blocks
                            try:
                                # Save JSON to a file
                                json_file = os.path.join(temp_dir, f"{video_id}_json_{i}.json")
                                with open(json_file, 'w', encoding='utf-8') as f:
                                    f.write(json_text[:10000])  # Limit size
                                json_samples.append({"file": json_file, "size": len(json_text)})
                            except:
                                continue
                        result["json_samples"] = json_samples
                
                else:
                    result["error"] = f"Non-200 status code: {response.status_code}"
                    
            except Exception as e:
                result["error"] = str(e)
            
            results.append(result)
        
        # Check for yt-dlp availability
        ytdlp_status = {}
        ytdlp_path = find_ytdlp_path()
        ytdlp_status["path"] = ytdlp_path
        
        try:
            # Try basic yt-dlp command for this URL
            cmd = [ytdlp_path, '--dump-json', '--no-download', '--no-warnings', url]
            ytdlp_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            ytdlp_status["return_code"] = ytdlp_result.returncode
            ytdlp_status["stderr"] = ytdlp_result.stderr
            
            if ytdlp_result.returncode == 0:
                try:
                    ytdlp_data = json.loads(ytdlp_result.stdout)
                    if 'url' in ytdlp_data:
                        ytdlp_status["found_url"] = True
                        # Don't include the actual URL in the response for security
                except:
                    ytdlp_status["json_parse_error"] = True
        except Exception as e:
            ytdlp_status["error"] = str(e)
        
        return jsonify({
            "video_id": video_id,
            "urls_tested": len(results),
            "results": results,
            "ytdlp_status": ytdlp_status,
            "debug_dir": temp_dir
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def find_ytdlp_path():
    """Find the path to yt-dlp executable"""
    ytdlp_path = None
    
    try:
        # Try to use where/which command first
        if os.name == 'nt':  # Windows
            try:
                result = subprocess.run(['where', 'yt-dlp'], capture_output=True, text=True, check=True)
                paths = result.stdout.strip().split('\n')
                if paths:
                    ytdlp_path = paths[0]
            except subprocess.CalledProcessError:
                # Try to find in Windows typical locations
                possible_paths = [
                    os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'yt-dlp', 'yt-dlp.exe'),
                    os.path.join(os.environ.get('LOCALAPPDATA', r'C:\Users\User\AppData\Local'), 'Programs', 'yt-dlp', 'yt-dlp.exe'),
                    os.path.join(os.path.dirname(sys.executable), 'Scripts', 'yt-dlp.exe')
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        ytdlp_path = path
                        break
        else:  # Linux/Mac
            try:
                result = subprocess.run(['which', 'yt-dlp'], capture_output=True, text=True, check=True)
                ytdlp_path = result.stdout.strip()
            except subprocess.CalledProcessError:
                # Try common Unix paths
                possible_paths = [
                    '/usr/bin/yt-dlp',
                    '/usr/local/bin/yt-dlp',
                    '/opt/homebrew/bin/yt-dlp',
                    os.path.join(os.path.expanduser('~'), '.local', 'bin', 'yt-dlp')
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        ytdlp_path = path
                        break
    except Exception:
        pass
    
    if not ytdlp_path:
        # Python executable path
        python_dir = os.path.dirname(sys.executable)
        
        # List of possible paths
        possible_paths = [
            os.path.join(python_dir, 'Scripts', 'yt-dlp.exe'),  # Windows
            os.path.join(python_dir, 'bin', 'yt-dlp'),          # Linux/Mac
            'yt-dlp',                                            # System path
            'yt-dlp.exe'                                         # Windows system path
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, '--version'], capture_output=True, check=True)
                ytdlp_path = path
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    
    # Return 'yt-dlp' as fallback if not found - let the system try to resolve it
    return ytdlp_path or 'yt-dlp'

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

@app.route('/api')
def api_documentation():
    """API documentation endpoint"""
    api_docs = {
        "api_version": "1.0",
        "name": "Social Media Video Downloader API",
        "description": "API for downloading videos from Instagram, YouTube, and TikTok",
        "endpoints": {
            "/api/download": {
                "method": "POST",
                "description": "Download a video using yt-dlp",
                "parameters": {
                    "url": "The URL of the video to download (required)"
                }
            },
            "/api/instant-download": {
                "method": "GET",
                "description": "Instantly download a video using yt-dlp",
                "parameters": {
                    "url": "The URL of the video to download (required)"
                }
            },
            "/api/instagram-download": {
                "method": "GET",
                "description": "Download an Instagram video using custom extraction",
                "parameters": {
                    "url": "The Instagram URL to download from (required)"
                }
            },
            "/api/instagram-download-robust": {
                "method": "GET",
                "description": "Download an Instagram video using multiple fallback methods",
                "parameters": {
                    "url": "The Instagram URL to download from (required)"
                }
            },
            "/api/debug-instagram": {
                "method": "GET",
                "description": "Debug Instagram URL extraction",
                "parameters": {
                    "url": "The Instagram URL to debug (required)"
                }
            },
            "/api/debug-ytdlp": {
                "method": "GET",
                "description": "Debug yt-dlp installation and status"
            },
            "/api/test-ytdlp": {
                "method": "GET",
                "description": "Test if yt-dlp is working correctly"
            },
            "/api/set-credentials": {
                "method": "POST",
                "description": "Save platform credentials",
                "parameters": {
                    "platform": "Platform name (instagram, youtube, tiktok) (required)",
                    "username": "Username for the platform (required)",
                    "password": "Password for the platform (required)"
                }
            },
            "/api/upload-cookies": {
                "method": "POST",
                "description": "Upload cookies file for a platform",
                "parameters": {
                    "platform": "Platform name (instagram, youtube, tiktok) (required)",
                    "cookie_file": "Cookie file in Netscape format (required)"
                },
                "note": "This endpoint requires a multipart/form-data request"
            }
        },
        "usage_examples": {
            "curl": "curl -X POST -H \"Content-Type: application/json\" -d '{\"url\":\"https://www.instagram.com/reel/ABC123/\"}' http://localhost:5000/api/download",
            "python": "import requests\n\nresponse = requests.post('http://localhost:5000/api/download', json={'url': 'https://www.instagram.com/reel/ABC123/'})\nprint(response.json())"
        }
    }
    return jsonify(api_docs)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create cookies directory if it doesn't exist
    os.makedirs(COOKIE_DIR, exist_ok=True)
    
    # Create platform-specific download directories
    for platform, directory in DOWNLOAD_DIRS.items():
        os.makedirs(directory, exist_ok=True)
        print(f"Created download directory for {platform}: {directory}")
    
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
            # Try to install yt-dlp automatically
            try:
                print("Attempting to install yt-dlp...")
                subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'], check=True)
                print("yt-dlp installation completed. Please restart the application.")
            except Exception as install_error:
                print(f"Error installing yt-dlp: {install_error}")
                print("Please install yt-dlp manually with: pip install yt-dlp")
    
    # Print supported platforms
    print(f"Supported platforms: {', '.join(SUPPORTED_PLATFORMS.keys())}")
    
    # Enable logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    print("Starting the Video Downloader web application...")
    # Use debug mode but catch more errors
    try:
        app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
    except Exception as e:
        print(f"Error starting the application: {e}")
        print("Trying to start in production mode...")
        app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 

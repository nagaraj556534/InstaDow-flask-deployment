from flask import Flask, request, jsonify, render_template, send_file, abort
import os
import tempfile
import re
import subprocess
import json
import sys
import uuid
import time
import random
from functools import wraps
import signal
from contextlib import contextmanager

app = Flask(__name__)

# Constants
COOKIE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies')
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')

# Simple cache implementation
class SimpleCache:
    def __init__(self, cache_dir, expiry_time=3600):
        self.cache_dir = cache_dir
        self.expiry_time = expiry_time
        os.makedirs(cache_dir, exist_ok=True)
    
    def get(self, key):
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            # Check if cache is expired
            if time.time() - os.path.getmtime(cache_file) < self.expiry_time:
                try:
                    with open(cache_file, 'r') as f:
                        return json.load(f)
                except:
                    return None
        return None
    
    def set(self, key, value):
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(cache_file, 'w') as f:
                json.dump(value, f)
            return True
        except:
            return False

# Initialize cache
cache = SimpleCache(CACHE_DIR)

# Cache decorator
def cached(expiry=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments
            key = f"{func.__name__}_{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result:
                return cached_result
            
            # If not in cache, call the function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(key, result)
            
            return result
        return wrapper
    return decorator

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
    
    # Validate URL - Updated to include all supported platforms
    if not re.match(r'https?://(www\.)?(instagram\.com|youtube\.com|youtu\.be|facebook\.com|fb\.watch|tiktok\.com|twitter\.com|x\.com)/.*', url):
        return jsonify({"error": "Invalid URL. This tool supports Instagram, YouTube, Facebook, TikTok, and Twitter only."}), 400
    
    return download_with_ytdlp(url)

@app.route('/api/download-with-smd', methods=['POST'])
def download_with_smd():
    """Download video using Social-Media-Downloader instead of yt-dlp directly"""
    try:
        data = request.json
        
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        url = data['url']
        
        # Validate URL - Same as our existing validation
        if not re.match(r'https?://(www\.)?(instagram\.com|youtube\.com|youtu\.be|facebook\.com|fb\.watch|tiktok\.com|twitter\.com|x\.com)/.*', url):
            return jsonify({"error": "Invalid URL. This tool supports Instagram, YouTube, Facebook, TikTok, and Twitter only."}), 400
        
        # Import SMD here to avoid affecting startup if it's not installed
        try:
            from smd.core.downloader_engine import Downloader
            from smd.utils.url_utils import URLUtils
        except ImportError:
            return jsonify({
                "error": "Social-Media-Downloader not installed",
                "solution": "Run 'pip install social-media-downloader' to enable this feature"
            }), 500
        
        # Create temporary directory for download
        temp_dir = tempfile.mkdtemp(prefix='smd_')
        
        # Detect platform from URL
        if "instagram" in url.lower():
            platform = "Instagram"
        elif "youtube" in url.lower() or "youtu.be" in url.lower():
            platform = "YouTube"
        elif "facebook" in url.lower() or "fb.watch" in url.lower():
            platform = "Facebook"
        elif "tiktok" in url.lower():
            platform = "TikTok"
        elif "twitter" in url.lower() or "x.com" in url.lower():
            platform = "Twitter"
        else:
            platform = "Unknown"
        
        # Configure Social-Media-Downloader
        config = {
            "download_path": temp_dir,
            "format": "best",  # Choose best quality
            "quiet": True
        }
        
        # Initialize downloader
        downloader = Downloader(config)
        
        # Check cache first
        cache_key = f"smd_download_{hash(url)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        # Download the video
        try:
            url_utils = URLUtils()
            platform_name = url_utils.detect_platform(url)
            
            if not platform_name:
                return jsonify({"error": "Unsupported platform or invalid URL"}), 400
            
            print(f"Downloading video from {platform_name}...")
            result = downloader.download_video(url)
            
            if not result or not result.get("success"):
                return jsonify({
                    "error": f"Failed to download video: {result.get('error', 'Unknown error')}",
                    "solution": "Try using the regular downloader or update SMD"
                }), 500
            
            # Get downloaded file path from result
            file_path = result.get("file_path")
            if not file_path or not os.path.exists(file_path):
                return jsonify({"error": "Could not find downloaded file"}), 500
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Prepare response
            response = {
                "success": True,
                "video_info": {
                    "filename": os.path.basename(file_path),
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "local_path": file_path,
                    "platform": platform,
                    "title": result.get("title", os.path.basename(file_path))
                }
            }
            
            # Cache the successful result
            cache.set(cache_key, response)
            
            return jsonify(response)
            
        except Exception as e:
            # Log the specific exception
            print(f"SMD download error: {str(e)}")
            
            return jsonify({
                "error": f"Error using Social-Media-Downloader: {str(e)}",
                "solution": "Try using the regular downloader or update SMD"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500

# Timeout handler for subprocess calls
class TimeoutError(Exception):
    pass

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutError("Timed out")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def download_with_ytdlp(url):
    """Download video using yt-dlp with cookie support and exponential backoff"""
    try:
        # Check if we have a cached result for this URL
        cache_key = f"download_{hash(url)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
            
        # Create temporary directory with unique name
        temp_dir = tempfile.mkdtemp(prefix='ytdlp_')
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({"error": "yt-dlp is not found. Please install it first."}), 500
            
        # Determine platform and set up cookie parameters
        cookie_params = []
        
        # Detect platform from URL
        if "instagram" in url.lower():
            platform = "Instagram"
        elif "youtube" in url.lower() or "youtu.be" in url.lower():
            platform = "YouTube"
        elif "facebook" in url.lower() or "fb.watch" in url.lower():
            platform = "Facebook"
        elif "tiktok" in url.lower():
            platform = "TikTok"
        elif "twitter" in url.lower() or "x.com" in url.lower():
            platform = "Twitter"
        else:
            platform = "Unknown"
        
        # Ensure cookie directory exists
        os.makedirs(COOKIE_DIR, exist_ok=True)
        
        # Set up cookies based on platform
        cookie_path = os.path.join(COOKIE_DIR, f"{platform.lower()}_cookies.txt")
        if os.path.exists(cookie_path):
            cookie_params = ['--cookies', cookie_path]
        
        # Add extra parameters to help avoid bot detection and rate limiting
        extra_params = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            '--add-header', 'Accept-Language:en-US,en;q=0.9',
            '--no-check-certificates',
            '--extractor-retries', '3',
            '--socket-timeout', '15',
            '--sleep-interval', '2',
            '--max-sleep-interval', '5',
            '--sleep-subtitles', '1',
            '--retries', '3',
            '--fragment-retries', '3',
            '--file-access-retries', '3',
            '--concurrent-fragments', '1'
        ]
        
        # For YouTube, use format selection to speed up downloads
        if platform == "YouTube":
            # Prefer lower quality to avoid timeouts
            extra_params.extend([
                '-f', 'best[height<=480]/best',
                '--no-playlist',
                '--no-check-formats'
            ])
        
        # Add proxy if available
        proxy_file = os.path.join(COOKIE_DIR, 'proxy.txt')
        if os.path.exists(proxy_file):
            with open(proxy_file, 'r') as f:
                proxy_url = f.read().strip()
                if proxy_url:
                    extra_params.extend(['--proxy', proxy_url])
        
        # Implement exponential backoff for YouTube
        max_retries = 3  # Reduced from 5 to 3
        retry_count = 0
        video_info = None
        
        while retry_count < max_retries:
            try:
                # Add a delay before making requests to YouTube to avoid rate limiting
                if platform == "YouTube":
                    # Shorter backoff times: 1, 2, 4 seconds
                    backoff_time = (2 ** retry_count) / 2 if retry_count > 0 else 1
                    time.sleep(backoff_time)
                    
                # Get video info first with a timeout
                info_cmd = [ytdlp_path, '--dump-json'] + cookie_params + extra_params + [url]
                
                try:
                    # Use timeout to prevent hanging
                    process = subprocess.Popen(
                        info_cmd, 
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # Wait for process with timeout (20 seconds)
                    stdout, stderr = process.communicate(timeout=20)
                    
                    if process.returncode != 0:
                        raise subprocess.CalledProcessError(
                            process.returncode, 
                            info_cmd, 
                            output=stdout, 
                            stderr=stderr
                        )
                    
                    video_info = json.loads(stdout)
                    
                except subprocess.TimeoutExpired:
                    process.kill()
                    raise TimeoutError("yt-dlp process timed out")
                
                # Success! Break out of retry loop
                break
                
            except (subprocess.CalledProcessError, TimeoutError) as e:
                error_output = ""
                if isinstance(e, subprocess.CalledProcessError):
                    error_output = e.stderr if hasattr(e, 'stderr') else str(e)
                else:
                    error_output = "Process timed out"
                
                # If it's a rate limiting error and we haven't reached max retries
                if ("Too Many Requests" in error_output or "429" in error_output) and retry_count < max_retries - 1:
                    retry_count += 1
                    # Log the retry attempt
                    print(f"Rate limited by YouTube. Retry {retry_count}/{max_retries} after {(2**retry_count)/2} seconds")
                    continue
                else:
                    # Either not a rate limit error or we've reached max retries
                    if "Sign in to confirm you're not a bot" in error_output or "Too Many Requests" in error_output:
                        return jsonify({
                            "error": f"{platform} requires authentication to verify you're not a bot or is rate limiting requests",
                            "solution": f"1. Upload {platform} cookies from a logged-in browser session\n2. Wait a few minutes before trying again\n3. Try using a VPN or proxy",
                            "has_cookies": os.path.exists(cookie_path),
                            "retry_after": 60  # Suggest waiting 1 minute
                        }), 429
                    elif "login required" in error_output or "Requested content is not available" in error_output:
                        return jsonify({
                            "error": f"{platform} login required",
                            "solution": f"Upload {platform} cookies from a logged-in browser session",
                            "has_cookies": os.path.exists(cookie_path)
                        }), 403
                    elif "timed out" in error_output.lower():
                        return jsonify({
                            "error": f"The request to {platform} timed out",
                            "solution": "Try again later when the service is less busy"
                        }), 504
                    else:
                        return jsonify({"error": f"yt-dlp error: {error_output}"}), 500
        
        # If we couldn't get video info after all retries
        if not video_info:
            return jsonify({
                "error": f"Failed to get video info after {max_retries} attempts",
                "solution": "Please try again later or use a different URL"
            }), 429
        
        # For YouTube videos, we'll return just the info without downloading to avoid timeouts
        if platform == "YouTube":
            # Prepare response with just the video info and direct URL if available
            video_url = None
            if 'url' in video_info:
                video_url = video_info['url']
            elif 'formats' in video_info and len(video_info['formats']) > 0:
                # Find a medium quality format
                formats = sorted(video_info['formats'], 
                                key=lambda x: x.get('height', 0) if x.get('height', 0) <= 720 else 0, 
                                reverse=True)
                if formats:
                    video_url = formats[0].get('url')
            
            if not video_url:
                return jsonify({
                    "error": "Could not extract direct video URL",
                    "solution": "Try downloading with cookies or a proxy"
                }), 500
            
            response = {
                "success": True,
                "video_info": {
                    "filename": f"{video_info.get('title', 'video')}.mp4",
                    "direct_url": video_url,
                    "size_mb": "unknown",  # We don't download so size is unknown
                    "caption": video_info.get('description', ''),
                    "owner": video_info.get('uploader', ''),
                    "platform": platform,
                    "title": video_info.get('title', '')
                }
            }
            
            # Cache the successful result
            cache.set(cache_key, response)
            
            return jsonify(response)
        
        # For non-YouTube platforms, continue with download
        # Reset retry counter for download
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Download the video with timeout
                download_cmd = [ytdlp_path, '-o', output_template] + cookie_params + extra_params + [url]
                
                try:
                    # Use timeout to prevent hanging
                    process = subprocess.Popen(
                        download_cmd, 
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # Wait for process with timeout (45 seconds)
                    stdout, stderr = process.communicate(timeout=45)
                    
                    if process.returncode != 0:
                        raise subprocess.CalledProcessError(
                            process.returncode, 
                            download_cmd, 
                            output=stdout, 
                            stderr=stderr
                        )
                    
                except subprocess.TimeoutExpired:
                    process.kill()
                    raise TimeoutError("yt-dlp download process timed out")
                
                # Success! Break out of retry loop
                break
                
            except (subprocess.CalledProcessError, TimeoutError) as e:
                error_output = ""
                if isinstance(e, subprocess.CalledProcessError):
                    error_output = e.stderr if hasattr(e, 'stderr') else str(e)
                else:
                    error_output = "Process timed out"
                
                # If it's a rate limiting error and we haven't reached max retries
                if ("Too Many Requests" in error_output or "429" in error_output) and retry_count < max_retries - 1:
                    retry_count += 1
                    continue
                else:
                    # Either not a rate limit error or we've reached max retries
                    return jsonify({"error": f"yt-dlp download error: {error_output}"}), 500
        
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
        
        # Prepare response
        response = {
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
        }
        
        # Cache the successful result
        cache.set(cache_key, response)
        
        return jsonify(response)
                
    except Exception as e:
        return jsonify({"error": f"Error using yt-dlp: {str(e)}"}), 500

@app.route('/api/get-info', methods=['POST'])
@cached(expiry=1800)  # Cache for 30 minutes
def get_info():
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data['url']
    
    # Validate URL - Updated to include all supported platforms
    if not re.match(r'https?://(www\.)?(instagram\.com|youtube\.com|youtu\.be|facebook\.com|fb\.watch|tiktok\.com|twitter\.com|x\.com)/.*', url):
        return jsonify({"error": "Invalid URL. This tool supports Instagram, YouTube, Facebook, TikTok, and Twitter only."}), 400
    
    try:
        # Find yt-dlp executable path
        ytdlp_path = find_ytdlp_path()
        
        if not ytdlp_path:
            return jsonify({"error": "yt-dlp is not found. Please install it first."}), 500
        
        # Determine platform and set up cookie parameters
        cookie_params = []
        
        # Detect platform from URL
        if "instagram" in url.lower():
            platform = "Instagram"
        elif "youtube" in url.lower() or "youtu.be" in url.lower():
            platform = "YouTube"
        elif "facebook" in url.lower() or "fb.watch" in url.lower():
            platform = "Facebook"
        elif "tiktok" in url.lower():
            platform = "TikTok"
        elif "twitter" in url.lower() or "x.com" in url.lower():
            platform = "Twitter"
        else:
            platform = "Unknown"
        
        # Set up cookies based on platform
        cookie_path = os.path.join(COOKIE_DIR, f"{platform.lower()}_cookies.txt")
        if os.path.exists(cookie_path):
            cookie_params = ['--cookies', cookie_path]
        
        # Add extra parameters to help avoid bot detection
        extra_params = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            '--add-header', 'Accept-Language:en-US,en;q=0.9',
            '--no-check-certificates',
            '--extractor-retries', '5',
            '--socket-timeout', '30',
            '--sleep-interval', '5',
            '--max-sleep-interval', '10',
            '--sleep-subtitles', '3'
        ]
        
        # Add proxy if available
        proxy_file = os.path.join(COOKIE_DIR, 'proxy.txt')
        if os.path.exists(proxy_file):
            with open(proxy_file, 'r') as f:
                proxy_url = f.read().strip()
                if proxy_url:
                    extra_params.extend(['--proxy', proxy_url])
        
        # Implement exponential backoff for YouTube
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Add a delay before making requests to YouTube to avoid rate limiting
                if platform == "YouTube":
                    # Exponential backoff: 2^retry_count seconds (1, 2, 4, 8, 16)
                    backoff_time = 2 ** retry_count if retry_count > 0 else 2
                    time.sleep(backoff_time)
                
                # Get video info
                info_cmd = [ytdlp_path, '--dump-json'] + cookie_params + extra_params + [url]
                result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
                video_info = json.loads(result.stdout)
                
                # Success! Break out of retry loop
                break
                
            except subprocess.CalledProcessError as e:
                error_output = e.stderr if e.stderr else str(e)
                
                # If it's a rate limiting error and we haven't reached max retries
                if ("Too Many Requests" in error_output or "429" in error_output) and retry_count < max_retries - 1:
                    retry_count += 1
                    # Log the retry attempt
                    print(f"Rate limited by YouTube. Retry {retry_count}/{max_retries} after {2**retry_count} seconds")
                    continue
                else:
                    # Either not a rate limit error or we've reached max retries
                    if "Sign in to confirm you're not a bot" in error_output or "Too Many Requests" in error_output:
                        return jsonify({
                            "error": f"{platform} requires authentication to verify you're not a bot or is rate limiting requests",
                            "solution": f"1. Upload {platform} cookies from a logged-in browser session\n2. Wait a few minutes before trying again\n3. Try using a VPN or proxy",
                            "has_cookies": os.path.exists(cookie_path),
                            "retry_after": 60  # Suggest waiting 1 minute
                        }), 429
                    elif "login required" in error_output or "Requested content is not available" in error_output:
                        return jsonify({
                            "error": f"{platform} login required",
                            "solution": f"Upload {platform} cookies from a logged-in browser session",
                            "has_cookies": os.path.exists(cookie_path)
                        }), 403
                    else:
                        return jsonify({"error": f"yt-dlp error: {error_output}"}), 500
        
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
    if platform not in ['youtube', 'instagram', 'facebook', 'tiktok', 'twitter']:
        return jsonify({"error": "Invalid platform. Must be 'youtube', 'instagram', 'facebook', 'tiktok', or 'twitter'"}), 400
    
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

@app.route('/api/upload-proxy', methods=['POST'])
def upload_proxy():
    """Endpoint to upload proxy configuration"""
    data = request.json
    
    if not data or 'proxy_url' not in data:
        return jsonify({"error": "No proxy URL provided"}), 400
    
    proxy_url = data['proxy_url']
    if not proxy_url:
        return jsonify({"error": "Empty proxy URL"}), 400
    
    try:
        # Ensure cookie directory exists
        os.makedirs(COOKIE_DIR, exist_ok=True)
        
        # Save the proxy URL to a file
        proxy_file = os.path.join(COOKIE_DIR, 'proxy.txt')
        with open(proxy_file, 'w') as f:
            f.write(proxy_url)
        
        return jsonify({
            "success": True,
            "message": "Proxy configuration saved successfully"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to save proxy configuration: {str(e)}"}), 500

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
        
        # Check if cookie files exist for all platforms
        platforms = ['youtube', 'instagram', 'facebook', 'tiktok', 'twitter']
        cookies_status = {}
        
        for platform in platforms:
            cookies_status[platform] = os.path.exists(os.path.join(COOKIE_DIR, f"{platform}_cookies.txt"))
        
        return jsonify({
            "success": True,
            "yt_dlp_version": version,
            "yt_dlp_path": ytdlp_path,
            "python_version": sys.version,
            "cookies": cookies_status
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error testing yt-dlp: {str(e)}",
            "python_version": sys.version
        }), 500

@app.route('/api/supported-platforms', methods=['GET'])
def supported_platforms():
    """Return a list of supported platforms and their status"""
    platforms = [
        {"name": "YouTube", "id": "youtube", "url_pattern": "youtube.com or youtu.be"},
        {"name": "Instagram", "id": "instagram", "url_pattern": "instagram.com"},
        {"name": "Facebook", "id": "facebook", "url_pattern": "facebook.com or fb.watch"},
        {"name": "TikTok", "id": "tiktok", "url_pattern": "tiktok.com"},
        {"name": "Twitter (X)", "id": "twitter", "url_pattern": "twitter.com or x.com"}
    ]
    
    # Check if cookie files exist for each platform
    for platform in platforms:
        platform_id = platform["id"]
        cookie_path = os.path.join(COOKIE_DIR, f"{platform_id}_cookies.txt")
        platform["has_cookies"] = os.path.exists(cookie_path)
    
    return jsonify({
        "success": True,
        "platforms": platforms
    })

@app.route('/api/clear-cache', methods=['POST', 'GET'])
def clear_cache():
    """Clear the cache to force fresh downloads"""
    try:
        if os.path.exists(CACHE_DIR):
            # Delete all files in cache directory
            for file in os.listdir(CACHE_DIR):
                file_path = os.path.join(CACHE_DIR, file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        
        return jsonify({
            "success": True,
            "message": "Cache cleared successfully"
        })
    except Exception as e:
        return jsonify({
            "error": f"Failed to clear cache: {str(e)}"
        }), 500

@app.route('/api/smart-download', methods=['POST'])
def smart_download():
    """Smart download that tries SMD first, then falls back to yt-dlp if needed"""
    try:
        data = request.json
        
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        url = data['url']
        
        # Validate URL - Same as our existing validation
        if not re.match(r'https?://(www\.)?(instagram\.com|youtube\.com|youtu\.be|facebook\.com|fb\.watch|tiktok\.com|twitter\.com|x\.com)/.*', url):
            return jsonify({"error": "Invalid URL. This tool supports Instagram, YouTube, Facebook, TikTok, and Twitter only."}), 400
        
        # Check if we have a cached result
        cache_key = f"smart_download_{hash(url)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        # STEP 1: Try Social-Media-Downloader first
        try:
            # Import SMD
            from smd.core.downloader_engine import Downloader
            from smd.utils.url_utils import URLUtils
            
            # Create temporary directory for download
            temp_dir = tempfile.mkdtemp(prefix='smd_')
            
            # Configure Social-Media-Downloader
            config = {
                "download_path": temp_dir,
                "format": "best",  # Choose best quality
                "quiet": True
            }
            
            # Initialize downloader
            downloader = Downloader(config)
            
            # Download the video
            url_utils = URLUtils()
            platform_name = url_utils.detect_platform(url)
            
            if not platform_name:
                raise Exception("Unsupported platform or invalid URL")
            
            print(f"Trying SMD first: Downloading video from {platform_name}...")
            result = downloader.download_video(url)
            
            if not result or not result.get("success"):
                raise Exception(f"SMD download failed: {result.get('error', 'Unknown error')}")
            
            # Get downloaded file path from result
            file_path = result.get("file_path")
            if not file_path or not os.path.exists(file_path):
                raise Exception("Could not find downloaded file")
            
            # Detect platform from URL
            if "instagram" in url.lower():
                platform = "Instagram"
            elif "youtube" in url.lower() or "youtu.be" in url.lower():
                platform = "YouTube"
            elif "facebook" in url.lower() or "fb.watch" in url.lower():
                platform = "Facebook"
            elif "tiktok" in url.lower():
                platform = "TikTok"
            elif "twitter" in url.lower() or "x.com" in url.lower():
                platform = "Twitter"
            else:
                platform = "Unknown"
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Prepare response
            response = {
                "success": True,
                "method": "smd",
                "video_info": {
                    "filename": os.path.basename(file_path),
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "local_path": file_path,
                    "platform": platform,
                    "title": result.get("title", os.path.basename(file_path))
                }
            }
            
            # Cache the successful result
            cache.set(cache_key, response)
            
            print("SMD download successful!")
            return jsonify(response)
            
        except Exception as e:
            # Log the SMD error
            print(f"SMD download failed: {str(e)}")
            print("Falling back to yt-dlp...")
            
            # STEP 2: Fall back to yt-dlp if SMD fails
            try:
                # Call our existing yt-dlp implementation
                yt_dlp_response = download_with_ytdlp(url)
                
                # If it's a response object, extract the JSON
                if hasattr(yt_dlp_response, 'json'):
                    yt_dlp_data = yt_dlp_response.json
                    if callable(yt_dlp_data):
                        yt_dlp_data = yt_dlp_data()
                else:
                    yt_dlp_data = yt_dlp_response
                
                # Add method information
                if isinstance(yt_dlp_data, dict) and yt_dlp_data.get('success'):
                    yt_dlp_data['method'] = 'yt-dlp'
                    
                    # Cache the successful result
                    cache.set(cache_key, yt_dlp_data)
                
                return jsonify(yt_dlp_data) if isinstance(yt_dlp_data, dict) else yt_dlp_response
                
            except Exception as yt_dlp_error:
                # Both methods failed
                return jsonify({
                    "error": f"Both download methods failed. SMD error: {str(e)}. yt-dlp error: {str(yt_dlp_error)}",
                    "solution": "Please try again later or use a different URL"
                }), 500
    
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500

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
    
    # Create cookies directory if it doesn't exist
    os.makedirs(COOKIE_DIR, exist_ok=True)
    
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)
    
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
    
    # Check if we're running in a production environment (like Render)
    is_production = os.environ.get('RENDER', False) or os.environ.get('PRODUCTION', False)
    
    print("Starting the Social Media Video Downloader web application...")
    if is_production:
        # In production, let the WSGI server handle the app
        print("Running in production mode")
    else:
        # In development, use Flask's built-in server
        app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 

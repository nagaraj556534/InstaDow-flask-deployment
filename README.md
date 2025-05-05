# YouTube & Instagram Video Downloader

A simple web application that allows you to download videos from YouTube and Instagram using yt-dlp.

## Features

- Download videos from YouTube (including shorts)
- Download videos from Instagram (posts, reels, and stories)
- No login required
- Simple and clean user interface
- Built with Python 3.13 and yt-dlp

## Prerequisites

- Python 3.13 or higher
- pip (Python package manager)

## Installation

1. Clone this repository or download the source code.

2. Navigate to the project directory:
   ```
   cd Instagram
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the web server:
   ```
   python app.py
   ```

2. Open your web browser and go to:
   ```
   http://localhost:5000
   ```

3. Enter the URL of the YouTube or Instagram video you want to download.

4. Click "Get Information" to see details about the video.

5. Click "Download Video" to download the video to your device.

## How It Works

This application uses yt-dlp (https://github.com/yt-dlp/yt-dlp), a powerful command-line tool for downloading videos from various platforms. The web interface makes it easy to use without needing to know command-line operations.

## Troubleshooting

If you encounter any issues:

1. Make sure yt-dlp is installed correctly:
   ```
   yt-dlp --version
   ```

2. If you get a "yt-dlp not found" error, try reinstalling:
   ```
   pip uninstall yt-dlp
   pip install yt-dlp
   ```

3. Check the application logs for more detailed error messages.

## Legal Notice

This tool is for educational purposes only. Please respect the terms of service of all platforms. Do not download copyrighted content without permission.

## License

This project is open source and available under the MIT License. 
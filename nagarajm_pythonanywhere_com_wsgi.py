import sys
import os

# Add your project directory to the path
project_home = '/home/NagarajM/Instagram_BE'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables (if needed)
os.environ['PYTHONPATH'] = project_home

# Specify the correct virtualenv path
virtualenv_path = '/home/NagarajM/Instagram_BE/venv'
try:
    # For Python 3, use this line
    activate_this = os.path.join(virtualenv_path, 'bin/activate_this.py')
    # If using Windows-style paths on PythonAnywhere (unlikely but possible)
    if not os.path.exists(activate_this):
        activate_this = os.path.join(virtualenv_path, 'Scripts/activate_this.py')
        
    if os.path.exists(activate_this):
        with open(activate_this) as file_:
            exec(file_.read(), dict(__file__=activate_this))
    else:
        # If activate_this.py doesn't exist, try adding the site-packages directly
        site_packages = os.path.join(virtualenv_path, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
        if os.path.exists(site_packages):
            sys.path.insert(0, site_packages)
        else:
            print(f"Warning: Could not find site-packages at {site_packages}")
except Exception as e:
    print(f"Virtualenv activation failed: {e}")
    print(f"Tried to activate: {activate_this}")
    # Continue anyway

# Import your Flask app
try:
    from app import app as application
except ModuleNotFoundError as e:
    print(f"Import error: {e}")
    print(f"sys.path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")
    raise

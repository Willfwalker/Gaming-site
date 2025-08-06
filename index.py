from app import app

# Vercel entry point
# This file is used by Vercel to serve the Flask application
# The app is already configured with caching and optimizations in app.py

if __name__ == '__main__':
    # This won't run on Vercel, but useful for local testing
    app.run(debug=False, host='0.0.0.0', port=5000)

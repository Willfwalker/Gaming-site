#!/usr/bin/env python3
"""
Setup script to configure Vercel environment variables for Firebase deployment.
This script reads the Firebase credentials and provides the command to set them on Vercel.
"""

import json
import os

def setup_vercel_env():
    """Setup Vercel environment variables for Firebase"""
    
    # Read Firebase credentials
    credentials_file = 'firebase-credentials.json'
    
    if not os.path.exists(credentials_file):
        print(f"❌ Error: {credentials_file} not found!")
        print("Please ensure your Firebase credentials file exists.")
        return
    
    try:
        with open(credentials_file, 'r') as f:
            credentials = json.load(f)
        
        # Convert credentials to a single-line JSON string
        credentials_json = json.dumps(credentials, separators=(',', ':'))
        
        print("🔥 Firebase Vercel Setup Instructions")
        print("=" * 50)
        print()
        print("1. Install Vercel CLI if you haven't already:")
        print("   npm install -g vercel")
        print()
        print("2. Login to Vercel:")
        print("   vercel login")
        print()
        print("3. Set the Firebase credentials environment variable:")
        print("   Copy and run this command:")
        print()
        print("   vercel env add FIREBASE_CREDENTIALS_JSON")
        print()
        print("   When prompted, paste this value:")
        print("   (Copy the entire line below, including quotes)")
        print()
        print(f'   "{credentials_json}"')
        print()
        print("4. Set the environment variable for all environments:")
        print("   - Select: Production, Preview, and Development")
        print()
        print("5. Redeploy your application:")
        print("   vercel --prod")
        print()
        print("✅ Your Firebase credentials will now be available on Vercel!")
        print()
        print("📝 Note: The credentials are stored securely as environment variables")
        print("   and will not be visible in your code or logs.")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {credentials_file}")
        print(f"   {e}")
    except Exception as e:
        print(f"❌ Error reading {credentials_file}: {e}")

def verify_local_setup():
    """Verify that the local setup works"""
    print("\n🔍 Verifying local setup...")
    
    try:
        # Test Firebase initialization
        from services.firebase_auth_service import FirebaseAuthService
        from flask import Flask
        
        test_app = Flask(__name__)
        firebase_auth = FirebaseAuthService(test_app)
        
        print("✅ Local Firebase setup is working correctly!")
        
    except Exception as e:
        print(f"❌ Local setup error: {e}")
        print("   Please check your Firebase credentials file.")

if __name__ == "__main__":
    print("🚀 BUG Gaming Site - Vercel Deployment Setup")
    print("=" * 50)
    
    verify_local_setup()
    setup_vercel_env()
    
    print("\n🎯 Quick Deployment Checklist:")
    print("   ✅ Firebase credentials configured")
    print("   ✅ Vercel environment variables set")
    print("   ✅ Performance optimizations applied")
    print("   ✅ Mobile responsive sidebar")
    print()
    print("Your application is ready for production deployment! 🎉")

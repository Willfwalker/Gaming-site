import os
import json
import requests
from functools import wraps
from flask import request, jsonify, session, redirect, url_for
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv
import secrets

# Load environment variables
load_dotenv()

# Firebase project information
FIREBASE_CONFIG = {
    'apiKey': os.getenv('FIREBASE_API_KEY'),
    'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN'),
    'projectId': os.getenv('FIREBASE_PROJECT_ID'),
    'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET'),
    'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
    'appId': os.getenv('FIREBASE_APP_ID'),
    'measurementId': os.getenv('FIREBASE_MEASUREMENT_ID')
}

class FirebaseAuthService:
    def __init__(self, app=None):
        self.app = app
        self.firebase_app = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the Firebase Admin SDK with Flask app"""
        self.app = app

        # Initialize Firebase Admin SDK if not already initialized
        if not self.firebase_app and not firebase_admin._apps:
            try:
                # Check if we're in Vercel environment with JSON credentials as env var
                firebase_credentials_json = os.getenv('FIREBASE_CREDENTIALS_JSON')

                if firebase_credentials_json:
                    # Parse the JSON string from environment variable
                    try:
                        cred_dict = json.loads(firebase_credentials_json)
                        cred = credentials.Certificate(cred_dict)
                        print("Using Firebase credentials from environment variable")
                    except json.JSONDecodeError:
                        print("Error parsing Firebase credentials JSON from environment")
                        raise
                else:
                    # Get the path to the Firebase service account file for local development
                    firebase_service_account = os.getenv('FIREBASE_SERVICE_ACCOUNT', 'bug-site-firebase-adminsdk-fbsvc-38e4147289.json')
                    # Create credentials from the service account file
                    cred = credentials.Certificate(firebase_service_account)
                    print(f"Using Firebase credentials from file: {firebase_service_account}")

                self.firebase_app = firebase_admin.initialize_app(cred)
                print("Firebase Admin SDK initialized successfully")
            except Exception as e:
                print(f"Firebase initialization error: {e}")

        # Register routes with the Flask app
        self._register_routes()

    def _register_routes(self):
        """Register authentication routes with the Flask app"""
        if self.app:
            self.app.add_url_rule('/api/register', 'register', self.register, methods=['POST'])
            self.app.add_url_rule('/api/login', 'login', self.login, methods=['POST'])
            self.app.add_url_rule('/api/logout', 'logout', self.logout, methods=['POST'])
            self.app.add_url_rule('/api/user', 'get_user', self.get_user, methods=['GET'])
            self.app.add_url_rule('/api/reset-password', 'reset_password', self.reset_password, methods=['POST'])
            self.app.add_url_rule('/api/firebase-config', 'get_firebase_config', self.get_firebase_config, methods=['GET'])
            # Note: google_auth and google_callback are registered in app.py

    def login_required(self, f):
        """Authentication middleware"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)
        return decorated_function

    def register(self):
        """Register a new user with email and password"""
        try:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return jsonify({"error": "Email and password are required"}), 400

            # Create user in Firebase
            user = auth.create_user(
                email=email,
                password=password
            )

            return jsonify({
                "message": "User created successfully",
                "user_id": user.uid
            }), 201

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    def login(self):
        """Login with email and password"""
        try:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return jsonify({"error": "Email and password are required"}), 400

            try:
                user = auth.get_user_by_email(email)

                # Set session
                session['user_id'] = user.uid

                return jsonify({
                    "message": "Login successful",
                    "user_id": user.uid
                }), 200

            except auth.UserNotFoundError:
                return jsonify({"error": "Invalid credentials"}), 401

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    def logout(self):
        """Logout the current user"""
        session.pop('user_id', None)
        return jsonify({"message": "Logged out successfully"}), 200

    def get_user(self):
        """Get the current user's information"""
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            user_id = session.get('user_id')
            user = auth.get_user(user_id)

            return jsonify({
                "user_id": user.uid,
                "email": user.email,
                "display_name": user.display_name,
                "email_verified": user.email_verified
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    def reset_password(self):
        """Send a password reset email"""
        try:
            data = request.get_json()
            email = data.get('email')

            if not email:
                return jsonify({"error": "Email is required"}), 400

            # In a real implementation, use Firebase Auth REST API
            # to send a password reset email
            # This is a placeholder for the actual implementation

            return jsonify({
                "message": "Password reset email sent"
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    def get_firebase_config(self):
        """Return Firebase configuration for client-side use"""
        return jsonify(FIREBASE_CONFIG)

    def create_custom_token(self, uid, additional_claims=None):
        """Create a custom token for a user"""
        try:
            custom_token = auth.create_custom_token(uid, additional_claims)
            return custom_token
        except Exception as e:
            print(f"Error creating custom token: {e}")
            return None

    def verify_id_token(self, id_token):
        """Verify an ID token and return the decoded token"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            print(f"Error verifying ID token: {e}")
            return None

    def google_auth(self):
        """Initiate Google OAuth authentication flow"""
        # Generate a random state token to prevent CSRF attacks
        state = secrets.token_hex(16)
        session['google_oauth_state'] = state

        # Google OAuth configuration
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        # Use the route defined in app.py
        # Ensure this matches exactly what's configured in Google Cloud Console
        redirect_uri = request.url_root.rstrip('/') + '/google-callback'

        # Construct Google OAuth URL
        oauth_url = 'https://accounts.google.com/o/oauth2/v2/auth'
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'email profile',
            'state': state,
            'prompt': 'select_account'
        }

        # Construct the full URL with query parameters
        auth_url = f"{oauth_url}?" + '&'.join([f"{key}={value}" for key, value in params.items()])

        return redirect(auth_url)

    def google_callback(self):
        """Handle Google OAuth callback and authenticate user"""
        # Verify state parameter to prevent CSRF attacks
        state = request.args.get('state')
        stored_state = session.pop('google_oauth_state', None)

        if not state or state != stored_state:
            return jsonify({"error": "Invalid state parameter"}), 400

        # Get authorization code from callback
        code = request.args.get('code')
        if not code:
            return jsonify({"error": "Authorization code not provided"}), 400

        try:
            # Exchange authorization code for tokens
            client_id = os.getenv('GOOGLE_CLIENT_ID')
            client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
            # Use the route defined in app.py
            # Ensure this matches exactly what's configured in Google Cloud Console
            redirect_uri = request.url_root.rstrip('/') + '/google-callback'

            token_url = 'https://oauth2.googleapis.com/token'
            token_payload = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }

            # Make POST request to get tokens
            token_response = requests.post(token_url, data=token_payload)
            token_data = token_response.json()

            if 'error' in token_data:
                return jsonify({"error": token_data['error']}), 400

            # Get ID token from response
            id_token = token_data.get('id_token')
            if not id_token:
                return jsonify({"error": "ID token not provided"}), 400

            # Verify the ID token with Firebase
            decoded_token = self.verify_id_token(id_token)
            if not decoded_token:
                return jsonify({"error": "Invalid ID token"}), 400

            # Get user info from decoded token
            uid = decoded_token['uid']
            email = decoded_token.get('email')
            name = decoded_token.get('name')
            picture = decoded_token.get('picture')

            # Check if user exists in Firebase
            try:
                user = auth.get_user(uid)
            except auth.UserNotFoundError:
                # Create a new user record if not exists
                user = auth.create_user(
                    uid=uid,
                    email=email,
                    display_name=name,
                    photo_url=picture,
                    email_verified=decoded_token.get('email_verified', False)
                )

            # Set session
            session['user_id'] = user.uid

            # Redirect to the dashboard page after successful login
            return redirect(url_for('home_page'))

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    def sign_in_with_google_token(self, id_token):
        """Authenticate a user with a Google ID token"""
        try:
            # Verify the ID token with Firebase
            decoded_token = self.verify_id_token(id_token)
            if not decoded_token:
                return jsonify({"error": "Invalid ID token"}), 400

            # Get user info from decoded token
            uid = decoded_token['uid']
            email = decoded_token.get('email')
            name = decoded_token.get('name')
            picture = decoded_token.get('picture')

            # Check if user exists in Firebase
            try:
                user = auth.get_user(uid)
            except auth.UserNotFoundError:
                # Create a new user record if not exists
                user = auth.create_user(
                    uid=uid,
                    email=email,
                    display_name=name,
                    photo_url=picture,
                    email_verified=decoded_token.get('email_verified', False)
                )

            # Set session
            session['user_id'] = user.uid

            return jsonify({
                "message": "Login successful",
                "user_id": user.uid,
                "email": user.email,
                "display_name": user.display_name
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 400

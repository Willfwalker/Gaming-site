import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_firebase_connection():
    """Test Firebase connection with credentials"""
    try:
        # Get the path to the Firebase service account file
        firebase_service_account = os.getenv('FIREBASE_SERVICE_ACCOUNT', 'bug-site-firebase-adminsdk-fbsvc-38e4147289.json')
        
        print(f"Using Firebase credentials from file: {firebase_service_account}")
        
        # Create credentials from the service account file
        cred = credentials.Certificate(firebase_service_account)
        
        # Initialize Firebase app
        firebase_app = firebase_admin.initialize_app(cred)
        
        # Initialize Firestore
        db = firestore.client()
        
        # Test query
        users_ref = db.collection('users').limit(1)
        users = list(users_ref.stream())
        
        if users:
            print(f"Successfully connected to Firebase and found {len(users)} user(s)")
            for user in users:
                user_data = user.to_dict()
                print(f"User ID: {user.id}, Email: {user_data.get('email', 'No email')}")
        else:
            print("Successfully connected to Firebase but found no users")
            
        return True
    except Exception as e:
        print(f"Firebase connection error: {e}")
        return False

if __name__ == "__main__":
    success = test_firebase_connection()
    print(f"Firebase connection test {'succeeded' if success else 'failed'}")

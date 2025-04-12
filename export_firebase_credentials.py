import json
import os

def export_firebase_credentials():
    """Export Firebase credentials as a JSON string for Vercel environment variables"""
    try:
        # Get the path to the Firebase service account file
        firebase_service_account = os.getenv('FIREBASE_SERVICE_ACCOUNT', 'bug-site-firebase-adminsdk-fbsvc-38e4147289.json')
        
        # Read the file
        with open(firebase_service_account, 'r') as f:
            credentials_json = json.load(f)
        
        # Convert to JSON string
        credentials_str = json.dumps(credentials_json)
        
        print("=== FIREBASE_CREDENTIALS_JSON ===")
        print(credentials_str)
        print("=== END FIREBASE_CREDENTIALS_JSON ===")
        
        print("\nCopy the JSON string above and set it as the FIREBASE_CREDENTIALS_JSON environment variable in Vercel.")
        
    except Exception as e:
        print(f"Error exporting Firebase credentials: {e}")

if __name__ == "__main__":
    export_firebase_credentials()

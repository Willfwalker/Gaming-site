from datetime import datetime
from firebase_admin import firestore

class AnnouncementService:
    def __init__(self, db):
        self.db = db
        self.announcements_ref = db.collection('announcements')
    
    def create_announcement(self, title, content, created_by, importance='normal'):
        """
        Create a new announcement
        
        Args:
            title (str): The announcement title
            content (str): The announcement content
            created_by (str): User ID of the admin who created the announcement
            importance (str): Importance level ('normal', 'important', 'urgent')
            
        Returns:
            str: The ID of the created announcement
        """
        try:
            # Create announcement data
            announcement_data = {
                'title': title,
                'content': content,
                'created_by': created_by,
                'importance': importance,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Add to Firestore
            doc_ref = self.announcements_ref.add(announcement_data)
            
            return doc_ref[1].id
        except Exception as e:
            print(f"Error creating announcement: {str(e)}")
            return None
    
    def get_all_announcements(self, limit=10):
        """
        Get all announcements, sorted by creation date (newest first)
        
        Args:
            limit (int): Maximum number of announcements to return
            
        Returns:
            list: List of announcement dictionaries
        """
        try:
            # Query announcements, ordered by creation date (descending)
            query = self.announcements_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
            
            announcements = []
            for doc in query.stream():
                announcement = doc.to_dict()
                announcement['id'] = doc.id
                announcements.append(announcement)
                
            return announcements
        except Exception as e:
            print(f"Error getting announcements: {str(e)}")
            return []
    
    def get_announcement(self, announcement_id):
        """
        Get a specific announcement by ID
        
        Args:
            announcement_id (str): The announcement ID
            
        Returns:
            dict: The announcement data or None if not found
        """
        try:
            doc = self.announcements_ref.document(announcement_id).get()
            if doc.exists:
                announcement = doc.to_dict()
                announcement['id'] = doc.id
                return announcement
            return None
        except Exception as e:
            print(f"Error getting announcement: {str(e)}")
            return None
    
    def update_announcement(self, announcement_id, title=None, content=None, importance=None):
        """
        Update an existing announcement
        
        Args:
            announcement_id (str): The announcement ID
            title (str, optional): New title
            content (str, optional): New content
            importance (str, optional): New importance level
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get fields to update
            update_data = {}
            if title is not None:
                update_data['title'] = title
            if content is not None:
                update_data['content'] = content
            if importance is not None:
                update_data['importance'] = importance
                
            # Add updated timestamp
            update_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Update in Firestore
            self.announcements_ref.document(announcement_id).update(update_data)
            
            return True
        except Exception as e:
            print(f"Error updating announcement: {str(e)}")
            return False
    
    def delete_announcement(self, announcement_id):
        """
        Delete an announcement
        
        Args:
            announcement_id (str): The announcement ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.announcements_ref.document(announcement_id).delete()
            return True
        except Exception as e:
            print(f"Error deleting announcement: {str(e)}")
            return False

from datetime import datetime

class UserStatsService:
    def __init__(self, db):
        self.db = db
        self.user_stats_ref = db.collection('user_stats')
        self.users_ref = db.collection('users')
    
    def get_user_stats(self, user_id):
        """
        Get stats for a specific user
        """
        try:
            stats_doc = self.user_stats_ref.document(user_id).get()
            if stats_doc.exists:
                stats = stats_doc.to_dict()
                stats['id'] = user_id
                return stats
            else:
                # Create default stats if they don't exist
                default_stats = self._create_default_stats(user_id)
                return default_stats
        except Exception as e:
            print(f"Error getting user stats: {str(e)}")
            return None
    
    def get_leaderboard(self, game_type, limit=10):
        """
        Get leaderboard for a specific game type
        """
        try:
            # Query user stats sorted by wins for the specific game
            stats_query = self.user_stats_ref.where(f'games.{game_type}.played', '>', 0).order_by(f'games.{game_type}.wins', direction='DESCENDING').limit(limit)
            
            leaderboard = []
            for doc in stats_query.stream():
                user_stats = doc.to_dict()
                user_stats['id'] = doc.id
                
                # Get user display name
                user_doc = self.users_ref.document(doc.id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    user_stats['display_name'] = user_data.get('display_name', 'Unknown Player')
                else:
                    user_stats['display_name'] = 'Unknown Player'
                
                # Calculate win percentage
                game_stats = user_stats.get('games', {}).get(game_type, {})
                wins = game_stats.get('wins', 0)
                played = game_stats.get('played', 0)
                
                if played > 0:
                    win_percentage = (wins / played) * 100
                else:
                    win_percentage = 0
                
                leaderboard_entry = {
                    'user_id': doc.id,
                    'display_name': user_stats['display_name'],
                    'wins': wins,
                    'losses': played - wins,
                    'win_percentage': round(win_percentage, 1)
                }
                
                leaderboard.append(leaderboard_entry)
            
            return leaderboard
        except Exception as e:
            print(f"Error getting leaderboard: {str(e)}")
            return []
    
    def update_user_stats(self, user_id, game_type, won=False):
        """
        Update user stats after a game
        """
        try:
            stats_ref = self.user_stats_ref.document(user_id)
            stats_doc = stats_ref.get()
            
            if stats_doc.exists:
                stats = stats_doc.to_dict()
            else:
                stats = self._create_default_stats(user_id)
            
            # Ensure the game type exists in the stats
            if 'games' not in stats:
                stats['games'] = {}
            
            if game_type not in stats['games']:
                stats['games'][game_type] = {
                    'played': 0,
                    'wins': 0,
                    'losses': 0,
                    'last_played': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            # Update the stats
            stats['games'][game_type]['played'] += 1
            if won:
                stats['games'][game_type]['wins'] += 1
            else:
                stats['games'][game_type]['losses'] += 1
            
            stats['games'][game_type]['last_played'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Update total stats
            stats['total_games'] += 1
            if won:
                stats['total_wins'] += 1
            else:
                stats['total_losses'] += 1
            
            # Save the updated stats
            stats_ref.set(stats)
            
            return stats
        except Exception as e:
            print(f"Error updating user stats: {str(e)}")
            return None
    
    def _create_default_stats(self, user_id):
        """
        Create default stats for a new user
        """
        default_stats = {
            'id': user_id,
            'total_games': 0,
            'total_wins': 0,
            'total_losses': 0,
            'games': {
                'mario-kart': {
                    'played': 0,
                    'wins': 0,
                    'losses': 0,
                    'last_played': None
                },
                'smash-bros': {
                    'played': 0,
                    'wins': 0,
                    'losses': 0,
                    'last_played': None
                }
            },
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save the default stats
        self.user_stats_ref.document(user_id).set(default_stats)
        
        return default_stats
    
    def initialize_sample_stats(self):
        """
        Initialize sample user stats for testing
        """
        # Check if stats collection already has data
        existing_stats = list(self.user_stats_ref.limit(1).stream())
        
        # Only initialize if no stats exist
        if not existing_stats:
            # Get all users
            users = []
            for user in self.users_ref.stream():
                users.append(user.id)
            
            if not users:
                # If no users exist, we can't create sample stats
                return
            
            # Create sample stats for Mario Kart
            for i, user_id in enumerate(users[:5]):
                wins = 20 - (i * 2)
                losses = i * 2
                played = wins + losses
                
                self.user_stats_ref.document(user_id).set({
                    'total_games': played,
                    'total_wins': wins,
                    'total_losses': losses,
                    'games': {
                        'mario-kart': {
                            'played': played,
                            'wins': wins,
                            'losses': losses,
                            'last_played': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        },
                        'smash-bros': {
                            'played': 0,
                            'wins': 0,
                            'losses': 0,
                            'last_played': None
                        }
                    },
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            # Create sample stats for Smash Bros
            for i, user_id in enumerate(users[5:10]):
                wins = 25 - (i * 3)
                losses = i * 2
                played = wins + losses
                
                self.user_stats_ref.document(user_id).set({
                    'total_games': played,
                    'total_wins': wins,
                    'total_losses': losses,
                    'games': {
                        'mario-kart': {
                            'played': 0,
                            'wins': 0,
                            'losses': 0,
                            'last_played': None
                        },
                        'smash-bros': {
                            'played': played,
                            'wins': wins,
                            'losses': losses,
                            'last_played': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    },
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            print("Sample user stats initialized in Firestore.")

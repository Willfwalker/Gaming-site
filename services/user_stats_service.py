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
            # For simplicity, we'll just get all user stats and filter/sort in memory
            # This is a workaround for the Firestore query issue
            stats_query = self.user_stats_ref.limit(100)  # Get a reasonable number of users

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

                # Only include users who have played this game
                if played > 0:
                    win_percentage = (wins / played) * 100

                    leaderboard_entry = {
                        'user_id': doc.id,
                        'display_name': user_stats['display_name'],
                        'wins': wins,
                        'losses': played - wins,
                        'win_percentage': round(win_percentage, 1)
                    }

                    leaderboard.append(leaderboard_entry)

            # Sort by wins (descending)
            leaderboard.sort(key=lambda x: x['wins'], reverse=True)

            # Limit to requested number
            leaderboard = leaderboard[:limit]

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

    def get_game_player_counts(self):
        """
        Get the count of players for each game
        """
        try:
            # Get all user stats
            stats_query = self.user_stats_ref.limit(100)  # Get a reasonable number of users

            # Initialize counters
            mario_kart_count = 0
            smash_bros_count = 0

            # Count players for each game
            for doc in stats_query.stream():
                user_stats = doc.to_dict()

                # Check if user has played Mario Kart
                mario_kart_stats = user_stats.get('games', {}).get('mario-kart', {})
                if mario_kart_stats.get('played', 0) > 0:
                    mario_kart_count += 1

                # Check if user has played Smash Bros
                smash_bros_stats = user_stats.get('games', {}).get('smash-bros', {})
                if smash_bros_stats.get('played', 0) > 0:
                    smash_bros_count += 1

            return {
                'mario-kart': mario_kart_count,
                'smash-bros': smash_bros_count
            }
        except Exception as e:
            print(f"Error getting game player counts: {str(e)}")
            return {
                'mario-kart': 0,
                'smash-bros': 0
            }

    def get_top_players(self, limit=3):
        """
        Get top players across all games
        """
        try:
            # Get all user stats
            stats_query = self.user_stats_ref.limit(100)  # Get a reasonable number of users

            # Collect all players with their stats
            players = []
            for doc in stats_query.stream():
                user_stats = doc.to_dict()
                user_id = doc.id

                # Get user display name
                user_doc = self.users_ref.document(user_id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    display_name = user_data.get('display_name', 'Unknown Player')
                else:
                    display_name = 'Unknown Player'

                # Calculate total points (wins * 100)
                total_points = user_stats.get('total_wins', 0) * 100

                # Determine primary game (the one with most wins)
                mario_kart_wins = user_stats.get('games', {}).get('mario-kart', {}).get('wins', 0)
                smash_bros_wins = user_stats.get('games', {}).get('smash-bros', {}).get('wins', 0)

                primary_game = 'mario-kart' if mario_kart_wins >= smash_bros_wins else 'smash-bros'
                primary_game_name = 'Mario Kart' if primary_game == 'mario-kart' else 'Smash Bros'

                # Add to players list
                players.append({
                    'user_id': user_id,
                    'display_name': display_name,
                    'points': total_points,
                    'primary_game': primary_game,
                    'primary_game_name': primary_game_name
                })

            # Sort by points (descending)
            players.sort(key=lambda x: x['points'], reverse=True)

            # Limit to requested number
            return players[:limit]
        except Exception as e:
            print(f"Error getting top players: {str(e)}")
            return []

    def get_all_players(self, limit=100):
        """
        Get all registered players with their stats

        Args:
            limit (int): Maximum number of players to return

        Returns:
            list: List of player dictionaries with their stats
        """
        try:
            # Get all users
            users_query = self.users_ref.limit(limit)

            players = []
            for user_doc in users_query.stream():
                user_id = user_doc.id
                user_data = user_doc.to_dict()

                # Get user stats
                stats_doc = self.user_stats_ref.document(user_id).get()
                if stats_doc.exists:
                    stats = stats_doc.to_dict()
                else:
                    stats = self._create_default_stats(user_id)

                # Calculate total games and win percentage
                total_games = stats.get('total_games', 0)
                total_wins = stats.get('total_wins', 0)
                win_percentage = round((total_wins / total_games) * 100, 1) if total_games > 0 else 0

                # Determine primary game (the one with most wins)
                mario_kart_wins = stats.get('games', {}).get('mario-kart', {}).get('wins', 0)
                smash_bros_wins = stats.get('games', {}).get('smash-bros', {}).get('wins', 0)

                primary_game = 'mario-kart' if mario_kart_wins >= smash_bros_wins else 'smash-bros'
                primary_game_name = 'Mario Kart' if primary_game == 'mario-kart' else 'Smash Bros'

                # Create player object
                player = {
                    'user_id': user_id,
                    'display_name': user_data.get('display_name', 'Unknown Player'),
                    'email': user_data.get('email', ''),
                    'created_at': user_data.get('created_at', ''),
                    'total_games': total_games,
                    'total_wins': total_wins,
                    'total_losses': stats.get('total_losses', 0),
                    'win_percentage': win_percentage,
                    'points': total_wins * 100,  # Points calculation (wins * 100)
                    'primary_game': primary_game,
                    'primary_game_name': primary_game_name,
                    'mario_kart_stats': stats.get('games', {}).get('mario-kart', {}),
                    'smash_bros_stats': stats.get('games', {}).get('smash-bros', {})
                }

                players.append(player)

            # Sort by points (descending)
            players.sort(key=lambda x: x['points'], reverse=True)

            return players
        except Exception as e:
            print(f"Error getting all players: {str(e)}")
            return []

    def get_game_statistics(self):
        """
        Get statistics for each game
        """
        try:
            # Get all user stats
            stats_query = self.user_stats_ref.limit(100)  # Get a reasonable number of users

            # Initialize statistics
            mario_kart_stats = {
                'total_games': 0,
                'total_wins': 0,
                'total_losses': 0,
                'avg_win_percentage': 0,
                'recent_matches': []
            }

            smash_bros_stats = {
                'total_games': 0,
                'total_wins': 0,
                'total_losses': 0,
                'avg_win_percentage': 0,
                'recent_matches': []
            }

            # Collect game statistics
            mario_kart_players = 0
            smash_bros_players = 0

            for doc in stats_query.stream():
                user_stats = doc.to_dict()
                user_id = doc.id

                # Get user display name
                user_doc = self.users_ref.document(user_id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    display_name = user_data.get('display_name', 'Unknown Player')
                else:
                    display_name = 'Unknown Player'

                # Get Mario Kart stats
                mk_stats = user_stats.get('games', {}).get('mario-kart', {})
                mk_played = mk_stats.get('played', 0)
                mk_wins = mk_stats.get('wins', 0)
                mk_losses = mk_stats.get('losses', 0)
                mk_last_played = mk_stats.get('last_played')

                if mk_played > 0:
                    mario_kart_players += 1
                    mario_kart_stats['total_games'] += mk_played
                    mario_kart_stats['total_wins'] += mk_wins
                    mario_kart_stats['total_losses'] += mk_losses

                    if mk_last_played:
                        mario_kart_stats['recent_matches'].append({
                            'player': display_name,
                            'date': mk_last_played
                        })

                # Get Smash Bros stats
                sb_stats = user_stats.get('games', {}).get('smash-bros', {})
                sb_played = sb_stats.get('played', 0)
                sb_wins = sb_stats.get('wins', 0)
                sb_losses = sb_stats.get('losses', 0)
                sb_last_played = sb_stats.get('last_played')

                if sb_played > 0:
                    smash_bros_players += 1
                    smash_bros_stats['total_games'] += sb_played
                    smash_bros_stats['total_wins'] += sb_wins
                    smash_bros_stats['total_losses'] += sb_losses

                    if sb_last_played:
                        smash_bros_stats['recent_matches'].append({
                            'player': display_name,
                            'date': sb_last_played
                        })

            # Calculate average win percentages
            if mario_kart_stats['total_games'] > 0:
                mario_kart_stats['avg_win_percentage'] = round((mario_kart_stats['total_wins'] / mario_kart_stats['total_games']) * 100, 1)

            if smash_bros_stats['total_games'] > 0:
                smash_bros_stats['avg_win_percentage'] = round((smash_bros_stats['total_wins'] / smash_bros_stats['total_games']) * 100, 1)

            # Sort recent matches by date (descending) and limit to 5
            mario_kart_stats['recent_matches'].sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
            mario_kart_stats['recent_matches'] = mario_kart_stats['recent_matches'][:5]

            smash_bros_stats['recent_matches'].sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
            smash_bros_stats['recent_matches'] = smash_bros_stats['recent_matches'][:5]

            return {
                'mario-kart': mario_kart_stats,
                'smash-bros': smash_bros_stats
            }
        except Exception as e:
            print(f"Error getting game statistics: {str(e)}")
            return {
                'mario-kart': {
                    'total_games': 0,
                    'total_wins': 0,
                    'total_losses': 0,
                    'avg_win_percentage': 0,
                    'recent_matches': []
                },
                'smash-bros': {
                    'total_games': 0,
                    'total_wins': 0,
                    'total_losses': 0,
                    'avg_win_percentage': 0,
                    'recent_matches': []
                }
            }

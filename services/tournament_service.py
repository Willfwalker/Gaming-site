from datetime import datetime
from firebase_admin import firestore

class TournamentService:
    def __init__(self, db):
        self.db = db
        self.tournaments_ref = db.collection('tournaments')
        self.registrations_ref = db.collection('tournament_registrations')
        self.admin_users_ref = db.collection('admin_users')
        self.user_stats_ref = db.collection('user_stats')

    def get_all_tournaments(self):
        """
        Fetch all tournaments from Firestore and calculate their status
        """
        tournaments = []
        featured_tournament = None

        # Fetch all tournaments
        for doc in self.tournaments_ref.stream():
            tournament = doc.to_dict()
            tournament['id'] = doc.id

            # Only calculate status if it's not already set
            if 'status' not in tournament:
                # Calculate tournament status based on date
                tournament_date = datetime.strptime(tournament['date'], '%Y-%m-%d')
                current_date = datetime.now()

                if tournament_date.date() > current_date.date():
                    tournament['status'] = 'upcoming'
                elif tournament_date.date() < current_date.date():
                    tournament['status'] = 'completed'
                else:
                    tournament['status'] = 'ongoing'

            # Check if this is the featured tournament
            if tournament.get('featured', False):
                featured_tournament = tournament

            tournaments.append(tournament)

        # If no featured tournament, use the first one (if available)
        if not featured_tournament and tournaments:
            featured_tournament = tournaments[0]

        return tournaments, featured_tournament

    def register_for_tournament(self, user_id, tournament_id, gamertag=None, discord=None):
        """
        Register a user for a tournament
        """
        if not tournament_id:
            return {'success': False, 'message': 'Tournament ID is required'}, 400

        try:
            # Get the tournament
            tournament_ref = self.tournaments_ref.document(tournament_id)
            tournament = tournament_ref.get()

            if not tournament.exists:
                return {'success': False, 'message': 'Tournament not found'}, 404

            tournament_data = tournament.to_dict()

            # Check if tournament is open for registration
            tournament_date = datetime.strptime(tournament_data['date'], '%Y-%m-%d')
            current_date = datetime.now()

            if tournament_date.date() <= current_date.date():
                return {'success': False, 'message': 'Registration for this tournament is closed'}, 400

            # Check if tournament is full
            if tournament_data['spots_used'] >= tournament_data['total_spots']:
                return {'success': False, 'message': 'Tournament is full'}, 400

            # Check if user is already registered
            existing_registration = self.registrations_ref.where('tournament_id', '==', tournament_id).where('user_id', '==', user_id).limit(1).get()

            if len(list(existing_registration)) > 0:
                return {'success': False, 'message': 'You are already registered for this tournament'}, 400

            # Register the user
            registration_data = {
                'tournament_id': tournament_id,
                'user_id': user_id,
                'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tournament_name': tournament_data['name'],
                'tournament_date': tournament_data['date'],
                'game': tournament_data['game']
            }

            # Add optional fields if provided
            if gamertag:
                registration_data['gamertag'] = gamertag
            if discord:
                registration_data['discord'] = discord

            # Add registration to Firestore
            self.registrations_ref.add(registration_data)

            # Update tournament spots used
            tournament_ref.update({
                'spots_used': tournament_data['spots_used'] + 1
            })

            return {
                'success': True,
                'message': f'Successfully registered for {tournament_data["name"]}',
                'spots_remaining': tournament_data['total_spots'] - (tournament_data['spots_used'] + 1)
            }, 200

        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}, 500

    def get_user_registrations(self, user_id):
        """
        Get all tournament registrations for a user
        """
        try:
            # Get all registrations for the user
            registrations = self.registrations_ref.where('user_id', '==', user_id).get()

            result = []
            for reg in registrations:
                reg_data = reg.to_dict()
                reg_data['id'] = reg.id
                result.append(reg_data)

            return {'success': True, 'registrations': result}, 200

        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}, 500

    def init_tournament_data(self):
        """
        Initialize sample tournament data if none exists
        """
        # Check if tournaments collection already has data
        existing_tournaments = list(self.tournaments_ref.limit(1).stream())

        # Only initialize if no tournaments exist
        if not existing_tournaments:
            # Sample tournament data
            tournaments = [
                {
                    'name': 'BUG Mario Kart Grand Prix',
                    'date': '2025-04-15',
                    'total_spots': 32,
                    'spots_used': 16,
                    'description': 'Join our monthly Mario Kart tournament and compete for glory and prizes! This tournament will feature custom tracks and special rules. All skill levels are welcome.',
                    'prize_pool': '$100',
                    'game': 'mario-kart',
                    'featured': True,
                    'time': '7:00 PM'
                },
                {
                    'name': 'Weekly Smash Tournament',
                    'date': '2025-04-20',
                    'total_spots': 16,
                    'spots_used': 8,
                    'description': 'Our weekly Smash Bros tournament is back! Show off your skills and compete against other players in the community.',
                    'prize_pool': '$50',
                    'game': 'smash-bros',
                    'featured': False,
                    'time': '6:00 PM'
                },
                {
                    'name': 'Weekend Cup Challenge',
                    'date': '2025-04-11',
                    'total_spots': 24,
                    'spots_used': 24,
                    'description': 'A weekend-long Mario Kart tournament with multiple stages and elimination rounds.',
                    'prize_pool': '$75',
                    'game': 'mario-kart',
                    'featured': False,
                    'time': '5:00 PM'
                },
                {
                    'name': 'Pro Smash Invitational',
                    'date': '2025-04-05',
                    'total_spots': 12,
                    'spots_used': 12,
                    'description': 'An invitation-only tournament for our top Smash Bros players. Winner: SmashKing',
                    'prize_pool': '$120',
                    'game': 'smash-bros',
                    'featured': False,
                    'time': '8:00 PM',
                    'winner': 'SmashKing'
                },
                {
                    'name': 'Rainbow Road Challenge',
                    'date': '2025-04-25',
                    'total_spots': 12,
                    'spots_used': 3,
                    'description': 'Can you master the Rainbow Road? This special tournament focuses exclusively on the most challenging tracks.',
                    'prize_pool': '$25',
                    'game': 'mario-kart',
                    'featured': False,
                    'time': '7:30 PM'
                },
                {
                    'name': 'March Madness Cup',
                    'date': '2025-03-28',
                    'total_spots': 32,
                    'spots_used': 32,
                    'description': 'Our biggest Mario Kart tournament of the month with special prizes and challenges.',
                    'prize_pool': '$150',
                    'game': 'mario-kart',
                    'featured': False,
                    'time': '6:30 PM',
                    'winner': 'RainbowRoad'
                },
                {
                    'name': 'May Day Showdown',
                    'date': '2025-05-01',
                    'total_spots': 24,
                    'spots_used': 0,
                    'description': 'Celebrate May Day with our special Smash Bros tournament featuring unique rulesets and challenges.',
                    'prize_pool': '$150',
                    'game': 'smash-bros',
                    'featured': False,
                    'time': '7:00 PM'
                }
            ]

            # Add tournaments to Firestore
            for tournament in tournaments:
                self.tournaments_ref.add(tournament)

            print("Sample tournament data initialized in Firestore.")

    def is_admin(self, user_id):
        """
        Check if a user is an admin
        """
        if not user_id:
            return False

        try:
            admin_doc = self.admin_users_ref.document(user_id).get()
            return admin_doc.exists
        except Exception as e:
            print(f"Error checking admin status: {str(e)}")
            return False

    def create_tournament(self, tournament_data):
        """
        Create a new tournament
        """
        try:
            # Set initial values
            tournament_data['spots_used'] = 0

            # Add tournament to Firestore
            tournament_ref = self.tournaments_ref.add(tournament_data)
            tournament_id = tournament_ref[1].id

            # If this is marked as featured, unmark any other featured tournaments
            if tournament_data.get('featured', False):
                self._update_featured_tournaments(tournament_id)

            return {'success': True, 'message': 'Tournament created successfully', 'tournament_id': tournament_id}, 201
        except Exception as e:
            return {'success': False, 'message': f'Error creating tournament: {str(e)}'}, 500

    def update_tournament(self, tournament_id, tournament_data):
        """
        Update an existing tournament
        """
        try:
            # Get the tournament
            tournament_ref = self.tournaments_ref.document(tournament_id)
            tournament = tournament_ref.get()

            if not tournament.exists:
                return {'success': False, 'message': 'Tournament not found'}, 404

            # Update tournament in Firestore
            tournament_ref.update(tournament_data)

            # If this is marked as featured, unmark any other featured tournaments
            if tournament_data.get('featured', False):
                self._update_featured_tournaments(tournament_id)

            return {'success': True, 'message': 'Tournament updated successfully'}, 200
        except Exception as e:
            return {'success': False, 'message': f'Error updating tournament: {str(e)}'}, 500

    def delete_tournament(self, tournament_id):
        """
        Delete a tournament
        """
        try:
            # Get the tournament
            tournament_ref = self.tournaments_ref.document(tournament_id)
            tournament = tournament_ref.get()

            if not tournament.exists:
                return {'success': False, 'message': 'Tournament not found'}, 404

            # Delete all registrations for this tournament
            registrations = self.registrations_ref.where('tournament_id', '==', tournament_id).stream()
            for reg in registrations:
                reg.reference.delete()

            # Delete the tournament
            tournament_ref.delete()

            return {'success': True, 'message': 'Tournament deleted successfully'}, 200
        except Exception as e:
            return {'success': False, 'message': f'Error deleting tournament: {str(e)}'}, 500

    def get_tournament(self, tournament_id):
        """
        Get a specific tournament by ID
        """
        try:
            # Get the tournament
            tournament_ref = self.tournaments_ref.document(tournament_id)
            tournament = tournament_ref.get()

            if not tournament.exists:
                return {'success': False, 'message': 'Tournament not found'}, 404

            tournament_data = tournament.to_dict()
            tournament_data['id'] = tournament_id

            # Check if tournament has a status field (manually set by admin)
            if 'status' not in tournament_data:
                # Calculate tournament status based on date
                tournament_date = datetime.strptime(tournament_data['date'], '%Y-%m-%d')
                current_date = datetime.now()

                if tournament_date.date() > current_date.date():
                    tournament_data['status'] = 'upcoming'
                elif tournament_date.date() < current_date.date():
                    tournament_data['status'] = 'completed'
                else:
                    tournament_data['status'] = 'ongoing'

            print(f"Tournament {tournament_id} status: {tournament_data.get('status')}")

            return {'success': True, 'tournament': tournament_data}, 200
        except Exception as e:
            return {'success': False, 'message': f'Error getting tournament: {str(e)}'}, 500

    def close_tournament(self, tournament_id, winner_id=None, results=None):
        """
        Close a tournament, set its status to completed, and optionally assign a winner and participant results
        """
        try:
            print(f"Closing tournament: {tournament_id}, winner_id: {winner_id}, results: {results}")

            # Get the tournament
            tournament_ref = self.tournaments_ref.document(tournament_id)
            tournament = tournament_ref.get()

            if not tournament.exists:
                print(f"Tournament not found: {tournament_id}")
                return {'success': False, 'message': 'Tournament not found'}, 404

            tournament_data = tournament.to_dict()
            print(f"Tournament data: {tournament_data}")

            # Update tournament status
            update_data = {
                'status': 'completed',
                'closed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Set winner if provided
            if winner_id:
                update_data['winner_id'] = winner_id
                print(f"Setting winner ID: {winner_id}")

                # Get winner's gamertag from registrations
                winner_reg = self.registrations_ref.where('tournament_id', '==', tournament_id).where('user_id', '==', winner_id).limit(1).get()
                if winner_reg:
                    gamertag = winner_reg[0].to_dict().get('gamertag', 'Unknown')
                    update_data['winner'] = gamertag
                    print(f"Winner gamertag: {gamertag}")
                else:
                    print(f"No registration found for winner ID: {winner_id}")
                    # Use a default winner name if no registration found
                    update_data['winner'] = 'Tournament Winner'

            # Update tournament
            print(f"Updating tournament with data: {update_data}")
            tournament_ref.update(update_data)

            # Update participant results if provided
            if results and isinstance(results, list):
                game_type = tournament_data.get('game', 'unknown')
                print(f"Processing {len(results)} participant results for game type: {game_type}")

                for result in results:
                    user_id = result.get('user_id')
                    points = result.get('points', 0)
                    position = result.get('position')

                    if not user_id:
                        print("Skipping result with no user ID")
                        continue

                    print(f"Processing result for user {user_id}: position={position}, points={points}")

                    # Update registration with results
                    reg_query = self.registrations_ref.where('tournament_id', '==', tournament_id).where('user_id', '==', user_id).limit(1).get()
                    if reg_query:
                        reg_ref = reg_query[0].reference
                        reg_update = {
                            'points': points,
                            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }

                        if position is not None:
                            reg_update['position'] = position

                        print(f"Updating registration for user {user_id} with data: {reg_update}")
                        reg_ref.update(reg_update)
                    else:
                        print(f"No registration found for user {user_id}")

                    # Update user stats based on results
                    # Winner gets a win, others get a loss
                    is_winner = (user_id == winner_id)
                    print(f"Updating stats for user {user_id}, is_winner: {is_winner}, points: {points}")
                    self._update_user_stats(user_id, game_type, is_winner, points)

            print("Tournament closed successfully")
            return {'success': True, 'message': 'Tournament closed successfully'}, 200
        except Exception as e:
            print(f"Error closing tournament: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Error closing tournament: {str(e)}'}, 500

    def get_tournament_participants(self, tournament_id):
        """
        Get all participants for a specific tournament
        """
        try:
            print(f"Getting participants for tournament: {tournament_id}")
            # Get the tournament
            tournament_ref = self.tournaments_ref.document(tournament_id)
            tournament = tournament_ref.get()

            if not tournament.exists:
                print(f"Tournament not found: {tournament_id}")
                return {'success': False, 'message': 'Tournament not found'}, 404

            # Get all registrations for this tournament
            registrations = []
            reg_query = self.registrations_ref.where('tournament_id', '==', tournament_id).stream()

            for reg in reg_query:
                reg_data = reg.to_dict()
                reg_data['id'] = reg.id

                # Get user display name
                user_id = reg_data.get('user_id')
                if user_id:
                    user_doc = self.db.collection('users').document(user_id).get()
                    if user_doc.exists:
                        reg_data['display_name'] = user_doc.to_dict().get('display_name', 'Unknown')
                    else:
                        reg_data['display_name'] = 'Unknown'

                registrations.append(reg_data)

            print(f"Found {len(registrations)} participants for tournament {tournament_id}")

            # If no participants found, create a dummy participant for testing
            if not registrations:
                print("No participants found, creating a dummy participant for testing")
                # Get the first user from the users collection
                users = list(self.db.collection('users').limit(1).stream())
                if users:
                    user_id = users[0].id
                    user_data = users[0].to_dict()
                    display_name = user_data.get('display_name', 'Test User')

                    # Create a dummy registration
                    dummy_reg = {
                        'id': 'dummy-reg-id',
                        'user_id': user_id,
                        'tournament_id': tournament_id,
                        'gamertag': 'TestPlayer123',
                        'display_name': display_name,
                        'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    registrations.append(dummy_reg)

            return {'success': True, 'participants': registrations}, 200
        except Exception as e:
            print(f"Error getting tournament participants: {str(e)}")
            return {'success': False, 'message': f'Error getting tournament participants: {str(e)}'}, 500

    def _update_user_stats(self, user_id, game_type, won=False, points=0):
        """
        Update user stats after tournament completion
        """
        try:
            print(f"Updating stats for user {user_id}, game {game_type}, won={won}, points={points}")

            # Ensure points is an integer
            try:
                points = int(points)
            except (TypeError, ValueError):
                print(f"Invalid points value: {points}, defaulting to 0")
                points = 0

            stats_ref = self.user_stats_ref.document(user_id)
            stats_doc = stats_ref.get()

            if stats_doc.exists:
                stats = stats_doc.to_dict()
                print(f"Existing stats found for user {user_id}")
            else:
                # Create default stats if they don't exist
                print(f"Creating new stats for user {user_id}")
                stats = {
                    'total_games': 0,
                    'total_wins': 0,
                    'total_losses': 0,
                    'total_points': 0,
                    'games': {},
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            # Ensure the game type exists in the stats
            if 'games' not in stats:
                print("'games' field not found in stats, creating it")
                stats['games'] = {}

            if game_type not in stats['games']:
                print(f"Game type {game_type} not found in stats, creating it")
                stats['games'][game_type] = {
                    'played': 0,
                    'wins': 0,
                    'losses': 0,
                    'points': 0,
                    'last_played': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            # Update the stats
            stats['games'][game_type]['played'] += 1
            stats['games'][game_type]['points'] += points
            if won:
                stats['games'][game_type]['wins'] += 1
            else:
                stats['games'][game_type]['losses'] += 1

            stats['games'][game_type]['last_played'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update total stats
            stats['total_games'] += 1
            stats['total_points'] += points
            if won:
                stats['total_wins'] += 1
            else:
                stats['total_losses'] += 1

            stats['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Save the updated stats
            print(f"Saving updated stats for user {user_id}")
            stats_ref.set(stats)

            return True
        except Exception as e:
            print(f"Error updating user stats: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _update_featured_tournaments(self, new_featured_id):
        """
        Helper method to ensure only one tournament is featured at a time
        """
        # Get all currently featured tournaments
        featured_tournaments = self.tournaments_ref.where('featured', '==', True).stream()

        # Unmark all other tournaments as featured
        for tournament in featured_tournaments:
            if tournament.id != new_featured_id:
                tournament.reference.update({'featured': False})

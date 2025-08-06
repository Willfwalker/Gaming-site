import os
import json
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, Response
from flask_caching import Cache
from flask_compress import Compress
from datetime import datetime
from services.firebase_auth_service import FirebaseAuthService
from services.tournament_service import TournamentService
from services.user_stats_service import UserStatsService
from services.announcement_service import AnnouncementService
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import auth, firestore

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Performance optimizations
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session timeout

# Configure caching - use simple cache for development, Redis for production
cache_config = {
    'CACHE_TYPE': 'simple',  # In-memory cache for development
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes default timeout
}

# Use Redis if available (for production)
redis_url = os.getenv('REDIS_URL')
if redis_url:
    cache_config = {
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_URL': redis_url,
        'CACHE_DEFAULT_TIMEOUT': 300
    }

cache = Cache(app, config=cache_config)

# Enable response compression
compress = Compress(app)

# Add error handlers for better debugging
@app.errorhandler(404)
def page_not_found(e):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested URL was not found on the server.',
        'status_code': 404,
        'path': request.path,
        'method': request.method,
        'env': os.environ.get('VERCEL_ENV', 'development')
    }), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(e),
        'status_code': 500,
        'path': request.path,
        'method': request.method,
        'env': os.environ.get('VERCEL_ENV', 'development')
    }), 500

# Initialize Firebase Auth Service (this also initializes Firebase Admin SDK)
firebase_auth = FirebaseAuthService(app)

# Initialize Firestore database (after Firebase is initialized)
try:
    db = firestore.client()
    print("Firestore client initialized successfully")
except Exception as e:
    print(f"Error initializing Firestore client: {e}")
    raise e

# Initialize services
tournament_service = TournamentService(db)
user_stats_service = UserStatsService(db)
announcement_service = AnnouncementService(db)

# Cached helper functions
@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_cached_announcements(limit=5):
    """Get announcements with caching"""
    return announcement_service.get_all_announcements(limit=limit)

@cache.memoize(timeout=600)  # Cache for 10 minutes
def is_user_admin(user_id):
    """Check if user is admin with caching"""
    return tournament_service.is_admin(user_id)

# Context processor to add admin status and user info to all templates
@app.context_processor
def inject_template_vars():
    if 'user_id' in session:
        user_id = session.get('user_id')
        user_name = session.get('user_name', 'User')
        is_admin = is_user_admin(user_id)
        # Get announcements for the notification bell
        announcements = get_cached_announcements(limit=5)
        return {
            'is_admin': is_admin,
            'user_name': user_name,
            'user_id': user_id,
            'announcements': announcements
        }
    return {
        'is_admin': False,
        'user_name': None,
        'user_id': None,
        'announcements': get_cached_announcements(limit=5)
    }

@app.route('/', methods=['GET'])
def home():
    return redirect(url_for('home_page'))

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'message': 'Service is running',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'environment': os.environ.get('VERCEL_ENV', 'development')
    })

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login_view():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            return render_template('login.html', error="Email and password are required")

        try:
            user = auth.get_user_by_email(email)
            session['user_id'] = user.uid
            session['user_name'] = user.display_name

            return redirect(url_for('home_page'))
        except Exception as e:
            return render_template('login.html', error=str(e))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not email or not password or not username:
            return render_template('register.html', error="All fields are required")

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match")

        try:
            # Create user in Firebase
            user = auth.create_user(
                email=email,
                password=password,
                display_name=username
            )

            # Store user profile in Firestore
            db.collection('users').document(user.uid).set({
                'email': email,
                'display_name': username,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            # Initialize user stats
            user_stats_service.get_user_stats(user.uid)

            return redirect(url_for('login_view'))
        except Exception as e:
            return render_template('register.html', error=str(e))

    return render_template('register.html')

@app.route('/logout')
def logout_page():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('login_view'))

@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access settings', 'error')
        return redirect(url_for('login_view'))

    user_id = session.get('user_id')

    if request.method == 'POST':
        # Get form data
        display_name = request.form.get('display_name')
        email = request.form.get('email')

        # Validate form data
        if not display_name or not email:
            flash('Display name and email are required', 'error')
            return redirect(url_for('settings_page'))

        try:
            # Update user in Firebase Auth
            auth.update_user(
                user_id,
                display_name=display_name,
                email=email
            )

            # Update user profile in Firestore
            db.collection('users').document(user_id).update({
                'display_name': display_name,
                'email': email,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            # Update session
            session['user_name'] = display_name

            flash('Profile updated successfully', 'success')
            return redirect(url_for('settings_page'))

        except Exception as e:
            flash(f'Failed to update profile: {str(e)}', 'error')
            return redirect(url_for('settings_page'))

    # GET request - show settings form
    try:
        # Get user data from Firebase Auth
        user = auth.get_user(user_id)

        # Get additional user data from Firestore
        user_doc = db.collection('users').document(user_id).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}

        return render_template('settings.html',
                             user=user,
                             user_data=user_data)

    except Exception as e:
        flash(f'Failed to load user data: {str(e)}', 'error')
        return redirect(url_for('home_page'))

# Cached dashboard data functions
@cache.memoize(timeout=180)  # Cache for 3 minutes
def get_cached_player_counts():
    """Get game player counts with caching"""
    return user_stats_service.get_game_player_counts()

@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_cached_top_players(limit=3):
    """Get top players with caching"""
    return user_stats_service.get_top_players(limit=limit)

@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_cached_game_statistics():
    """Get game statistics with caching"""
    return user_stats_service.get_game_statistics()

@cache.memoize(timeout=180)  # Cache for 3 minutes
def get_cached_tournaments():
    """Get tournaments with caching"""
    return tournament_service.get_all_tournaments()

@app.route('/')
@app.route('/home')
def home_page():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('login_view'))

    # Get user ID from session
    user_id = session.get('user_id')

    # Get cached data (expensive operations)
    player_counts = get_cached_player_counts()
    top_players = get_cached_top_players(limit=3)
    game_stats = get_cached_game_statistics()
    tournaments, featured_tournament = get_cached_tournaments()
    upcoming_tournaments = [t for t in tournaments if t.get('status') == 'upcoming']

    # Get user's stats (user-specific, can't cache globally)
    user_stats = user_stats_service.get_user_stats(user_id)

    # Get announcements (already cached in context processor)
    announcements = get_cached_announcements(limit=3)

    return render_template('home.html',
                           player_counts=player_counts,
                           top_players=top_players,
                           game_stats=game_stats,
                           upcoming_tournaments=upcoming_tournaments[:3],
                           featured_tournament=featured_tournament,
                           user_stats=user_stats,
                           announcements=announcements)

# Cached leaderboard functions
@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_cached_leaderboard(game_type, limit=10):
    """Get leaderboard with caching"""
    return user_stats_service.get_leaderboard(game_type, limit)

@app.route('/leaderboard', methods=['GET'])
@app.route('/leaderboard/<game_type>', methods=['GET'])
def leaderboard_page(game_type=None):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access the leaderboard', 'error')
        return redirect(url_for('login_view'))

    # If a specific game type is provided, only get that leaderboard
    if game_type:
        if game_type == 'mario-kart':
            mario_kart_leaderboard = get_cached_leaderboard('mario-kart', 10)
            smash_bros_leaderboard = None
            active_game = 'mario-kart'
        elif game_type == 'smash-bros':
            mario_kart_leaderboard = None
            smash_bros_leaderboard = get_cached_leaderboard('smash-bros', 10)
            active_game = 'smash-bros'
        else:
            # Invalid game type, redirect to main leaderboard
            return redirect(url_for('leaderboard_page'))
    else:
        # Get leaderboards for each game type
        mario_kart_leaderboard = get_cached_leaderboard('mario-kart', 5)
        smash_bros_leaderboard = get_cached_leaderboard('smash-bros', 5)
        active_game = None

    return render_template('leaderboard.html',
                           mario_kart_leaderboard=mario_kart_leaderboard,
                           smash_bros_leaderboard=smash_bros_leaderboard,
                           active_game=active_game)

# Cached players function
@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_cached_all_players():
    """Get all players with caching"""
    return user_stats_service.get_all_players()

@app.route('/players', methods=['GET'])
def players_page():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access players', 'error')
        return redirect(url_for('login_view'))

    # Get all players from service (cached)
    players = get_cached_all_players()

    return render_template('players.html', players=players)

@app.route('/tournaments', methods=['GET'])
def tournaments_page():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access tournaments', 'error')
        return redirect(url_for('login_view'))

    # Get tournaments from service (cached)
    tournaments, featured_tournament = get_cached_tournaments()

    user_id = session.get('user_id')
    return render_template('tournaments.html', tournaments=tournaments, featured_tournament=featured_tournament, user_id=user_id)



@app.route('/api/tournaments/register', methods=['POST'])
def register_for_tournament():
    # Check if user is logged in
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to register for tournaments'}), 401

    user_id = session.get('user_id')
    tournament_id = request.json.get('tournament_id')
    gamertag = request.json.get('gamertag')
    discord = request.json.get('discord')

    # Use the tournament service to register the user
    result, status_code = tournament_service.register_for_tournament(user_id, tournament_id, gamertag, discord)

    return jsonify(result), status_code


@app.route('/api/tournaments/user-registrations', methods=['GET'])
def get_user_registrations():
    # Check if user is logged in
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to view your registrations'}), 401

    user_id = session.get('user_id')

    # Use the tournament service to get user registrations
    result, status_code = tournament_service.get_user_registrations(user_id)

    return jsonify(result), status_code


# Admin routes
@app.route('/admin/tournaments', methods=['GET'])
def admin_tournaments_page():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access admin panel', 'error')
        return redirect(url_for('login_view'))

    # Check if user is an admin
    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        flash('You do not have permission to access the admin panel', 'error')
        return redirect(url_for('tournaments_page'))

    # Get tournaments from service
    tournaments, _ = tournament_service.get_all_tournaments()

    return render_template('admin_tournaments.html', tournaments=tournaments)

# Admin API routes
@app.route('/api/admin/tournaments', methods=['POST'])
def create_tournament():
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to access admin features'}), 401

    user_id = session.get('user_id')
    if not is_user_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Get tournament data from request
    tournament_data = request.json

    # Create tournament
    result, status_code = tournament_service.create_tournament(tournament_data)

    # Clear tournament cache when new tournament is created
    if result.get('success'):
        cache.delete_memoized(get_cached_tournaments)

    return jsonify(result), status_code

@app.route('/api/admin/tournaments/<tournament_id>', methods=['GET'])
def get_tournament(tournament_id):
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to access admin features'}), 401

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Get tournament
    result, status_code = tournament_service.get_tournament(tournament_id)

    return jsonify(result), status_code

@app.route('/api/admin/tournaments/<tournament_id>', methods=['PUT'])
def update_tournament(tournament_id):
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to access admin features'}), 401

    user_id = session.get('user_id')
    if not is_user_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Get tournament data from request
    tournament_data = request.json

    # Update tournament
    result, status_code = tournament_service.update_tournament(tournament_id, tournament_data)

    # Clear tournament cache when tournament is updated
    if result.get('success'):
        cache.delete_memoized(get_cached_tournaments)

    return jsonify(result), status_code

@app.route('/api/admin/tournaments/<tournament_id>', methods=['DELETE'])
def delete_tournament(tournament_id):
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to access admin features'}), 401

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Delete tournament
    result, status_code = tournament_service.delete_tournament(tournament_id)

    return jsonify(result), status_code

@app.route('/api/admin/tournaments/<tournament_id>/close', methods=['POST'])
def close_tournament(tournament_id):
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to access admin features'}), 401

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Get data from request
    data = request.json
    winner_id = data.get('winner_id')
    results = data.get('results', [])

    # Close tournament
    result, status_code = tournament_service.close_tournament(tournament_id, winner_id, results)

    return jsonify(result), status_code

@app.route('/api/admin/tournaments/<tournament_id>/participants', methods=['GET'])
def get_tournament_participants(tournament_id):
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to access admin features'}), 401

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Get tournament participants
    result, status_code = tournament_service.get_tournament_participants(tournament_id)

    return jsonify(result), status_code

# Initialize admin user if it doesn't exist
def init_admin_user():
    # Check if admin_users collection exists and has at least one admin
    admin_users_ref = db.collection('admin_users')
    existing_admins = list(admin_users_ref.limit(1).stream())

    # Only initialize if no admin users exist
    if not existing_admins:
        # Get the first user from the authentication system
        try:
            # List users (limited to 1)
            users = auth.list_users(max_results=1).users

            if users:
                # Add the first user as an admin
                admin_users_ref.document(users[0].uid).set({
                    'email': users[0].email,
                    'display_name': users[0].display_name,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                print(f"Admin user created: {users[0].email}")
            else:
                print("No users found to make admin")
        except Exception as e:
            print(f"Error creating admin user: {str(e)}")
    else:
        print("Admin user already exists")

    # For debugging, print all admin users
    try:
        print("Current admin users:")
        for admin in admin_users_ref.stream():
            admin_data = admin.to_dict()
            print(f"Admin ID: {admin.id}, Email: {admin_data.get('email')}")
    except Exception as e:
        print(f"Error listing admin users: {str(e)}")

# API routes for user stats
@app.route('/api/leaderboard/<game_type>', methods=['GET'])
def get_leaderboard(game_type):
    # Check if user is logged in
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to view leaderboard'}), 401

    # Get leaderboard for the specified game type (cached)
    leaderboard = get_cached_leaderboard(game_type, 10)

    return jsonify({'success': True, 'leaderboard': leaderboard}), 200

@app.route('/api/user/stats', methods=['GET'])
def get_user_stats():
    # Check if user is logged in
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login to view your stats'}), 401

    user_id = session.get('user_id')

    # Get user stats
    stats = user_stats_service.get_user_stats(user_id)

    if stats:
        return jsonify({'success': True, 'stats': stats}), 200
    else:
        return jsonify({'success': False, 'message': 'Failed to retrieve user stats'}), 500

# Initialize user stats data
def init_user_stats():
    # Create users collection if it doesn't exist
    users_ref = db.collection('users')
    existing_users = list(users_ref.limit(1).stream())

    if not existing_users:
        # Get all users from Firebase Auth
        try:
            firebase_users = auth.list_users().users

            for user in firebase_users:
                # Add user to Firestore
                users_ref.document(user.uid).set({
                    'email': user.email,
                    'display_name': user.display_name or user.email.split('@')[0],
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

            print(f"Added {len(firebase_users)} users to Firestore")
        except Exception as e:
            print(f"Error initializing users: {str(e)}")

    # Initialize sample user stats
    user_stats_service.initialize_sample_stats()

# Admin routes for announcement management
@app.route('/admin/announcements')
def admin_announcements_page():
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        flash('Please login to access this page', 'error')
        return redirect(url_for('login_view'))

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('home_page'))

    # Get all announcements
    announcements = announcement_service.get_all_announcements()

    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/admin/announcements/create', methods=['GET', 'POST'])
def admin_create_announcement():
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        flash('Please login to access this page', 'error')
        return redirect(url_for('login_view'))

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('home_page'))

    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        content = request.form.get('content')
        importance = request.form.get('importance', 'normal')

        # Validate form data
        if not title or not content:
            flash('Please fill in all required fields', 'error')
            return render_template('admin/create_announcement.html')

        # Create announcement
        announcement_id = announcement_service.create_announcement(
            title=title,
            content=content,
            created_by=user_id,
            importance=importance
        )

        if announcement_id:
            # Clear announcements cache when new announcement is created
            cache.delete_memoized(get_cached_announcements)
            flash('Announcement created successfully', 'success')
            return redirect(url_for('admin_announcements_page'))
        else:
            flash('Failed to create announcement', 'error')
            return render_template('admin/create_announcement.html')

    return render_template('admin/create_announcement.html')

@app.route('/admin/announcements/edit/<announcement_id>', methods=['GET', 'POST'])
def admin_edit_announcement(announcement_id):
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        flash('Please login to access this page', 'error')
        return redirect(url_for('login_view'))

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('home_page'))

    # Get the announcement
    announcement = announcement_service.get_announcement(announcement_id)
    if not announcement:
        flash('Announcement not found', 'error')
        return redirect(url_for('admin_announcements_page'))

    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        content = request.form.get('content')
        importance = request.form.get('importance', 'normal')

        # Validate form data
        if not title or not content:
            flash('Please fill in all required fields', 'error')
            return render_template('admin/edit_announcement.html', announcement=announcement)

        # Update announcement
        success = announcement_service.update_announcement(
            announcement_id=announcement_id,
            title=title,
            content=content,
            importance=importance
        )

        if success:
            flash('Announcement updated successfully', 'success')
            return redirect(url_for('admin_announcements_page'))
        else:
            flash('Failed to update announcement', 'error')
            return render_template('admin/edit_announcement.html', announcement=announcement)

    return render_template('admin/edit_announcement.html', announcement=announcement)

@app.route('/admin/announcements/delete/<announcement_id>', methods=['POST'])
def admin_delete_announcement(announcement_id):
    # Check if user is logged in and is an admin
    if 'user_id' not in session:
        flash('Please login to access this page', 'error')
        return redirect(url_for('login_view'))

    user_id = session.get('user_id')
    if not tournament_service.is_admin(user_id):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('home_page'))

    # Delete the announcement
    success = announcement_service.delete_announcement(announcement_id)

    if success:
        flash('Announcement deleted successfully', 'success')
    else:
        flash('Failed to delete announcement', 'error')

    return redirect(url_for('admin_announcements_page'))

# API route to get announcements
@app.route('/api/announcements', methods=['GET'])
def api_get_announcements():
    limit = request.args.get('limit', 5, type=int)
    announcements = announcement_service.get_all_announcements(limit=limit)
    return jsonify({'success': True, 'announcements': announcements})

# Cached search data function
@cache.memoize(timeout=600)  # Cache for 10 minutes
def get_search_data():
    """Get search data with caching"""
    players = get_cached_all_players()
    tournaments, _ = get_cached_tournaments()
    return players, tournaments

# API route for global search
@app.route('/api/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify({'success': False, 'message': 'Query too short'})

    results = []

    # Get cached search data
    players, tournaments = get_search_data()

    # Search for players
    for player in players:
        if query.lower() in player['display_name'].lower():
            results.append({
                'category': 'Players',
                'title': player['display_name'],
                'subtitle': f"{player['primary_game_name']} • {player['total_wins']} wins",
                'url': f"/players?search={player['display_name']}"
            })

    # Search for tournaments
    for tournament in tournaments:
        if query.lower() in tournament['name'].lower() or query.lower() in tournament['description'].lower():
            results.append({
                'category': 'Tournaments',
                'title': tournament['name'],
                'subtitle': f"{tournament['date']} • {tournament['status']}",
                'url': f"/tournaments?id={tournament['id']}"
            })

    # Search for games
    games = [
        {'id': 'mario-kart', 'name': 'Mario Kart', 'description': 'Racing game featuring Mario characters'},
        {'id': 'smash-bros', 'name': 'Super Smash Bros', 'description': 'Fighting game with Nintendo characters'}
    ]

    for game in games:
        if query.lower() in game['name'].lower() or query.lower() in game['description'].lower():
            results.append({
                'category': 'Games',
                'title': game['name'],
                'subtitle': game['description'],
                'url': f"/leaderboard/{game['id']}"
            })

    # Limit results
    results = results[:10]

    return jsonify({'success': True, 'results': results})

# Initialize data for both local development and Vercel deployment
# Initialize admin user
init_admin_user()

# Initialize user stats
init_user_stats()

if __name__ == '__main__':
    # Run the app only when executed directly (not when imported by vercel_app.py)
    app.run(debug=True)

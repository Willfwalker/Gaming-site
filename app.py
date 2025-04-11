import os
import json
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, Response
from datetime import datetime
from services.firebase_auth_service import FirebaseAuthService
from services.tournament_service import TournamentService
from services.user_stats_service import UserStatsService
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import auth, firestore

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

firebase_auth = FirebaseAuthService(app)

# Initialize Firestore database
db = firestore.client()

# Initialize services
tournament_service = TournamentService(db)
user_stats_service = UserStatsService(db)

@app.route('/', methods=['GET'])
def home():
    return redirect(url_for('leaderboard_page'))

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

            return redirect(url_for('leaderboard_page'))
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
    return redirect(url_for('login_view'))

@app.route('/')
@app.route('/home')
def home_page():
    return render_template('home.html')

@app.route('/leaderboard', methods=['GET'])
def leaderboard_page():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access the leaderboard', 'error')
        return redirect(url_for('login_view'))

    # Get leaderboards for each game type
    mario_kart_leaderboard = user_stats_service.get_leaderboard('mario-kart', 5)
    smash_bros_leaderboard = user_stats_service.get_leaderboard('smash-bros', 5)

    return render_template('leaderboard.html',
                           mario_kart_leaderboard=mario_kart_leaderboard,
                           smash_bros_leaderboard=smash_bros_leaderboard)

@app.route('/tournaments', methods=['GET'])
def tournaments_page():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login to access tournaments', 'error')
        return redirect(url_for('login_view'))

    # Get tournaments from service
    tournaments, featured_tournament = tournament_service.get_all_tournaments()

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
    if not tournament_service.is_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Get tournament data from request
    tournament_data = request.json

    # Create tournament
    result, status_code = tournament_service.create_tournament(tournament_data)

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
    if not tournament_service.is_admin(user_id):
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403

    # Get tournament data from request
    tournament_data = request.json

    # Update tournament
    result, status_code = tournament_service.update_tournament(tournament_id, tournament_data)

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

    # Get leaderboard for the specified game type
    leaderboard = user_stats_service.get_leaderboard(game_type, 10)

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

# Initialize data for both local development and Vercel deployment
# Initialize admin user
init_admin_user()

# Initialize user stats
init_user_stats()

if __name__ == '__main__':
    # Run the app only when executed directly (not when imported by vercel_app.py)
    app.run(debug=True)

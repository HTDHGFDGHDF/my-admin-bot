import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# FIX: User database is moved to environment variables for better security and scalability.
# In your environment (.env file or server settings), you would define variables like:
# USER_KEY_1="key-for-admin-one"
# USER_NAME_1="Mr.NOOB"
# USER_KEY_2="key-for-admin-two"
# USER_NAME_2="Mr.Pro"
# This is a simplified example; a real database would be a better solution for many users.
def load_users_from_env():
    users = {}
    i = 1
    while True:
        key = os.environ.get(f'USER_KEY_{i}')
        name = os.environ.get(f'USER_NAME_{i}')
        if key and name:
            users[key] = {"name": name}
            i += 1
        else:
            break
    return users

user_database = load_users_from_env()

@app.route('/execute-command', methods=['POST'])
def execute_command():
    # This check is perfect, no changes needed.
    data = request.get_json()
    if not data or 'userKey' not in data or 'fullCommand' not in data:
        return jsonify({"success": False, "message": "Invalid request format."}), 400

    user_key = data.get('userKey')
    
    # Logic remains the same, but it now uses the user_database loaded from environment variables.
    if user_key not in user_database:
        return jsonify({"success": False, "message": "Authentication Failed: Invalid Key"}), 401

    try:
        # This part is handled securely, no changes needed.
        wabbit_api_key = os.environ.get('WABBITBOT_API_KEY')
        if not wabbit_api_key:
            return jsonify({"success": False, "message": "SERVER ERROR: WabbitBot API Key is not configured."}), 500

        full_command = data.get('fullCommand')
        
        # This logic is sound, assuming commands have a prefix. No changes needed.
        command_parts = full_command.split(' ')
        command_to_send = " ".join(command_parts[1:])

        wabbit_api_url = 'https://integrations.wabbit.gg/api/starve/commands'

        # This request is well-formed, no changes needed.
        response = requests.post(
            wabbit_api_url,
            headers={'x-api-key': wabbit_api_key, 'Content-Type': 'application/json'},
            json={'commands': [command_to_send]},
            timeout=10
        )
        
        # Raising an exception for bad status codes is a good practice.
        response.raise_for_status() # This will raise an HTTPError for 4xx or 5xx responses.
        
        response_data = response.json()

        # Response handling is robust, no changes needed.
        if response_data.get('operation', {}).get('ok'):
            success_msg = response_data.get('result', [None, None, None, 'Success!'])[3]
            return jsonify({"success": True, "message": success_msg})
        else:
            error_msg = response_data.get('operation', {}).get('error', 'Unknown Error.')
            return jsonify({"success": False, "message": f"API Error: {error_msg}"})

    # Added specific handling for request exceptions.
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"API request failed: {e}"}), 503 # 503 Service Unavailable
    except Exception as e:
        # General error handling is excellent.
        return jsonify({"success": False, "message": f"Critical server error: {e}"}), 500

@app.route('/')
def home():
    return "Bot server is alive and listening."

# This block is perfect for local testing.
if __name__ == "__main__":
    # Note: For production, user keys should be loaded securely from the environment.
    # The 'load_users_from_env' function does this. Ensure your environment variables are set.
    if not user_database:
        print("Warning: No user keys found in environment variables (e.g., USER_KEY_1, USER_NAME_1).")
    app.run(debug=True)
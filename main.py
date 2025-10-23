import os
import requests
import secrets
import discord
from discord.ext import commands
from flask import Flask, request, jsonify
from flask_cors import CORS
from upstash_redis import Redis
from threading import Thread

# ===============================================
# PART 1: SETUP - CONNECT TO THE SECURE DATABASE
# ===============================================

# This is secure. It reads the connection details from Render's secrets.
redis = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"),
)

# ===============================================
# PART 2: THE WEB SERVER (for Tampermonkey)
# ===============================================
app = Flask(__name__)
CORS(app)

@app.route('/execute-command', methods=['POST'])
def execute_command_route():
    data = request.get_json()
    user_key = data.get('userKey')
    full_command = data.get('fullCommand')

    if not user_key or not full_command:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    # AUTHENTICATION: Check if the key exists in our database
    user_id = redis.hget("keys", user_key)
    if not user_id:
        return jsonify({"success": False, "message": "Authentication Failed: Invalid Key"}), 401

    # AUTHORIZATION: Check user permissions
    user_data = redis.hgetall(f"user:{user_id}") or {}
    allowed_servers = (user_data.get("servers") or "").split(',')
    
    parts = full_command.split()
    server_name = parts[0].lower()
    
    if server_name not in allowed_servers and "*" not in allowed_servers:
         return jsonify({"success": False, "message": f"Permission Denied: No access to server '{server_name}'."}), 403

    # EXECUTION: Get server's API key and run the command
    wabbit_api_key = redis.hget("servers", server_name)
    if not wabbit_api_key:
         return jsonify({"success": False, "message": f"Server Error: '{server_name}' is not configured."}), 404

    try:
        command_to_send = " ".join(parts[1:])
        response = requests.post(
            'https://integrations.wabbit.gg/api/starve/commands',
            headers={'x-api-key': wabbit_api_key, 'Content-Type': 'application/json'},
            json={'commands': [command_to_send]}
        )
        response_data = response.json()

        if response_data.get('operation', {}).get('ok'):
            msg = response_data.get('result', [None, None, None, 'Success!'])[3]
            return jsonify({"success": True, "message": msg})
        else:
            err = response_data.get('operation', {}).get('error', 'Unknown Error.')
            return jsonify({"success": False, "message": f"API Error: {err}"})

    except Exception as e:
        return jsonify({"success": False, "message": "A critical server error occurred."}), 500

def run_flask_app():
    app.run(host='0.0.0.0', port=10000) # Render uses port 10000

# ===============================================
# PART 3: THE DISCORD BOT (The Management Interface)
# ===============================================
bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f"Secure Discord Bot ONLINE as {bot.user}")

@bot.slash_command(name="add_server", description="Configure a server with its WabbitBot API key.")
async def add_server(ctx, server_name: str, api_key: str):
    redis.hset("servers", {server_name.lower(): api_key})
    await ctx.respond(f"✅ Server '{server_name.lower()}' has been configured.", ephemeral=True)

@bot.slash_command(name="grant_access", description="Grant a user access to servers (e.g., server1,server2 or * for all).")
async def grant_access(ctx, user: discord.Member, servers: str):
    user_id = str(user.id)
    server_list_str = servers.lower()

    # Get user data or create a new profile
    user_data = redis.hgetall(f"user:{user_id}") or {}
    
    # Generate a key if they don't have one
    if "key" not in user_data:
        new_key = secrets.token_hex(24)
        user_data["key"] = new_key
        redis.hset("keys", {new_key: user_id})

    # Set their server permissions
    user_data["servers"] = server_list_str
    redis.hset(f"user:{user_id}", user_data)
    
    await user.send(f"🔑 **Admin Access Update**\n\nYour secret key is: `{user_data['key']}`\nYou have access to servers: `{server_list_str}`")
    await ctx.respond(f"✅ Access granted for {user.mention}. Key sent via DM.", ephemeral=True)

@bot.slash_command(name="revoke_all_access", description="Completely revoke a user's admin key and all permissions.")
async def revoke_all_access(ctx, user: discord.Member):
    user_id = str(user.id)
    user_data = redis.hgetall(f"user:{user_id}")
    if user_data and "key" in user_data:
        redis.hdel("keys", user_data["key"]) # Delete the login key
    redis.delete(f"user:{user_id}") # Delete their user profile
    await ctx.respond(f"🔥 All permissions for {user.mention} have been permanently revoked.", ephemeral=True)

# ===============================================
# PART 4: STARTING EVERYTHING
# ===============================================
flask_thread = Thread(target=run_flask_app)
flask_thread.start()
bot.run(os.environ.get('DISCORD_BOT_TOKEN'))

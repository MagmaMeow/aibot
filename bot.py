import os
import threading
import asyncio
import discord
from discord.ext import commands
import google.generativeai as genai
from flask import Flask, request, render_template_string, Response

# =========================
# --- Load from Environment
# =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# =========================
# --- Gemini Setup
# =========================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# =========================
# --- Discord Bot Setup
# =========================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

# =========================
# --- Global State
# =========================
chat_active = False
chat_history = []
sudo_blacklist = set()
SUDO_PASSWORD = "Parker"

# =========================
# --- Flask Web Panel
# =========================
app = Flask(__name__)
USERNAME = "magma"
PASSWORD = "marrow"

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response("❌ Authentication required.", 401,
                    {"WWW-Authenticate": 'Basic realm="Login Required"'})

@app.before_request
def require_auth():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Bot Control Shell</title>
<style>
body { background:#121212; color:#fff; font-family:monospace; padding:20px; }
input { width:80%%; padding:10px; border:none; margin-top:10px; }
button { padding:10px; background:#1db954; border:none; color:#fff; cursor:pointer; }
.log { margin-top:20px; padding:10px; background:#222; }
</style>
</head>
<body>
<h1>🤖 Bot Control Shell</h1>
<form method="post">
<input type="text" name="command" placeholder="Enter command (set/reset/aauthnot/rmove)" autofocus>
<button type="submit">Run</button>
</form>
<div class="log">
<p><b>Last Response:</b></p>
<p>{{ response }}</p>
</div>
</body>
</html>
"""

last_response = "No command run yet."

@app.route("/", methods=["GET", "POST"])
def control_panel():
    global chat_active, chat_history, last_response
    if request.method == "POST":
        cmd = request.form.get("command", "").strip().lower()
        if cmd == "set":
            chat_active = True
            chat_history = []
            last_response = "🤖 Bot bound (responding to all messages)."
        elif cmd == "reset":
            chat_history = []
            last_response = "🔄 Conversation reset."
        elif cmd == "aauthnot":
            chat_active = False
            last_response = "🛑 Bot unbound (no longer auto-responding)."
        elif cmd == "rmove":
            last_response = "👋 Use .rmove in Discord to remove the bot from a server."
        else:
            last_response = f"⚠️ Unknown command: {cmd}"
    return render_template_string(HTML_TEMPLATE, response=last_response)

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# =========================
# --- Discord Events
# =========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# =========================
# --- AI Commands
# =========================
@bot.command()
async def set(ctx):
    global chat_active, chat_history
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You don’t have permission to use this.")
    chat_active = True
    chat_history = []
    await ctx.send("🤖 AI bot is now bound to respond to every message.")

@bot.command()
async def reset(ctx):
    global chat_history
    chat_history = []
    await ctx.send("🔄 Conversation reset.")

@bot.command()
async def aauthnot(ctx):
    global chat_active
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You don’t have permission to use this.")
    chat_active = False
    await ctx.send("🛑 AI bot has been unbound (no longer auto-responding).")

@bot.command()
async def rmove(ctx):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You don’t have permission to use this.")
    await ctx.send("👋 Leaving this server now...")
    await ctx.guild.leave()

# =========================
# --- Sudo System
# =========================
@bot.command()
async def sudo(ctx, password: str, *, command: str = None):
    global chat_active
    if ctx.author.id in sudo_blacklist:
        return await ctx.send("⛔ You are banned from using sudo.")
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Only my owner can use sudo.")
    if password != SUDO_PASSWORD:
        return await ctx.send("❌ Wrong sudo password.")
    if not command:
        return await ctx.send("⚡ Provide a command. Example: .sudo Parker help")

    command = command.lower()

    if command == "help":
        cmds = [
            "ban <@user> - Ban a user from sudo",
            "unban <@user> - Unban a user from sudo",
            "list - List all blacklisted users",
            "say <msg> - Make the bot say something",
            "purge <n> - Delete n messages",
            "kick <@user> - Kick a user",
            "nick <@user> <name> - Change nickname",
            "shutdown - Shutdown bot",
            "bind - Activate auto-reply",
            "unbind - Deactivate auto-reply",
        ]
        await ctx.send("📜 **Sudo Commands:**\n" + "\n".join(cmds))

    elif command.startswith("ban"):
        if ctx.message.mentions:
            user = ctx.message.mentions[0]
            sudo_blacklist.add(user.id)
            await ctx.send(f"⛔ {user} has been banned from sudo.")
        else:
            await ctx.send("⚠️ Mention a user to ban.")

    elif command.startswith("unban"):
        if ctx.message.mentions:
            user = ctx.message.mentions[0]
            sudo_blacklist.discard(user.id)
            await ctx.send(f"✅ {user} has been unbanned from sudo.")
        else:
            await ctx.send("⚠️ Mention a user to unban.")

    elif command == "list":
        if not sudo_blacklist:
            await ctx.send("✅ No one is blacklisted.")
        else:
            users = [f"<@{uid}>" for uid in sudo_blacklist]
            await ctx.send("⛔ Blacklisted users:\n" + "\n".join(users))

    elif command.startswith("say"):
        msg = command.replace("say", "", 1).strip()
        await ctx.send(msg)

    elif command.startswith("purge"):
        try:
            n = int(command.split()[1])
            await ctx.channel.purge(limit=n+1)
            await ctx.send(f"🧹 Deleted {n} messages.")
        except:
            await ctx.send("⚠️ Usage: .sudo Parker purge <n>")

    elif command.startswith("kick"):
        if ctx.message.mentions:
            user = ctx.message.mentions[0]
            await ctx.guild.kick(user)
            await ctx.send(f"👢 Kicked {user}")
        else:
            await ctx.send("⚠️ Mention a user to kick.")

    elif command.startswith("nick"):
        parts = command.split()
        if len(parts) >= 3 and ctx.message.mentions:
            user = ctx.message.mentions[0]
            new_name = " ".join(parts[2:])
            await user.edit(nick=new_name)
            await ctx.send(f"✏️ Changed {user}'s nickname to {new_name}")
        else:
            await ctx.send("⚠️ Usage: .sudo Parker nick @user NewName")

    elif command == "shutdown":
        await ctx.send("⚡ Shutting down...")
        await bot.close()

    elif command == "bind":
        chat_active = True
        await ctx.send("🤖 AI auto-reply activated.")

    elif command == "unbind":
        chat_active = False
        await ctx.send("🛑 AI auto-reply deactivated.")

    else:
        await ctx.send("⚠️ Unknown sudo command.")

# =========================
# --- AI Auto Reply
# =========================
async def generate_ai_reply(history):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: model.generate_content(history))

@bot.event
async def on_message(message):
    global chat_history, chat_active
    if message.author.bot:
        return

    # Always process commands first
    await bot.process_commands(message)

    if message.author

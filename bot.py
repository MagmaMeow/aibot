import discord
from discord.ext import commands
import google.generativeai as genai
import os
from flask import Flask, request, render_template_string
import threading

# --- Load from environment ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Gemini Setup ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# --- Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

# Conversation state
chat_active = False
chat_history = []

# --- Flask App for Web Service ---
app = Flask(__name__)

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
            last_response = "👋 Bot will leave the server (use inside Discord)."
        else:
            last_response = f"⚠️ Unknown command: {cmd}"
    return render_template_string(HTML_TEMPLATE, response=last_response)


def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# --- Discord Bot Events ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


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


@bot.event
async def on_message(message):
    global chat_history, chat_active

    if message.author.bot:
        return
    await bot.process_commands(message)

    if chat_active:
        chat_history.append({"role": "user", "content": message.content})
        try:
            response = model.generate_content(chat_history)
            reply = response.text
            chat_history.append({"role": "assistant", "content": reply})
            await message.channel.send(reply)
        except Exception as e:
            await message.channel.send(f"⚠️ Error: {e}")


# --- Start both Flask and Discord ---
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(DISCORD_TOKEN)

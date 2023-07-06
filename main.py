import os
import json
import datetime
import pytz
from html_parser import html_to_text
import logging.handlers
import discord
import asyncio
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.INFO)


handler = logging.handlers.RotatingFileHandler(
    filename="discord.log",
    encoding="utf-8",
    maxBytes=32 * 1024 * 1024,
    backupCount=5,  # Rotate through 5 files
)
dt_fmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# Discord bot token
DISCORD_BOT_TOKEN = os.getenv("DICORD_BOT_TOKEN")

# Google Calendar API credentials
SERVICE_ACCOUNT_CREDS = r"H:/PROGRAMS/metagpt/web/SERVICE_ACCOUNT_CREDENTIALS.json"
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")


intents = discord.Intents.all()
intents.message_content = True
intents.members = True
# Bot prefix
bot = commands.Bot(command_prefix="!", intents=intents)
events = []


# Manual command sync command, owner only, guild specific
@bot.hybrid_command()
async def sync(ctx):
    if str(ctx.author.id) == "498248765698867201":
        bot.tree.copy_global_to(guild=discord.Object(id=1123547534074314936))
        await bot.tree.sync(guild=discord.Object(id=1123547534074314936))
        await ctx.send("Synced!")
    else:
        await ctx.send("Sorry, only the bot owner can execute this command.")


# Load users' notification settings from JSON file
with open("userslist.json", "r") as file:
    users = json.load(file)


# Helper function to save users' notification settings to JSON file
def save_users_list():
    with open("userslist.json", "w") as file:
        json.dump(users, file, indent=4)


# Helper function to retrieve upcoming events from Google Calendar
def get_upcoming_events(max_results=10):
    with open("H:\PROGRAMS\metagpt\web\SERVICE_ACCOUNT_CREDENTIALS.json") as f:
        creds = Credentials.from_service_account_info(json.load(f))
    service = build("calendar", "v3", credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
    events_result = (
        service.events()
        .list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


# Helper function to send DM notification to users
from html_parser import html_to_text


async def send_notification(user_id, event):
    print("send_notification function called")
    logger.info("send_notification function called")
    if isinstance(event, dict):
        print("event is a dictionary")
    else:
        print("event is not a dictionary")
        print(event)
    try:
        if "summary" in event and event["summary"]:
            user = await bot.fetch_user(user_id)
            print(f"User object: {user}")
            logger.info(f"User object: {user}")

            # Extract event details
            event_title = event["summary"]
            event_start = datetime.datetime.fromisoformat(event["start"]["dateTime"])
            event_start_str = event_start.strftime(
                "%B %d %Y at %I:%M %p"
            )  # Format the start time
            event_details = event.get(
                "description", ""
            )  # Use an empty string if there are no details

            # Convert HTML to markdown
            event_details = html_to_text(event_details)

            # Format the message
            message = f"Event Title: {event_title} at {event_start_str}\nEvent Details: {event_details}"

            await user.send(message)
            logger.info("Notification sent")
            print("Notification sent")
        else:
            logger.error("Invalid event data: missing or empty 'summary' key")
            print("Invalid event data: missing or empty 'summary' key")
    except Exception as e:
        logger.exception(f"An error occurred while sending notification: {str(e)}")


# Discord bot event - Bot is ready
@bot.event
async def on_ready():
    print("Bot is ready")
    check_events.start()


# Discord bot command - Opt In for notifications
@bot.hybrid_command()
async def opt_in(ctx):
    user_id = ctx.author.id

    # Check if user is already opted in
    if str(user_id) in users:
        await ctx.send("You are already opted in!")
    else:
        users[str(user_id)] = {"notification_time": None}
        save_users_list()
        await ctx.send("You are now opted in for notifications!")


# Discord bot command - Opt Out from notifications
@bot.hybrid_command()
async def opt_out(ctx):
    user_id = ctx.author.id

    # Check if user is already opted out
    if str(user_id) not in users:
        await ctx.send("You are already opted out!")
    else:
        del users[str(user_id)]
        save_users_list()
        await ctx.send("You are now opted out from notifications!")


# Discord bot command - Set notification time
@bot.hybrid_command()
async def set_notification(ctx, time_minutes: int):
    user_id = ctx.author.id

    # Check if user is opted in
    if str(user_id) not in users:
        await ctx.send("You need to opt in first!")
        return

    # Check if time_minutes is within the allowed range
    if time_minutes < 5 or time_minutes > 5 * 24 * 60:
        await ctx.send(
            "Invalid notification time. Must be between 5 minutes and 5 days."
        )
        return

    users[str(user_id)]["notification_time"] = time_minutes
    save_users_list()
    await ctx.send(f"Notification time set to {time_minutes} minutes.")


# Discord bot command - List upcoming events
@bot.hybrid_command()
async def list_events(ctx):
    events = get_upcoming_events(max_results=7)
    if not events:
        await ctx.send("No upcoming events found.")
        return

    output = "Upcoming events:\n"
    for event in events:
        start = datetime.datetime.fromisoformat(
            event["start"].get("dateTime", event["start"].get("date"))
        )
        start_str = start.strftime("%B %d %Y at %I:%M %p")
        event_details = event.get("description", "")
        event_details = html_to_text(event_details)
        output += (
            f"- {event['summary']}: {start_str}. Event Details - {event_details}\n"
        )

    await ctx.send(output)


@tasks.loop(minutes=60)
async def fetch_events():
    global events
    events = get_upcoming_events(max_results=50)  # Increase max_results if needed


@tasks.loop(minutes=5)
async def check_notifications():
    current_time = datetime.datetime.now(pytz.timezone("America/Los_Angeles"))

    # Load users list
    with open("userslist.json") as f:
        users = json.load(f)

    # Iterate through users and their notification settings
    for user_id, settings in users.items():
        notification_time = settings["notification_time"]

        # Skip users with no notification time set
        if notification_time is None:
            continue

        # Calculate the cutoff time for sending notifications
        cutoff_time = current_time + datetime.timedelta(minutes=notification_time)

        # Iterate through the events and notify users if needed
        for event in events:
            event_start = datetime.datetime.fromisoformat(event["start"]["dateTime"])
            if event_start > current_time and event_start <= cutoff_time:
                await send_notification(user_id, event)


# Background task - Check and send notifications
@tasks.loop(minutes=60)  # Adjust the interval according to your needs
async def check_events():
    current_time = datetime.datetime.now(pytz.timezone("America/Los_Angeles"))

    # Iterate through users and their notification settings
    for user_id, settings in users.items():
        notification_time = settings["notification_time"]

        # Skip users with no notification time set
        if notification_time is None:
            continue

        # Calculate the cutoff time for sending notifications
        cutoff_time = current_time + datetime.timedelta(minutes=notification_time)

        # Retrieve upcoming events
        events = get_upcoming_events(max_results=50)  # Increase max_results if needed

        # Iterate through the events and notify users if needed
        for event in events:
            event_start = datetime.datetime.fromisoformat(event["start"]["dateTime"])
            if event_start > current_time and event_start <= cutoff_time:
                await send_notification(user_id, event)


async def main():
    await bot.login(os.getenv("DISCORD_BOT_TOKEN"))
    await bot.connect()


while True:
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")

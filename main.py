import json
import os
import datetime
import pytz
import aiohttp
from pytz import timezone
from html_parser import html_to_text
import logging.handlers
import discord
import asyncio
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import schedule
import time
import subprocess

# LOGGING
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    filename="discord.log",
    encoding="utf-8",
    maxBytes=32 * 1024 * 1024,
    backupCount=5,
)
dt_fmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
)
handler.setFormatter(formatter)
logger.addHandler(handler)



DISCORD_BOT_TOKEN = os.getenv("BOT_TOKEN_TESTER")
SERVICE_ACCOUNT_CREDS = r"H:/PROGRAMS/metagpt/web/SERVICE_ACCOUNT_CREDENTIALS.json"
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
events = []
responded_messages = set()
session = None

async def create_session():
    global session
    session = aiohttp.ClientSession()
async def close_session():
    await session.close()
    await session.close()
async def main():
    await create_session()
    await bot.login(os.getenv("BOT_TOKEN_TESTER"))
    await bot.connect()
    await session.close()


# scraper, runs at 8am every morning.
def run_script(script_path):
    subprocess.call(['python', script_path])

    schedule.every().day.at("08:00").do(run_script, script_path='H:/PROGRAMS/adjutanto/scrapers/amLeague_scraper.py')
    schedule.every().day.at("08:00").do(run_script, script_path='H:/PROGRAMS/adjutanto/scrapers/cranky_scraper.py')
    schedule.every().day.at("08:00").do(run_script, script_path='H:/PROGRAMS/adjutanto/scrapers/designedkiller_scraper.py')
    schedule.every().day.at("08:00").do(run_script, script_path='H:/PROGRAMS/adjutanto/scrapers/mallkus_scraper.py')

    # keep it on
    while True:
        schedule.run_pending()
        time.sleep(1)


# Manual sync command, owner only, guild specific
@bot.hybrid_command()
async def sync(ctx):
    if str(ctx.author.id) == "498248765698867201":
        bot.tree.copy_global_to(guild=discord.Object(id=643684572428500992))
        await bot.tree.sync(guild=discord.Object(id=643684572428500992))
        await ctx.send("Synced!")
    else:
        await ctx.send("Sorry, only the bot owner can execute this command.")


# Load user from JSON 
with open("userslist.json", "r") as file:
    users = json.load(file)


#  save user notification to JSON 
def save_users_list():
    with open("userslist.json", "w") as file:
        json.dump(users, file, indent=4)


# retrieve upcoming events from Calendar
def get_upcoming_events(max_results=10):
    with open("H:\PROGRAMS\metagpt\web\SERVICE_ACCOUNT_CREDENTIALS.json") as f:
        creds = Credentials.from_service_account_info(json.load(f))
    service = build("calendar", "v3", credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + "Z"
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


# Sending of direct messages
async def send_notification(user_id, event, tz):
    print("send_notification function called")
    logger.info("send_notification function called")
    # Get user's chosen MMR range
    user = users[str(user_id)]
    mmr_range = user.get("mmr_range")
    # Check event title for MMR tag
    event_title = event["summary"]
    if "Plat" in event_title and mmr_range != "Platinum":
        return
    elif "Dia" in event_title and mmr_range != "Diamond":
        return
    elif "Masters" in event_title and mmr_range != "Masters":
        return
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
            event_start = datetime.datetime.fromisoformat(event["start"]["dateTime"]).astimezone(tz)
            event_start_str = event_start.strftime(
                "%B %d %Y at %I:%M %p"
            )  # Format the start time
            event_details = event.get("description", "")
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


# Opt In
@bot.hybrid_command()
async def opt_in(ctx):
    user_id = ctx.author.id
    if str(user_id) in users:
        await ctx.send("You are already opted in!")
    else:
        users[str(user_id)] = {"notification_time": None}
        save_users_list()
        await ctx.send("You are now opted in for notifications!")


# Opt Out
@bot.hybrid_command()
async def opt_out(ctx):
    user_id = ctx.author.id
    if str(user_id) not in users:
        await ctx.send("You are already opted out!")
    else:
        del users[str(user_id)]
        save_users_list()
        await ctx.send("You are now opted out from notifications!")


# OMG Buttons!!!!!!!!!!!!!!!!!!!
class TimeZoneButtons(discord.ui.View):
    def __init__(self, *, timeout=None):
        super().__init__(timeout=timeout)
        
        
    @discord.ui.button(label="America/Los_Angeles", style=discord.ButtonStyle.primary)
    async def pacific_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "America/Los_Angeles"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Pacific Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")
            
            
    @discord.ui.button(label="America/Denver", style=discord.ButtonStyle.primary)
    async def mountain_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "America/Denver"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Mountain Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")

        
    @discord.ui.button(label="America/Chicago", style=discord.ButtonStyle.primary)
    async def central_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "America/Chicago"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Central Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


    @discord.ui.button(label="America/New_York", style=discord.ButtonStyle.primary)
    async def eastern_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "America/New_York"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Eastern Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


    @discord.ui.button(label="Europe/London", style=discord.ButtonStyle.primary)
    async def greenwich_mean_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Europe/London"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Greenwich Mean Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


    @discord.ui.button(label="Europe/Paris", style=discord.ButtonStyle.primary)
    async def central_european_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Europe/Paris"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Central European Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")
            

    @discord.ui.button(label="Asia/Dubai", style=discord.ButtonStyle.primary)
    async def united_arab_emirates_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Asia/Dubai"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to United Arab Emirates Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


    @discord.ui.button(label="Asia/Tokyo", style=discord.ButtonStyle.primary)
    async def japan_standard_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Asia/Tokyo"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Japan Standard Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


    @discord.ui.button(label="Asia/Kolkata", style=discord.ButtonStyle.primary)
    async def india_standard_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Asia/Kolkata"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to India Standard Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


    @discord.ui.button(label="Australia/Sydney", style=discord.ButtonStyle.primary)
    async def australian_eastern_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Australia/Sydney"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Australian Eastern Time.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


@bot.hybrid_command()
async def set_notification(ctx, time_minutes: int,):
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

    # Ask for user's time zone
    await ctx.send("Please select your time zone:", view=TimeZoneButtons())


# List upcoming events
@bot.hybrid_command()
async def list_events(ctx):
    events = get_upcoming_events(max_results=7)
    if not events:
        await ctx.send("No upcoming events found.")
        return
    embed = discord.Embed(
        title="Upcoming Events",
        color=0x00FF00
    )
    for event in events:
        start = datetime.datetime.fromisoformat(event["start"].get("dateTime", event["start"].get("date")))
        start_str = start.strftime("%B %d %Y at %I:%M %p")
        event_details = event.get("description", "")
        event_details = html_to_text(event_details)
        embed.add_field(
            name=event["summary"], 
            value=f"{start_str}\n{event_details}",
            inline=False
        )
    await ctx.send(embed=embed)


# 3 minutes loop de loop
@tasks.loop(minutes=3)
async def check_notifications():
    # Load users list
    with open("userslist.json") as f:
        users = json.load(f)

    # Iterate through users 
    for user_id, settings in users.items():
        notification_time = settings["notification_time"]
        user_time_zone = settings.get("time_zone", "America/Indiana/Tell_City")
        tz = timezone(user_time_zone)

        # Skip users with no notification time set
        if notification_time is None:
            continue

        current_time = datetime.datetime.now(tz)
        cutoff_time = current_time + datetime.timedelta(minutes=notification_time)

        # Iterate through the events and notify users if needed
        for event in events:
            event_start = tz.localize(datetime.datetime.fromisoformat(event["start"]["dateTime"]))
            if event_start > current_time and event_start <= cutoff_time:
                await send_notification(user_id, event, tz)


# Check and send notifications
@tasks.loop(minutes=60)  # Adjust the interval according to your needs
async def check_events():
    # Iterate through users and their notification settings
    for user_id, settings in users.items():
        tz = pytz.timezone(settings.get("time_zone", "America/Indiana/Tell_City"))
        current_time = datetime.datetime.now(tz)

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
            event_start = datetime.datetime.fromisoformat(event["start"]["dateTime"]).astimezone(tz)
            if event_start > current_time and event_start <= cutoff_time:
                await send_notification(user_id, event, tz)


#skill buttons
class MMRRangeButtons(discord.ui.View):

    @discord.ui.button(label="Basic/Diamond and below")
    async def platinum(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        users[user_id]["mmr_range"] = "basic"
        save_users_list()
        await interaction.response.send_message("MMR range set to Platinum")

    @discord.ui.button(label="Minor/High diamond/Masters") 
    async def diamond(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        users[user_id]["mmr_range"] = "minor"
        save_users_list()
        await interaction.response.send_message("MMR range set to Diamond")

    @discord.ui.button(label="Major/Masters and Up")
    async def masters(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        users[user_id]["mmr_range"] = "major"
        save_users_list()
        await interaction.response.send_message("MMR range set to Masters+")
        
        
    @discord.ui.button(label="Open/GM")
    async def masters(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        users[user_id]["mmr_range"] = "Open/GM"
        save_users_list()
        await interaction.response.send_message("MMR range set to Open/GM")

@bot.hybrid_command()
async def set_mmr_range(ctx):
    await ctx.send("Select your MMR range:", view=MMRRangeButtons())

# Fancy embed
@bot.hybrid_command()
async def embed(ctx):
    embed = discord.Embed(
        title="Usage",
        description="**Step 1.** -__/Opt_in__\n"
        "**Step 2.** - __/Set_Notification__\n"
        "This is the amount of time prior to an event in which youd like to be notified. It must be within a range of 5 minutes to 5 days.*\n\n"
        "**Other Commands**\n"
        "- __/Opt_out__ -Remove yourself from the notification list\n\n"
        "- __/List_Events__ - Lists the next 7 days worth of events.",
        colour=0xD70909,
        timestamp=datetime.datetime.now(),
    )
    embed.set_author(name="Adjutant", icon_url="https://imgur.com/15xTN3R.jpg")
    embed.add_field(
        name="Currently in beta",
        value="*There will be some bugs to work out. Please let me know if you run into any issues.*",
    )
    embed.set_image(url="https://imgur.com/msNei0f.jpg")
    embed.set_thumbnail(url="https://imgur.com/msNei0f.jpg")
    embed.set_footer(text="The Adjutant/{}".format(ctx.author.display_name))
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print("Bot is ready")
    check_events.start()

@bot.event
async def on_disconnect():
    await close_session(session)
while True:
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
        
        
import os
import json
import datetime
import pytz
from pytz import timezone
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

# set to keep track of responded message IDs(for sync command)
responded_messages = set()


# Manual sync command, owner only, guild specific
@bot.hybrid_command()
async def sync(ctx):
    if str(ctx.author.id) == "498248765698867201":
        bot.tree.copy_global_to(guild=discord.Object(id=1123547534074314936))
        await bot.tree.sync(guild=discord.Object(id=1123547534074314936))
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



@bot.event
async def on_ready():
    print("Bot is ready")
    check_events.start()


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


# 3 minutes loop to send notifications
@tasks.loop(minutes=3)
async def check_notifications():
    # Load users list
    with open("userslist.json") as f:
        users = json.load(f)

    # Iterate through users and their notification settings
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


# Background task - Check and send notifications
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


async def main():
    await bot.login(os.getenv("DISCORD_BOT_TOKEN"))
    await bot.connect()
while True:
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
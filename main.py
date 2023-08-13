import os
import json
import datetime
import time
import pytz
from pytz import timezone
from html_parser import html_to_text
import logging.handlers
import discord
import asyncio
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dateutil.parser import parse
from dateutil.tz import gettz


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


DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SERVICE_ACCOUNT_CREDENTIALS = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
responded_messages = set()
synced = False     
sent_notifications = set()


@tasks.loop(minutes=3)
async def check_notifications():
    DEFAULT_NOTIFICATION_TIME = 60 # in minutes
    with open("userslist.json", "r") as file:
        users = json.load(file)
    current_time = time.time() 
    events = get_upcoming_events() 
    for user_id, user_data in users.items():
        alert_time = user_data.get('notification_time', DEFAULT_NOTIFICATION_TIME) * 60
        user_time_zone = user_data['time_zone'] 
        for event in events:  # Loop through all events
            event_time = parse(event['start']['dateTime']).astimezone(gettz(user_time_zone)).timestamp()
            diff_time = event_time - current_time
            if 0 <= diff_time <= alert_time and (user_id, event['id']) not in sent_notifications:
                await send_notification(user_id, event, user_time_zone)
                sent_notifications.add((user_id, event['id']))


@tasks.loop(minutes=60)                                                                                               # Background task Check notifications
async def check_events():
    global events
    events = get_upcoming_events(max_results=50)


@tasks.loop(hours=24)
async def clear_sent_notifications():
    sent_notifications.clear()


@bot.event
async def on_ready():
    print("Bot is ready")
    check_notifications.start()
    check_events.start()
    clear_sent_notifications.start()


@bot.hybrid_command()                                                                                                  # Manual sync command, owner only, guild specificsynced = False
async def sync(ctx):
    global synced
    if str(ctx.author.id) == "498248765698867201":
        if not synced:
            bot.tree.copy_global_to(guild=discord.Object(id=1123547534074314936))
            await bot.tree.sync(guild=discord.Object(id=1123547534074314936))
            synced = True
            await ctx.send("Synced!")
        else:
            await ctx.send("The bot has already been synced.")
    else:
        await ctx.send("Sorry, only the bot owner can execute this command.")


with open("userslist.json", "r") as file:                                                                       # Load user from JSON 
    users = json.load(file)


def save_users_list():                                                                                          #  save user notification to JSON 
    with open("userslist.json", "w") as file:
        json.dump(users, file, indent=4)


def get_upcoming_events(max_results=10):
    credentials_json = os.environ.get("SERVICE_ACCOUNT_CREDENTIALS")
    if not credentials_json:
        raise ValueError("SERVICE_ACCOUNT_CREDENTIALS environment variable is not set")
        
    creds = Credentials.from_service_account_info(json.loads(credentials_json))
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


async def send_notification(user_id, event, tz):                                                              # Sending of direct messages
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

            event_title = event["summary"]
            tzinfo = gettz(tz)  # Convert a tzinfo object
            event_start = datetime.datetime.fromisoformat(event["start"]["dateTime"]).astimezone(tzinfo)
            event_start_str = event_start.strftime(
                "%B %d %Y at %I:%M %p"
        )                                                                                                      # Format the start time
            event_details = event.get("description", "")

            event_details = html_to_text(event_details)                                                        # Convert HTML to markdown

            message = f"Event Title: {event_title} at {event_start_str}\nEvent Details: {event_details}"
            await user.send(message)
            logger.info("Notification sent")
            print("Notification sent")
        else:
            logger.error("Invalid event data: missing or empty 'summary' key")
            print("Invalid event data: missing or empty 'summary' key")
    except Exception as e:
        logger.exception(f"An error occurred while sending notification: {str(e)}")


@bot.hybrid_command()                                                                                             #Opt In
async def opt_in(ctx):
    user_id = ctx.author.id
    if str(user_id) in users:
        await ctx.send("You are already opted in!")
    else:
        users[str(user_id)] = {"notification_time": None}
        save_users_list()
        await ctx.send("You are now opted in for notifications!")


@bot.hybrid_command()                                                                                              # Opt Out
async def opt_out(ctx):
    user_id = ctx.author.id
    if str(user_id) not in users:
        await ctx.send("You are already opted out!")
    else:
        del users[str(user_id)]
        save_users_list()
        await ctx.send("You are now opted out from notifications!")


# OMG BUTTONS!!
class TimeZoneButtons(discord.ui.View):
    def __init__(self, *, timeout=240):
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
            
    @discord.ui.button(label="Europe/Bucharest (EEST)", style=discord.ButtonStyle.primary)
    async def eastern_europe_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Europe/Bucharest"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Europe/Bucharest(EEST).")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")
            
    @discord.ui.button(label="Asia/Taipei", style=discord.ButtonStyle.primary)
    async def asia_taipei_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = str(interaction.user.id)
            users[user_id]["time_zone"] = "Asia/Taipei"
            save_users_list()  
            await interaction.response.edit_message(content="Your time zone is set to Asia/Taipei.")
        except discord.errors.NotFound:
            print(f"The interaction has either expired or was not found.")


@bot.hybrid_command()
async def set_notification(ctx, time_minutes: int,):
    user_id = ctx.author.id
    await ctx.defer()

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


@bot.hybrid_command()
async def list_events(ctx):
    events = get_upcoming_events(max_results=11)
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


@bot.hybrid_command()
async def embed(ctx):
    embed = discord.Embed(
        title="Usage",
        description="**Step 1.** -__/Opt_in__\n"
        "**Step 2.** - __/Set_Notification__\n"
        "This is the amount of time prior to an event in which youd like to be notified. It must be within a range of 5 minutes to 5 days.*\n\n"
        "**Other Commands**\n"
        "- __/Opt_out__ - Remove yourself from the notification list\n\n"
        "- __/List_Events__ - Lists the next 7 days worth of events.",
        colour=0xD70909,
        timestamp=datetime.datetime.now(),
    )
    embed.set_author(name="Adjutant", icon_url="https://imgur.com/6c1lsDt.jpg")
    embed.add_field(
        name="Currently in beta",
        value=" If your event/s are not on the calendar and you'd like to ad them see Eleven.*There will be some bugs to work out. Please let me know if you run into any issues.*",
    )
    embed.set_image(url="https://imgur.com/Jv3tcPS.jpg")
    embed.set_thumbnail(url="https://imgur.com/YgoWRjq.jpg")
    embed.set_footer(text="The Adjutant/{}".format(ctx.author.display_name))
    await ctx.send(embed=embed)


async def main():
    await bot.login(os.getenv("BOT_TOKEN_TESTER"))
    await bot.connect()
while True:
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
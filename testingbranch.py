import os
import json
import pytz
import aiohttp
import discord
import asyncio
import datetime
import requests
import logging.handlers
from pytz import timezone
from bs4 import BeautifulSoup
from html_parser import html_to_text
from discord.ext import commands, tasks
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials


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
SERVICE_ACCOUNT_CREDS = r"H:\\PROGRAMS\\adjutanto\\SERVICE_ACCOUNT_CREDENTIALS.json"
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

intents = discord.Intents.all()
intents.message_content = True
intents.members = True
events = []
# set to keep track of responded message IDs(for sync command)
responded_messages = set()

session = None
async def create_session():
    global session
    session = aiohttp.ClientSession()
async def close_session():
    await session.close()
    
    
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
@tasks.loop(minutes=60)
async def crawl_sites_and_insert_events():
    print("Fetching tournament data and inserting into calendar...")

    # Get upcoming tournaments
    upcoming_tournaments = get_upcoming_tournaments()

    # Format them into Calendar events
    events = [format_event(tournament) for tournament in upcoming_tournaments]

    # Insert them
    insert_events_to_calendar(events)

    print("Inserted events.")

    await check_events()


@tasks.loop(minutes=60)  
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


async def main():
    await create_session()
    await bot.login(os.getenv("BOT_TOKEN_TESTER"))
    await bot.connect()
    await session.close()
    await crawl_sites_and_insert_events.start()


bot = commands.Bot(command_prefix="!", intents=intents)


@bot.hybrid_command()
@commands.is_owner()
async def manual_crawl(ctx):
    print("Manual crawl initiated...")
    await crawl_sites_and_insert_events()


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
        
        
        from bs4 import BeautifulSoup


def get_upcoming_tournaments():
    tournament_types = ['Minor_Tournaments', 'Major_Tournaments', 'Basic_Tournaments']
    base_url = 'https://liquipedia.net/starcraft2/'
    upcoming_tournaments = []
    for tournament_type in tournament_types:
        url = f"{base_url}{tournament_type}"
        page = requests.get(url)
        soup = BeautifulSoup(page.text, 'html.parser')
        tables = soup.find_all('table', {'class': 'wikitable'})
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                details = row.find_all('td')
                if len(details) < 4 or not details[3].has_attr('class'):
                    continue
                data = {}
                data['Name'] = details[1].text.strip()
                data['Date'] = ' '.join(details[2].text.strip().split(' ')[-3:])
                data['Type'] = tournament_type.split('_')[0]
                
                if 'tick' in details[3]['class']:
                    # This is an upcoming tournament
                    upcoming_tournaments.append(data)
    return upcoming_tournaments


def format_event(tournament):
    # Converts the time into Google Calendar's required format
    # Adjust the hours, timezone etc. based on the actual schedule of tournaments
    date_str = tournament['Date'] + " 12:00:00"
    date_object = datetime.strptime(date_str, '%B %d, %Y %I:%M:%S')
    start_time = date_object.isoformat()
    # Let's assume the event lasts for 3 hours
    end_hour = date_object.hour + 3
    end_day = date_object.day
    if end_hour >= 24:
        end_hour -= 24
        end_day += 1
    end_time = date_object.replace(hour=end_hour, day=end_day).isoformat()
    event = {
        'summary': tournament['Name'],
        'description': f"{tournament['Type']} StarCraft II Tournament",
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/Los_Angeles',
        },
    }
    return event



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


def insert_events_to_calendar(events, calendar_id="9102d8e30bd9f6469e6700a92306c790191af209f622e1bc52a701e5a34e24a0@group.calendar.google.com"):
    # Load the credentials from your service account key file
    creds = Credentials.from_service_account_file(r'H:\PROGRAMS\adjutanto\SERVICE_ACCOUNT_CREDENTIALS.json')

    # Build the service
    service = build('calendar', 'v3', credentials=creds)

    # Insert the events
    for event in events:
        event = service.events().insert(calendarId=calendar_id, body=event).execute()

upcoming_tournaments = get_upcoming_tournaments()
events = [format_event(tournament) for tournament in upcoming_tournaments]
insert_events_to_calendar(events)

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


# Set Notification command
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


# Set MMR Range Command
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
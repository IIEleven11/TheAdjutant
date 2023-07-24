from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import os
from google.oauth2.service_account import Credentials 
from googleapiclient.discovery import build
import pytz
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError
import logging

logging.basicConfig(filename='errors.log', level=logging.ERROR)
driver = webdriver.Chrome()

url = "https://play.eslgaming.com/starcraft/global/sc2/open/1on1-series"

driver.get(url)

# Wait until the tournaments are loaded
wait = WebDriverWait(driver, 10)
tournaments_loaded = EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.league-list.cups a'))
wait.until(tournaments_loaded)

# Get the tournament links
tournaments = driver.find_elements(By.CSS_SELECTOR, 'div.league-list.cups a')
event_titles = []
event_dates = []
event_times = []
event_links = []

def handle_api_error(e):
  print(f"API Error: {e}")


for tournament in tournaments:
    title = tournament.get_attribute('title')
    date = tournament.find_element(By.CSS_SELECTOR, 'div.date').text
    time = tournament.find_element(By.CSS_SELECTOR, 'div.time').text  
    href = tournament.get_attribute('href')
    tournament_url = 'https://play.eslgaming.com' + href if href else None

    if not tournament_url:
        continue

    print(f"Title: {title}\nDate: {date}\nTime: {time}\nURL: {tournament_url}\n---")
    
    # Parse date and time
    start_datetime = datetime.strptime(f"{date} {time}", "%A, %b %d, %Y %H:%M")
    
    event_titles.append(title)
    event_dates.append(date)
    event_times.append(time) 
    event_links.append(tournament_url)


driver.quit()

# Load credentials and create an API client
credentials = Credentials.from_service_account_file(
    "SERVICE_ACCOUNT_CREDENTIALS.json",
    scopes=['https://www.googleapis.com/auth/calendar']  
)

try:
  service = build('calendar', 'v3', credentials=credentials)
except Exception as e:
  print(f"Error creating calendar service: {e}")
  exit(1)
  
# Get the calendar ID  
calendar_id = os.getenv("GOOGLE_CALENDAR_ID")

# Timezone for the events
timezone = 'America/Los_Angeles'  

# Calculate utc offset
cdt = pytz.timezone(timezone)
utc_offset_min = cdt.utcoffset(datetime.now()).total_seconds() / 60

# Parse events and add to Google Calendar
for title, start_datetime, link in zip(event_titles, event_dates, event_links):

  # Convert to RFC3339 format
  start_time_rfc3339 = (start_datetime - timedelta(minutes=utc_offset_min)).isoformat("T") + "Z"  
  end_time_rfc3339 = (start_datetime + timedelta(hours=1) - timedelta(minutes=utc_offset_min)).isoformat("T") + "Z"

  try:
    # Check if event already exists
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time_rfc3339,
        timeMax=end_time_rfc3339,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

  except Exception as e:
      print(f"Error getting existing events: {e}")
      
  if any(event['summary'] == title for event in events):
      print(f"Event '{title}' already exists in the calendar.")

  else:
      event = {
        "summary": title,
        "description": link,
        "start": {
          "dateTime": start_time_rfc3339,
          "timeZone": timezone,  
        },
        "end": {
          "dateTime": end_time_rfc3339,
          "timeZone": timezone,
        },
      }
    
      try:
        service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"Event '{title}' added to the calendar.")
        
      except Exception as e:
        print(f"Error adding event: {e}")
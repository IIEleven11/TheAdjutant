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

driver = webdriver.Chrome()
wait = WebDriverWait(driver, 20)
driver.get('https://challonge.com/communities/DesignedKiller/tournaments')
today = datetime.now()

# Find the filter button
filter_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@class='filter button-dropdown -inline']//button[@class='btn btn-lg btn-light-default trigger']")))
filter_button.click()

# Find the Pending checkbox
pending_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//li[@class='item']//label[@class='checkbox-control -thin']//span[text()='Pending']")))
pending_checkbox.click()


wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tournament-block .details")))

# Loop through each tournament, get the title, date, and time
tournaments = driver.find_elements(By.CSS_SELECTOR, '.tournament-block .details')


event_titles = []
event_dates = []
event_times = []
event_links = []

for tournament in tournaments:
    try:
        title = tournament.find_element(By.CSS_SELECTOR, ".details .name").text
        date_str = tournament.find_element(By.CSS_SELECTOR, ".fa-calendar").find_element(By.XPATH, "./..").text
        time =  tournament.find_element(By.CSS_SELECTOR, ".fa-clock-o").find_element(By.XPATH, "./..").text
        links = tournament.find_elements(By.CSS_SELECTOR, ".cover, .body") # Get both links

        # Convert string date into datetime format
        event_date = datetime.strptime(date_str, '%a, %B %d, %Y')

        # Ignore the past events
        if event_date >= today:
            event_titles.append(title)
            event_dates.append(date_str)
            event_times.append(time)

            # We can have multiple links per event, extract and store each one
            for link_element in links:
                event_links.append(link_element.get_attribute('href'))

    except Exception as e:
        print("An error occurred: ", e)

driver.quit()

print(event_titles)
print(event_dates)
print(event_times)
print(event_links)


# Load credentials and create an API client
credentials = Credentials.from_service_account_file(
    "H:\\PROGRAMS\\adjutanto\\SERVICE_ACCOUNT_CREDENTIALS.json", 
    scopes=['https://www.googleapis.com/auth/calendar']
)
service = build('calendar', 'v3', credentials=credentials)

# Get the calendar ID
calendar_id = os.getenv("GOOGLE_CALENDAR_ID")

# Timezone for the events
timezone = 'Europe/Moscow'  # CDT timezone

# Calculate the utc offset for the event to ensure time correctness regardless of DST
cdt = pytz.timezone(timezone)
utc_offset_min = cdt.utcoffset(datetime.now()).total_seconds() / 60

# Parse events and add to Google Calendar
for title, date_str, time_str, link in zip(event_titles, event_dates, event_times, event_links):
    # Trim 'CDT' from time string and combine date and time strings together
    time_str_no_tz = time_str.replace(' EEST', '')
    start_time_str = f"{date_str} {time_str_no_tz}"
    
    # Convert string datetime into datetime object
    start_time = datetime.strptime(start_time_str, '%a, %B %d, %Y %I:%M %p')  # No %Z required as timezone is removed
    
    # Google Calendar's API requires datetimes in the RFC3339 format
    # Convert start and end time to RFC3339 format
    start_time_rfc3339 = (start_time - timedelta(minutes=utc_offset_min)).isoformat("T") + "Z"  # Convert to UTC
    end_time_rfc3339 = (start_time + timedelta(hours=1) - timedelta(minutes=utc_offset_min)).isoformat("T") + "Z"  # We'll use a duration of 1 hour for each event


    # Check if event already exists
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time_rfc3339,
        timeMax=end_time_rfc3339,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if any(event['summary'] == title for event in events):
        print(f"Event '{title}' already exists in the calendar.")
    else:
        event = {
            "summary": title,
            "description": link,  # Add the link to the event description
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
            print(f"An error occurred while adding the event '{title}' to the calendar: {e}")



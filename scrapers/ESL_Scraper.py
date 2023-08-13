
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dateutil.parser import parse
import os
import datetime
from playwright.sync_api import sync_playwright
os.environ['DEBUG'] = 'pw:api'


# Function for web scraping
def scrape_website():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # set headless to False to see the action
        page = browser.new_page()
        page.goto('https://play.eslgaming.com/starcraft/global/sc2/open/1on1-series')

        title_element = page.query_selector(".title")
        title = title_element.inner_text() if title_element else None

        date_time_element = page.query_selector("format-date > div")
        date_time = date_time_element.inner_text() if date_time_element else None

        url_element = page.query_selector("a[title^='StarCraft']")
        url = url_element.get_attribute("href") 
        if url_element:
            url = url_element.get_attribute("href")
        else:
            url = None
        event_divs = page.query_selector_all(".panel-pane.pane-league-list .match")


        events = []
        max_events = 3

        for event_div in event_divs[:min(len(event_divs), max_events)]:
            event_title_element = event_div.query_selector("h2")
            event_title = event_title_element.inner_text() if event_title_element else None
            
            individual_events = event_div.query_selector_all("//div[@class='pane-content']//li")
            
            for individual_event in individual_events:
                event = individual_event.inner_text()
                events.append({
                    'title': title,
                    'date time': date_time,
                    'url': url,
                    'event title': event_title,
                    'event': event
                })

    browser.close()
    return title, date_time, url, events


events = scrape_website()

for event in events:
    print(event)

for event in events: 
    print(event)  # print the details of each event



# Function for adding event to Google Calendar
def add_to_calendar(title, date_time, url):
    date_time = parse(date_time)  # convert to datetime object
    
    # Add one hour to the scraped time for event's end time
    end_time = date_time + datetime.timedelta(hours=1)
    
    # Load credentials from the service account file
    creds = Credentials.from_service_account_file('H:\\PROGRAMS\\adjutanto\\SERVICE_ACCOUNT_CREDENTIALS.json', scopes=['https://www.googleapis.com/auth/calendar'])
    
    # Build the service
    service = build('calendar', 'v3', credentials=creds)
    
    # Event details
    event = {
        'summary': title,
        'description': url,
        'start': {
            'dateTime': date_time.isoformat(),
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Los_Angeles',
        },
    }

    # Add the event
    calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
    event = service.events().insert(calendarId=calendar_id, body=event).execute()
    print('Event created: %s' % (event.get('htmlLink')))

# Calling the functions
title, date_time, url = scrape_website()
add_to_calendar(title, date_time, url)

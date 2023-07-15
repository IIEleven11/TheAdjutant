# Adjutant

Discord bot that can notify you about upcoming events.

At the moment its Starcraft 2 specific. Possibly could expand its borders at a later date

- Use -
- /Opt in - Opt in to alerts

- /Opt out - Opt out of alerts

- /List events - lists the next 7 days worth of events
-     This has follow up options where user selects their time zone. (I had to hardcode these, if a timezone isnt there that you want to use see the "class TimeZoneButtons"

- /Set Notification - Set the amount of time prior to an event in which youd like to be notified.
  this command must be in minutes. (currently looking into how to best accept input in any format) which would be 1 day 2 hours 30 minutes. So if you wanted a 1 hours notification your input would be 60. 2 hours would be 120 etc...
- Bot reads from a specific google calendar using a google service account. If you would like your event added to this calendar please let me know.


You will need these things to run this bot yourself
- Google service account credentials
- Google calendar API Key
- Discord bot token with app commands allowed

intents.message_content
intents.members



Things that need to be done.

Organize this so its not one big file

Setup MMR range specific Notifications.

Look into other ways of populating the calendar automatically

/List events needs to be time zone specific like the DM's. So according to the user issuing the /list_events command

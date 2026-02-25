Shipping Quote Bot
A Slack bot that automates shipping quote requests by parsing workflow submissions, calculating package weights based on device types, fetching real-time carrier rates from the ShipStation API, and posting formatted quotes back to the requesting user in-thread.

How It Works
A team member submits a shipping quote request through a Slack Workflow Builder form
The bot monitors a designated channel for incoming workflow submissions
It parses the request to extract device details, shipping zip code, and shipping method
Package weight is calculated based on device type:
Smart Labels / ECO1: 0.125 lbs per device
All other devices: 1.5 lbs per device
Mixed orders are supported (e.g., "10 smart labels, 4 ECO1, 5 voyagers")
The bot calls the ShipStation API to get a real-time shipping rate
A formatted quote is posted back in the message thread, tagging the original requester

Exception Handling
International orders — Non-US zip codes are detected automatically. The bot tags the fulfillment team user group for manual assistance instead of generating a quote.
Overweight shipments — Orders exceeding 50 lbs are flagged and routed to the fulfillment team.
Tech Stack

Python 3 — Core application logic
Slack Bolt — Slack event handling and message posting
ShipStation API — Real-time carrier rate lookups
Docker / Docker Compose — Containerized deployment
Project Structure
├── bot.py                 # Main bot application
├── Dockerfile             # Container image definition
├── docker-compose.yml     # Service orchestration
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not tracked)
└── .gitignore             # Git ignore rules

Environment Variables
Create a .env file in the project root with the following:
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SHIPSTATION_API_KEY=your-shipstation-api-key
SHIPSTATION_API_SECRET=your-shipstation-api-secret
PYTHONUNBUFFERED=1
Note: Never commit your .env file. It is excluded via .gitignore.
Slack App Configuration
The bot requires the following OAuth scopes under Bot Token Scopes:
channels:history — Read messages in public channels
channels:read — View basic channel info
chat:write — Post messages
groups:history — Read messages in private channels
usergroups:read — Read user group info
usergroups:write — Mention user groups in messages
After adding scopes, reinstall the app to your workspace.

Setup & Deployment
Clone the repository:
   git clone https://github.com/YOUR_USERNAME/shipping-bot.git
   cd shipping-bot
   
Create your .env file with the required environment variables listed above.
Build and start the bot:
   docker-compose up -d --build
   
Verify the bot is running:
   docker-compose logs -f
   
You should see ⚡️ Bolt app is running! in the output.

Updating
After making changes to bot.py:
docker-compose down
docker-compose build --no-cache
docker-compose up -d

Sample Quote Output:
@JayBryant Here is the shipping quote:
📦 Devices: 10 smart labels, 4 ECO1, 5 voyagers (9.25 lbs)
📍 Ship To: 40243 | Ship From: 27284
🚚 Method: UPS® Ground
💰 Quoted Rate: $12.47

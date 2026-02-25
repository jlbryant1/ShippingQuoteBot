import os
import re
import math
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
load_dotenv()
# --- Config ---
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SHIPSTATION_API_KEY = os.environ["SHIPSTATION_API_KEY"]
SHIPSTATION_API_SECRET = os.environ["SHIPSTATION_API_SECRET"]
SHIP_FROM_ZIP = "27284"
B2B_CHANNEL_ID = os.environ.get("B2B_CHANNEL_ID")
FULFILLMENT_MENTION = "@fulfillment"
app = App(token=SLACK_BOT_TOKEN)
# --- Shipping method mapping ---
METHOD_MAP = {
    "ground": "ups_ground",
    "2nd day air": "ups_2nd_day_air",
    "2-day": "ups_2nd_day_air",
    "next day air": "ups_next_day_air",
    "overnight": "ups_next_day_air",
    "3 day select": "ups_3_day_select",
}
def parse_quote_request(text):
    print(f"PARSE  INPUT: {repr(text[:200])}")
    try:
        user_mention_match = re.search(r"<@([A-Z0-9]+)>", text, re.IGNORECASE)
        devices_match = re.search(r"#\s*of\s*Devices\*?\s*\n\*?(.+?)(?:\n\n|\n\*|$)", text, re.IGNORECASE | re.DOTALL)
        zip_match = re.search(r"Shipping Zip Code\*?\s*\n\*?(.+?)(?:\*|\n|$)", text, re.IGNORECASE)
        method_match = re.search(r"Shipping Method\*?\s*\n\*?(.+?)(?:\*|\n|$)", text, re.IGNORECASE)
        raw_zip = zip_match.group(1).strip() if zip_match else None
        is_international = not re.match(r"^\d{5}$", raw_zip) if raw_zip else False
        # Parse devices field for weight calculation
        devices_text = devices_match.group(1).strip().strip("*") if devices_match else ""
        total_weight = 0
        total_devices = 0
        # Clean the text of all asterisks first
        clean_text = devices_text.replace("*", "")
        # Check for parenthesized breakdown
        paren_match = re.search(r"\((.+)\)", clean_text)
        parse_text = paren_match.group(1) if paren_match else clean_text
        sub_items = re.findall(r"(\d+)\s+([^,]+)", parse_text)
        print(f"DEBUG sub_items: {sub_items}")
        print(f"DEBUG clean_text: {repr(clean_text)}")
        print(f"DEBUG parse_text: {repr(parse_text)}")
        print(f"DEBUG sub_items: {sub_items}")
        if sub_items:
            for count_str, name in sub_items:
                count = int(count_str)
                name_clean = name.strip().lower()
                total_devices += count
                if "smart label" in name_clean or "eco1" in name_clean or "eco 1" in name_clean:
                    total_weight += count * 0.125
                else:
                    total_weight += count * 1.5
        else:
            num_match = re.match(r"(\d+)", clean_text)
            if num_match:
                total_devices = int(num_match.group(1))
                total_weight = total_devices * 1.5
        return {
            "user_id": user_mention_match.group(1) if user_mention_match else None,
            "devices": total_devices,
            "devices_text": devices_text,
            "weight": round(total_weight, 2),
            "zip": raw_zip,
            "is_international": is_international,
            "method": method_match.group(1).strip().lower() if method_match else None,
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None
    
#Function to search ShipStation Rates
def get_shipstation_rates(to_zip, weight_lbs):
    url = "https://ssapi.shipstation.com/shipments/getrates"
    payload = {
        "carrierCode": "ups",
        "fromPostalCode": SHIP_FROM_ZIP,
        "toPostalCode": to_zip,
        "toCountry": "US",
        "weight": {"value": weight_lbs, "units": "pounds"},
        "confirmation": "none",
        "residential": True
    }
    response = requests.post(url, json=payload, auth=(SHIPSTATION_API_KEY, SHIPSTATION_API_SECRET))
    print(f"ShipStation response: {response.status_code} - {response.text[:200]}")
    if response.status_code == 200:
        return response.json()
    return None

#Function to to get the shipping  method
def match_rate(rates, method_key):
    for rate in rates:
        service = rate.get("serviceName", "").lower()
        if method_key.replace("ups_", "").replace("_", " ") in service:
            return rate
    for rate in rates:
        service = rate.get("serviceName", "").lower()
        for keyword in method_key.replace("ups_", "").split("_"):
            if keyword in service:
                return rate
    return None

#Event function that detects when a shipping quote drops inn the channel
@app.event("message")
def handle_message_events(body, say, client):
    event = body.get("event", {})
    subtype = event.get("subtype")
    print(f"Message received - subtype: {subtype}, text preview: {event.get('text', '')[:80]}")
    if subtype in ("message_deleted", "message_changed"):
        return
    channel = event.get("channel")
    if B2B_CHANNEL_ID and channel != B2B_CHANNEL_ID:
        return
    text = event.get("text", "") or ""
    if not re.search(r"Request Shipping Quote", text, re.IGNORECASE):
        return 

    #Error Handling
    print(f"BOT TRIGGERED - text: {text[:100]}")
    user_id = event.get("user")
    thread_ts = event.get("ts")
    parsed = parse_quote_request(text)
    print(f"Parsed: {parsed}")
    requester_id = (parsed.get("user_id") if parsed else None) or user_id
    if not parsed or not all([parsed["devices"], parsed["zip"], parsed["method"]]):
        say(text=f"<@{requester_id}> :warning: I couldn't parse the request. Please check the format.", thread_ts=thread_ts, channel=channel)
        return
    weight = parsed["weight"]

    #If Quote is International
    if parsed["is_international"]:
        
        #Function for the bot to reply in the message thread and tag the fulfillment team
        client.chat_postMessage(
            channel=body["event"]["channel"],
            text=f"<@{requester_id}> :earth_africa: This looks like an international order. @fulfillment please assist with this quote.",
            link_names=True, 
            thread_ts=body["event"].get("thread_ts") or body["event"]["ts"]
            )
        return 
    ##If Quote is over 50lbs
    if weight > 50:
         #Function for the bot to reply in the message thread and tag the fulfillment team
        say(
            text=f"<@{requester_id}> :warning: This shipment is {weight} lbs, which exceeds the 50 lb limit. {FULFILLMENT_MENTION} please assist with this quote.",
            thread_ts=thread_ts,
            channel=channel
        )
        return
    method_key = None
    for keyword, code in METHOD_MAP.items():
        if keyword in parsed["method"]:
            method_key = code
            break

    #Error Handling
    if not method_key:
        say(text=f"<@{requester_id}> :warning: Unrecognized shipping method: {parsed['method']}.", thread_ts=thread_ts, channel=channel)
        return
    rates = get_shipstation_rates(parsed["zip"], weight)
    if not rates:
        say(text=f"<@{requester_id}> :x: Failed to retrieve rates from ShipStation.", thread_ts=thread_ts, channel=channel)
        return
    matched_rate = match_rate(rates, method_key)
    if not matched_rate:
        say(text=f"<@{requester_id}> :warning: No UPS rate found for {parsed['method']} to zip {parsed['zip']}.", thread_ts=thread_ts, channel=channel)
        return
    base_rate = float(matched_rate["shipmentCost"]) + float(matched_rate.get("otherCost", 0))
    final_quote = math.ceil(base_rate * 1.2 * 100) / 100

    #Sucessful Quote Response
    say(
        text=(
            f"<@{requester_id}> Here is the shipping quote:\n\n"
            f":package: Devices: {parsed['devices_text']} ({weight} lbs)\n"
            f":round_pushpin: Ship To: {parsed['zip']} | Ship From: {SHIP_FROM_ZIP}\n"
            f":truck: Method: {matched_rate['serviceName']}\n"
            f":moneybag: Quoted Rate: ${final_quote:.2f}"
        ),
        thread_ts=thread_ts,
        channel=channel
    )
# --- Run the bot ---
if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
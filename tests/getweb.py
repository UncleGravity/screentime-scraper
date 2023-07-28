import json
import requests
from datetime import datetime, timedelta, timezone
from aw_client import ActivityWatchClient

def get_web_events():
    aw_client = ActivityWatchClient("browser-usage-fetcher")

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=1)
    end_time = now

    # browser_watcher_bucket_id = f"aw-watcher-web_{aw_client.hostname}"
    browser_watcher_bucket_id = "aw-watcher-web-chrome"
    return aw_client.get_events(bucket_id=browser_watcher_bucket_id, limit=-1, start=start_time, end=end_time)
    
def send_to_api(data, api_endpoint):
    headers = {'Content-Type': 'application/json'}
    response = requests.post(api_endpoint, json=data, headers=headers)

    if response.status_code == 200:
        print("Data sent successfully to the API!")
    else:
        print(f"Failed to send data to the API, status code: {response.status_code}")

if __name__ == "__main__":
    API_ENDPOINT = "http://your-api-endpoint.example.com/path"
    browser_usage_data = get_web_events()

    for entry in browser_usage_data:
        print(entry.to_json_str())
    # send_to_api(browser_usage_data, API_ENDPOINT)

from time import sleep
import urllib.parse
import requests


class Roku:
    # Class Attributes
    roku_channel_id = {"netflix": "12", "hulu": "2285", "amazon": "13"}

    def __init__(self, ip):
        self.ip = ip

    def play_on_roku(self, endpoint):
        response = requests.post(endpoint, headers={"cache-control": "no-cache"})
        self.press_right()
        print(f"Roku Response Code = {response}")

    def press_right(self):
        keypress = f"http://{self.ip}:8060/keypress/right"
        sleep(1)

        for i in range(8):
            sleep(0.25)
            requests.post(keypress, headers={"cache-control": "no-cache"})

    def build_roku_search_endpoint(self, show_name, service, ip):
        params = {
            "title": show_name,
            "type": "tv-show",
            "season": "1",
            "provider-id": self.roku_channel_id.get(service),
        }

        return "http://{}:8060/search/browse?".format(ip) + urllib.parse.urlencode(
            params, quote_via=urllib.parse.quote
        )

    def build_roku_deeplink_endpoint(self, ip, service, show_id):
        return f"http://{ip}:8060/launch/{self.roku_channel_id.get(service)}?contentId={show_id}"

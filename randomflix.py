import random
import urllib.parse
import os, sys
from time import sleep

import requests
import webbrowser
import argparse


# Argument Parser
parser = argparse.ArgumentParser(
    description='Plays a random show from a chosen list directly on Roku or in a web browser')

parser.add_argument('-m', '--mode', type=int, choices=[1, 2, 3, 4],
                    help='1 = Watched Mode, 2 = Background Mode, 3 = Active Mode, 4 = Full Random')
parser.add_argument('-p', '--pause', action='store_true',
                    help='If set, program will present the show on deck and pause.')
parser.add_argument('-l', '--local', action='store_true',
                    help='By default plays on Roku, set flag to play on browser')
parser.add_argument('-s', '--search', action='store_true',
                    help='If set, program will Roku Search the show, rather than auto-playing')
parser.add_argument('-t', '--test', action='store_true',
                    help='Ignores the randomly picked show and runs against hard-coded test')
parser.add_argument('--ip',
                    help='IP address of Roku on the network')

# Set Defaults for use in Android Interpreters that don't allow args, such as PyDroid
parser.set_defaults(mode=1, pause=False, local=False, search=True, ip='192.168.1.163') # 192.168.1.163 / 192.168.1.197
args = parser.parse_args()

# Initialize Service Mapping
serviceDict = {"netflix": "12", "hulu": "2285", "amazon": "13"}


def load_show_list():
    # Read in shows.txt and load show category dictionaries
    watched, background, new = {}, {}, {}

    file = open('shows.txt', 'r')

    for line in file:
        if line.startswith("#") | line.startswith("\n"):
            continue
        else:
            line = line.split(",")
            if line[2].strip() == "1":
                watched.update({line[0].strip(): line[1].strip()})
            
            elif line[2].strip() == "2":
                background.update({line[0].strip(): line[1].strip()})
            
            elif line[2].strip() == "3":
                new.update({line[0].strip(): line[1].strip()})
    
    file.close()
    return watched, background, new


def get_show():
    # Break down random show URL into required components

    if args.mode == 1:
        temp = {**watchedShows}
        show = random.choice(list(temp.keys()))
        show_url = temp.get(show)

    if args.mode == 2:
        temp = {**watchedShows, **backgroundShows}
        show = random.choice(list(temp.keys()))
        show_url = temp.get(show)

    elif args.mode == 3:
        show = random.choice(list(newShows.keys()))
        show_url = newShows.get(show)

    elif args.mode == 4:
        temp = {**watchedShows, **backgroundShows, **newShows}
        show = random.choice(list(temp.keys()))
        show_url = temp.get(show)

    if args.test:
        # temp = {"How I Met Your Mother": "https://www.hulu.com/series/how-i-met-your-mother-bc68ac79-3ace-4427-9ec0-5ee6f314d194"}
        temp = {"Avatar: The Last Airbender": "https://www.netflix.com/title/70142405"}
        # temp = {"Battlestar Galactica", "https://www.amazon.com/gp/video/detail/B000UU2YKE"}
        show = random.choice(list(temp.keys()))
        show_url = temp.get(show)

    return temp, show, show_url


def get_streaming_service_info():
    # Build info from url
    showId = url.split("/")[-1]
    service = url.split(".")[1]
    return showId, service


def build_endpoint():
    if service in serviceDict.keys() and not args.search:
        # Deep link into supported services, such as Netflix and Amazon
        # Roku seems to have broken this functionality. Deeplinking into an episode isn't working for any service
        return 'http://{}:8060/launch/{}?contentId={}'.format(args.ip, serviceDict.get(service), showId)

    else:
        # Search for show on Roku Universal Search and launch show if found
        params = {'title': showName,
                  'type': 'tv-show',
                  'season': '1',
                  'provider-id': serviceDict.get(service)
                  }

        return 'http://{}:8060/search/browse?'.format(args.ip) + urllib.parse.urlencode(params,
                                                                                        quote_via=urllib.parse.quote)


def get_whats_playing():
    whats_playing = ("\n"
                     "Show: {}\n"
                     "Show URL: {}\n"
                     "HTTP Endpoint: {}\n"
                     "Service: {}\n"
                     .format(showName, url, endpoint, service.capitalize()))
    print(whats_playing)


def press_right():
    keypress = 'http://{}:8060/keypress/right'.format(args.ip)
    sleep(1)
    for i in range(8):
        sleep(0.25)
        requests.post(keypress, headers={'cache-control': 'no-cache'})


def play_on_roku():
    # Build request and hit Roku DeepLink Endpoint
    response = requests.post(endpoint, headers={'cache-control': 'no-cache'})
    if args.search:
        press_right()

    print("Roku Response Code = " + str(response))


# Main
watchedShows, backgroundShows, newShows = load_show_list()
tempDict, showName, url = get_show()
showId, service = get_streaming_service_info()
endpoint = build_endpoint()
get_whats_playing()

if args.pause:
    # Allow user to decide if they want to watch the random show surfaced
    if input("Enter to continue or x to exit\n").lower() == "x":
        exit(0)

if args.local:
    # Open Show in Browser
    webbrowser.open(url.strip(), new=1)
    exit(0)
else:
    try:
        play_on_roku()
    except:
        print("Error connecting to Roku ... configured IP might not longer be right")

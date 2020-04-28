import random
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

# Defaults section for changing args on Pydroid
parser.set_defaults(mode=3, pause=False, local=False, ip='192.168.1.163')
args = parser.parse_args()


# Initialize Service Mapping
serviceDict = {"netflix": "12", "hulu": "2285", "amazon": "13"}


# Read in shows.txt and load show category dictionaries
def show_loader():
    watched, background, new = {}, {}, {}

    file = open("shows.txt", 'r')

    for line in file:
        if line.startswith("#") | line.startswith("\n"):
            continue
        else:
            line = line.strip().split(",")
            if line[2] == "1":
                watched.update({line[0]: line[1]})
            elif line[2] == "2":
                background.update({line[0]: line[1]})
            elif line[2] == "3":
                new.update({line[0]: line[1]})
    file.close()
    return watched, background, new


def random_show():
    # Break down random show URL into required components

    if args.mode == 1:
        temp = {**watchedShows}
        show = random.choice(list(temp.keys()))
        url = temp.get(show)

    if args.mode == 2:
        temp = {**watchedShows, **backgroundShows}
        show = random.choice(list(temp.keys()))
        url = temp.get(show)

    elif args.mode == 3:
        show = random.choice(list(newShows.keys()))
        url = newShows.get(show)

    elif args.mode == 4:
        temp = {**watchedShows, **backgroundShows, **newShows}
        show = random.choice(list(temp.keys()))
        url = temp.get(show)

    if args.test:
        temp = {"White Rabbit Project": "https://www.netflix.com/title/80091245"}
        show = random.choice(list(temp.keys()))
        url = temp.get(show)

    return temp, show, url


def url_builder():
    # Build info from url
    showId = url.split("/")[-1]
    service = url.split(".")[1]
    return showId, service


def endpoint_builder():
    if service in serviceDict.keys() and not args.search:
        return 'http://{}:8060/launch/{}?contentId={}&mediaType=season'.format(args.ip, serviceDict.get(service), showId)
    else:
        return 'http://{}:8060/search/browse?title={}&type=tv-show&launch=true'.format(args.ip, showName)


def whats_playing():
    print()
    print("Show: " + showName)
    print("url: " + url)
    print("Service = " + service.capitalize())
    print()


def play_on_roku():
    # Build request and hit Roku DeepLink Endpoint
    response = requests.post(endpoint, headers={'cache-control': 'no-cache'})
    print("Roku Response Code = " + str(response))


# Main
watchedShows, backgroundShows, newShows = show_loader()
tempDict, showName, url = random_show()
showId, service = url_builder()
endpoint = endpoint_builder()

whats_playing()

if args.pause:
    if input("Enter to continue or x to exit\n").lower() == "x":
        exit(0)

if args.local:
    # Open Show in Browser
    webbrowser.open(url)
    exit(0)
else:
    play_on_roku()




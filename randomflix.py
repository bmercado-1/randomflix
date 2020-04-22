import random
import requests
import webbrowser
import argparse


# Argument Parser
parser = argparse.ArgumentParser(
    description='Plays a random show from a chosen list directly on Roku or in a web browser')

parser.add_argument('-p', '--pause', action='store_true',
                    help='If set, program will present the show on deck and pause.')
parser.add_argument('-l', '--local', action='store_true', help='By default plays on Roku, set flag to play on browser')
parser.add_argument('-m', '--mode', type=int, choices=[1, 2, 3],
                    help='1 = Background Mode, 2 = Active Mode, 3 = Mixed Mode')
parser.add_argument('-s', '--search', action='store_true',
                    help='If set, program will Roku Search the show, rather than auto-playing')
parser.add_argument('-t', '--test', action='store_true',
                    help='Ignores the randomly picked show and runs against hard-coded test')
parser.add_argument('--ip', help='IP address of Roku on the network')

parser.set_defaults(mode=3, ip='192.168.1.163')
args = parser.parse_args()

# Flag Override for qPython
args.pause = True
serviceDict = {"netflix": "12", "hulu": "2285", "amazon": "13"}


# List of shows to random from
watchedShows = {
    # Have already been seen and can be run randomly
    "30 Rock": "https://www.hulu.com/series/30-rock-44e1031e-f7ac-443d-86d2-7a2eaa26ed5b",
    "Agents of Shield": "https://www.netflix.com/title/70279852",
    "American Dad": "https://www.hulu.com/series/american-dad-977c8e25-cde0-41b7-80ce-e746f2d2093f",
    "Better Off Ted": "https://www.hulu.com/series/better-off-ted-14e68536-2cef-4cf2-b15f-2ccfe2e3cbc3",
    "Bleach": "https://www.netflix.com/title/70204957",
    "Bones": "https://www.amazon.com/Pilot/dp/B000HVMML2",
    "Brooklyn Nine-Nine": "https://www.hulu.com/series/brooklyn-nine-nine-daf48b7a-6cd7-4ef6-b639-a4811ec95232",
    "Castlevania": "https://www.netflix.com/title/80095241",
    "Chopped": "https://www.hulu.com/series/chopped-505f251f-ab3e-4f2b-a503-15dbbf1476e3",
    "Chuck": "https://www.amazon.com/gp/video/detail/B000VUA2MK",
    "CSI": "https://www.hulu.com/series/csi-crime-scene-investigation-e316aa0d-6df1-445b-98d9-ea1d165bcf81",
    "Diners, Drive-Ins and Dives": "https://www.hulu.com/series/diners-drive-ins-and-dives-858c27f7-7afd-4185-8612-cc76d18fea34",
    # "Doctor Who": "https://www.amazon.com/gp/video/detail/B003LQ3YXU",
    "Don't Trust The Bitch In Apartment 23": "https://www.hulu.com/series/dont-trust-the-b-in-apt-23-45ad58c6-79e6-4f6c-bb9a-7a7079251834",
    "Dragon Ball Z Kai": "https://www.adultswim.com/videos/dragon-ball-z-kai",
    "Family Guy": "https://www.hulu.com/series/family-guy-3c3c0f8b-7366-4d15-88ab-18050285978e",
    "Eureka": "https://www.amazon.com/gp/video/detail/B000U6BT40",
    "Fixer Upper": "https://www.hulu.com/series/fixer-upper-29f6df10-e8e5-4941-a21a-6252ea0c476b",
    # "Friends": "https://www.netflix.com/title/70153404",
    "Full-Metal Alchemist": "https://www.netflix.com/title/70204980",
    "Full-Metal Alchemist: Brotherhood": "https://www.netflix.com/title/70204981",
    "Futurama": "https://www.hulu.com/series/futurama-85bf4cc1-cd8b-4469-ad87-7289217a0b74",
    "Good Eats": "https://www.foodnetwork.com/shows/good-eats",
    "Heroes": "https://www.amazon.com/dp/B000U6C35O",
    "House": "https://www.amazon.com/gp/video/detail/B000WCT7M8",
    "House Hunters": "https://www.hulu.com/series/house-hunters-d9110a19-3f29-4ed1-b55c-0f4aa6869a05",
    "How I Met Your Mother": "https://www.hulu.com/series/how-i-met-your-mother-bc68ac79-3ace-4427-9ec0-5ee6f314d194",
    "Invader Zim": "https://www.hulu.com/series/invader-zim-3d24cbdc-bee5-4699-baab-4ac3f6c2ee8d",
    "Key & Peele": "https://www.hulu.com/series/key-peele-cf07f2ab-45d6-43c8-ad39-f63215072b0e",
    "Law and Order: SVU": "https://www.hulu.com/series/law-order-special-victims-unit-720ef5c1-fc77-4924-98c5-491455a06895",
    "Lie to Me": "https://www.hulu.com/series/lie-to-me-3ff40a52-bb7f-4c21-9f9d-19e50368778e",
    "Love It or List It": "https://www.hulu.com/series/love-it-or-list-it-60a3a861-26b0-45a7-9ebb-808615bb75bb",
    "Lost": "https://www.hulu.com/series/lost-466b3994-b574-44f1-88bc-63707507a6cb",
    "Lucifer": "https://www.netflix.com/title/80057918",
    "Mom": "https://www.hulu.com/series/mom-5ef1115f-7836-4fa8-9ee2-72d45d3a8861",
    "MythBusters": "https://www.hulu.com/series/mythbusters-1e623f06-e636-48b2-a314-7c1c3f02d078",
    "N.C.I.S.": "https://www.netflix.com/title/70142386",
    "Naruto Shippuden": "https://www.hulu.com/series/naruto-shippuden-c6321cb1-1879-4d7f-9e2f-8d7d4fc55544",
    "Neon Genesis Evangelion": "https://www.netflix.com/title/81033445",
    "New Girl": "https://www.netflix.com/title/70196145",
    "Numb3rs": "https://www.amazon.com/gp/video/detail/B00C16GFF0",
    "Ouran High School Host Club": "https://www.netflix.com/title/70205014",
    "Pokemon: The Indigo League": "https://www.netflix.com/title/70297439",
    "Property Brothers": "https://www.hulu.com/series/property-brothers-cc1677bf-a3cb-41d9-b641-5e87d8bbccbd",
    "Rick and Morty": "https://www.hulu.com/series/rick-and-morty-d76d6361-3fbf-4842-8dd7-e05520557280",
    "Robot Chicken": "https://www.adultswim.com/videos/robot-chicken",
    "Scrubs": "https://www.hulu.com/series/scrubs-bba197b5-eb03-4a09-b5f6-f04c053471d7",
    "South Park": "https://www.hulu.com/series/south-park-69ceddec-44ed-4122-af29-d31a7315876d",
    "Teenage Mutant Ninja Turtles": "https://www.hulu.com/series/teenage-mutant-ninja-turtles-eea4f209-0f98-4b51-8b2e-eceb2fbbd058",
    "That 70's Show": "https://www.netflix.com/title/70155610",
    "The Boondocks": "https://www.hulu.com/series/the-boondocks-eb173824-2514-4cc2-a4c6-b50ada7629bf",
    "The Office": "https://www.netflix.com/title/70136120",
    "The Mandalorian": "https://disneyplusoriginals.disney.com/show/the-mandalorian",
    "The Strain": "https://www.hulu.com/series/the-strain-d424ff74-760e-4070-a490-73b89d180fc4",
    "The Walking Dead": "https://www.netflix.com/title/70177057",
    "Unbreakable Kimmy Schmidt": "https://www.netflix.com/title/80025384",
    "Yu-Gi-Oh!": "https://www.netflix.com/title/70177034"
}

backgroundShows = {
    # Haven't seen them, but won't mind them coming up at random, whether you're paying attention or not.
    "Adam Ruins Everything": "https://www.netflix.com/title/80996949",
    "Angie Tribeca": "https://www.hulu.com/series/angie-tribeca-03f94dfd-6309-4c82-b290-b11e1ab4cd8e",
    "Archer": "https://www.hulu.com/series/archer-22b4b3c8-0827-42d2-a841-50e8f3464dc2",
    "Anthony Bourdain: Parts Unknown": "https://www.netflix.com/title/70304979",
    "Arrested Development": "https://www.netflix.com/title/70140358",
    "Arrow": "https://www.netflix.com/title/70242081",
    "Black Mirror": "https://www.netflix.com/title/70264888",
    "Bob's Burgers": "https://www.hulu.com/series/bobs-burgers-fdeb1018-4472-442f-ba94-fb087cdea069",
    "Broad City": "hulu.com/series/broad-city-25fd484f-f2e1-43ff-a671-afd13d095690",
    "Bojack Horseman": "https://www.netflix.com/title/70300800",
    "Buffy The Vampire Slayer": "https://www.hulu.com/series/buffy-the-vampire-slayer-f2c277c5-62b4-417c-b277-8435b70176dd",
    "Community": "https://www.hulu.com/series/community-200c56d4-124c-41a1-b7d2-688f86f432bf",
    "Criminal Minds": "https://www.netflix.com/title/70153390",
    "Curb Your Enthusiasm": "https://www.amazon.com/gp/video/detail/B003QFDXT6",
    "Daredevil": "https://www.netflix.com/title/80018294",
    "Death Note": "https://www.netflix.com/title/70204970",
    "Dragon Ball Super": "https://www.adultswim.com/videos/dragon-ball-super",
    "Drunk History": "https://www.hulu.com/series/drunk-history-b2c24686-450d-4634-a109-075def91cf11",
    "Flash": "https://www.netflix.com/title/80027042",
    "Future Man": "https://www.hulu.com/series/future-man-6771f12e-3195-4844-b489-f21732aa789b",
    "Gotham": "https://www.netflix.com/title/80020542",
    "Haven": "https://www.netflix.com/title/70177067",
    "It's Always Sunny in Philadelphia": "https://www.hulu.com/series/its-always-sunny-in-philadelphia-2171423f-3326-4dfa-b193-b40494e60109",
    "iZombie": "https://www.netflix.com/title/80027159",
    "Legends of Tomorrow": "https://www.netflix.com/title/80066080",
    "Parks and Recreation": "https://www.netflix.com/title/70143842",
    "Person of Interest": "https://www.netflix.com/title/70197042",
    "Planet Earth": "https://www.netflix.com/title/70219642",
    "Prison Breaks": "https://www.hulu.com/series/prison-break-d1d023da-ebb7-474c-b858-c4890e2d5757",
    "Santa Clarita Diet": "https://www.netflix.com/title/80095815",
    "Schitts Creek": "https://www.netflix.com/title/80036165",
    "Star Trek": "https://www.netflix.com/title/70136140",
    "Star Trek: The Next Generation": "https://www.netflix.com/title/70158329",
    "Soul Eater": "https://www.netflix.com/title/70205024",
    "Supernatural": "https://www.netflix.com/title/70143825",
    "The Blue Planet": "https://www.netflix.com/title/70235731",
    "The Flash": "https://www.netflix.com/title/80027042",
    "The Good Wife": "https://www.hulu.com/series/the-good-wife-4eab0297-aead-4aab-9615-781707c11d63",
    "The Librarians": "https://www.hulu.com/series/the-librarians-f8751b7a-2d4b-46f1-bcae-df7b8e317f99",
    "The Magicians": "https://www.netflix.com/title/80092801",
    "The Mindy Project": "https://www.hulu.com/series/the-mindy-project-6a9ba460-9474-481a-a3d8-dbc942f12355",
    "The Orville": "https://www.hulu.com/app/series/the-orville-21e70fbf-6a51-41b3-88e9-f111830b046c",
    "The Twilight Zone": "https://www.netflix.com/title/70172488",
    "The X-Files": "https://www.amazon.com/gp/video/detail/B001BWQ0XM",
    "Veronica Mars": "https://www.hulu.com/series/veronica-mars-4626972c-9da7-40fe-aed7-977f55f48fc5",
    "White Rabbit Project": "https://www.netflix.com/title/80091245",
    "Will & Grace": "https://www.hulu.com/series/will-grace-1998-4294fbac-7b85-4efd-aae0-49f1270e64b5",
    "White Collar": "https://www.hulu.com/series/white-collar-58d3d0ce-8d86-4ccd-bd0c-104551448432",
}

newShows = {
    # Shows on your watchlist. Intended for full attention.
    "24": "https://www.amazon.com/gp/video/detail/B00C177ROM",
    "Altered Carbon": "https://www.netflix.com/title/80097140",
    "American Horror Story": "https://www.netflix.com/title/70210884",
    "Attack on Titan": "https://www.hulu.com/series/attack-on-titan-9c91ffa3-dc20-48bf-8bc5-692e37c76d88",
    "Bates Motel": "https://www.netflix.com/title/70272479",
    "Battlestar Galactica": "https://www.amazon.com/gp/video/detail/B000UU2YKE",
    "Black Butler": "https://www.netflix.com/title/70204955",
    "Breaking Bad": "https://www.netflix.com/title/70143836",
    "Chilling Adventures of Sabrina": "https://www.netflix.com/title/80223989",
    "Code Geass: Lelouch of the Rebellion": "https://www.netflix.com/title/80065146",
    "Dracula": "https://www.netflix.com/title/80997687",
    "Death Note": "https://www.netflix.com/title/70204970",
    "Designated Survivor": "https://www.netflix.com/title/80113647",
    "Devilman Crybaby": "https://www.netflix.com/title/80174974",
    "Dexter": "https://www.netflix.com/title/70136126",
    "Disenchantment": "https://www.netflix.com/title/80095697",
    "Gurren Lagann": "https://www.netflix.com/title/70213196",
    "Good Omens": "https://www.amazon.com/gp/video/detail/B07FMK5LSX",
    "Halt and Catch Fire": "https://www.netflix.com/title/70302182",
    "House of Cards": "https://www.netflix.com/title/70178217",
    "Legion": "https://www.hulu.com/series/legion-ae87e56c-5b3b-44f6-9154-b07c8e60fe6c",
    "Locke and Key": "https://www.netflix.com/title/80241239",
    "Love, Death, and Robots": "https://www.netflix.com/title/80174608",
    "Lost in Space": "https://www.netflix.com/title/80104198",
    "One Punch Man": "https://www.netflix.com/title/80117291",
    "Persona 5: The Animation": "https://www.hulu.com/series/persona5-the-animation-6507e2ba-9faf-49e9-978f-6718a365c4fd",
    "Philip K. Dick's Electric Dreams": "https://www.amazon.com/gp/video/detail/B075NTXMN9",
    "Russian Doll": "https://www.netflix.com/title/80211627",
    "Sex Education": "https://www.netflix.com/title/80197526",
    "Sherlock": "https://www.netflix.com/title/70202589",
    "Spartacus": "https://www.netflix.com/title/70136152",
    "Stranger Things": "https://www.netflix.com/title/80057281",
    "Teenage Mutant Ninja Turtles": "https://www.hulu.com/series/teenage-mutant-ninja-turtles-eea4f209-0f98-4b51-8b2e-eceb2fbbd058",
    "The 100": "https://www.netflix.com/title/70283264",
    "The Dragon Prince": "https://www.netflix.com/title/80212245",
    "The Expanse": "https://www.amazon.com/gp/video/detail/B01MT0UHLT",
    "The Ghost Whisperer": "https://www.amazon.com/gp/video/detail/B007F8TUQU",
    "The Good Place": "https://www.netflix.com/title/80113701",
    "The Handmaid's Tale": "https://www.hulu.com/series/the-handmaids-tale-565d8976-9d26-4e63-866c-40f8a137ce5f",
    "The Magicians": "https://www.netflix.com/title/80092801",
    "The Tudors": "https://www.netflix.com/title/70136129",
    "The Umbrella Academy": "https://www.netflix.com/title/80186863",
    "Veronica Mars": "https://www.hulu.com/series/veronica-mars-4626972c-9da7-40fe-aed7-977f55f48fc5",
    "You": "https://www.netflix.com/title/80211991"
}


def random_show():
    # Break down random show URL into required components
    if args.mode == 1:
        tempDict = {**watchedShows, **backgroundShows}
        showName = random.choice(list(tempDict.keys()))
        url = tempDict.get(showName)

    elif args.mode == 2:
        showName = random.choice(list(newShows.keys()))
        url = newShows.get(showName)

    elif args.mode == 3:
        tempDict = {**watchedShows, **backgroundShows, **newShows}
        showName = random.choice(list(tempDict.keys()))
        url = tempDict.get(showName)

    if args.test:
        tempDict = {"White Rabbit Project": "https://www.netflix.com/title/80091245"}
        showName = random.choice(list(tempDict.keys()))
        url = tempDict.get(showName)

    return tempDict, showName, url


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
tempDict, showName, url = random_show()
showId, service = url_builder()
endpoint = endpoint_builder()

if args.pause:
    input("Press enter to continue")

if args.local:
    # Open Show in Browser
    webbrowser.open_new(url)
    exit(0)
else:
    play_on_roku()




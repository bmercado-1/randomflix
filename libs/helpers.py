from json import dump, load
import argparse


# Argument Parser
parser = argparse.ArgumentParser(description='Plays a random show from a chosen list directly on Roku or in a web browser')

parser.add_argument('-m', '--mode', type=int, choices=[1, 2, 3, 4],
                    help='1 = Watched Mode, 2 = Background Mode, 3 = Active Mode, 4 = Full Random')
parser.add_argument('-p', '--play', action='store_true',
                    help='If set, program play random choice and exit.')
parser.add_argument('-l', '--local', action='store_true',
                    help='By default plays on Roku, set flag to play on browser')
parser.add_argument('-s', '--search', action='store_true',
                    help='If set, program will Roku Search the show, rather than auto-playing')
parser.add_argument('-t', '--test', action='store_true',
                    help='Ignores the randomly picked show and runs against hard-coded test')
args = parser.parse_args()


def generate_default_config():
    """
    Resets program config to default settings
    :return: JSON file
    """

    config = {"mode": "2",
              "search": True,
              "ip": "192.168.1.163",
              "ip2": "192.168.1.197",
              }

    with open("./config.json", mode='w') as config_file:
        dump(config, config_file, indent=4)


def read_config_file():
    try:
        with open("./config.json", mode='r') as config_file:
            config = load(config_file)
            return config

    except FileNotFoundError:
        print("Config File Does Not Exist! Generating Default")
        generate_default_config()


def strikeout(text):
    return ''.join([u"\u0336" + char for char in text])

# Randomflix
### Plays a random show from a chosen list directly on Roku or in a web browser


```shell script
usage: randomflix.py [-h] [-p] [-l] [-m {1,2,3}] [-s] [-t] [--ip IP]

optional arguments:
  -h, --help            show this help message and exit
  -p, --pause           If set, program will present the show on deck and
                        pause.
  -l, --local           By default plays on Roku, set flag to play on browser
  -m {1,2,3}, --mode {1,2,3}
                        1 = Background Mode, 2 = Active Mode, 3 = Mixed Mode
  -s, --search          If set, program will Roku Search the show, rather than
                        auto-playing
  -t, --test            Ignores the randomly picked show and runs against
                        hard-coded test
  --ip IP               IP address of Roku on the network
```
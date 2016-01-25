# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import re
import unicodedata
import datetime
import urllib.request
import urllib.error
import sys
import csv


def game_dates():
    """
    donbest uses the date format YYYYMMDD in their urls. This function sets the start date and end date for the
    2013-2014 season and the 2014-2015 season, then formats the datetime.date to be compatible with donbest.

    :return dates: list of dates in donbest url format
    """
    dates = []

    # no puckline data prior to the 2013-2014 season is archived on donbest
    start_date2013 = datetime.date(2013, 10, 1)
    end_date2013 = datetime.date(2014, 4, 13)
    day = start_date2013

    # strip the hyphens from the datetime.dates and increment the date until we reach the end of the season
    while day <= end_date2013:
        d = re.sub("-", "", str(day))
        dates.append(d)
        day += datetime.timedelta(days=1)

    start_date2014 = datetime.date(2014, 10, 8)
    end_date2014 = datetime.date(2015, 4, 11)
    day = start_date2014
    while day <= end_date2014:
        d = re.sub("-", "", str(day))
        dates.append(d)
        day += datetime.timedelta(days=1)

    # # use in testing only
    # start_date_test = datetime.date(2014, 10, 8)
    # end_date_test = datetime.date(2014, 10, 25)
    # day = start_date_test
    # while day <= end_date_test:
    #     d = re.sub("-", "", str(day))
    #     dates.append(d)
    #     day += datetime.timedelta(days=1)

    return dates


def scraper(gamedates):
    """
    This gigantic function scrapes the donbest site for the data we want, and then formats it in a way that we can use.

    :param gamedates: a list of date strings compatible with donbest's url format
    :return games: a dict of games with headers as keys and associated puckline data as values
    """
    games = []

    # this comes in handy later
    puckline_test = re.compile("^[+-][1-6]\.5")

    for date in gamedates:
        try:
            url = urllib.request.urlopen("http://www.donbest.com/nhl/odds/puck-lines/" + date + ".html")
            soup = BeautifulSoup(url, "html.parser")
            tbl = soup.find("div", {"id": "oddsHolder"}).find("table")

            headers = ["rot_away", "rot_home", "opening_away_line", "opening_away_price", "opening_home_line",
                       "opening_home_price", "away_team", "home_team", "time", "away_score", "home_score",
                       "live_status", "status", "Westgate_away_line", "Westgate_away_price", "Westgate_home_line",
                       "Westgate_home_price", "Mirage_away_line", "Mirage_away_price", "Mirage_home_line",
                       "Mirage_home_price", "Station_away_line", "Station_away_price", "Station_home_line",
                       "Station_home_price", "Pinnacle_away_line", "Pinnacle_away_price", "Pinnacle_home_line",
                       "Pinnacle_home_price", "SIA_away_line", "SIA_away_price", "SIA_home_line", "SIA_home_price"]

            # get the data and strip it of any unicode stuff
            for tr in tbl.findAll("tr", {"class": re.compile(r'statistics_table_')}):
                values = []
                for td in tr.findAll("td"):
                    for val in td.findAll(text=True):
                        v = unicodedata.normalize("NFKD", val)
                        # separate the puckline spread from the puckline price (they are spaced apart by a newline char)
                        if "\n" in v:
                            v2 = v.split("\n")
                            values.append(v2[0])
                            values.append(int(v2[1]))
                        else:
                            values.append(v)

                # zip up the headers and add on the date value
                game = dict(zip(headers, values))
                # get rid of postponed games
                if game["time"] == "PP":
                    print("game on", date, "postponed, skipping.", file=sys.stderr)
                    continue

                # westgate hangs the most amount of pucklines so we use them as a test case to make sure we are looking
                # at the donbest puckline page rather than the random ml/total page it responds with sometimes.
                test_str = game["Westgate_home_line"]
                if not re.match(puckline_test, test_str):
                    if test_str == "-":
                        print("puck line appears not to be available on donbest on date", date, "\ndata scraped was:",
                              file=sys.stderr)
                        print(game, file=sys.stderr)
                        break
                    else:
                        # for some reason, donbest sometimes fucks up their puckline page and instead presents ml/totals
                        # in that case, we append the date of the game to gamedates to try it again later.
                        print("mystery donbest page error: data scraped appears not to be puck line. will append", date,
                              "to gamedates and try again later. data scraped was:", file=sys.stderr)
                        print(game, file=sys.stderr)
                        gamedates.append(date)
                        continue

                # de-string
                game["Westgate_home_line"] = float(game["Westgate_home_line"])
                game["Westgate_away_line"] = float(game["Westgate_away_line"])
                game["home_score"] = int(game["home_score"])
                game["away_score"] = int(game["away_score"])

                # add more useful values here
                game["date"] = date
                game["total_score"] = game["home_score"] + game["away_score"]

                fav_line = -1.5
                dog_line = 1.5
                if game["Westgate_home_line"] == fav_line:
                    game["fav"] = "home"
                    game["dog"] = "away"
                elif game["Westgate_home_line"] == dog_line:
                    game["fav"] = "away"
                    game["dog"] = "home"
                else:
                    print("non-standard puckline, discarding", file=sys.stderr)
                    continue

                if game["fav"] == "home":
                    if (game["home_score"] + fav_line - game["away_score"]) > 0:
                        game["spread_winner"] = "home"
                        game["fav_winner"] = 1
                        game["dog_winner"] = 0
                    elif (game["home_score"] + fav_line - game["away_score"]) < 0:
                        game["spread_winner"] = "away"
                        game["dog_winner"] = 1
                        game["fav_winner"] = 0
                    else:
                        print("error evaluating spread winner, ignoring. data gathered:\n", game, file=sys.stderr)
                        continue

                elif game["fav"] == "away":
                    if (game["away_score"] + fav_line - game["home_score"]) > 0:
                        game["spread_winner"] = "away"
                        game["fav_winner"] = 1
                        game["dog_winner"] = 0
                    elif (game["away_score"] + fav_line - game["home_score"]) < 0:
                        game["spread_winner"] = "home"
                        game["dog_winner"] = 1
                        game["fav_winner"] = 0
                    else:
                        print("error evaluating spread winner, ignoring. data gathered:\n", game, file=sys.stderr)
                        continue

                else:
                    print("cannot establish puckline favorites, discarding.", file=sys.stderr)
                    continue

                # # uncomment if you want to watch more shit scroll across your screen
                # print(game)

                # get rid of useless variables and "non final" games and append the "good" ones to the games list
                game.pop("opening_away_line")
                game.pop("opening_home_line")
                game.pop("opening_away_price")
                game.pop("opening_home_price")
                game.pop("live_status")
                game.pop("Station_home_line")
                game.pop("Station_home_price")
                game.pop("Station_away_line")
                game.pop("Station_away_price")
                game.pop("Mirage_away_line")
                game.pop("Mirage_away_price")
                game.pop("Mirage_home_line")
                game.pop("Mirage_home_price")
                if game["status"] != "FINAL":
                    continue
                games.append(game)

        except AttributeError:
            # sometimes donbest will randomly offer up a malformed page. take the game date, append it to gamedate,
            # and try it again until we get something that works, just like we did above.
            print("attribute error\n date:", date, "\nurl object:", url, "\ndonbest likely served a malformed page.",
                  "don't worry, will try gamedate again later.", file=sys.stderr)
            gamedates.append(date)
            continue

        except urllib.error.HTTPError or urllib.error.URLError or TimeoutError:
            # if it times out (or whatever), append the game date to gamedates and try again later with all the others.
            print("HTTP error:", "\nurl object:", url, "\ndate:", date, "will try again later.", file=sys.stderr)
            gamedates.append(date)
            continue

        except ValueError:
            print("data cast error, malformed/missing game data, not going to try again. game info:", file=sys.stderr)
            continue
    print("\nscraped data loaded into memory.\n")
    return games


def write_csv(dat):
    try:
        fpucklines = "pucklines.csv"
        with open(fpucklines, "w", newline="") as csvfile:
            fnames = ["date", "rot_away", "rot_home", "away_team", "home_team", "time", "away_score", "home_score",
                      "status", "Westgate_away_line", "Westgate_away_price", "Westgate_home_line",
                      "Westgate_home_price", "total_score", "fav", "dog", "spread_winner",
                      "fav_winner", "dog_winner", "Pinnacle_away_line", "Pinnacle_away_price", "Pinnacle_home_line",
                      "Pinnacle_home_price", "SIA_away_line", "SIA_away_price", "SIA_home_line", "SIA_home_price"]

            writer = csv.DictWriter(csvfile, fieldnames=fnames)
            writer.writeheader()
            for d in dat:
                writer.writerow(d)

            csvfile.close()

            print("data written to", fpucklines)

    except ValueError:
        print("error converting data to CSV format. do you have your fieldnames set up correctly?", file=sys.stderr)

    except PermissionError:
        print("you don't have permission to open pucklines.csv. is it currently opened elsewhere?", file=sys.stderr)

    except FileNotFoundError:
        print("bad filename.", file=sys.stderr)


def main():
    """
    Get game date strings for donbest's puckline urls, then scrape the data and write it to a csv file
    """
    dates = game_dates()
    dat = scraper(dates)
    write_csv(dat)

if __name__ == "__main__":
    main()

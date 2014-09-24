#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from google.appengine.ext import ndb
from google.appengine.api import urlfetch

import datetime
import json
import logging
import webapp2

import models


class ByteHandler(webapp2.RequestHandler):
    def get_game_to_cache(self, now, url, cache=None):
        result = urlfetch.fetch(url)
        if result.status_code == 200:
            game = json.loads(result.content)
            if not 'data' in game or not 'game' in game['data']:
                logging.error("Missing some required params in a game- {sched}"
                              .format(json.dumps(game)))
                self.response.write("Missing some required params in a game - {sched}"
                                    .format(json.dumps(game)))
                return

            game = game['data']['game']
            if not 'home_team_runs' in game or not 'away_team_runs' in game or not \
                    'inning' in game or not 'top_inning' in game or not 'ind' in game:
                logging.error("Missing required params for a game - {game}".format(game=game))
                return None

            if cache is None:
                cache = models.GameCache(home_team_runs=int(game['home_team_runs']),
                                         away_team_runs=int(game['away_team_runs']),
                                         inning=int(game['inning']),
                                         top_inning=game['top_inning'],
                                         status=game['ind'],
                                         refresh_time=(now + datetime.timedelta(minutes=3)))
            else:
                cache.home_team_runs = game['home_team_runs']
                cache.away_team_runs = game['away_team_runs']
                cache.inning = game['inning']
                cache.top_inning = game['top_inning']
                cache.status = game['status']
                cache.refresh_time = (now + datetime.timedelta(minutes=3))
                cache.put_async()

            return cache
        else:
            logging.error("There was an error getting a game! - {code} {message}"
                          .format(code=result.status_code, message=result.content))
            return None

    def post(self):
        try:
            team = json.loads(self.request.body)['data']['team']
        except (ValueError, KeyError):
            logging.error("There was no team passed to the ByteHandler")
            self.error(400)
            return

        now = datetime.datetime.now() - datetime.timedelta(hours=1)
        now_even = datetime.datetime.now().replace(hour=0,
                                                   minute=0,
                                                   second=0,
                                                   microsecond=0)
        q = models.GameInfo.query(ndb.AND(
            ndb.OR(
                models.GameInfo.home_team == team,
                models.GameInfo.away_team == team
            ),
            models.GameInfo.day == now_even
        )).fetch(1)

        if len(q) <= 0:
            err = "Unable to find team {team} for day {day}".format(team=team, day=str(now_even))
            logging.error(err)
            self.error(400)
            return

        game = q[0]
        if now > game.start_time:
            # game is live
            if game.cache_key is None:
                cache = self.get_game_to_cache(now, game.game_day_data_url)
                if cache is not None:
                    game.cache_key = cache.key
                    game.put_async()
                    cache.put_async()
            else:
                cache = game.cache_key.get()
                if cache.status != 'F' and now > cache.refresh_time:
                    cache = self.get_game_to_cache(now, game.game_day_data_url, cache=cache)

            if cache is None:
                logging.error("Unable to get game info")
                self.error(500)
                return

            if cache.status == 'F':
                inning = "Final"
            else:
                inning = "{top_bottom} {inning}".format(top_bottom=("Top" if cache.top_inning == "Y" else "Bottom"),
                                                        inning=str(cache.inning))

            homer = team == game.home_team
            if homer:
                if cache.home_team_runs > cache.away_team_runs:
                    note_type = "good"
                elif cache.home_team_runs < cache.away_team_runs:
                    note_type = "bad"
                else:
                    note_type = "ok"
            else:
                if cache.away_team_runs > cache.home_team_runs:
                    note_type = "good"
                elif cache.away_team_runs < cache.home_team_runs:
                    note_type = "bad"
                else:
                    note_type = "ok"

            byte = {
                "name": "{away_team} @ {home_team}".format(away_team=game.away_team, home_team=game.home_team),
                "message": inning,
                "note": {
                    "message": "{away_score} - {home_score}".format(away_score=cache.away_team_runs,
                                                                    home_score=cache.home_team_runs),
                    "type": note_type
                },
                "url": game.game_day_url
            }
            self.response.write(json.dumps(byte))
        else:
            # return game preview
            byte = {
                "name": "{away_team} @ {home_team}".format(away_team=game.away_team, home_team=game.home_team),
                "message": game.start_time_display,
                "url": game.game_day_url
            }
            self.response.write(json.dumps(byte))

app = webapp2.WSGIApplication([
    ('/byte', ByteHandler)
], debug=True)

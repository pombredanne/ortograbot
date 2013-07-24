# -*- coding: utf-8 -*-
import langid
import logging
import pymongo
import os
import re
import sys
import twitter
import urllib
from datetime import datetime
from datetime import timedelta
from random import choice
from random import randint

logging.basicConfig()
logger = logging.getLogger(__name__)


class OrtograBot(object):
    """
    OrtograBot searches for certain orthographic errors on twitter and reports
    back to the user with the proper form.
    """

    def __init__(self, mongodb_url=None):
        """Setup MongoDB databse, Twitter API and rules"""
        mongodb_url = os.environ.get("MONGOHQ_URL", mongodb_url)
        self.debug = bool(os.environ.get("DEBUG", True))
        client = pymongo.MongoClient(mongodb_url)
        self.db = client[mongodb_url.rsplit("/", 1)[1]]
        credentials = self.db.twitterCredentials.find_one()
        self.username = credentials["username"]
        self.api = twitter.Api(
            consumer_key=credentials["consumer_key"],
            consumer_secret=credentials["consumer_secret"],
            access_token_key=credentials["access_token_key"],
            access_token_secret=credentials["access_token_secret"]
        )
        self.rules = [
            {
                "search": u"tí",
                "message": u"ti nunca lleva tilde → "
                           u"http://buscon.rae.es/dpd/?key=ti&origen=REDPD",
                "lang": u"es",
            },
            {
                "search": u"cuidate",
                "message": u"cuídate es esdrújula, "
                           u"por lo que siempre lleva tilde → "
                           u"http://buscon.rae.es/dpd/?key=tilde#113",
                "lang": u"es",
            },
            {
                "search": u"corazon",
                "message": u"corazón es aguda acabada en -n, "
                           u"por lo que siempre lleva tilde → "
                           u"http://buscon.rae.es/dpd/?key=tilde#111",
                "lang": u"es",
            },
            {
                "search": u"bicep",
                "message": u"la palabra «bicep» no existe, "
                           u"es bíceps, llana y con tilde por acabar en -s "
                           u"precedida de consonante → "
                           u"http://lema.rae.es/dpd/?key=b%C3%ADceps",
                "lang": u"es",
            },
            {
                "search": u"biceps",
                "message": u"bíceps es llana y acabada en -s "
                           u"precedida de consonante, "
                           u"por lo que siempre lleva tilde → "
                           u"http://lema.rae.es/dpd/?key=b%C3%ADceps",
                "lang": u"es",
            }
        ]
        self.punctuation = re.compile(r"[ \.,\?\!¡¿\n\t\-]+")
        self.emojis = [
            u"🐭", u"🐮", u"🐱", u"🐵", u"😁", u"😂", u"😃", u"😄", u"😅",
            u"😆", u"😇", u"😈", u"😉", u"😊", u"😋", u"😌", u"😍", u"😎",
            u"😏", u"😰", u"😱", u"😲", u"😳", u""]

    def run_rule(self):
        """Run one random rule and reply to the twitter user if needed"""
        rule = choice(self.rules)
        # HACK: Using quote_plus and encode to fix a bug in python-twitter
        #       search function
        search = urllib.quote_plus(rule["search"].encode("utf-8"))
        results = self.api.GetSearch(search)
        for status_obj in results:
            text_lower = status_obj.text.lower()
            if (rule["search"] not in self.punctuation.split(text_lower)
                    or self.username.lower() in text_lower
                    or langid.classify(status_obj.text)[0] != rule["lang"]):
                continue
            # To guarantee some human-like behaviour,
            # it only replies 25% of the time
            if randint(1, 100) > 75:
                # The 75% remaining, just tweet random messages
                if not self.debug:
                    try:
                        if randint(1, 100) > 75:
                            # 75% from the message of the rule
                            message = u"Recuerda: {} {}".format(
                                rule["message"],
                                choice(self.emojis)
                            )
                            # Add a random emoji icon to messages to avoid
                            # duplicated statuses
                            self.api.PostUpdate(message)
                        else:
                            # 25% a friendly message
                            message = (u"Soy ortolibán, "
                                       u"tu corrector ortográfico "
                                       u"amigo {}".format(choice(self.emojis)))
                            self.api.PostUpdate(message)
                    except Exception:
                        logger.error("Unexpected error: %s",
                                     sys.exc_info()[0:2])
                continue
            post_time = datetime.strptime(status_obj.created_at,
                                          '%a %b %d %H:%M:%S +0000 %Y')
            now = datetime.utcnow()
            one_day_ago = now - timedelta(days=1)
            reply_to = {
                "status_id": status_obj.id,
                "screen_name": status_obj.user.screen_name,
                "post_time": post_time,
                "text": status_obj.text,
                "reply_time": now,
                "search": rule["search"],
                "lang": rule["lang"],
                "place": status_obj.place,
                "coordinates": status_obj.coordinates,
            }
            user_already_messaged = self.db.messaged.find_one({
                "screen_name": reply_to["screen_name"],
                "search": rule["search"],
                "lang": rule["lang"],
                "reply_time": {"$gte": one_day_ago}
            })
            if not user_already_messaged:
                try:
                    reply_message = u"@{} {}".format(reply_to["screen_name"],
                                                     rule["message"])
                    if not self.debug:
                        self.api.PostUpdate(
                            reply_message,
                            in_reply_to_status_id=status_obj.id
                        )
                    self.db.messaged.insert(reply_to, safe=True)
                    # We only reply to one user
                    break
                except Exception:
                    logger.error("Unexpected error: %s", sys.exc_info()[0:2])

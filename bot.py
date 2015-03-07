import tweepy
from tweepy.streaming import StreamListener
import requests
import json
from collections import Counter
import sys
import os


API_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
API_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
ACCESS_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

concepts = json.load(open("concepts_books.json", "r"))

auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)

api = tweepy.API(auth)

tweeted = [status.text for status in api.user_timeline("GutenFlag")]


def uniqify(seq, idfun=None): 
    if idfun is None:
       def idfun(x): return x
    seen = {}
    result = []
    for item in seq:
       marker = idfun(item)
       if marker in seen: continue
       seen[marker] = 1
       result.append(item)
    return result


def get_status_text(user):
    return " ".join([status.text for status in api.user_timeline(user)])


def get_alchemy_json(text):
    endpt = "http://access.alchemyapi.com/calls/text/TextGetRankedConcepts"
    payload = {
        "apikey": os.environ.get('ALCHEMY_API_KEY'),
        "text": text,
        "outputMode": "json",
        "showSourceText": 0,
        "knowledgeGraph": 1,
        "maxRetrieve": 500
    }
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    r = requests.post(endpt, data=payload, headers=headers)
    return r.json()


def concept_list(alchemy_json):
    return sorted([(c["text"], c["relevance"]) for c in alchemy_json["concepts"]], key=lambda x: x[1])


def find_intersect(cl):
    cl_dict = dict(cl)
    user_concept_set = set([c[0] for c in cl])
    alchemy_set = set(concepts.keys())
    intersect = sorted(list(user_concept_set & alchemy_set), key=lambda x: cl_dict[x])
    return intersect


def find_books(cl):
    candidates = []
    for c in cl:
        candidates.extend(concepts[c])
    candidate_tuples = sorted(candidates, key=lambda x: x[1])
    cand = [i[0] for i in candidate_tuples]
    hiFreq = dict(Counter(cand).most_common())
    candi = uniqify(sorted(cand, key=lambda x: hiFreq[x]))
    return candi


def make_tweet(cl, user, tid):
    if cl:
        if len(cl) > 2:
            rec_list = cl[-3:]
        else:
            rec_list = cl
        ul = " ".join(["http://gutenberg.org/ebooks/"+c for c in rec_list])
        text = "%s for @%s" % (ul, user)
    else:
        text = "Sorry, @%s. I have no recommendations for you at the moment. Write some more relevant tweets and try again!" % user
    if not text in tweeted:
        api.update_status(status=text, in_reply_to_status_id=tid)
        tweeted.append(text)



def recommend(un, tweet_id):
    make_tweet(
        find_books(
            find_intersect(
                concept_list(
                    get_alchemy_json(
                        get_status_text(un))))), un, tweet_id)


class RecListener(StreamListener):
    def on_status(self, status):
        print status.text
        print status.user.screen_name
        print status.id
        recommend(status.user.screen_name, status.id)

    def on_error(self, status_code):
        print >> sys.stderr, 'Encountered error with status code:', status_code
        return True # Don't kill the stream

    def on_timeout(self):
        print >> sys.stderr, 'Timeout...'
        return True # Don't kill the stream



sapi = tweepy.streaming.Stream(auth, RecListener())
sapi.filter(track=['@gutenflag'])

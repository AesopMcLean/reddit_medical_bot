import praw
import string
import copy
import json
import yaml
import time
import calendar
import datetime

PHRASES = ['peripheral nerv', 'central nerv', 'electrical stimulat', 'electric stimulat', 'epidural', 'rejuvenat',
           'cas-', 'cas9', 'cas3', 'cas1', 'myelin', 'synap', 'implant', 'transplant', 'nerve', 'neuro', 'regenerat',
           'gene therap', 'gene edit', 'chemotherap', 'organoid', 'surger', 'neural', 'muscle', 'muscular', 'mucus',
           'traumatic brain']

KEYWORDS = ['ngf', 'bdnf', 'pns', 'cns', 'spine', 'spinal', 'trkb', 'gene', 'nasal', 'injury', 'autonomic']

EXCLUDE_PHRASE = ['?', 'climate change', 'forest', 'aubrey de grey', 'environment', 'food', 'crop', 'farm',
                  'neural net', 'neural-net', 'fossil', 'amazon', 'samsung']

EXCLUDE_KEYWORD = ['depression', 'anxiety', 'ancient', 'cat', 'cats', 'dog', 'dogs', 'prize']

EXCLUDE_DOMAIN = ['youtube.com', 'youtu.be', 'imgur.com', 'reddit.com', 'redd.it', 'instagram.com', 'dailymail.co',
                  'vimeo.com', 'forms.gle', 'strawpoll.me', 'strawpoll.com', 'forbes.com', 'vice.com', 'huffpost.com',
                  'huffingtonpost.com', 'twitter.com', 'docs.google.com', 'futurism.com', 'naturalnews.com',
                  'newsweek.com', 'bigthink.com', 'scienceblogs.com', 'ageofautism.com', 'psychologytoday.com',
                  'foodbabe.com', 'gfycat.com', 'facebook.com', 'sky.com']

SEARCH_SUBREDDITS = ['science', 'technology', 'bioscience', 'health', 'sciences', 'everythingscience', 'medtech',
                     'biotech', 'crispr', 'stemcells', 'futurology', 'longevity']

with open('flair_choices.json') as json_file:
    FLAIR_CHOICES = json.load(json_file)

with open('medical_bot_credentials.yml', 'r') as yml_file:
    credentials = yaml.safe_load(yml_file)


def main():
    reddit = praw.Reddit(client_id=credentials["client_id"],
                         client_secret=credentials["client_secret"],
                         user_agent='<console:%s:1.1.0 (by /u/Future_Hope)>' % credentials["username"],
                         username=credentials["username"],
                         password=credentials["password"])

    home_subreddit = reddit.subreddit('regenerate')
    user = reddit.redditor(credentials["username"])

    def largest_number(flair_dict):
        highest = []
        for key, value in flair_dict.items():
            for keyword in value[1]:
                value[0] += value[1][keyword]
            highest.append([value[0], key])
        if max(highest)[0] is 0:
            return 'miscellaneous'.title()  # default flair if no match found
        else:
            return max(highest)[1].title()

    def flair_title(submission):
        flair_copy = copy.deepcopy(FLAIR_CHOICES)
        # title with punctuation removed, lower case, NOT SPLIT INTO LIST but left as string
        normalized_text = submission.title.translate(str.maketrans('', '', string.punctuation)).lower()
        for flair in flair_copy:
            for keyword in flair_copy[flair][1]:
                while keyword in normalized_text:  # to count occurrences of each keyword
                    flair_copy[flair][1][keyword] += 1
                    normalized_text = normalized_text.replace(keyword, "", 1)
        return largest_number(flair_copy)

    def set_flair_as(submission):
        flair_dict = submission.flair.choices()  # dict of flair choices and their ID codes
        # finds and returns the flair ID for the chosen flair
        template_id = next(x for x in flair_dict if x['flair_text'] == flair_title(submission))['flair_template_id']
        return submission.flair.select(template_id)

    def validity_check(post_subreddit, current_submission):
        for phrase in EXCLUDE_PHRASE:
            if phrase in current_submission.title.lower():
                return False
        for domain in EXCLUDE_DOMAIN:
            if domain in current_submission.url.lower():
                return False
        # title with punctuation removed, lower case, and string split into a list of all words
        normalize_title = \
            current_submission.title.translate(str.maketrans('', '', string.punctuation)).lower().split()
        for word in EXCLUDE_KEYWORD:
            if word in normalize_title:
                return False
        for home_submission in post_subreddit.new(limit=None):
            if current_submission.url == home_submission.url \
                    or current_submission.title.lower() == home_submission.title.lower()\
                    or current_submission.selftext is not ""\
                    or current_submission.created_utc <= (calendar.timegm(time.gmtime()) - 23652000):  # <= 9 months old
                return False
        return True

    def submit_post(post_subreddit, current_subreddit, current_submission):
        current_submission.crosspost(post_subreddit, title=None, send_replies=False)
        for new_submission in post_subreddit.new(limit=1):
            set_flair_as(new_submission)
            new_submission.reply("This is a crosspost from /r/%s. Here is the link to the original thread: %s"
                                 % (current_subreddit, current_submission.permalink))
        for comment in user.comments.new(limit=1):
            comment.mod.distinguish(sticky=True)
        print("%s: Submitted - %s - From %s - %s\n-----"
              % (credentials["username"], datetime.datetime.now().strftime("%a, %b %d, %Y %I:%M:%S %p"),
                 current_subreddit.display_name.upper(),
                 current_submission.title))

    def try_post(post_subreddit, current_subreddit, current_submission):
        try:
            submit_post(post_subreddit, current_subreddit, current_submission)
        except praw.exceptions.APIException as e:
            if e.error_type == "INVALID_CROSSPOST_THING":
                print("%s: EXCEPTION - Crosspost\n-----" % credentials["username"])
                while True:
                    subreddit_scraper()
                    saved_scraper()

    def subreddit_scraper():
        for subreddit in SEARCH_SUBREDDITS:
            current_subreddit = reddit.subreddit(subreddit)
            submission_stream = current_subreddit.stream.submissions(pause_after=-1)
            for current_submission in submission_stream:
                if current_submission is None:  # None means no new posts
                    break
                # title with punctuation removed, lower case, and string split into a list of all words
                normalize_title = \
                    current_submission.title.translate(str.maketrans('', '', string.punctuation)).lower().split()
                for word in KEYWORDS:
                    if word in normalize_title:
                        if validity_check(home_subreddit, current_submission):
                            try_post(home_subreddit, current_subreddit, current_submission)
                for phrase in PHRASES:
                    if phrase in current_submission.title.lower():
                        if validity_check(home_subreddit, current_submission):
                            try_post(home_subreddit, current_subreddit, current_submission)

    def saved_scraper():
        saved = user.saved(limit=None)
        for current_save in saved:
            repost = False
            for home_submission in home_subreddit.new(limit=None):
                if current_save.url == home_submission.url \
                        or current_save.title == home_submission.title:
                    repost = True
            if repost is False:
                try_post(home_subreddit, current_save.subreddit, current_save)
            current_save.unsave()

    while True:
        subreddit_scraper()
        saved_scraper()


if __name__ == "__main__":
    logf = open("exception.log", "w")
    print("%s: Started\n-----" % credentials["username"])
    # time.sleep(15)
    try:
        main()
    except Exception as e:
        logf.write("Exception on {0}: {1}\n".format(str(datetime.datetime.now().strftime("%a, %b %d, %Y %I:%M:%S %p")),
                                                    str(e)))
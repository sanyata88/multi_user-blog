import os
import re
import codecs
import hashlib
import hmac
import random
import string
import webapp2
import jinja2

from users import *

from google.appengine.ext import ndb

def portfolio_key(name = 'default'):
    """Assigns a key to BlogPost"""
    return ndb.Key('portfolio', name)

class Project(ndb.Model):
    """Contains info about a blog post"""
    title = ndb.StringProperty(required = True)
    description = ndb.TextProperty(required = True)
    created = ndb.DateTimeProperty(auto_now_add = True)
    # TODO: Find way to include an image
    link = ndb.StringProperty(required = False)

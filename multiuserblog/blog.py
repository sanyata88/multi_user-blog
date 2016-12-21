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

def blog_key(name = 'default'):
    """Assigns a key to BlogPost"""
    return ndb.Key('blogs', name)

class BlogPost(ndb.Model):
    """Contains info about a blog post"""
    subject = ndb.StringProperty(required = True)
    content = ndb.TextProperty(required = True)
    created = ndb.DateTimeProperty(auto_now_add = True)
    author = ndb.StructuredProperty(User)
    likes = ndb.IntegerProperty(default = 0)

class Comment(ndb.Model):
    """Contains info about a comment"""
    post_id = ndb.IntegerProperty(required = True)
    author = ndb.StructuredProperty(User)
    content = ndb.StringProperty(required = True)
    created = ndb.DateTimeProperty(auto_now_add = True)

class Like(ndb.Model):
    """Contains info about a like"""
    post_id = ndb.IntegerProperty(required = True)
    author = ndb.StructuredProperty(User)

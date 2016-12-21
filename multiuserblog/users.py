import os
import re
import codecs
import hashlib
import hmac
import random
import string
import webapp2
import jinja2

from secret import secret as SECRET
from google.appengine.ext import ndb

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$") # valid user
PWD_RE = re.compile(r"^.{3,20}$") # valid password
EMAIL_RE = re.compile(r"^[\S]+@[\S]+.[\S]+$") # valid email

def valid_username(username):
    """Checks if username is valid"""
    return USER_RE.match(username)

def valid_password(password):
    """Checks if password is valid"""
    return PWD_RE.match(password)

def valid_email(email):
    """Checks if email is valid"""
    return EMAIL_RE.match(email)

def hash_str(s):
    """Hashes s using HMAC"""
    return hmac.new(SECRET, s).hexdigest()

def make_secure_val(s):
    """Makes a secure value using hash"""
    return "%s|%s" % (s, hash_str(s))

def check_secure_val(h):
    """Checks if h is a valid secure value"""
    val = h.split('|')[0]
    if h == make_secure_val(val):
        return val

def make_salt():
    """Makes a salt for password hashing"""
    return ''.join(random.choice(string.letters) for x in xrange(5))

def make_pw_hash(name, pw, salt = None):
    """Hashes password"""
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (h, salt)

def valid_pw(name, pw, h):
    """Deciphers password hash and determines validity"""
    salt = h.split(',')[1]
    return h == make_pw_hash(name, pw, salt)

def users_key(group = 'default'):
    """Defines a key for User"""
    return ndb.Key('users', group)

class User(ndb.Model):
    """Contains info about a user"""
    username = ndb.StringProperty(required = True)
    pwd_hash = ndb.StringProperty(required = True)
    email = ndb.StringProperty()

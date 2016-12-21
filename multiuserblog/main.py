import os
import re
import time
import codecs
import hashlib
import hmac
import random
import string 

import webapp2
import jinja2

from users import *
from blog import *
from portfolio import Project, portfolio_key

from google.appengine.ext import ndb

template_dir = os.path.join(os.path.dirname(document.__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

class Handler(webapp2.RequestHandler):
    """Defines functions for rendering pages and setting cookies"""
    def write(self, *a, **kw):
        """Writes to the web page"""
        self.response.write(*a, **kw)

    def render_str(self, template, **kw):
        """Renders a Jinja template"""
        kw['user'] = self.user
        t = jinja_env.get_template(template)
        return t.render(kw)

    def render(self, template, **kw):
        """Writes rendered template to page"""
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        """Sets a cookie"""
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        """Reads a cookie and returns its value"""
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def initialize(self, *a, **kw):
        """Initializes the page with the signed-in user"""
        webapp2.RequestHandler.initialize(self, *a, **kw)
        username = self.read_secure_cookie('user')
        self.user = User.gql("WHERE username = '%s'" % username).get()

class MainHandler(Handler):
    """Renders the front page"""
    def get(self):
        self.render("index.html")

class Rot13Handler(Handler):
    """Handles the secret Rot13 page"""
    def get(self):
        self.render("rot13.html")

    def post(self):
        text = self.request.get("text")
        if text:
            text = codecs.encode(text, 'rot_13')
        self.render('rot13.html', text = text)

class SignupHandler(Handler):
    """Handles the signup page"""
    def get(self):
        self.render("signup.html")

    def post(self):
        user_error = False
        pwd_error = False
        verify_error = False
        email_error = False
        exist_error = False
        username = self.request.get("username")
        password = self.request.get("password")
        verify = self.request.get("verify")
        email = self.request.get("email")

        user = User.gql("WHERE username = '%s'" % username).get()
        if user:
            exist_error = True # user already exists
            self.render("signup.html", exist_error = exist_error,
                                       username = username,
                                       email = email)
        else:
            if not username or not valid_username(username):
                user_error = True # username invalid
            if not password or not verify or not valid_password(password):
                pwd_error = True # password invalid
            if password != verify:
                verify_error = True # passwords don't match
            if email and not valid_email(email):
                email_error = True # email invalid

            if user_error or pwd_error or verify_error or email_error:
                self.render("signup.html", user_error = user_error,
                                           pwd_error = pwd_error,
                                           verify_error = verify_error,
                                           email_error = email_error,
                                           username = username,
                                           email = email)
            else:
                # Everything is good, register the user
                user = User(username = username, pwd_hash = make_pw_hash(username, password), email = email)
                user.put()
                user_cookie = make_secure_val(str(username))
                self.response.headers.add_header("Set-Cookie", "user=%s; Path=/" % user_cookie)
                time.sleep(0.1)
                self.redirect("/welcome")

class WelcomeHandler(Handler):
    """Renders the welcome page"""
    def get(self):
        user = self.request.cookies.get('user')
        if user:
            username = check_secure_val(user)
            if username:
                self.render("welcome.html", username = username)
            else:
                self.redirect('/signup')
        else:
            self.redirect('/signup')

class LoginHandler(Handler):
    """Handles user login"""
    def get(self):
        self.render("login.html")

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")
        user = User.gql("WHERE username = '%s'" % username).get()
        if user and valid_pw(username, password, user.pwd_hash):
            user_cookie = make_secure_val(str(username))
            self.response.headers.add_header("Set-Cookie", "user=%s; Path=/" % user_cookie)
            self.redirect("/welcome")
        else:
            error = "Not a valid username or password"
            self.render("login.html", username = username, error = error)

class LogoutHandler(Handler):
    """Handles user logout, redirects to signup on completion"""
    def get(self):
        self.response.headers.add_header("Set-Cookie", "user=; Path=/")
        self.redirect("/login")

class BlogHandler(Handler):
    """Renders the main blog page"""
    def get(self):
        posts = BlogPost.gql("ORDER BY created DESC")
        self.render("blog.html", posts = posts)

class NewPostHandler(Handler):
    """Handles creation of new posts"""
    def get(self):
        if self.user.email == "anthony.fumagalli@gmail.com":
            self.render("newpost.html")
        elif self.user:
            error = "you do not have permission to create a post, but you may comment on existing posts"
            self.redirect("/blog")
        else:
            self.redirect("/login")

    def post(self):
        if not self.user:
            # if no user, redirect to blog page
            self.redirect("/blog")
        subject = self.request.get("subject")
        content = self.request.get("content")
        if subject and content:
            post = BlogPost(parent = blog_key(), subject = subject, content = content, author = self.user)
            post.put()
            self.redirect("/blog/%s" % str(post.key.id()))
        else:
            error = "you need both a subject and content"
            self.render("newpost.html", subject = subject, content = content, error = error)

class PostHandler(Handler):
    """Renders the page for a single post, handles comments and likes on post"""
    def get(self, post_id):
        key = ndb.Key('BlogPost', int(post_id), parent=blog_key())
        post = key.get()
        comments = Comment.gql("WHERE post_id = %s ORDER BY created DESC" % int(post_id))
        liked = None
        if self.user:
            liked = Like.gql("WHERE post_id = :1 AND author.username = :2", int(post_id), self.user.username).get()
        if not post:
            self.error(404)
            return
        self.render("blogpost.html", post = post, comments = comments, liked = liked)
    def post(self, post_id):
        key = ndb.Key('BlogPost', int(post_id), parent=blog_key())
        post = key.get()
        if self.request.get("like"):
            # User liked post
            if post and self.user:
                post.likes += 1
                like = Like(post_id = int(post_id), author = self.user)
                like.put()
                post.put()
                time.sleep(0.2)
            self.redirect("/blog/%s" % post_id)
        elif self.request.get("unlike"):
            # User unliked post
            if post and self.user:
                post.likes -= 1
                like = Like.gql("WHERE post_id = :1 AND author.username = :2", int(post_id), self.user.username).get()
                key = like.key
                key.delete()
                post.put()
                time.sleep(0.2)
            self.redirect("/blog/%s" % post_id)
        else:
            # User commented on post
            content = self.request.get("content")
            if content:
                comment = Comment(content = str(content), author = self.user, post_id = int(post_id))
                comment.put()
                time.sleep(0.1)
                self.redirect("/blog/%s" % post_id)
            else:
                self.render("blogpost.html", post = post)

class EditPostHandler(Handler):
    """Handles editing of blog posts"""
    def get(self):
        if self.user:
            post_id = self.request.get("post")
            key = ndb.Key('BlogPost', int(post_id), parent=blog_key())
            post = key.get()
            if not post:
                self.error(404)
                return
            self.render("editpost.html", subject = post.subject, content = post.content)
        else:
            self.redirect("/login")

    def post(self):
        post_id = self.request.get("post")
        key = ndb.Key('BlogPost', int(post_id), parent=blog_key())
        post = key.get()
        if post and post.author.username == self.user.username:
            subject = self.request.get("subject")
            content = self.request.get("content")
            if subject and content:
                post.subject = subject
                post.content = content
                post.put()
                time.sleep(0.1)
                self.redirect("/blog")
            else:
                error = "you need both a subject and content"
                self.render("editpost.html", subject = subject, content = content, error = error)
        else:
            self.redirect("/blog")

class DeletePostHandler(Handler):
    """Handles deletion of blog posts"""
    def get(self):
        if self.user:
            post_id = self.request.get("post")
            key = ndb.Key('BlogPost', int(post_id), parent=blog_key())
            post = key.get()
            if not post:
                self.error(404)
                return
            self.render("deletepost.html", post = post)
        else:
            self.redirect("/login")

    def post(self):
        post_id = self.request.get("post")
        key = ndb.Key('BlogPost', int(post_id), parent=blog_key())
        post = key.get()
        if post and post.author.username == self.user.username:
            key.delete()
            time.sleep(0.1)
        self.redirect("/blog")

class EditCommentHandler(Handler):
    """Handles editing of comments"""
    def get(self):
        if self.user:
            comment_id = self.request.get("comment")
            key = ndb.Key('Comment', int(comment_id))
            comment = key.get()
            if not comment:
                self.error(404)
                return
            self.render("editcomment.html", content = comment.content, post_id = comment.post_id)
        else:
            self.redirect("/login")

    def post(self):
        comment_id = self.request.get("comment")
        key = ndb.Key('Comment', int(comment_id))
        comment = key.get()
        if comment and comment.author.username == self.user.username:
            content = self.request.get("content")
            if content:
                comment.content = content
                comment.put()
                time.sleep(0.1)
                self.redirect("/blog/%s" % comment.post_id)
            else:
                error = "you need both a subject and content"
                self.render("editcomment.html", content = content, post_id = comment.post_id, error = error)
        else:
            self.redirect("/blog/%s" % comment.post_id)

class DeleteCommentHandler(Handler):
    """Handles deletion of comments"""
    def get(self):
        if self.user:
            comment_id = self.request.get("comment")
            key = ndb.Key('Comment', int(comment_id))
            comment = key.get()
            if not comment:
                self.error(404)
                return
            self.render("deletecomment.html", comment = comment)
        else:
            self.redirect("/login")

    def post(self):
        comment_id = self.request.get("comment")
        key = ndb.Key('Comment', int(comment_id))
        comment = key.get()
        if comment and comment.author.username == self.user.username:
            post_id = comment.post_id
            key.delete()
            time.sleep(0.1)
        self.redirect("/blog/%s" % post_id)

class AboutHandler(Handler):
    """Handles rendering of the about me page"""
    def get(self):
        self.render("about.html")

class PortfolioHandler(Handler):
    """Renders the main portfolio page"""
    def get(self):
        projects = Project.gql("ORDER BY created DESC")
        self.render("portfolio.html", projects = projects)

class NewProjectHandler(Handler):
    """Handles creation of new portfolio projects"""
    def get(self):
        if self.user.email == "anthony.fumagalli@gmail.com":
            self.render("newproject.html")
        elif self.user:
            error = "you do not have permission to create a project, but you may comment on existing projects"
            self.redirect("/portfolio")
        else:
            self.redirect("/login")

    def post(self):
        if not self.user:
            # if no user, redirect to blog page
            self.redirect("/portfolio")
        title = self.request.get("title")
        description = self.request.get("description")
        link = self.request.get("link")
        if title and description:
            project = Project(parent = portfolio_key(), title = title, description = description, link = link)
            project.put()
            self.redirect("/portfolio")
            # self.redirect("/portfolio/%s" % str(project.key.id()))
        else:
            error = "you need both a title and description"
            self.render("newproject.html", title = title, description = description, link = link, error = error)

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/rot13', Rot13Handler),
    ('/signup', SignupHandler),
    ('/welcome', WelcomeHandler),
    ('/login', LoginHandler),
    ('/logout', LogoutHandler),
    ('/blog', BlogHandler),
    ('/blog/newpost', NewPostHandler),
    ('/blog/([0-9]+)', PostHandler),
    ('/blog/edit', EditPostHandler),
    ('/blog/delete', DeletePostHandler),
    ('/comment/edit', EditCommentHandler),
    ('/comment/delete', DeleteCommentHandler),
    ('/about', AboutHandler),
    ('/portfolio', PortfolioHandler),
    ('/portfolio/newproject', NewProjectHandler)
], debug=True)

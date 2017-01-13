import os
import re
import random
import hashlib
import hmac
import database
from string import letters

import webapp2
import jinja2

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

secret = '31bd41fff8aa4157a5d2fec13c99451d'

def hashPassword(password, username):
    return hashlib.sha256(password + username + secret).hexdigest()

def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class MasterHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def error(self):
        self.render('error.html')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and database.User.getUserById(uid)

class MainPage(MasterHandler):
    def get(self):
        posts = database.Post.query()
        self.render('index.html', posts = posts)

class AccountPage(MasterHandler):
    def get(self):
        self.render('account.html')

class LoginPage(MasterHandler):
    def get(self):
        self.render('login.html')

    def post(self):
        name = self.request.get('username')
        password = self.request.get('password')
        password_hash = hashPassword(password, name)
        user = database.User.getUserByNameAndPassword(
            name, password_hash)
        if user:
            self.set_secure_cookie('user_id', str(
                               database.User.getUserId(user)))
            self.redirect('/')
        else:
            msg = 'Invalid login'
            self.render('login.html', error = msg)

class RegisterPage(MasterHandler):
    def get(self):
        self.render('register.html')

    def post(self):
        name = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')

        if valid_username(name):
            if valid_password(password):
                if password == verify:
                    user = database.User.getUserByName(name)
                    if user:
                        if user.user_name == name:
                            msg = "The username already exisits."
                            self.render('register.html', error = msg)
                    else:
                        password_hash = hashPassword(password, name)
                        user_id = database.User.addUser(name, password_hash)
                        self.set_secure_cookie('user_id', str(user_id))
                        self.redirect('/')
                else:
                    msg = "The passwords do not match."
                    self.render('register.html', error = msg)
            else:
                msg = "That wasn't a valid password."
                self.render('register.html', error = msg)
        else:
            msg = "That's not a valid username."
            self.render('register.html', error = msg)

class LogoutPage(MasterHandler):
    def get(self):
        self.logout()
        self.redirect('/')



class PostPage(MasterHandler):
    def get(self, post_id):
        post = database.Post.getPost(int(post_id))
        if not post:
            return self.error()
        comments = database.Comment.getCommentsByPostId(post_id)
        like_text = 'Like'
        if self.user:
            user = self.user
            like = database.LikePost.getLikeByPostAndAuthor(post_id, user.user_name)
            if like:
                like_text = 'Liked'
        self.render("viewpost.html", post = post, comments = comments, like = like_text)

class AddPostPage(MasterHandler):
    def get(self):
        if self.user:
            self.render("addpost.html")
        else:
            self.redirect("/login")

    def post(self):
        if not self.user:
            return self.redirect('/')

        user = self.user
        title = self.request.get('title')
        content = self.request.get('content')
        author = user.user_name
        post_id = database.Post.addPost(title = title,
                                        content = content,
                                        author = author)
        self.redirect('/post/' + str(post_id))


class EditPostPage(MasterHandler):
    def get(self, post_id):
        post = database.Post.getPost(int(post_id))
        if not post:
            self.error()
            return
        self.render("addpost.html", post = post)

    def post(self, post_id):
        if not self.user:
            return self.redirect('/')

        user = self.user
        title = self.request.get('title')
        content = self.request.get('content')
        #post_id = self.request.get('post_id')
        author = user.user_name
        database.Post.editPost(title = title,
                               content = content,
                               author = author,
                               post_id = post_id)
        self.redirect('/post/' + str(post_id))

class DeletePost(MasterHandler):
    def get(self):
        self.redirect('/')

    def post(self):
        if not self.user:
            return self.redirect('/')

        user = self.user
        post_id = self.request.get('postid')
        post = database.Post.getPost(post_id)

        if post.post_author == user.user_name:
            success = database.Post.deletePost(int(post_id))
            if success:
                self.render('index.html')
                self.redirect('/')
        else:
            self.error(401)
            return

class AddComment(MasterHandler):
    def post(self):
        if not self.user:
            return self.redirect('/')

        user = self.user
        post_id = self.request.get('post_id')
        content = self.request.get('content')
        if post_id and content:
            database.Comment.addComment(post_id = post_id, text = content, author = user.user_name)
            return self.redirect('/post/'+post_id)
        else:
            return self.error()

class EditComment(MasterHandler):

    def get(self, comment_id):
        self.render('editcomment.html')
    def post(self, comment_id):
        if not self.user:
            return self.redirect('/')
        comment_id = self.request.get('comment_id')
        commentObj = database.Comment.getComment(comment_id)
        comment = self.request.get('comment')
        if comment:
            commentObj.comment_text = comment
            commentObj.put()
            post = Post.get_by_id(int(comment.comment_post))
            self.redirect('/post/%s')


class DeleteComment(MasterHandler):
    def get(self):
        self.redirect('/')

    def post(self):
        if not self.user:
            return self.redirect('/')

        user = self.user
        comment_id = self.request.get('comment_id')
        comment = database.Comment.getComment(comment_id)

        if comment.comment_author == user.user_name:
            success = database.Comment.deleteComment(int(comment_id))
            if success:
                return self.redirect('/')
        else:
            self.error(401)
            return

class AddLike(MasterHandler):
    def get(self, post_id):
        if not self.user:
            return self.redirect('/')

        user = self.user
        post = database.Post.getPost(post_id)
        if not post:
            return self.redirect('/')
        like = database.LikePost.getLikeByPostAndAuthor(post_id, user.user_name)
        if like:
            database.LikePost.deleteLike(like.key.id())
        else:
            if post.post_author == user.user_name:
                return self.redirect('/')
            else:
                database.LikePost.addLike(post_id, user.user_name)

        return self.redirect('/post/'+post_id)

        if post_id and content:
            database.Comment.addComment(post_id = post_id, text = content, author = user.user_name)
            return self.redirect('/post/'+post_id)
        else:
            return self.error()

class DeleteLike(MasterHandler):
    def get(self):
        self.redirect('/')

    def post(self):
        if not self.user:
            return self.redirect('/')

        user = self.user
        post_id = self.request.get('postid')
        post = database.Post.getPost(post_id)

        if post.post_author == user.user_name:
            success = database.Post.deletePost(int(post_id))
            if success:
                self.render('index.html')
                self.redirect('/')
        else:
            self.error(401)
            return

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/account', AccountPage),
    ('/login', LoginPage),
    ('/register', RegisterPage),
    ('/logout', LogoutPage),
    ('/newpost', AddPostPage),
    ('/editpost/([0-9]+)', EditPostPage),
    ('/post/([0-9]+)', PostPage),
    ('/delete', DeletePost),
    ('/addcomment', AddComment),
    ('/editcomment/([0-9]+)', EditComment),
    ('/deletecomment', DeleteComment),
    ('/addlike/([0-9]+)', AddLike),
    ('/deletelike', DeleteLike),
], debug=True)

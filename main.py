from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from functools import wraps
from flask import abort
from flask_gravatar import Gravatar
from datetime import date
import smtplib
import os

# creating an app
app = Flask(__name__)
# Need to have a secret key for displaying flash messages and functionality of Login Manager
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
# using database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL1", "sqlite:///registeredUsers.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# initializing login manager
login_manager = LoginManager()
login_manager.init_app(app)

# for creating avatars next to comment author name
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)

# users database
class Users(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    registrant_name = db.Column(db.String(200), nullable=False)
    registrant_email = db.Column(db.String(200), nullable=False, unique=True)
    registrant_password = db.Column(db.String(1000), nullable=False)

    posts = relationship("Posts", back_populates="author")
    comments = relationship("Comments", back_populates="comment_author")

# posts database
class Posts(db.Model):
    __tablename__ = "posted_blogs"
    id = db.Column(db.Integer, primary_key=True)
    post_title = db.Column(db.String(250), nullable=False)
    post_body = db.Column(db.String(5000), nullable=False)
    date = db.Column(db.String(250), nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("Users", back_populates="posts")

    comments = relationship("Comments", back_populates="post")

# comments database
class Comments(db.Model):
    __tablename__ = "posted_comments"
    id = db.Column(db.Integer, primary_key=True)
    comment_body = db.Column(db.String(500), nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("Users", back_populates="comments")

    posted_blog_id = db.Column(db.Integer, db.ForeignKey("posted_blogs.id"))
    post = relationship("Posts", back_populates="comments")


# email received from users database
class Contacts(db.Model):
    __tablename__ = "email_inquiries"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False)
    email_body = db.Column(db.String(5000), nullable=False)


# db.create_all()

# callback used to reload the user object from the user ID stored in the session
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

# admin access only decorator
def admin_only_access(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return function(*args, **kwargs)
    return decorated_function


# once user or admin logs in they will see a list of posts
@app.route('/')
def home():
    all_posts = Posts.query.all()
    if all_posts == None:
        return render_template("base.html")
    return render_template("base.html", posts=all_posts, current_user=current_user)


# register page form
@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["your_name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        print(name, email, password, confirm_password)
        if Users.query.filter_by(registrant_email=email).first():
            flash("Email already exists. Choose another email or go to log in page.")
            return redirect(url_for("register"))
        elif password != confirm_password:
            flash("Password does not match. Try again.")
            return redirect(url_for("register"))
        else:
            new_user = Users(
                registrant_name=name,
                registrant_email=email,
                registrant_password=generate_password_hash(password=password, method="pbkdf2:sha256", salt_length=8)
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("home", current_user=current_user))
    return render_template("register.html")


# login page form
@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = Users.query.filter_by(registrant_email=email).first()
        # print(email, password, user)
        if user == None:
            flash("Email does not exist in database. Enter another email or go to registration page.")
            return redirect(url_for("login"))
        elif not check_password_hash(user.registrant_password, password):
            flash("Incorrect password.")
            return redirect(url_for("login"))
        else:
            login_user(user)
            # print(current_user.id)
            return redirect(url_for("home", current_user=current_user))

    return render_template("login.html")

# contact page form
@app.route('/contact', methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        email_inquiry = Contacts(
            email=request.form["email"],
            email_body=request.form["message"]
        )
        db.session.add(email_inquiry)
        db.session.commit()
        return redirect(url_for("home", current_user=current_user))
    return render_template("contact.html")

# route only for admin user to add new post or ediit existing post
@app.route('/post', methods=["GET", "POST"])
@login_required
@admin_only_access
def post():
    post_to_change = True
    if request.method == "POST":
        new_post = Posts(
            post_title=request.form["title"],
            post_body=request.form["post_body"],
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("home", current_user=current_user))
    return render_template("post.html", current_user=current_user, new_post=post_to_change)


# route to see clicked post where user can leave a comment
@app.route('/show-post', methods=["GET", "POST"])
@login_required
def show_post():
    post_to_display = Posts.query.get(request.args.get("post_id"))
    comments = Comments.query.all()
    comments_to_display = [comment for comment in comments if comment.posted_blog_id == post_to_display.id]
    if request.method == "POST":
        new_comment = Comments(
            comment_body=request.form["comment"],
            author_id=current_user.id,
            posted_blog_id=post_to_display.id
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("home", current_user=current_user))
    return render_template("show-post.html", post=post_to_display, comments=comments_to_display, current_user=current_user)


# route for admin where he can delete existing posts and comments
@app.route('/delete')
@login_required
@admin_only_access
def delete():
    item_to_delete = request.args.to_dict()
    item_to_delete_key = list(item_to_delete.keys())[0]
    if item_to_delete_key == "post_id":
        post_to_delete = Posts.query.get(request.args.get("post_id"))
        db.session.delete(post_to_delete)
        db.session.commit()
    else:
        comment_to_delete = Comments.query.get(request.args.get("comment_id"))
        db.session.delete(comment_to_delete)
        db.session.commit()
    return redirect(url_for("home", current_user=current_user))


# route for admin to edit existing post
@app.route('/edit', methods=["GET", "POST"])
@login_required
@admin_only_access
def edit():
    post_to_change = False
    post_to_edit = Posts.query.get(request.args.get("post_id"))
    if request.method == "POST":
        post_to_edit.post_title = request.form["change_title"]
        post_to_edit.post_body = request.form["change_post_body"]
        db.session.commit()
        return redirect(url_for("home", current_user=current_user))
    return render_template("post.html", current_user=current_user, post=post_to_edit, new_post=post_to_change)


# route for admin to see a list of all emails send by users via contact page
@app.route('/email-messages')
@login_required
@admin_only_access
def see_emails():
    all_emails = Contacts.query.all()
    if all_emails == None:
        return render_template("emails.html", current_user=current_user)
    return render_template("emails.html", emails=all_emails, current_user=current_user)


# route for admin to see specific email send by user and reply by sending email back
@app.route('/show-email', methods=["GET", "POST"])
@login_required
@admin_only_access
def show_email():
    email = Contacts.query.get(request.args.get("email_id"))
    if request.method == "POST":
        my_email = os.environ.get("MY_EMAIL")
        my_password = os.environ.get("MY_PASSWORD")
        with smtplib.SMTP("smtp.gmail.com") as connection:
            connection.starttls()
            connection.login(user=my_email, password=my_password)
            connection.sendmail(
                from_addr=my_email,
                to_addrs=email.email,
                msg=f"Subject: Email Reply From Danijel's Blog Post\n\n{request.form['email_reply']}"
            )
            db.session.delete(email)
            db.session.commit()
            return redirect(url_for("see_emails", current_user=current_user))
    return render_template("show-email.html", email=email)

# route for users to download pdf file for specific post
@app.route('/download', methods=["GET", "POST"])
@login_required
def download():
    file_name = request.args.get("file_title").lower()
    print(file_name)
    if "project" in file_name:
        file_name = file_name.replace(" ", "")
        return send_from_directory('static', filename=f'files/{file_name}_code.pdf')
    return send_from_directory('static', filename=f'files/{file_name}_cheatsheet.pdf')

# logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000)

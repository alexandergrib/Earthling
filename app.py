import os
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for)

from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

if os.path.exists("env.py"):
    import env

app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

app.jinja_env.add_extension('jinja2.ext.loopcontrols')

mongo = PyMongo(app)


@app.route("/")
def index():
    animation_info = list(mongo.db.animation.find())
    # for i in animation_info:
    #     mongo.db.animation.insert_one(i)
    return render_template("index.html", index_page=True,
                           animation_info=animation_info)


@app.route('/calendar')
def calendar():
    return render_template("calendar.html")


# ==========handle login logout register======================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect(url_for('profile'))
    if request.method == "POST":
        # check if username already exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})
        if existing_user:
            flash("Username already exists")
            return redirect(url_for("register"))
        validate_password = True if request.form.get(
            "password") == request.form.get("password2") else flash(
            "Passwords not matching")
        validate_password2 = True if request.form.get(
            'password_is_valid') == 'yes' else flash("Passwords not valid")
        if validate_password and validate_password2:
            register_user = {
                "username": request.form.get("username").lower(),
                "password": generate_password_hash(
                    request.form.get("password"))
            }
            mongo.db.users.insert_one(register_user)
            # put the new user into 'session' cookie
            session["user"] = request.form.get("username").lower()
            flash("Registration Successful!")
            return redirect(url_for("index"))
        else:
            return redirect((url_for('register')))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for('profile'))
    if request.method == "POST":
        # check if username exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})
        if existing_user:
            # ensure hashed password matches user input
            if check_password_hash(
                    existing_user["password"], request.form.get("password")):
                session["user"] = request.form.get("username").lower()
                flash("Welcome, {}".format(
                    request.form.get("username")))
                return redirect(url_for("index"))
            else:
                # invalid password match
                flash("Incorrect Username and/or Password")
                return redirect(url_for("login"))
        else:
            # username doesn't exist
            flash("Incorrect Username and/or Password")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        # remove user from session cookie
        flash("You have been logged out")
        session.pop("user")
        return redirect(url_for("index"))

    return redirect(url_for('index'))


class Error(Exception):  # Class from cloudinary used here temporary
    pass


@app.route("/profile/", methods=["GET", "POST"])
def profile():
    """
    User profile check if user exists, if not redirects to home page
    """
    # grab the session user's username from db
    if request.method == "POST":
        pass
    try:
        mongo.db.users.find_one({
            "username": session["user"]
        })["username"]
    except Error:
        return redirect(url_for("login"))
    if "user" in session:
        blog_list = mongo.db.blog.find(
            {"created_by": {'$eq': session['user']}})
        category_list = list(mongo.db.categories.find())
        return render_template("profile.html", blog_list=blog_list,
                               category_list=category_list)
    return redirect(url_for("index"))


@app.errorhandler(404)
def page_not_found(*args, **kwargs):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404


@app.route("/categories")
def categories():
    if "user" in session:
        categories = list(mongo.db.categories.find())
        return render_template("categories.html",
                               categories=categories)
    else:
        return render_template('404.html'), 404


@app.route("/add_category", methods=["GET", "POST"])
def add_category():
    """
    Add a category
    """
    if "user" in session:
        if request.method == "POST":
            category_name = request.form.get("category_name")
            category_description = request.form.get("category_description")
            category = {
                "name": category_name,
                "description": category_description
            }
            mongo.db.categories.insert_one(category)
            return redirect(url_for("categories"))
        return render_template("add_category.html")
    else:
        return render_template('404.html'), 404


@app.route("/<category_id>/edit_category", methods=["GET", "POST"])
def edit_category(category_id):
    """
    Edit a category
    """
    if "user" in session:
        if request.method == "POST":
            category_name = request.form.get("category_name")
            category_description = request.form.get("category_description")
            category = {
                "name": category_name,
                "description": category_description
            }
            mongo.db.categories.update_one({'_id': ObjectId(category_id)},
                                           {'$set': category})
            return redirect(url_for("categories"))
        category = mongo.db.categories.find_one(
            {'_id': ObjectId(category_id)})
        return render_template("edit_category.html",
                               category=category)
    else:
        return render_template('404.html'), 404


@app.route('/<category_id>/delete', methods=['GET', 'POST'])
def delete_category(category_id):
    """
    Delete a category
    """
    if "user" in session:
        blog_list = list(mongo.db.blog.find(
            {"categories": {"$all": [category_id, ]}}
        ))
        if not blog_list:
            category = mongo.db.categories.find_one(
                {'_id': ObjectId(category_id)})
            mongo.db.categories.delete_one({'_id': ObjectId(category_id)})
            flash('Successfully deleted {}'.format(category["name"]))
            return redirect(url_for('categories'))
        else:
            flash(
                'This category is referred to by blogs. It cannot be deleted until the associated blogs are removed first.')
            return redirect(url_for('categories'))
    else:
        return render_template('404.html'), 404


@app.route('/blog')
def blog():
    query_filter = None
    if request.args.get("filter"):
        query = request.args.get("filter")
        query_filter = mongo.db.categories.find_one(
            {"_id": ObjectId(query)})

        blog_list = list(mongo.db.blog.find(
            {"categories": {"$all": [query, ]}}
        ))
    else:
        blog_list = list(mongo.db.blog.find())
    category_list = list(mongo.db.categories.find())

    return render_template('blog.html', blog_list=blog_list,
                           category_list=category_list, filter=query_filter)


@app.route('/add_blog', methods=['GET', 'POST'])
def add_blog():
    # Check if user is in session
    blog_categories = mongo.db.categories.find()
    if request.method == 'POST':
        if "user" in session:
            submit = {
                'categories': request.form.getlist('categories_list'),
                'title': request.form.get('title'),
                'blog_text': request.form.get('blog_text'),
                'created_by': session['user']
            }
            mongo.db.blog.insert_one(submit)
            flash("Record {} created".format(submit['title']))
            return redirect(url_for('blog'))
        else:
            return redirect(url_for("login"))
    return render_template('add_blog.html', categories=blog_categories)


@app.route('/edit_blog/<blog_id>', methods=['GET', 'POST'])
def edit_blog(blog_id):
    single_blog = mongo.db.blog.find_one(
        {"_id": ObjectId(blog_id)})

    if "user" in session:
        blog_categories = list(mongo.db.categories.find())
        if request.method == 'POST':
            if "user" in session:
                if single_blog['created_by'] == session['user']:
                    submit = {
                        'categories': request.form.getlist('categories_list'),
                        'title': request.form.get('title'),
                        'blog_text': request.form.get('blog_text'),
                        'created_by': session['user']
                    }
                    mongo.db.blog.update_one({"_id": ObjectId(blog_id)},
                                             {"$set": submit})
                    flash("Record {} updated".format(submit['title']))
                    return redirect(url_for('profile'))
                else:
                    flash('You only allowed to remove your own records')
                    return redirect(url_for('profile'))
    else:
        return redirect(url_for("login"))
    return render_template('edit_blog.html', categories=blog_categories,
                           blog=single_blog)


@app.route('/delete_blog/<blog_id>')
def delete_blog(blog_id):
    if "user" in session:
        record = mongo.db.blog.find_one(
            {"_id": ObjectId(blog_id)}
        )
        if record['created_by'] == session['user']:
            mongo.db.blog.delete_many(
                {"_id": ObjectId(blog_id)}
            )
            flash('Successfully deleted {}'.format(record["title"]))
            return redirect(url_for('profile'))
        else:
            flash('You only allowed to remove your own records')
            return redirect(url_for('profile'))
    else:
        flash("You need to be logged in to perform this action")
        return redirect(url_for('login'))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=False)

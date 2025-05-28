import os
from reddit_crawler import crawl_subreddit, Post
from datetime import datetime, timezone

from flask import Flask, render_template, redirect, url_for, send_from_directory, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)
app.secret_key = 'the spice will flow'

# SQLite Database directory
database = 'crawler_service.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # Initialisation

"""
    Model/Table of Report
"""
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.String(100), nullable=False)
    subreddit = db.Column(db.String(100), nullable=False)
    sort = db.Column(db.String(100), nullable=False)
    post_count = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(100), nullable=False)

    # one-to-many, one-to-one relationship between Report and Post
    post = db.relationship('Post', backref='report', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Report {self.id}: r/{self.subreddit}/{self.sort} ({self.target_posts})>"

"""
    Model/Table of Post
"""
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False)
    unique_id = db.Column(db.String(500), nullable=False, unique=False)
    perma_link = db.Column(db.String(500), nullable=False)
    href_content = db.Column(db.String(500), nullable=False)
    comment_count = db.Column(db.Integer, nullable=False)
    post_title = db.Column(db.String(500), nullable=False)
    post_author = db.Column(db.String(500), nullable=False)
    post_score = db.Column(db.Integer, nullable=False)
    media_content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"<Post {self.id}: '{self.post_title}' by {self.post_author} (Score: {self.post_score})>"

# Report directory
report_directory = os.path.join(app.root_path, 'reports')
os.makedirs(report_directory, exist_ok=True)

crawled_posts: list[Post] = []
all_reports = []

"""
    Routes for html pages
"""
@app.route('/')
def index():
    """
        Main page
    """
    try:
        db_reports = Report.query.order_by(Report.timestamp.desc()).all()
        report_list = [{
            'id' : report.id,
            'timestamp' : report.timestamp,
            'subreddit' : report.subreddit,
            'sort' : report.sort,
            'post_count' : report.post_count,
            'filename' : report.filename
        } for report in db_reports]
    except SQLAlchemyError as e:
        print("Unable to fetch past reports from the SQLite Database")
        report_list = []

    return render_template('main_page.html', reports = report_list)

@app.route('/crawl', methods=['POST'])
def crawl():
    """
        Crawl page status
    """
    subreddit = request.form.get('subreddit', 'memes') # Getting settings from the form
    sort = request.form.get('sort', 'top')
    target_posts = request.form.get('target_posts', '20')
    user_handle = request.form.get('user_handle', '').strip()

    try:
        target_posts = int(target_posts)
        if not(3 <= target_posts <= 100):
            print("More than 3 or less than 100", "Error")
            return redirect(url_for('index'))
    except ValueError:
        print("Invalid post number", "Error")
        return redirect(url_for('index'))

    # Crawls subreddit with settings from the form
    print(f"Crawling r/{subreddit}/{sort} for {target_posts} posts.")
    crawled_posts = crawl_subreddit(subreddit, sort, target_posts)
    if crawled_posts:
        print(f'Successfully Crawled {len(crawled_posts)} posts from {subreddit}/{sort}', 'success')
    else:
        print(f"Failed to crawl {subreddit}/{sort}", "error")
    top_posts = crawled_posts[:target_posts]

    # Report variables
    report_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')
    report_file = f"report_{subreddit}_{sort}_{report_timestamp}.html"
    report_path = os.path.join(report_directory, report_file)

    """
        Pushing to Database
    """
    try:
        new_report = Report( # New Report
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S'),
            subreddit = subreddit,
            sort = sort,
            post_count = len(top_posts),
            filename = report_file,
        )
        db.session.add(new_report)
        db.session.flush()

        for post in top_posts:
            new_post = Post( # New Post
                report_id = new_report.id,
                unique_id = post.unique_id,
                perma_link = post.perma_link,
                href_content = post.href_content,
                comment_count = post.comment_count,
                post_title = post.post_title,
                post_author = post.post_author,
                post_score = post.post_score,
                media_content = post.media_content,
                timestamp = post.timestamp
            )
            db.session.add(new_post)
        db.session.commit()
        print("Successfully pushed to SQLite database")
        print(f"Contents: {new_report.post_count} posts under {new_report.id}")
    except SQLAlchemyError as e:
        db.session.rollback()
        print("Error saving to the SQLite database")

    """
        Generating and saving HTML Report
    """
    print(f"DEBUG: Generating HTML Report for {subreddit}/{sort}, {target_posts} posts")

    html = render_template( # HTML that passes data into the template
        'html_report.html',
        posts = top_posts,
        subreddit = subreddit,
        sort = sort,
        target_posts = target_posts)

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            print(f"DEBUG: Hello")
            f.write(html)
        print(f"DEBUG: Report successfully written to file: {report_path}")
    except IOError as e:
        print(f'Failed to save {report_file}', 'error')
    except Exception as e:
        print(f'Unexcepted error while saving', 'error')
    print(f"Redirecting to {report_file}")
    # return redirect(url_for('report', filename = report_file))
    return redirect(url_for('index'))

@app.route('/report/<path:filename>')
def report(filename):
    """
        For the static report file
    """
    return send_from_directory(report_directory, filename)

@app.route('/view_report/<int:report_id>')
def view_report(report_id):
    """
        Fetches report using report id and renders it dynamically
    """
    try:
        get_report = Report.query.get_or_404(report_id)
        report_posts = Post.query.filter_by(report_id=report_id).all()
        report_posts.sort(key=lambda post: post.post_score, reverse=True)

        print(f"DEBUG: Report {report_id} successfully fetched, now being rendered")
        return render_template('html_report.html',
                               posts = report_posts,
                               subreddit = get_report.subreddit,
                               sort = get_report.sort,
                               target_posts = get_report.post_count)
    except SQLAlchemyError as e:
        print(f"ERROR: Database error: {e}", "error")
        return redirect(url_for('index'))
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", "error")
        return redirect(url_for('index'))

@app.route('/download_report/<int:report_id>')
def download_report(report_id):
    """
        Fetches report using report id and downloads it
    """
    try:
        get_report = Report.query.get_or_404(report_id)
        report_name = get_report.filename
        return send_from_directory(report_directory, report_name, as_attachment=True)
    except SQLAlchemyError as e:
        print(f"ERROR: Database error: {e}", "error")
        return redirect(url_for('index'))
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", "error")
        return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

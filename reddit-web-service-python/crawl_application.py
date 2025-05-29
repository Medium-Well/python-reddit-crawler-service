import os
import threading
import asyncio

from dotenv import load_dotenv
from reddit_crawler import crawl_subreddit, Post
from datetime import datetime, timezone

from flask import Flask, render_template, redirect, url_for, send_from_directory, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

from telegram import Bot, Update
from telegram.error import TelegramError, InvalidToken
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext

app = Flask(__name__)
app.secret_key = 'the spice will flow'

# ----------------------------------------------------------------------------------------- #

# SQLite Database directory
database = 'crawler_service.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # Initialisation

# ----------------------------------------------------------------------------------------- #

# Telegram bot token
token_path = os.path.join(os.path.dirname(__file__), 'token.env')
load_dotenv(token_path)
token = os.getenv('TOKEN')

try:
    telegram_bot = Bot(token)
except InvalidToken:
    print('Invalid token')
    telegram_bot = None

# ----------------------------------------------------------------------------------------- #

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
    media_content = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"<Post {self.id}: '{self.post_title}' by {self.post_author} (Score: {self.post_score})>"

"""
    Model/Table
"""
class TelegramUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(100), nullable=False)
    chat_id = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"<Telegram User: @{self.handle}, chat_id: {self.chat_id}>"

# ----------------------------------------------------------------------------------------- #

# Telegram bot start command helper function - registers user if they have not been
async def start_command(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    handle = user.username
    print(f"Username: {handle}, chat_id: {chat_id}")

    with app.app_context():
        try:
            registered = TelegramUser.query.filter_by(handle=handle).first()
            if not registered:
                user = TelegramUser(handle=handle, chat_id=chat_id)
                db.session.add(user)
                db.session.commit()
                await update.message.reply_text(f"Hello there! You have been registered! Handle: {handle}, chat_id: {chat_id}")
                print(f"Registered User : {handle}, chat_id: {chat_id}")
        except SQLAlchemyError as e:
            await update.message.reply_text(f"Error: Database error : {e}")
            print(f"ERROR: SQLITE Database error: {e}")
        except Exception as e:
            print(f"ERROR: Unexpected error: unexpected error: {e}")

# Telegram bot poll threading - starts up when the application runs
def bot_polling():
    if not token:
        print("ERROR: No token detected")
        return

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        application = ApplicationBuilder().token(token).build()
        application.add_handler(CommandHandler('start', start_command))
        loop.run_until_complete(application.run_polling())
        print("Telegram bot is now polling")

    except InvalidToken as e:
        print(f"ERROR: Invalid token: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")

# ----------------------------------------------------------------------------------------- #

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

# ----------------------------------------------------------------------------------------- #

@app.route('/crawl', methods=['POST'])
async def crawl():
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
            print("ERROR: More than 3 or less than 100")
            return redirect(url_for('index'))
    except ValueError:
        print("ERROR: Invalid post number")
        return redirect(url_for('index'))

    # Check if handle is registered
    registered = None
    if user_handle:
        user_handle = user_handle.strip('@')
        registered = TelegramUser.query.filter_by(handle=user_handle).first()
        if not registered:
            print("ERROR: User not found")
            return redirect(url_for('index'))

    # Crawls subreddit with settings from the form
    print(f"Crawling r/{subreddit}/{sort} for {target_posts} posts.")
    crawled_posts = crawl_subreddit(subreddit, sort, target_posts)
    if crawled_posts:
        print(f'Successfully Crawled {len(crawled_posts)} posts from {subreddit}/{sort}')
    else:
        print(f"ERROR: Failed to crawl {subreddit}/{sort}")
        return redirect(url_for('index'))
    top_posts = crawled_posts[:target_posts]

    # Report variables
    report_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')
    report_file = f"report_{subreddit}_{sort}_{report_timestamp}.pdf"
    report_path = os.path.join(report_directory, report_file)

    # Pushing new data to SQLite Database
    try:
        new_report = Report( # New Report
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S'),
            subreddit = subreddit,
            sort = sort,
            post_count = len(top_posts),
            filename = report_file
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
        print(f"Contents: {new_report.post_count} posts under report number {new_report.id}")
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"ERROR: Unable to save to the SQLite database: {e}")

    # Generating and saving HTML Report
    print(f"Generating HTML Report for {subreddit}/{sort}, {target_posts} posts")
    html = render_template( # HTML that passes data into the template
        'html_report.html',
        posts = top_posts,
        subreddit = subreddit,
        sort = sort,
        target_posts = target_posts)

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"DEBUG: Report successfully written to file: {report_path}")
    except IOError as e:
        print(f'ERROR: Failed to save {report_file}', 'error')
    except Exception as e:
        print(f'ERROR: Unexcepted error while saving', 'error')

    # Handles sending the report if handle is provided
    if registered and telegram_bot:
        try:
            if os.path.exists(report_path):
                with open(report_path, 'r', encoding='utf-8') as f:
                    await telegram_bot.send_document(
                        chat_id = registered.chat_id,
                        document = f,
                        filename = os.path.basename(report_file),
                        caption = f"Here is the {target_posts} post PDF report for r/{subreddit}/{sort}"
                    )
                print(f'Sent {report_file} successfully to {user_handle}')
            else:
                print(f'ERROR: Failed to send {report_file} to {user_handle}')
        except TelegramError as e:
            print(f'ERROR: Telegram API Error: {e}')
        except Exception as e:
            print(f'ERROR: Unexcepted error while sending: {e}')

    print(f'Crawled, Saved, Generated and Sent(?) report!')
    return redirect(url_for('index'))

# ----------------------------------------------------------------------------------------- #

# For the static PDF report file
@app.route('/report/<path:filename>')
async def report(filename):
    return send_from_directory(report_directory, filename)
# ----------------------------------------------------------------------------------------- #

# Fetches report using report id and renders it dynamically
@app.route('/view_report/<int:report_id>')
async def view_report(report_id):
    try:
        get_report = Report.query.get_or_404(report_id)
        report_posts = Post.query.filter_by(report_id=report_id).all()

        # Reports are sorted based on sorting setting
        if get_report.sort == 'new':report_posts.sort(key=lambda p: p.timestamp, reverse=True)
        else: report_posts.sort(key=lambda p: p.post_score, reverse=True)

        print(f"Report {report_id} successfully fetched, now being rendered")
        return render_template('html_report.html',
                               posts = report_posts,
                               subreddit = get_report.subreddit,
                               sort = get_report.sort,
                               target_posts = get_report.post_count)
    except SQLAlchemyError as e:
        print(f"ERROR: Database error: {e}")
        return redirect(url_for('index'))
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return redirect(url_for('index'))

# ----------------------------------------------------------------------------------------- #

# Fetches report using report id and downloads it
@app.route('/download_report/<int:report_id>')
async def download_report(report_id):
    try:
        get_report = Report.query.get_or_404(report_id)
        report_name = get_report.filename
        if not os.path.isfile(report_name):
            print(f"ERROR: Report File {report_name} does not exist")
            generate_html(report_id)
        return send_from_directory(report_directory, report_name, as_attachment=True)
    except SQLAlchemyError as e:
        print(f"ERROR: Database error: {e}", "error")
        return redirect(url_for('index'))
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", "error")
        return redirect(url_for('index'))

# ----------------------------------------------------------------------------------------- #

# Fetches report and sends it via Telegram bot
@app.route('/send_report/<int:report_id>')
async def send_report(report_id):
    tele_handle = request.args.get('user_handle', '').strip()

    # Checks initialisation for telegram bot
    if not telegram_bot:
        print("ERROR: No Telegram Bot configured")
        return redirect(url_for('index'))

    # Checks if telegram handle has been inputted
    if not tele_handle:
        print("ERROR: No Telegram Handle")
        return redirect(url_for('index'))

    tele_handle = tele_handle.strip('@') # Strips off the @
    registered = TelegramUser.query.filter_by(handle=tele_handle).first()

    # Checks if user is registered
    if not registered:
        print("ERROR: User not found")
        return redirect(url_for('index'))

    try:
        report = Report.query.get_or_404(report_id)
        report_path = os.path.join(report_directory, report.filename)

        # Checks report generation and sends
        if not os.path.exists(report_path):
            generate_html(report_id)

        with open(report_path, 'r', encoding='utf-8') as f:
            await telegram_bot.send_document(
                chat_id = registered.chat_id,
                document = f,
                filename = os.path.basename(report.filename),
                caption = f"Here is the {report.post_count} post report for r/{report.subreddit}/{report.sort}"
            )
        print(f'Sent {report.filename} successfully to @{tele_handle}')

    # Error Handling
    except SQLAlchemyError as e:
        print(f"ERROR: SQLite Database error: {e}")
    except TelegramError as e:
        print(f"ERROR: Telegram API Error: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
    return redirect(url_for('index'))

# ----------------------------------------------------------------------------------------- #

# Fetches and deletes the report
@app.route('/delete_report/<int:report_id>')
async def delete_report(report_id):
    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()

    report_path = os.path.join(report_directory, report.filename)
    if os.path.exists(report_path):
        os.remove(report_path)
        print(f"DEBUG: HTML file deleted from file system.")
    else:
        print(f"WARNING: HTML file not found.")

    print(f"Report {report_id} successfully deleted")
    return redirect(url_for('index'))

def generate_html(report_id):
    report = Report.query.get_or_404(report_id)
    report_posts = Post.query.filter_by(report_id=report_id).all()
    report_file = report.filename
    report_path = os.path.join(report_directory, report_file)

    if report.sort == 'new':report_posts.sort(key=lambda p: p.crawled_at, reverse=True)
    else: report_posts.sort(key=lambda p: p.post_score, reverse=True)

    # Generating and saving HTML Report
    print(f"Generating HTML Report for {report.subreddit}/{report.sort}, {report.post_count} posts")
    html = render_template( # HTML that passes data into the template
        'html_report.html',
        posts = report_posts,
        subreddit = report.subreddit,
        sort = report.sort,
        target_posts = report.post_count)

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"DEBUG: Report successfully written to file: {report_path}")
    except IOError as e:
        print(f'ERROR: Failed to save {report_file}', 'error')
    except Exception as e:
        print(f'ERROR: Unexcepted error while saving', 'error')

# ----------------------------------------------------------------------------------------- #

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database initialized")

    # To prevent opening multiple daemons on the same thread
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        telegram_thread = threading.Thread(target=bot_polling)
        telegram_thread.daemon = True
        telegram_thread.start()
        print("Bot is initialized")

    app.run(debug=True)

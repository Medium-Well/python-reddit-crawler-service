import os
import flask
from flask import Flask, render_template, redirect, url_for, flash, send_from_directory, request
from reddit_crawler import crawl_subreddit, Post
from datetime import datetime, timezone

app = Flask(__name__)
app.secret_key = 'the spice will flow'

# Report directory
report_directory = os.path.join(app.root_path, 'reports')
os.makedirs(report_directory, exist_ok=True)

crawled_posts: list[Post] = []
all_reports = []

@app.route('/')
def index():
    """
        Main page
    """
    return render_template('main_page.html', reports = all_reports)

@app.route('/crawl', methods=['POST'])
def crawl():
    """
        Crawl page status
    """
    global crawled_posts
    global all_reports

    subreddit = request.form.get('subreddit', 'memes')
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

    print(f"Crawling r/{subreddit}/{sort} for {target_posts} posts.")
    crawled_posts = crawl_subreddit(subreddit, sort, target_posts)

    if crawled_posts:
        print(f'Successfully Crawled {len(crawled_posts)} posts from {subreddit}/{sort}', 'success')
    else:
        print(f"Failed to crawl {subreddit}/{sort}", "error")

    top_posts = crawled_posts[:target_posts]

    report_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H-%M-%S')
    report_file = f"report_{subreddit}_{sort}_{report_timestamp}.html"
    report_path = os.path.join(report_directory, report_file)
    html = render_template('html_report.html', posts=top_posts, sort=sort, target_posts=target_posts, subreddit=subreddit)

    print(f"DEBUG: Trying to save to: {report_path}")
    print(f"DEBUG: {report_path}")
    print(f"DEBUG: {report_directory}")
    try:
        print(f"DEBUG: Woah")
        with open(report_path, 'w', encoding='utf-8') as f:
            print(f"DEBUG: Hello")
            f.write(html)
        print(f"DEBUG: Report successfully written to file: {report_path}")

        all_reports.append({
            'timestamp': report_timestamp,
            'subreddit': subreddit,
            'sort': sort,
            'target_posts': target_posts,
            'report_file': report_file,
            'user_handle': user_handle,
        })
        all_reports.sort(key=lambda r: r['timestamp'], reverse=True)

    except IOError as e:
        print(f'Failed to save {report_file}', 'error')

    return redirect(url_for('report', filename = report_file))

@app.route('/report/<filename>')
def report(filename):
    return send_from_directory(report_directory, filename)

if __name__ == '__main__':
    app.run(debug=True)

import os

import flask
from flask import Flask, render_template, redirect, url_for, flash, send_from_directory
from reddit_crawler import crawl_subreddit, Post

app = Flask(__name__)
app.secret_key = 'the spice will flow'

report_directory = os.path.join(app.root_path, 'reports')
os.makedirs(report_directory, exist_ok=True)

crawled_posts: list[Post] = []

@app.route('/')
def crawl():
    global crawled_posts

    subreddit = "memes"
    sort = "top"
    target_posts = 20

    crawled_posts = crawl_subreddit(subreddit, sort, target_posts)
    if crawled_posts:
        flash(f'Successfully Crawled {len(crawled_posts)} posts from {subreddit}/{sort}', 'success')
    else:
        flash(f"Failed to crawl {subreddit}/{sort}", "error")

    top_posts = crawled_posts[:target_posts]

    file = "report.html"
    filepath = os.path.join(report_directory, file)
    html = render_template('html_report.html', posts=top_posts)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        flash(f'Successfully Saved {file}', 'success')
    except IOError as e:
        flash(f'Failed to save {file}', 'error')

    return redirect(url_for('report', filename = file))

@app.route('/report/<filename>')
def report(filename):
    return send_from_directory(report_directory, filename)

if __name__ == '__main__':
    app.run(debug=True)

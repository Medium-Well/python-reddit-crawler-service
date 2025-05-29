from dataclasses import dataclass, field
from datetime import datetime, timezone

from bs4 import BeautifulSoup
import os
import time
import urllib.parse

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC

# ----------------------------------------------------------------------------------------- #
# Post dataclass for crawling use
@dataclass
class Post:
    unique_id: str
    perma_link: str
    href_content: str
    comment_count: str
    post_title: str
    post_author: str
    post_score: str
    media_content: None
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

# ----------------------------------------------------------------------------------------- #
# Main crawling function - takes in parameters such as subreddit name, sort by and how many to crawl
def crawl_subreddit(subreddit: str, sort: str , target_posts : int ) -> list[Post]:
    """
        Crawls a subreddit of your choice with a set target of 20 posts to crawl
        these posts are then saved as a Post dataclass
    """
    url = f"https://www.reddit.com/r/{subreddit}/{sort}" # allows for future improvements
    print(f"Beginning crawl for subreddit {url}")

    # Issues with each headless, debugging by trying a few options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    driver = None

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.set_page_load_timeout(90)
        driver.get(url)

        # Wait until at least one 'shreddit-post' element is present
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.TAG_NAME, "shreddit-post"))
        )
        print("At least one 'shreddit-post' element found. Starting crawl loop.")

        crawled_posts = []
        attempts = 0
        max_attempts = 5
        height = driver.execute_script("return document.body.scrollHeight")
        unique_ids = set()

        while len(crawled_posts) < target_posts and attempts < max_attempts:
            print(f"Attempt {attempts}/{max_attempts}")

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(20)

            current_height = driver.execute_script("return document.body.scrollHeight")
            if current_height == height:
                print(f"Unable to scroll down.")
                break
            height = current_height
            attempts += 1

            soupy = BeautifulSoup(driver.page_source, "html.parser")
            html_posts = soupy.find_all('shreddit-post')
            print(f"Crawled {len(html_posts)} posts")

            for post_element in html_posts:
                unique_id = post_element.get('id')
                if unique_id and unique_id not in unique_ids: # Prevent duplicate post saving
                    perma_link = post_element.get('permalink')
                    href_content = post_element.get('content-href')
                    comment_count_str = post_element.get('comment-count')
                    post_title = post_element.get('post-title')
                    post_author = post_element.get('author')
                    post_score_str = post_element.get('score')

                    media_content = None


                    if href_content:
                        parsed = urllib.parse.urlparse(href_content)
                        path_extension = os.path.splitext(href_content)[1].lower()
                        images = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
                        videos = ('.mp4', '.webm')
                        if path_extension in images or path_extension in videos:
                            media_content = href_content
                        elif 'v.redd.it' in href_content:
                            media_content = href_content

                    # if href_content and (href_content.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm')) or 'v.redd.it' in href_content):
                    #     media_content = href_content

                    if unique_id and perma_link and post_title and post_author:
                        crawled_posts.append(Post(
                            unique_id=unique_id,
                            perma_link=perma_link,
                            href_content=href_content if href_content else perma_link,
                            comment_count=comment_count_str,
                            post_title=post_title,
                            post_author=post_author,
                            post_score=post_score_str,
                            media_content=media_content))

                        unique_ids.add(unique_id)
                    else:
                        print(f"Skipping due to missing data fields")
            if len(crawled_posts) >= target_posts:
                print(f"Crawled {len(crawled_posts)}/{target_posts} posts")
                break

            print(f"Crawling {len(crawled_posts)}/{target_posts}")
        print(f"Crawling complete. Total posts: {len(crawled_posts)}")
        return crawled_posts

    # Error handling
    except TimeoutException:
        print("ERROR: Timeout error")
        return []
    except WebDriverException as e:
        print(f"ERROR: Web Driver error: {e} ")
        return []
    except Exception as e:
        print("ERROR: Unexpected error:", e)
        return []
    finally:
        if driver:
            driver.quit()

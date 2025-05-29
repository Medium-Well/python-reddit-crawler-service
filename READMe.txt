Reddit Web Service
Coding language : Python, HTML, CSS, Javascript
IDE : IntellJ
Done by : Mitchell Lim Chin Wei
Email : limmitchell@gmail.com
Date: 30th May 2025

Personal Note:

Coding assignment done for a software engineer job application.
This project was a first for me as I specialised in Machine Learning & Artificial Intelligence
during my study of Computer Science with SIM - University of London. Aside from some simple web
applications during Polytechnic and Year 1 and 2 of University, I have next to no proper experience
in building a full webservice application. This project was my stepping stone towards learning full
stack development.

Cheers, Mitchell

Project Structure:

- instance                      (folder)
---- { database file }          # Created automatically, can be deleted for database refresh

- reports                       (folder)
---- { static report files }    # Created for downloading

- templates                     (folder)
---- main_page.html             # Template html file
---- html_report.html           # Template html file

- crawl_application.py          # Main code script, API integrations and flask app routing
- reddit_crawler.py             # Handles web crawling
- requirements.txt              # Required Python Libraries
- token.env                     # Telegram Bot API Token

The token.env file has been omitted due to token credential, it works with any custom bot API key.
All required python libraries are in requirements.txt.
To install, run:
pip install -r requirements.txt

To run the application, run:
python crawl_application.py

After the application has started, use this link to go to your telegram chat with the bot. Clicking start
will register the tele handle and chat id into the database.
Link - https://t.me/CrawlingPythonBot

From here you can run all working functions of the project.
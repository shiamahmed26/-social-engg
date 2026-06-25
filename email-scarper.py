from bs4 import BeautifulSoup
import requests
import requests.exceptions
import urllib.parse
from collections import deque
import re

user_url = input('[+] Enter Target URL To Scan: ')
urls = deque([user_url])

scraped_urls = set()
emails = set()

count = 0
try:
    while len(urls) > 0:
        count += 1
        if count == 100:  # Added this limit to avoid infinite looping
            break
        url = urls.popleft()
        scraped_urls.add(url)

        parts = urllib.parse.urlsplit(url)
        base_url = '{0.scheme}://{0.netloc}'.format(parts)

        path = url[:url.rfind('/') + 1] if '/' in parts.path else url

        print('[%d] Processing %s' % (count, url))
        try:
            response = requests.get(url)
        except (requests.exceptions.MissingSchema, requests.exceptions.ConnectionError) as e:
            print("Error fetching URL:", e)
            continue

        new_emails = set(re.findall(r"[a-zA-Z0-9\.\-+_]+@[a-zA-Z0-9\.\-+_]+\.[a-zA-Z]+", response.text, re.I))
        if new_emails:
            print("Found emails:", new_emails)
        emails.update(new_emails)

        soup = BeautifulSoup(response.text, features="html.parser")

        for anchor in soup.find_all("a"):
            link = anchor.attrs.get('href', '')
            if link.startswith('/'):
                link = base_url + link
            elif not link.startswith('http'):
                link = path + link
            if link not in urls and link not in scraped_urls:
                urls.append(link)
except KeyboardInterrupt:
    print('[-] Closing!')

for mail in emails:
    print(mail)

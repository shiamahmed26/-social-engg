#!/usr/bin/env python3
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys
import time

class EmailScraper:
    def __init__(self):
        self.visited_urls = set()
        self.found_emails = set()
        
    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        parsed = urlparse(url)
        return parsed.netloc == base_domain
        
    def extract_emails(self, text):
        """Extract email addresses using regex"""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return set(re.findall(email_pattern, text))
        
    def scrape_page(self, url, base_domain):
        """Scrape a single page for emails and links"""
        if url in self.visited_urls:
            return
            
        self.visited_urls.add(url)
        
        try:
            # Add headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Extract emails from raw HTML
            emails = self.extract_emails(response.text)
            self.found_emails.update(emails)
            
            # Parse HTML and find links
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a', href=True)
            
            # Process found links
            for link in links:
                href = link['href']
                full_url = urljoin(url, href)
                
                if self.is_valid_url(full_url, base_domain):
                    self.scrape_page(full_url, base_domain)
                    
        except Exception as e:
            print(f"\033[91mError scraping {url}: {str(e)}\033[0m")
            
    def start_scraping(self, start_url):
        """Start the scraping process"""
        print(f"\033[92m[*] Starting email scraping for: {start_url}\033[0m")
        base_domain = urlparse(start_url).netloc
        
        self.scrape_page(start_url, base_domain)
        
        print("\n\033[94m[+] Found Emails:\033[0m")
        if self.found_emails:
            for email in sorted(self.found_emails):
                print(f"\033[96m{email}\033[0m")
        else:
            print("\033[93mNo email addresses found.\033[0m")
            
        print(f"\n\033[92m[*] Total unique emails found: {len(self.found_emails)}\033[0m")
        print(f"\033[92m[*] Total pages scanned: {len(self.visited_urls)}\033[0m")

def main():
    if len(sys.argv) != 2:
        print("\033[91mUsage: python3 email_scraper.py <website_url>\033[0m")
        print("Example: python3 email_scraper.py https://example.com")
        sys.exit(1)
        
    url = sys.argv[1]
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    scraper = EmailScraper()
    scraper.start_scraping(url)

if __name__ == "__main__":
    main()

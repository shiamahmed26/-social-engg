#!/usr/bin/env python3
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys
import time
from collections import defaultdict

class SocialMediaFinder:
    def __init__(self):
        self.visited_urls = set()
        self.social_links = defaultdict(set)
        
        # Define social media patterns
        self.social_patterns = {
            'Facebook': [
                r'facebook\.com/([a-zA-Z0-9.]+)',
                r'fb\.com/([a-zA-Z0-9.]+)'
            ],
            'Twitter': [
                r'twitter\.com/([a-zA-Z0-9_]+)',
                r'x\.com/([a-zA-Z0-9_]+)'
            ],
            'Instagram': [
                r'instagram\.com/([a-zA-Z0-9_.]+)'
            ],
            'LinkedIn': [
                r'linkedin\.com/(?:in|company)/([a-zA-Z0-9_-]+)'
            ],
            'YouTube': [
                r'youtube\.com/(?:user|c|channel)/([a-zA-Z0-9_-]+)',
                r'youtube\.com/@([a-zA-Z0-9_-]+)'
            ],
            'GitHub': [
                r'github\.com/([a-zA-Z0-9_-]+)'
            ],
            'TikTok': [
                r'tiktok\.com/@([a-zA-Z0-9_.]+)'
            ],
            'Pinterest': [
                r'pinterest\.com/([a-zA-Z0-9_]+)'
            ]
        }
        
    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        parsed = urlparse(url)
        return parsed.netloc == base_domain
        
    def find_social_links(self, text, url):
        """Find social media links using regex patterns"""
        for platform, patterns in self.social_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    username = match.group(1)
                    full_url = match.group(0)
                    if not full_url.startswith('http'):
                        full_url = f"https://{full_url}"
                    self.social_links[platform].add((username, full_url))
                    
    def scrape_page(self, url, base_domain):
        """Scrape a single page for social media links"""
        if url in self.visited_urls:
            return
            
        self.visited_urls.add(url)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Find social media links in raw HTML
            self.find_social_links(response.text, url)
            
            # Parse HTML and find additional links to scan
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check meta tags and link elements
            meta_tags = soup.find_all('meta', attrs={'content': True})
            for tag in meta_tags:
                self.find_social_links(tag['content'], url)
                
            # Find links in anchor tags
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                full_url = urljoin(url, href)
                
                # Process social media links
                self.find_social_links(href, url)
                
                # Continue crawling if same domain
                if self.is_valid_url(full_url, base_domain):
                    self.scrape_page(full_url, base_domain)
                    
        except Exception as e:
            print(f"\033[91mError scraping {url}: {str(e)}\033[0m")
            
    def start_scanning(self, start_url):
        """Start the scanning process"""
        print(f"\033[92m[*] Starting social media scan for: {start_url}\033[0m")
        base_domain = urlparse(start_url).netloc
        
        self.scrape_page(start_url, base_domain)
        
        print("\n\033[94m[+] Found Social Media Accounts:\033[0m")
        
        if not any(self.social_links.values()):
            print("\033[93mNo social media accounts found.\033[0m")
            return
            
        for platform, accounts in self.social_links.items():
            if accounts:
                print(f"\n\033[95m{platform}:\033[0m")
                for username, url in sorted(accounts):
                    print(f"\033[96mUsername: {username}\033[0m")
                    print(f"\033[96mURL: {url}\033[0m")
                    
        print(f"\n\033[92m[*] Total platforms found: {len([p for p in self.social_links if self.social_links[p]])}\033[0m")
        print(f"\033[92m[*] Total pages scanned: {len(self.visited_urls)}\033[0m")

def main():
    if len(sys.argv) != 2:
        print("\033[91mUsage: python3 social_finder.py <website_url>\033[0m")
        print("Example: python3 social_finder.py https://example.com")
        sys.exit(1)
        
    url = sys.argv[1]
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    finder = SocialMediaFinder()
    finder.start_scanning(url)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys
import time
import mimetypes
import os
from collections import defaultdict

class FileFinder:
    def __init__(self):
        self.visited_urls = set()
        self.found_files = defaultdict(set)
        
        # Define file types to search for
        self.file_extensions = {
            'Documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.csv', '.ppt', '.pptx'],
            'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'],
            'Audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
            'Video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
            'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'],
            'Code': ['.html', '.css', '.js', '.php', '.py', '.java', '.cpp', '.c', '.h', '.xml', '.json'],
            'Config': ['.conf', '.cfg', '.ini', '.env', '.htaccess'],
            'Database': ['.sql', '.db', '.sqlite', '.mdb'],
            'Fonts': ['.ttf', '.otf', '.woff', '.woff2'],
            'Others': ['.bak', '.log', '.tmp', '.swp']
        }

    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == base_domain
        except:
            return False

    def is_file_url(self, url):
        """Check if URL points to a file"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        for category, extensions in self.file_extensions.items():
            if any(path.endswith(ext) for ext in extensions):
                return True
        return False

    def categorize_file(self, url):
        """Categorize file based on its extension"""
        path = urlparse(url).path.lower()
        for category, extensions in self.file_extensions.items():
            if any(path.endswith(ext) for ext in extensions):
                return category
        return 'Others'

    def get_file_size(self, url):
        """Get file size using HEAD request"""
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            if 'content-length' in response.headers:
                size = int(response.headers['content-length'])
                if size < 1024:
                    return f"{size}B"
                elif size < 1024 * 1024:
                    return f"{size/1024:.1f}KB"
                else:
                    return f"{size/(1024*1024):.1f}MB"
            return "Unknown"
        except:
            return "Unknown"

    def scan_page(self, url, base_domain):
        """Scan a single page for files and links"""
        if url in self.visited_urls:
            return
            
        self.visited_urls.add(url)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML and find links
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links
            links = set()
            for tag in ['a', 'link', 'script', 'img', 'source', 'video', 'audio']:
                for element in soup.find_all(tag, href=True):
                    links.add(element['href'])
                for element in soup.find_all(tag, src=True):
                    links.add(element['src'])
            
            # Process found links
            for link in links:
                full_url = urljoin(url, link)
                
                if self.is_file_url(full_url):
                    category = self.categorize_file(full_url)
                    self.found_files[category].add(full_url)
                elif self.is_valid_url(full_url, base_domain):
                    self.scan_page(full_url, base_domain)
                    
        except Exception as e:
            print(f"\033[91mError scanning {url}: {str(e)}\033[0m")

    def start_scanning(self, start_url):
        """Start the file scanning process"""
        print(f"\033[92m[*] Starting file scan for: {start_url}\033[0m")
        base_domain = urlparse(start_url).netloc
        
        self.scan_page(start_url, base_domain)
        
        print("\n\033[94m[+] Found Files:\033[0m")
        
        total_files = sum(len(files) for files in self.found_files.values())
        
        if total_files == 0:
            print("\033[93mNo files found.\033[0m")
            return
            
        for category, files in self.found_files.items():
            if files:
                print(f"\n\033[95m{category} ({len(files)} files):\033[0m")
                for file_url in sorted(files):
                    size = self.get_file_size(file_url)
                    filename = os.path.basename(urlparse(file_url).path)
                    print(f"\033[96mFile: {filename}\033[0m")
                    print(f"\033[96mSize: {size}\033[0m")
                    print(f"\033[96mURL: {file_url}\033[0m")
                    print()
                    
        print(f"\n\033[92m[*] Total files found: {total_files}\033[0m")
        print(f"\033[92m[*] Total pages scanned: {len(self.visited_urls)}\033[0m")

def main():
    if len(sys.argv) != 2:
        print("\033[91mUsage: python3 file_finder.py <website_url>\033[0m")
        print("Example: python3 file_finder.py https://example.com")
        sys.exit(1)
        
    url = sys.argv[1]
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    finder = FileFinder()
    finder.start_scanning(url)

if __name__ == "__main__":
    main()

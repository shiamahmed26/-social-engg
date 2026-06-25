#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys
import time
import datetime
from collections import defaultdict
import magic
import re
import argparse
import logging
from colorama import Fore, Back, Style, init

# Initialize colorama
init()

class DocumentFinder:
    def __init__(self, verbose=False):
        self.visited_urls = set()
        self.found_documents = defaultdict(list)
        self.verbose = verbose
        self.setup_logging()
        
        # Define document types and their extensions
        self.document_types = {
            'PDF Documents': ['.pdf'],
            'Word Documents': ['.doc', '.docx', '.odt', '.rtf'],
            'Spreadsheets': ['.xls', '.xlsx', '.csv', '.ods'],
            'Presentations': ['.ppt', '.pptx', '.odp'],
            'Text Documents': ['.txt', '.md', '.tex'],
            'XML/Data': ['.xml', '.json', '.yaml', '.yml'],
            'Database': ['.sql', '.db', '.sqlite', '.mdb'],
            'Configuration': ['.conf', '.cfg', '.ini', '.env'],
            'Research/Technical': ['.bib', '.eps', '.ps'],
            'Backup/Logs': ['.bak', '.log', '.old']
        }
        
        self.doc_keywords = [
            'report', 'document', 'paper', 'thesis', 'dissertation',
            'manual', 'guide', 'documentation', 'whitepaper', 'publication',
            'research', 'analysis', 'study', 'review', 'assessment',
            'proposal', 'plan', 'policy', 'procedure', 'guideline'
        ]

    def setup_logging(self):
        """Setup logging configuration"""
        self.logger = logging.getLogger('DocumentFinder')
        self.logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        
        # Console handler with color formatting
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        
        # Create custom formatter
        class ColoredFormatter(logging.Formatter):
            def format(self, record):
                if record.levelno == logging.DEBUG:
                    color = Fore.CYAN
                elif record.levelno == logging.INFO:
                    color = Fore.GREEN
                elif record.levelno == logging.WARNING:
                    color = Fore.YELLOW
                elif record.levelno == logging.ERROR:
                    color = Fore.RED
                else:
                    color = Fore.WHITE
                
                record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
                return super().format(record)
        
        formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s',
                                   datefmt='%Y-%m-%d %H:%M:%S')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        try:
            parsed = urlparse(url)
            result = parsed.netloc == base_domain
            if self.verbose:
                self.logger.debug(f"Checking URL validity: {url} -> {'Valid' if result else 'Invalid'}")
            return result
        except Exception as e:
            self.logger.error(f"Error checking URL validity: {str(e)}")
            return False

    def is_document_url(self, url):
        """Check if URL points to a document"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Check extensions
        for category, extensions in self.document_types.items():
            if any(path.endswith(ext) for ext in extensions):
                if self.verbose:
                    self.logger.debug(f"Found document URL by extension: {url} -> {category}")
                return True
                
        # Check keywords
        if any(keyword in path.lower() for keyword in self.doc_keywords):
            if self.verbose:
                self.logger.debug(f"Found potential document URL by keyword: {url}")
            return True
            
        return False

    def get_document_metadata(self, url):
        """Get document metadata using HEAD request"""
        if self.verbose:
            self.logger.debug(f"Fetching metadata for: {url}")
            
        metadata = {}
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            headers = response.headers
            
            # Get size
            if 'content-length' in headers:
                size = int(headers['content-length'])
                if size < 1024:
                    metadata['size'] = f"{size}B"
                elif size < 1024 * 1024:
                    metadata['size'] = f"{size/1024:.1f}KB"
                else:
                    metadata['size'] = f"{size/(1024*1024):.1f}MB"
            else:
                metadata['size'] = "Unknown"
                
            # Get last modified date
            metadata['last_modified'] = headers.get('last-modified', 'Unknown')
            
            # Get content type
            metadata['content_type'] = headers.get('content-type', 'Unknown')
            
            if self.verbose:
                self.logger.debug(f"Metadata retrieved: {metadata}")
                
            return metadata
        except Exception as e:
            self.logger.error(f"Error fetching metadata: {str(e)}")
            return {'size': 'Unknown', 'content_type': 'Unknown', 'last_modified': 'Unknown'}

    def scan_page(self, url, base_domain, depth=0):
        """Scan a single page for documents"""
        if url in self.visited_urls:
            if self.verbose:
                self.logger.debug(f"Skipping already visited URL: {url}")
            return
            
        self.visited_urls.add(url)
        if self.verbose:
            self.logger.debug(f"Scanning page (depth {depth}): {url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if self.verbose:
                self.logger.debug(f"Successfully fetched page: {url} (Status: {response.status_code})")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Process links
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                
                if self.is_document_url(full_url):
                    if self.verbose:
                        self.logger.debug(f"Processing document URL: {full_url}")
                    
                    metadata = self.get_document_metadata(full_url)
                    category = self.categorize_document(full_url, metadata.get('content_type'))
                    
                    title = link.get_text().strip() or os.path.basename(urlparse(full_url).path)
                    
                    doc_info = {
                        'title': title,
                        'url': full_url,
                        'metadata': metadata,
                        'discovery_path': url
                    }
                    
                    self.found_documents[category].append(doc_info)
                    if self.verbose:
                        self.logger.info(f"Found document: {title} ({category})")
                        
                elif self.is_valid_url(full_url, base_domain):
                    if depth < 10:  # Limit recursion depth
                        self.scan_page(full_url, base_domain, depth + 1)
                    elif self.verbose:
                        self.logger.warning(f"Max depth reached, skipping: {full_url}")
                        
        except Exception as e:
            self.logger.error(f"Error scanning {url}: {str(e)}")

    def categorize_document(self, url, content_type=None):
        """Categorize document based on extension and content type"""
        path = urlparse(url).path.lower()
        
        # Try by extension first
        for category, extensions in self.document_types.items():
            if any(path.endswith(ext) for ext in extensions):
                if self.verbose:
                    self.logger.debug(f"Categorized by extension: {url} -> {category}")
                return category
        
        # Then try by content type
        if content_type:
            if 'pdf' in content_type:
                return 'PDF Documents'
            elif 'word' in content_type or 'officedocument' in content_type:
                return 'Word Documents'
            elif 'spreadsheet' in content_type:
                return 'Spreadsheets'
            elif 'presentation' in content_type:
                return 'Presentations'
            elif 'text' in content_type:
                return 'Text Documents'
        
        if self.verbose:
            self.logger.debug(f"Could not categorize document, using 'Other': {url}")
        return 'Other Documents'

    def start_scanning(self, start_url):
        """Start the document scanning process"""
        self.logger.info(f"Starting document scan for: {start_url}")
        start_time = time.time()
        
        base_domain = urlparse(start_url).netloc
        self.scan_page(start_url, base_domain)
        
        # Print results
        total_docs = sum(len(docs) for docs in self.found_documents.values())
        
        print(f"\n{Fore.BLUE}[+] Scan Results:{Style.RESET_ALL}")
        
        if total_docs == 0:
            print(f"{Fore.YELLOW}No documents found.{Style.RESET_ALL}")
            return
            
        for category, documents in self.found_documents.items():
            if documents:
                print(f"\n{Fore.MAGENTA}{category} ({len(documents)} found):{Style.RESET_ALL}")
                for doc in documents:
                    print(f"{Fore.CYAN}Title: {doc['title']}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}URL: {doc['url']}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Size: {doc['metadata']['size']}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Last Modified: {doc['metadata']['last_modified']}{Style.RESET_ALL}")
                    if self.verbose:
                        print(f"{Fore.CYAN}Discovery Path: {doc['discovery_path']}{Style.RESET_ALL}")
                    print()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n{Fore.GREEN}[*] Scan Statistics:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Total documents found: {total_docs}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Total pages scanned: {len(self.visited_urls)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Scan duration: {duration:.2f} seconds{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description='Document Finder - Website Document Scanner')
    parser.add_argument('url', help='Target website URL')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    url = args.url
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    finder = DocumentFinder(verbose=args.verbose)
    finder.start_scanning(url)

if __name__ == "__main__":
    main()

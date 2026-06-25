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

class DocumentFinder:
    def __init__(self):
        self.visited_urls = set()
        self.found_documents = defaultdict(list)
        
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
        
        # Keywords that might indicate document content
        self.doc_keywords = [
            'report', 'document', 'paper', 'thesis', 'dissertation',
            'manual', 'guide', 'documentation', 'whitepaper', 'publication',
            'research', 'analysis', 'study', 'review', 'assessment',
            'proposal', 'plan', 'policy', 'procedure', 'guideline'
        ]

    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == base_domain
        except:
            return False

    def is_document_url(self, url):
        """Check if URL points to a document"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Check extensions
        for category, extensions in self.document_types.items():
            if any(path.endswith(ext) for ext in extensions):
                return True
                
        # Check keywords in URL
        return any(keyword in path.lower() for keyword in self.doc_keywords)

    def categorize_document(self, url, content_type=None):
        """Categorize document based on extension and content type"""
        path = urlparse(url).path.lower()
        
        # First try by extension
        for category, extensions in self.document_types.items():
            if any(path.endswith(ext) for ext in extensions):
                return category
                
        # Then try by content type if available
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
        
        return 'Other Documents'

    def get_document_metadata(self, url):
        """Get document metadata using HEAD request"""
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
            if 'last-modified' in headers:
                metadata['last_modified'] = headers['last-modified']
            
            # Get content type
            if 'content-type' in headers:
                metadata['content_type'] = headers['content-type']
                
            return metadata
        except:
            return {'size': 'Unknown', 'content_type': 'Unknown', 'last_modified': 'Unknown'}

    def scan_page(self, url, base_domain):
        """Scan a single page for documents"""
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
            
            # Find documents in anchor tags
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                
                if self.is_document_url(full_url):
                    metadata = self.get_document_metadata(full_url)
                    category = self.categorize_document(full_url, metadata.get('content_type'))
                    
                    # Get document title from link text or filename
                    title = link.get_text().strip()
                    if not title:
                        title = os.path.basename(urlparse(full_url).path)
                    
                    doc_info = {
                        'title': title,
                        'url': full_url,
                        'metadata': metadata
                    }
                    
                    self.found_documents[category].append(doc_info)
                elif self.is_valid_url(full_url, base_domain):
                    self.scan_page(full_url, base_domain)
                    
            # Also scan for document keywords in page content
            for keyword in self.doc_keywords:
                elements = soup.find_all(text=re.compile(keyword, re.IGNORECASE))
                for element in elements:
                    parent = element.parent
                    if parent.name == 'a' and 'href' in parent.attrs:
                        href = parent['href']
                        full_url = urljoin(url, href)
                        if full_url not in [doc['url'] for docs in self.found_documents.values() for doc in docs]:
                            metadata = self.get_document_metadata(full_url)
                            category = 'Potential Documents'
                            doc_info = {
                                'title': parent.get_text().strip(),
                                'url': full_url,
                                'metadata': metadata,
                                'keyword_match': keyword
                            }
                            self.found_documents[category].append(doc_info)
                    
        except Exception as e:
            print(f"\033[91mError scanning {url}: {str(e)}\033[0m")

    def start_scanning(self, start_url):
        """Start the document scanning process"""
        print(f"\033[92m[*] Starting document scan for: {start_url}\033[0m")
        base_domain = urlparse(start_url).netloc
        
        self.scan_page(start_url, base_domain)
        
        print("\n\033[94m[+] Found Documents:\033[0m")
        
        total_docs = sum(len(docs) for docs in self.found_documents.values())
        
        if total_docs == 0:
            print("\033[93mNo documents found.\033[0m")
            return
            
        for category, documents in self.found_documents.items():
            if documents:
                print(f"\n\033[95m{category} ({len(documents)} found):\033[0m")
                for doc in documents:
                    print(f"\033[96mTitle: {doc['title']}\033[0m")
                    print(f"\033[96mURL: {doc['url']}\033[0m")
                    print(f"\033[96mSize: {doc['metadata']['size']}\033[0m")
                    if doc['metadata']['last_modified'] != 'Unknown':
                        print(f"\033[96mLast Modified: {doc['metadata']['last_modified']}\033[0m")
                    if 'keyword_match' in doc:
                        print(f"\033[96mMatched Keyword: {doc['keyword_match']}\033[0m")
                    print()
                    
        print(f"\n\033[92m[*] Total documents found: {total_docs}\033[0m")
        print(f"\033[92m[*] Total pages scanned: {len(self.visited_urls)}\033[0m")

def main():
    if len(sys.argv) != 2:
        print("\033[91mUsage: python3 doc_finder.py <website_url>\033[0m")
        print("Example: python3 doc_finder.py https://example.com")
        sys.exit(1)
        
    url = sys.argv[1]
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    finder = DocumentFinder()
    finder.start_scanning(url)

if __name__ == "__main__":
    main()

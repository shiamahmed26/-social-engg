#!/usr/bin/env python3
"""
Unified Website Intelligence Tool
Combines email finding, document discovery, social media detection, and subdomain enumeration
"""

import requests
import re
import socket
import sys
import time
import argparse
import logging
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Style, init

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    print(f"{Fore.YELLOW}[WARNING] dnspython not installed. Subdomain finder will have limited functionality.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Install with: pip install dnspython{Style.RESET_ALL}\n")

# Initialize colorama
init(autoreset=True)

class EmailScraper:
    def __init__(self, verbose=False):
        self.visited_urls = set()
        self.found_emails = set()
        self.verbose = verbose
        
    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        parsed = urlparse(url)
        return parsed.netloc == base_domain
        
    def extract_emails(self, text):
        """Extract email addresses using regex"""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return set(re.findall(email_pattern, text))
        
    def scrape_page(self, url, base_domain, depth=0, max_depth=3):
        """Scrape a single page for emails and links"""
        if url in self.visited_urls or depth > max_depth:
            return
            
        self.visited_urls.add(url)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            emails = self.extract_emails(response.text)
            self.found_emails.update(emails)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                full_url = urljoin(url, href)
                
                if self.is_valid_url(full_url, base_domain):
                    self.scrape_page(full_url, base_domain, depth + 1, max_depth)
                    
        except Exception as e:
            if self.verbose:
                print(f"{Fore.RED}Error scraping {url}: {str(e)}{Style.RESET_ALL}")
            
    def start_scraping(self, start_url):
        """Start the scraping process"""
        print(f"{Fore.GREEN}[*] Starting email scraping for: {start_url}{Style.RESET_ALL}")
        base_domain = urlparse(start_url).netloc
        
        self.scrape_page(start_url, base_domain)
        
        return {
            'emails': sorted(self.found_emails),
            'pages_scanned': len(self.visited_urls)
        }


class DocumentFinder:
    def __init__(self, verbose=False):
        self.visited_urls = set()
        self.found_documents = defaultdict(list)
        self.verbose = verbose
        
        self.document_types = {
            'PDF Documents': ['.pdf'],
            'Word Documents': ['.doc', '.docx', '.odt', '.rtf'],
            'Spreadsheets': ['.xls', '.xlsx', '.csv', '.ods'],
            'Presentations': ['.ppt', '.pptx', '.odp'],
            'Text Documents': ['.txt', '.md', '.tex'],
            'XML/Data': ['.xml', '.json', '.yaml', '.yml'],
            'Database': ['.sql', '.db', '.sqlite', '.mdb'],
            'Configuration': ['.conf', '.cfg', '.ini', '.env'],
            'Archives': ['.zip', '.rar', '.tar', '.gz', '.7z']
        }
        
        self.doc_keywords = [
            'report', 'document', 'paper', 'thesis', 'manual', 'guide',
            'documentation', 'whitepaper', 'research', 'analysis'
        ]

    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        parsed = urlparse(url)
        return parsed.netloc == base_domain

    def is_document_url(self, url):
        """Check if URL points to a document"""
        path = urlparse(url).path.lower()
        
        for category, extensions in self.document_types.items():
            if any(path.endswith(ext) for ext in extensions):
                return True
                
        if any(keyword in path for keyword in self.doc_keywords):
            return True
            
        return False

    def get_document_metadata(self, url):
        """Get document metadata using HEAD request"""
        metadata = {}
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            headers = response.headers
            
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
                
            metadata['last_modified'] = headers.get('last-modified', 'Unknown')
            metadata['content_type'] = headers.get('content-type', 'Unknown')
                
            return metadata
        except:
            return {'size': 'Unknown', 'content_type': 'Unknown', 'last_modified': 'Unknown'}

    def categorize_document(self, url, content_type=None):
        """Categorize document based on extension"""
        path = urlparse(url).path.lower()
        
        for category, extensions in self.document_types.items():
            if any(path.endswith(ext) for ext in extensions):
                return category
        
        return 'Other Documents'

    def scan_page(self, url, base_domain, depth=0, max_depth=3):
        """Scan a single page for documents"""
        if url in self.visited_urls or depth > max_depth:
            return
            
        self.visited_urls.add(url)
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                
                if self.is_document_url(full_url):
                    metadata = self.get_document_metadata(full_url)
                    category = self.categorize_document(full_url, metadata.get('content_type'))
                    
                    title = link.get_text().strip() or os.path.basename(urlparse(full_url).path)
                    
                    doc_info = {
                        'title': title,
                        'url': full_url,
                        'metadata': metadata
                    }
                    
                    self.found_documents[category].append(doc_info)
                        
                elif self.is_valid_url(full_url, base_domain):
                    self.scan_page(full_url, base_domain, depth + 1, max_depth)
                        
        except Exception as e:
            if self.verbose:
                print(f"{Fore.RED}Error scanning {url}: {str(e)}{Style.RESET_ALL}")

    def start_scanning(self, start_url):
        """Start the document scanning process"""
        print(f"{Fore.GREEN}[*] Starting document scan for: {start_url}{Style.RESET_ALL}")
        
        base_domain = urlparse(start_url).netloc
        self.scan_page(start_url, base_domain)
        
        total_docs = sum(len(docs) for docs in self.found_documents.values())
        
        return {
            'documents': dict(self.found_documents),
            'total_documents': total_docs,
            'pages_scanned': len(self.visited_urls)
        }


class SocialMediaFinder:
    def __init__(self, verbose=False):
        self.visited_urls = set()
        self.social_links = defaultdict(set)
        self.verbose = verbose
        
        self.social_patterns = {
            'Facebook': [r'facebook\.com/([a-zA-Z0-9.]+)', r'fb\.com/([a-zA-Z0-9.]+)'],
            'Twitter/X': [r'twitter\.com/([a-zA-Z0-9_]+)', r'x\.com/([a-zA-Z0-9_]+)'],
            'Instagram': [r'instagram\.com/([a-zA-Z0-9_.]+)'],
            'LinkedIn': [r'linkedin\.com/(?:in|company)/([a-zA-Z0-9_-]+)'],
            'YouTube': [r'youtube\.com/(?:user|c|channel)/([a-zA-Z0-9_-]+)', r'youtube\.com/@([a-zA-Z0-9_-]+)'],
            'GitHub': [r'github\.com/([a-zA-Z0-9_-]+)'],
            'TikTok': [r'tiktok\.com/@([a-zA-Z0-9_.]+)'],
            'Pinterest': [r'pinterest\.com/([a-zA-Z0-9_]+)']
        }
        
    def is_valid_url(self, url, base_domain):
        """Check if URL belongs to the same domain"""
        parsed = urlparse(url)
        return parsed.netloc == base_domain
        
    def find_social_links(self, text):
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
                    
    def scrape_page(self, url, base_domain, depth=0, max_depth=3):
        """Scrape a single page for social media links"""
        if url in self.visited_urls or depth > max_depth:
            return
            
        self.visited_urls.add(url)
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            self.find_social_links(response.text)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            meta_tags = soup.find_all('meta', attrs={'content': True})
            for tag in meta_tags:
                self.find_social_links(tag['content'])
                
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                full_url = urljoin(url, href)
                
                self.find_social_links(href)
                
                if self.is_valid_url(full_url, base_domain):
                    self.scrape_page(full_url, base_domain, depth + 1, max_depth)
                    
        except Exception as e:
            if self.verbose:
                print(f"{Fore.RED}Error scraping {url}: {str(e)}{Style.RESET_ALL}")
            
    def start_scanning(self, start_url):
        """Start the scanning process"""
        print(f"{Fore.GREEN}[*] Starting social media scan for: {start_url}{Style.RESET_ALL}")
        base_domain = urlparse(start_url).netloc
        
        self.scrape_page(start_url, base_domain)
        
        return {
            'social_links': dict(self.social_links),
            'pages_scanned': len(self.visited_urls)
        }


class SubdomainFinder:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.visited_urls = set()
        self.found_subdomains = {}
        self.main_domain = ""
        self.max_threads = 20
        
    def extract_domain(self, url):
        """Extract the main domain from a URL"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return domain
    
    def is_valid_subdomain(self, hostname, main_domain):
        """Check if hostname is a valid subdomain of main_domain"""
        if not hostname or not main_domain:
            return False
            
        if '://' in hostname:
            hostname = urlparse(hostname).netloc
            
        return hostname.endswith(main_domain) and hostname != main_domain
    
    def resolve_ip(self, domain):
        """Resolve domain to IP address"""
        ip_addresses = []
        
        if not DNS_AVAILABLE:
            try:
                ip = socket.gethostbyname(domain)
                ip_addresses.append(ip)
            except:
                pass
            return ip_addresses
        
        try:
            try:
                answers = dns.resolver.resolve(domain, 'A')
                for answer in answers:
                    ip_addresses.append(str(answer))
            except:
                pass
                
            try:
                answers = dns.resolver.resolve(domain, 'AAAA')
                for answer in answers:
                    ip_addresses.append(str(answer))
            except:
                pass
                
            return ip_addresses
        except:
            return []
    
    def check_website_status(self, url):
        """Check if website is accessible"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            return response.status_code
        except:
            return None
    
    def process_subdomain(self, subdomain):
        """Process a subdomain to gather its information"""
        if subdomain in self.found_subdomains:
            return
            
        ip_addresses = self.resolve_ip(subdomain)
        http_status = self.check_website_status(f"http://{subdomain}")
        https_status = self.check_website_status(f"https://{subdomain}")
        
        self.found_subdomains[subdomain] = {
            'ip_addresses': ip_addresses,
            'http_status': http_status,
            'https_status': https_status
        }
    
    def find_common_subdomains(self, main_domain):
        """Try to find common subdomains"""
        common_prefixes = [
            "www", "mail", "ftp", "webmail", "admin", "blog", "test", "dev",
            "staging", "api", "cdn", "media", "shop", "store", "portal", "app",
            "dashboard", "login", "support", "help", "docs", "forum"
        ]
        
        found = []
        
        for prefix in common_prefixes:
            subdomain = f"{prefix}.{main_domain}"
            try:
                socket.gethostbyname(subdomain)
                found.append(subdomain)
            except:
                pass
        
        return found
    
    def scan(self, url):
        """Main scanning function"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        self.main_domain = self.extract_domain(url)
        print(f"{Fore.GREEN}[*] Starting subdomain scan for: {self.main_domain}{Style.RESET_ALL}")
        
        print(f"{Fore.BLUE}[*] Checking common subdomains...{Style.RESET_ALL}")
        common_subdomains = self.find_common_subdomains(self.main_domain)
        
        all_subdomains = set(common_subdomains)
        all_subdomains.add(self.main_domain)
        all_subdomains.add(f"www.{self.main_domain}")
        
        print(f"{Fore.BLUE}[*] Processing {len(all_subdomains)} discovered subdomains...{Style.RESET_ALL}")
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            executor.map(self.process_subdomain, all_subdomains)
        
        active = [(s, i) for s, i in self.found_subdomains.items() if i['http_status'] or i['https_status']]
        
        return {
            'subdomains': self.found_subdomains,
            'active_count': len(active),
            'total_count': len(self.found_subdomains)
        }


def print_banner():
    """Print tool banner"""
    banner = f"""
{Fore.CYAN}{'='*70}
{Fore.GREEN} ██╗    ██╗███████╗██████╗     ██╗███╗   ██╗████████╗███████╗██╗     
{Fore.GREEN} ██║    ██║██╔════╝██╔══██╗    ██║████╗  ██║╚══██╔══╝██╔════╝██║     
{Fore.GREEN} ██║ █╗ ██║█████╗  ██████╔╝    ██║██╔██╗ ██║   ██║   █████╗  ██║     
{Fore.GREEN} ██║███╗██║██╔══╝  ██╔══██╗    ██║██║╚██╗██║   ██║   ██╔══╝  ██║     
{Fore.GREEN} ╚███╔███╔╝███████╗██████╔╝    ██║██║ ╚████║   ██║   ███████╗███████╗
{Fore.GREEN}  ╚══╝╚══╝ ╚══════╝╚═════╝     ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚══════╝
{Fore.YELLOW}        Unified Website Intelligence Tool v1.0
{Fore.CYAN}{'='*70}
{Style.RESET_ALL}"""
    print(banner)


def display_menu():
    """Display main menu"""
    menu = f"""
{Fore.YELLOW}[1]{Style.RESET_ALL} Email Scraper        - Find email addresses
{Fore.YELLOW}[2]{Style.RESET_ALL} Document Finder      - Discover hidden documents
{Fore.YELLOW}[3]{Style.RESET_ALL} Social Media Finder  - Find social media profiles
{Fore.YELLOW}[4]{Style.RESET_ALL} Subdomain Enumerator - Enumerate subdomains
{Fore.YELLOW}[5]{Style.RESET_ALL} Run All Scans        - Execute all modules
{Fore.YELLOW}[0]{Style.RESET_ALL} Exit

{Fore.GREEN}Select an option:{Style.RESET_ALL} """
    return menu


def display_results(module_name, results):
    """Display results for each module"""
    print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[+] {module_name} Results{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    
    if module_name == "Email Scraper":
        if results['emails']:
            for email in results['emails']:
                print(f"{Fore.GREEN}  ✓ {email}{Style.RESET_ALL}")
            print(f"\n{Fore.BLUE}Total emails found: {len(results['emails'])}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No emails found{Style.RESET_ALL}")
        print(f"{Fore.BLUE}Pages scanned: {results['pages_scanned']}{Style.RESET_ALL}")
    
    elif module_name == "Document Finder":
        if results['total_documents'] > 0:
            for category, docs in results['documents'].items():
                if docs:
                    print(f"\n{Fore.MAGENTA}{category} ({len(docs)}):{Style.RESET_ALL}")
                    for doc in docs:
                        print(f"  {Fore.CYAN}├─ {doc['title']}{Style.RESET_ALL}")
                        print(f"  {Fore.CYAN}│  URL: {doc['url']}{Style.RESET_ALL}")
                        print(f"  {Fore.CYAN}│  Size: {doc['metadata']['size']}{Style.RESET_ALL}")
                        print(f"  {Fore.CYAN}└─ Modified: {doc['metadata']['last_modified']}{Style.RESET_ALL}\n")
            print(f"{Fore.BLUE}Total documents: {results['total_documents']}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No documents found{Style.RESET_ALL}")
        print(f"{Fore.BLUE}Pages scanned: {results['pages_scanned']}{Style.RESET_ALL}")
    
    elif module_name == "Social Media Finder":
        found_any = any(results['social_links'].values())
        if found_any:
            for platform, accounts in results['social_links'].items():
                if accounts:
                    print(f"\n{Fore.MAGENTA}{platform}:{Style.RESET_ALL}")
                    for username, url in sorted(accounts):
                        print(f"  {Fore.GREEN}✓ @{username}{Style.RESET_ALL}")
                        print(f"    {Fore.CYAN}{url}{Style.RESET_ALL}")
            total = sum(len(accounts) for accounts in results['social_links'].values())
            print(f"\n{Fore.BLUE}Total accounts found: {total}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No social media accounts found{Style.RESET_ALL}")
        print(f"{Fore.BLUE}Pages scanned: {results['pages_scanned']}{Style.RESET_ALL}")
    
    elif module_name == "Subdomain Enumerator":
        active = [(s, i) for s, i in results['subdomains'].items() 
                  if i['http_status'] or i['https_status']]
        
        if active:
            print(f"{Fore.GREEN}Active Subdomains ({len(active)}):{Style.RESET_ALL}\n")
            for subdomain, info in sorted(active):
                http = info['http_status'] if info['http_status'] else "N/A"
                https = info['https_status'] if info['https_status'] else "N/A"
                
                print(f"  {Fore.CYAN}├─ {subdomain}{Style.RESET_ALL}")
                print(f"  {Fore.CYAN}│  HTTP: {http}  HTTPS: {https}{Style.RESET_ALL}")
                
                if info['ip_addresses']:
                    ips = ', '.join(info['ip_addresses'])
                    print(f"  {Fore.CYAN}└─ IPs: {ips}{Style.RESET_ALL}\n")
                else:
                    print(f"  {Fore.CYAN}└─ IPs: None{Style.RESET_ALL}\n")
        else:
            print(f"{Fore.YELLOW}No active subdomains found{Style.RESET_ALL}")
        
        print(f"{Fore.BLUE}Total subdomains: {results['total_count']}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}Active subdomains: {results['active_count']}{Style.RESET_ALL}")


def main():
    print_banner()
    
    parser = argparse.ArgumentParser(description='Unified Website Intelligence Tool')
    parser.add_argument('-u', '--url', help='Target URL (optional, can be provided interactively)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    target_url = args.url
    verbose = args.verbose
    
    # Get URL if not provided
    if not target_url:
        target_url = input(f"{Fore.GREEN}Enter target URL: {Style.RESET_ALL}").strip()
        if not target_url:
            print(f"{Fore.RED}Error: URL is required{Style.RESET_ALL}")
            sys.exit(1)
    
    # Add protocol if missing
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url
    
    print(f"\n{Fore.BLUE}Target: {target_url}{Style.RESET_ALL}")
    
    while True:
        choice = input(display_menu()).strip()
        
        if choice == '0':
            print(f"\n{Fore.GREEN}Thanks for using Web Intel Tool! Goodbye!{Style.RESET_ALL}\n")
            break
        
        elif choice == '1':
            print(f"\n{Fore.YELLOW}[*] Running Email Scraper...{Style.RESET_ALL}\n")
            scraper = EmailScraper(verbose=verbose)
            results = scraper.start_scraping(target_url)
            display_results("Email Scraper", results)
        
        elif choice == '2':
            print(f"\n{Fore.YELLOW}[*] Running Document Finder...{Style.RESET_ALL}\n")
            finder = DocumentFinder(verbose=verbose)
            results = finder.start_scanning(target_url)
            display_results("Document Finder", results)
        
        elif choice == '3':
            print(f"\n{Fore.YELLOW}[*] Running Social Media Finder...{Style.RESET_ALL}\n")
            finder = SocialMediaFinder(verbose=verbose)
            results = finder.start_scanning(target_url)
            display_results("Social Media Finder", results)
        
        elif choice == '4':
            if not DNS_AVAILABLE:
                print(f"\n{Fore.RED}[!] Subdomain finder requires dnspython library{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Install with: pip install dnspython{Style.RESET_ALL}\n")
                continue
            print(f"\n{Fore.YELLOW}[*] Running Subdomain Enumerator...{Style.RESET_ALL}\n")
            finder = SubdomainFinder(verbose=verbose)
            results = finder.scan(target_url)
            display_results("Subdomain Enumerator", results)
        
        elif choice == '5':
            print(f"\n{Fore.YELLOW}[*] Running All Scans...{Style.RESET_ALL}\n")
            
            # Email Scraper
            print(f"\n{Fore.MAGENTA}>>> Running Email Scraper{Style.RESET_ALL}")
            scraper = EmailScraper(verbose=verbose)
            email_results = scraper.start_scraping(target_url)
            display_results("Email Scraper", email_results)
            
            # Document Finder
            print(f"\n{Fore.MAGENTA}>>> Running Document Finder{Style.RESET_ALL}")
            doc_finder = DocumentFinder(verbose=verbose)
            doc_results = doc_finder.start_scanning(target_url)
            display_results("Document Finder", doc_results)
            
            # Social Media Finder
            print(f"\n{Fore.MAGENTA}>>> Running Social Media Finder{Style.RESET_ALL}")
            social_finder = SocialMediaFinder(verbose=verbose)
            social_results = social_finder.start_scanning(target_url)
            display_results("Social Media Finder", social_results)
            
            # Subdomain Enumerator
            if DNS_AVAILABLE:
                print(f"\n{Fore.MAGENTA}>>> Running Subdomain Enumerator{Style.RESET_ALL}")
                subdomain_finder = SubdomainFinder(verbose=verbose)
                subdomain_results = subdomain_finder.scan(target_url)
                display_results("Subdomain Enumerator", subdomain_results)
            else:
                print(f"\n{Fore.YELLOW}[!] Skipping Subdomain Enumerator (dnspython not installed){Style.RESET_ALL}")
        
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}[!] Interrupted by user. Exiting...{Style.RESET_ALL}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}[!] Fatal error: {str(e)}{Style.RESET_ALL}\n")
        sys.exit(1)

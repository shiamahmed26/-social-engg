#!/usr/bin/env python3
import requests
import socket
import dns.resolver
import re
import sys
import time
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Style, init

# Initialize colorama
init()

class SubdomainFinder:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.visited_urls = set()
        self.found_subdomains = {}  # {subdomain: {ip_addresses: [], status: str}}
        self.main_domain = ""
        self.max_threads = 20
        
        # DNS record types to query
        self.dns_record_types = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT']
        
    def print_verbose(self, message, level="info"):
        """Print message if verbose mode is enabled"""
        if not self.verbose:
            return
            
        if level == "info":
            print(f"{Fore.GREEN}[INFO] {message}{Style.RESET_ALL}")
        elif level == "debug":
            print(f"{Fore.CYAN}[DEBUG] {message}{Style.RESET_ALL}")
        elif level == "warning":
            print(f"{Fore.YELLOW}[WARNING] {message}{Style.RESET_ALL}")
        elif level == "error":
            print(f"{Fore.RED}[ERROR] {message}{Style.RESET_ALL}")
        elif level == "critical":
            print(f"{Fore.RED}{Style.BRIGHT}[CRITICAL] {message}{Style.RESET_ALL}")
    
    def extract_domain(self, url):
        """Extract the main domain from a URL"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Remove www if present
        if domain.startswith('www.'):
            domain = domain[4:]
            
        self.print_verbose(f"Extracted main domain: {domain}", "debug")
        return domain
    
    def is_valid_subdomain(self, hostname, main_domain):
        """Check if hostname is a valid subdomain of main_domain"""
        if not hostname or not main_domain:
            return False
            
        # Remove any protocol and path
        if '://' in hostname:
            hostname = urlparse(hostname).netloc
            
        # Check if it's a subdomain or the main domain
        return hostname.endswith(main_domain) and hostname != main_domain
    
    def resolve_ip(self, domain):
        """Resolve domain to IP address"""
        try:
            ip_addresses = []
            
            # Try for IPv4 addresses
            self.print_verbose(f"Resolving IPv4 for {domain}", "debug")
            try:
                answers = dns.resolver.resolve(domain, 'A')
                for answer in answers:
                    ip_addresses.append(str(answer))
            except:
                self.print_verbose(f"No IPv4 records found for {domain}", "debug")
                
            # Try for IPv6 addresses
            self.print_verbose(f"Resolving IPv6 for {domain}", "debug")
            try:
                answers = dns.resolver.resolve(domain, 'AAAA')
                for answer in answers:
                    ip_addresses.append(str(answer))
            except:
                self.print_verbose(f"No IPv6 records found for {domain}", "debug")
                
            return ip_addresses
        except Exception as e:
            self.print_verbose(f"Error resolving IP for {domain}: {str(e)}", "error")
            return []
    
    def get_dns_records(self, domain):
        """Get all DNS records for a domain"""
        records = {}
        
        for record_type in self.dns_record_types:
            try:
                answers = dns.resolver.resolve(domain, record_type)
                records[record_type] = [str(answer) for answer in answers]
                self.print_verbose(f"Found {record_type} records for {domain}: {records[record_type]}", "debug")
            except Exception as e:
                self.print_verbose(f"No {record_type} records found for {domain}: {str(e)}", "debug")
                records[record_type] = []
                
        return records
    
    def check_website_status(self, url):
        """Check if website is accessible and get its status code"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            self.print_verbose(f"Status for {url}: {response.status_code}", "debug")
            return response.status_code
        except Exception as e:
            self.print_verbose(f"Error checking status for {url}: {str(e)}", "debug")
            return None
    
    def process_subdomain(self, subdomain):
        """Process a subdomain to gather its information"""
        if subdomain in self.found_subdomains:
            return
            
        self.print_verbose(f"Processing subdomain: {subdomain}", "info")
        
        # Resolve IPs
        ip_addresses = self.resolve_ip(subdomain)
        
        # Try both HTTP and HTTPS
        http_status = self.check_website_status(f"http://{subdomain}")
        https_status = self.check_website_status(f"https://{subdomain}")
        
        # Get DNS records
        dns_records = self.get_dns_records(subdomain)
        
        # Store information
        self.found_subdomains[subdomain] = {
            'ip_addresses': ip_addresses,
            'http_status': http_status,
            'https_status': https_status,
            'dns_records': dns_records
        }
    
    def find_subdomains_in_page(self, url, main_domain):
        """Find subdomains in a web page"""
        if url in self.visited_urls:
            return []
            
        self.visited_urls.add(url)
        self.print_verbose(f"Scanning page for subdomains: {url}", "info")
        
        subdomains = set()
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            self.print_verbose(f"Retrieved page with status: {response.status_code}", "debug")
            
            # Extract subdomains from links
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links
            for tag in ['a', 'link', 'script', 'img', 'source', 'form']:
                for element in soup.find_all(tag, href=True):
                    href = element['href']
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)
                    hostname = parsed.netloc
                    
                    if self.is_valid_subdomain(hostname, main_domain):
                        subdomains.add(hostname)
                        self.print_verbose(f"Found subdomain in href: {hostname}", "debug")
                
                for element in soup.find_all(tag, src=True):
                    src = element['src']
                    full_url = urljoin(url, src)
                    parsed = urlparse(full_url)
                    hostname = parsed.netloc
                    
                    if self.is_valid_subdomain(hostname, main_domain):
                        subdomains.add(hostname)
                        self.print_verbose(f"Found subdomain in src: {hostname}", "debug")
            
            # Extract subdomains from plain text using regex
            subdomain_pattern = r'([a-zA-Z0-9][-a-zA-Z0-9]*\.)+' + re.escape(main_domain)
            text_subdomains = re.findall(subdomain_pattern, response.text)
            
            for subdomain in text_subdomains:
                if self.is_valid_subdomain(subdomain + main_domain, main_domain):
                    subdomains.add(subdomain + main_domain)
                    self.print_verbose(f"Found subdomain in text: {subdomain + main_domain}", "debug")
            
            return list(subdomains)
            
        except Exception as e:
            self.print_verbose(f"Error scanning page {url}: {str(e)}", "error")
            return []
            
    def find_common_subdomains(self, main_domain):
        """Try to find common subdomains"""
        common_prefixes = [
            "www", "mail", "ftp", "webmail", "admin", "intranet",
            "blog", "test", "dev", "staging", "api", "cdn", "media",
            "shop", "store", "secure", "portal", "beta", "app",
            "dashboard", "login", "auth", "vpn", "remote", "docs",
            "forum", "support", "help", "cloud", "ns1", "ns2",
            "mx", "smtp", "pop", "git", "gitlab", "jenkins",
            "jira", "wiki", "internal", "m"
        ]
        
        found = []
        
        self.print_verbose(f"Checking common subdomains for {main_domain}", "info")
        
        for prefix in common_prefixes:
            subdomain = f"{prefix}.{main_domain}"
            
            # Quick check if subdomain resolves
            try:
                socket.gethostbyname(subdomain)
                found.append(subdomain)
                self.print_verbose(f"Found common subdomain: {subdomain}", "info")
            except socket.gaierror:
                self.print_verbose(f"Common subdomain not found: {subdomain}", "debug")
        
        return found
    
    def scan(self, url):
        """Main scanning function"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        start_time = time.time()
        
        # Extract main domain
        self.main_domain = self.extract_domain(url)
        print(f"{Fore.GREEN}[*] Starting subdomain scan for: {self.main_domain}{Style.RESET_ALL}")
        
        # Find common subdomains
        print(f"{Fore.BLUE}[*] Checking common subdomains...{Style.RESET_ALL}")
        common_subdomains = self.find_common_subdomains(self.main_domain)
        
        # Find subdomains from main page
        print(f"{Fore.BLUE}[*] Scanning main website for subdomain references...{Style.RESET_ALL}")
        main_page_subdomains = self.find_subdomains_in_page(url, self.main_domain)
        
        # Combine all found subdomains
        all_subdomains = set(common_subdomains + main_page_subdomains)
        
        # Add the main domain itself
        all_subdomains.add(self.main_domain)
        all_subdomains.add(f"www.{self.main_domain}")
        
        # Process each subdomain in parallel
        print(f"{Fore.BLUE}[*] Processing {len(all_subdomains)} discovered subdomains...{Style.RESET_ALL}")
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            executor.map(self.process_subdomain, all_subdomains)
            
        # Display results
        self.display_results()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n{Fore.GREEN}[*] Scan completed in {duration:.2f} seconds{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[*] Found {len(self.found_subdomains)} subdomains for {self.main_domain}{Style.RESET_ALL}")
    
    def display_results(self):
        """Display the scan results"""
        print(f"\n{Fore.YELLOW}[+] Subdomain Scan Results:{Style.RESET_ALL}")
        
        if not self.found_subdomains:
            print(f"{Fore.RED}No subdomains found.{Style.RESET_ALL}")
            return
            
        # Group subdomains by status (active/inactive)
        active_subdomains = []
        inactive_subdomains = []
        
        for subdomain, info in self.found_subdomains.items():
            if info['http_status'] or info['https_status']:
                active_subdomains.append((subdomain, info))
            elif info['ip_addresses']:
                inactive_subdomains.append((subdomain, info))
        
        # Sort subdomains alphabetically
        active_subdomains.sort(key=lambda x: x[0])
        inactive_subdomains.sort(key=lambda x: x[0])
        
        # Display active subdomains
        print(f"\n{Fore.GREEN}Active Subdomains ({len(active_subdomains)}):{Style.RESET_ALL}")
        for subdomain, info in active_subdomains:
            http_status = info['http_status'] if info['http_status'] else "N/A"
            https_status = info['https_status'] if info['https_status'] else "N/A"
            
            status_color = Fore.GREEN if (http_status in [200, 301, 302] or https_status in [200, 301, 302]) else Fore.YELLOW
            
            print(f"\n{Fore.CYAN}Subdomain: {subdomain}{Style.RESET_ALL}")
            print(f"  {status_color}HTTP Status: {http_status}{Style.RESET_ALL}")
            print(f"  {status_color}HTTPS Status: {https_status}{Style.RESET_ALL}")
            
            if info['ip_addresses']:
                print(f"  IP Addresses:")
                for ip in info['ip_addresses']:
                    print(f"    {Fore.WHITE}{ip}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.YELLOW}No IP addresses found{Style.RESET_ALL}")
            
            # Print DNS records if in verbose mode
            if self.verbose:
                print(f"  DNS Records:")
                for record_type, records in info['dns_records'].items():
                    if records:
                        print(f"    {record_type}:")
                        for record in records:
                            print(f"      {record}")
        
        # Display inactive subdomains if verbose
        if inactive_subdomains:
            print(f"\n{Fore.YELLOW}Inactive Subdomains ({len(inactive_subdomains)}):{Style.RESET_ALL}")
            for subdomain, info in inactive_subdomains:
                print(f"\n{Fore.CYAN}Subdomain: {subdomain}{Style.RESET_ALL}")
                
                if info['ip_addresses']:
                    print(f"  IP Addresses:")
                    for ip in info['ip_addresses']:
                        print(f"    {Fore.WHITE}{ip}{Style.RESET_ALL}")
                else:
                    print(f"  {Fore.YELLOW}No IP addresses found{Style.RESET_ALL}")
                
                # Print DNS records if in verbose mode
                if self.verbose:
                    print(f"  DNS Records:")
                    for record_type, records in info['dns_records'].items():
                        if records:
                            print(f"    {record_type}:")
                            for record in records:
                                print(f"      {record}")

def main():
    parser = argparse.ArgumentParser(description='Subdomain Finder - Discover and enumerate subdomains')
    parser.add_argument('url', help='Target website URL or domain')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    finder = SubdomainFinder(verbose=args.verbose)
    finder.scan(args.url)

if __name__ == "__main__":
    main()

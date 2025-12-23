import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, urlparse, parse_qs

class ContactDiscoverer:
    """
    Background intelligence process that enriches prospect profiles 
    with contact information (Email/Phone).
    """
    
    # Standard flexible regex patterns
    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

    # Stricter US-centric regex: 
    # Optional +1, Area Code (200-999), Exchange (200-999), Subscriber (0000-9999)
    # Excludes 0xx/1xx area codes and exchanges.
    PHONE_REGEX = re.compile(r'(?:\+?1[-. ]?)?\(?([2-9]\d{2})\)?[-. ]?([2-9]\d{2})[-. ]?(\d{4})')

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _clean_instagram_url(self, url: str) -> str:
        """Decodes l.instagram.com redirect links to get the real URL."""
        if not url: return url
        if 'l.instagram.com' in url:
            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                if 'u' in qs:
                    return unquote(qs['u'][0])
            except Exception:
                pass
        return url
    
    def _validate_phone(self, phone_text: str) -> str:
        """
        Refines and validates the phone match.
        Returns formatted string (e.g., '(808) 555-1234') or None.
        """
        match = self.PHONE_REGEX.search(phone_text)
        if not match:
            return None
        
        # Standardize format
        area, exchange, subscriber = match.groups()
        return f"({area}) {exchange}-{subscriber}"

    def extract_from_website(self, url: str) -> dict:
        """
        Visits the website and crawls for mailto: links, tel: links, 
        or Contact Us pages to find emails and phone numbers.
        
        Returns:
            dict: {'email': str, 'phone_number': str, 'source': str} or None
        """
        clean_url = self._clean_instagram_url(url)
        try:
            # print(f"[Discovery] Crawling website: {clean_url}") 
            response = requests.get(clean_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            email = None
            phone = None
            
            # 1. Check mailto: links
            mailto = soup.select_one('a[href^="mailto:"]')
            if mailto:
                href = mailto.get('href')
                if href:
                    email_match = self.EMAIL_REGEX.search(href)
                    if email_match:
                        email = email_match.group(0)
                        
            # 2. Check text for regex matches if not found
            text_content = soup.get_text()
            
            if not email:
                email_match = self.EMAIL_REGEX.search(text_content)
                if email_match:
                    email = email_match.group(0)
            
            phone_raw = self.PHONE_REGEX.search(text_content)
            if phone_raw:
                phone = self._validate_phone(phone_raw.group(0))
                
            if email or phone:
                res = {
                    'email': email,
                    'phone_number': phone,
                    'source': f'Website ({clean_url})'
                }
                print(f"[Discovery] Website Scraping Result for {clean_url}: {res}")
                return res
            else:
                print(f"[Discovery] Website Scraping: No info found on {clean_url}")
                
        except Exception as e:
            self.logger.warning(f"Failed to extract from website {url}: {e}")
            
        return None

    def search_duckduckgo(self, query: str) -> dict:
        """
        Initiates a headless DuckDuckGo search and parses snippets.
        
        Returns:
            dict: {'email': str, 'phone_number': str, 'source': str} or None
        """
        try:
            print(f"[Discovery] Searching DuckDuckGo for: '{query}'")
            results = self._perform_search(query)
            
            for result in results:
                text = result.get('body', '') + " " + result.get('title', '')
                
                email_match = self.EMAIL_REGEX.search(text)
                phone_raw = self.PHONE_REGEX.search(text)
                
                email = email_match.group(0) if email_match else None
                phone = self._validate_phone(phone_raw.group(0)) if phone_raw else None
                
                if email or phone:
                    res = {
                        'email': email,
                        'phone_number': phone,
                        'source': 'DuckDuckGo'
                    }
                    print(f"[Discovery] Search Result Found: {res}")
                    return res
            
            print(f"[Discovery] Search complete. No contact info found in snippets.")
                    
        except Exception as e:
            self.logger.warning(f"Search failed for query '{query}': {e}")
            
        return None

    def _perform_search(self, query: str) -> list:
        """
        Helper to perform the actual search. 
        Isolated for easier mocking of the search provider (DDGS, requests, etc).
        Returns list of dicts: [{'title': str, 'body': str}]
        """
        try:
            url = 'https://html.duckduckgo.com/html/'
            response = requests.post(url, data={'q': query}, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.select('.result'):
                title_elem = result.select_one('.result__title')
                snippet_elem = result.select_one('.result__snippet')
                
                if title_elem and snippet_elem:
                    results.append({
                        'title': title_elem.get_text(strip=True),
                        'body': snippet_elem.get_text(strip=True)
                    })
            return results
        except Exception as e:
            self.logger.error(f"_perform_search failed: {e}")
            return []

    def process_profile(self, profile_data: dict) -> dict:
        """
        Main entry point. 
        1. Try extracting from Bio Link (if exists).
        2. Fallback to DuckDuckGo search if Step 1 fails.
        
        Args:
            profile_data (dict): Dictionary containing 'target_username', 'biography', 'bio_link', etc.
            
        Returns:
            dict: Updated profile data or just the discovered contact info.
        """
        bio_link = profile_data.get('bio_link')
        website_result = None
        
        if bio_link:
            website_result = self.extract_from_website(bio_link)
            if website_result and website_result.get('email') and website_result.get('phone_number'):
                return website_result

        # Check biography for phone number (if provided)
        bio_text = profile_data.get('biography', '')
        if bio_text:
            bio_phone_raw = self.PHONE_REGEX.search(bio_text)
            if bio_phone_raw:
                found_phone = self._validate_phone(bio_phone_raw.group(0))
                if found_phone:
                    print(f"[Discovery] Found phone number directly in BIO: {found_phone}")
                    if website_result:
                        website_result['phone_number'] = found_phone
                    else:
                        website_result = {'email': None, 'phone_number': found_phone, 'source': 'Instagram Bio'}

        # Fallback to search
        # Support both 'name' (from prompt) and 'target_username' (from test/existing code)
        name = profile_data.get('name', profile_data.get('target_username', ''))
        address = profile_data.get('address', '')
        
        query = f"{name} {address} email phone".strip()
        search_result = self.search_duckduckgo(query)
        
        if website_result and search_result:
            # Merge results, preferring website
            return {
                'email': website_result.get('email') or search_result.get('email'),
                'phone_number': website_result.get('phone_number') or search_result.get('phone_number'),
                'source': f"{website_result.get('source')} + {search_result.get('source')}"
            }
        
        return website_result or search_result
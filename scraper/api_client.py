import httpx
import time
import os
from typing import Dict, Any, Optional
from config.settings import settings
from database.connection import DatabaseConnection
from database.token_queries import TokenQueries


class KeyCRMClient:
    
    def __init__(self, bearer_token: Optional[str] = None, auto_refresh: bool = True, db: Optional[DatabaseConnection] = None):
        self.base_url = settings.KEYCRM_BASE_URL
        self.db = db
        self.timeout = settings.REQUEST_TIMEOUT
        self.delay = settings.REQUEST_DELAY
        self.auto_refresh = auto_refresh
        self.token_refreshed = False
        
        if bearer_token:
            self.bearer_token = bearer_token
        elif db:
            token_queries = TokenQueries(db)
            self.bearer_token = token_queries.get_token('bearer_token')
            if not self.bearer_token:
                raise ValueError("No bearer token found in database. Run 'python main.py auth' first")
        else:
            self.bearer_token = settings.KEYCRM_BEARER_TOKEN
            if not self.bearer_token:
                raise ValueError("Bearer token is required. Set KEYCRM_BEARER_TOKEN in .env or run 'python main.py auth'")
        
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers()
        )
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.bearer_token}',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'UserLocale': 'uk'
        }
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = endpoint if endpoint.startswith('http') else f"{self.base_url}{endpoint}"
        
        try:
            response = self.client.request(method, url, **kwargs)
            response.raise_for_status()
            
            if self.delay > 0:
                time.sleep(self.delay)
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and self.auto_refresh and not self.token_refreshed:
                new_token = self._refresh_token()
                
                if new_token:
                    self.bearer_token = new_token
                    self.client.headers['Authorization'] = f'Bearer {new_token}'
                    self.token_refreshed = True
                    
                    return self._make_request(method, endpoint, **kwargs)
                else:
                    raise
            else:
                raise
        except httpx.RequestError as e:
            raise
        except Exception as e:
            raise
    
    def _refresh_token(self) -> Optional[str]:
        try:
            from scraper.auth import KeyCRMAuth
            
            auth = KeyCRMAuth(db=self.db)
            new_token = auth.extract_bearer_token()
            
            if self.db:
                token_queries = TokenQueries(self.db)
                token_queries.save_token(new_token, token_type='bearer_token')
            
            if os.getenv('GITHUB_ACTIONS') == 'true':
                self._update_github_secret('KEYCRM_BEARER_TOKEN', new_token)
            
            return new_token
            
        except Exception:
            return None
    
    def _update_github_secret(self, secret_name: str, secret_value: str) -> bool:
        try:
            import base64
            from nacl import encoding, public
            
            github_token = os.getenv('GITHUB_TOKEN')
            repo = os.getenv('GITHUB_REPOSITORY')
            
            if not github_token or not repo:
                return False
            
            api_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
            
            key_url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
            key_response = httpx.get(key_url, headers={
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            })
            key_response.raise_for_status()
            key_data = key_response.json()
            
            public_key = public.PublicKey(key_data['key'].encode(), encoding.Base64Encoder())
            sealed_box = public.SealedBox(public_key)
            encrypted = sealed_box.encrypt(secret_value.encode())
            encrypted_value = base64.b64encode(encrypted).decode()
            
            response = httpx.put(api_url, json={
                'encrypted_value': encrypted_value,
                'key_id': key_data['key_id']
            }, headers={
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            })
            response.raise_for_status()
            
            return True
            
        except Exception:
            return False
    
    def get_orders(self, page: int = 1, per_page: Optional[int] = None, custom_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        per_page = per_page or settings.ORDERS_PER_PAGE
        
        if not custom_filters:
            raise ValueError(
                "No filters provided. KEYCRM_FILTERS_URL must be set to specify which orders to scrape. "
                "Example: https://your-company.keycrm.app/orders?filters[manager_id]=312&filters[status_id]=36"
            )
        
        params = custom_filters.copy()
        params['page'] = page
        if 'per_page' not in params:
            params['per_page'] = per_page
        
        return self._make_request('GET', '/orders', params=params)
    
    def get_order_by_id(self, order_id: int) -> Dict[str, Any]:
        return self._make_request('GET', f'/orders/{order_id}')
    
    def get_statuses(self) -> Dict[str, Any]:
        return self._make_request('GET', '/orders/statuses', params={'with_disabled': 1})
    
    def get_users(self) -> Dict[str, Any]:
        return self._make_request('GET', '/users')
    
    def close(self):
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class OrdersScraper:
    
    def __init__(self, client: KeyCRMClient):
        self.client = client
    
    def scrape_all_orders(self, max_pages: Optional[int] = None, custom_filters: Optional[Dict[str, Any]] = None) -> list:
        all_orders = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
            
            try:
                response = self.client.get_orders(page=page, custom_filters=custom_filters)
            except Exception:
                break
            
            orders = response.get('data', [])
            if not orders:
                break
            
            all_orders.extend(orders)
            
            links = response.get('links', {})
            if not links.get('next'):
                break
            
            page += 1
        
        return all_orders
    
    def scrape_page(self, page: int = 1) -> list:
        response = self.client.get_orders(page=page)
        orders = response.get('data', [])
        return orders
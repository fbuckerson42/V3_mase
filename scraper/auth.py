from playwright.sync_api import sync_playwright, Page
import re
import time
import os
from typing import Optional
from config.settings import settings
from database.connection import DatabaseConnection
from database.token_queries import TokenQueries


class KeyCRMAuth:
    def __init__(self, login: Optional[str] = None, password: Optional[str] = None, db: Optional[DatabaseConnection] = None):
        self.login = login or settings.KEYCRM_LOGIN
        self.password = password or settings.KEYCRM_PASSWORD
        self.web_url = settings.KEYCRM_WEB_URL
        self.db = db
        if not self.login or not self.password:
            raise ValueError("Login and password are required. Set KEYCRM_LOGIN and KEYCRM_PASSWORD in .env")

    def extract_bearer_token(self) -> str:
        snapshot_path = os.path.join(os.getcwd(), 'token_snapshot.json')
        if os.path.exists(snapshot_path):
            try:
                import json
                with open(snapshot_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                token = data.get('token') or data.get('bearer_token') or data.get('auth_token')
                if token:
                    return token
            except Exception:
                pass
        
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=is_github_actions)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='uk-UA',
                timezone_id='Europe/Kiev',
                extra_http_headers={
                    'Accept-Language': 'uk,en-US;q=0.9,en;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                }
            )
            page = context.new_page()
            responses = []
            errors = []

            def log_response(response):
                if 'login' in response.url.lower() or 'auth' in response.url.lower() or 'api' in response.url.lower():
                    responses.append(f"{response.status} {response.url}")
                    if response.status >= 400:
                        errors.append(f"Error response: {response.status} {response.url}")
            page.on('response', log_response)

            try:
                page.goto(f"{self.web_url}/login", wait_until="domcontentloaded", timeout=60000)
                if os.getenv('GITHUB_ACTIONS') == 'true':
                    page.screenshot(path='01_login_page.png')
                    with open('01_login_page.html', 'w', encoding='utf-8') as f:
                        f.write(page.content())

                page.wait_for_selector('input', timeout=10000)
                if os.getenv('GITHUB_ACTIONS') == 'true':
                    page.screenshot(path='02_form_visible.png')

                email_input = page.locator('input').first
                password_input = page.locator('input[type="password"]').first
                email_input.fill(self.login)
                password_input.fill(self.password)

                if os.getenv('GITHUB_ACTIONS') == 'true':
                    page.screenshot(path='03_credentials_filled.png')

                try:
                    page.locator('text=Увійти').click()
                except Exception:
                    page.locator('input[type="password"]').press('Enter')

                page.wait_for_timeout(15000)

                current_url = page.url
                try:
                    title = page.title()
                except Exception:
                    title = 'N/A'
                
                dashboard_indicators = ["text=Замовлення", "text=Продажі", "text=Покупці", "a[href*='/app/orders']", "text=Огляд"]
                login_successful = False
                for indicator in dashboard_indicators:
                    try:
                        if page.locator(indicator).count() > 0:
                            login_successful = True
                            break
                    except:
                        pass
                
                if not login_successful and (current_url.endswith('/login') or current_url.endswith('/login/')):
                    page.screenshot(path='04_login_failed.png')
                    with open('04_login_failed.html', 'w', encoding='utf-8') as f:
                        f.write(page.content())
                    page_content = page.content()
                    with open('04_login_failed_full.html', 'w', encoding='utf-8') as f:
                        f.write(page_content)
                    error_msg = "No visible error message"
                    for selector in ['text=Помилка', 'text=Error', 'text=Invalid', 'text=Невірн']:
                        try:
                            error_elem = page.locator(selector).first
                            if error_elem.count() > 0:
                                error_msg = error_elem.text_content(timeout=1000)
                                break
                        except:
                            pass
                    interactive = os.getenv('AUTH_INTERACTIVE', 'false').lower() == 'true'
                    if interactive:
                        input()
                        token = self._extract_token_from_network(page) or self._extract_token_from_storage(page)
                        if not token:
                            raise Exception("Login not completed and token not extracted")
                        return token
                    else:
                        raise Exception("Login not completed in interactive environment.")
                    token = self._extract_token_from_network(page)
                    if not token:
                        token = self._extract_token_from_storage(page)
                    if not token:
                        raise Exception(f"Login failed: {error_msg}")
                    return token

                try:
                    page.goto(f"{self.web_url}/app/orders", wait_until="load")
                    page.wait_for_timeout(2000)
                    try:
                        current = page.url
                        if '/app/orders' not in current:
                            page.goto(f"{self.web_url}/orders", wait_until="load")
                            page.wait_for_timeout(2000)
                    except Exception:
                        pass
                except Exception:
                    pass

                try:
                    indicators = ["text=Замовлення", "text=Продажі", "text=Покупці"]
                    for ind in indicators:
                        if page.locator(ind).count() > 0:
                            break
                except Exception:
                    pass
                time.sleep(3)
                token = self._extract_token_from_network(page)
                if not token:
                    token = self._extract_token_from_storage(page)
                if not token:
                    raise Exception("Failed to extract Bearer token")
                return token
            except Exception as e:
                raise
            finally:
                browser.close()

    def _extract_token_from_storage(self, page: Page) -> Optional[str]:
        try:
            all_keys = page.evaluate("() => Object.keys(localStorage)")
            all_storage = page.evaluate("() => { const r = {}; for(const k of Object.keys(localStorage)) { try { r[k] = localStorage.getItem(k); } catch(e){ r[k] = null; } } return r; }")
            token = None
            token_key = None
            for key in all_keys:
                if key.lower() in ['token','access_token','auth_token','bearer_token','jwt']:
                    value = page.evaluate("(k) => localStorage.getItem(k)", key)
                    if value:
                        token = value
                        token_key = key
                        break
            if not token:
                for key in all_keys:
                    value = page.evaluate("(k) => localStorage.getItem(k)", key)
                    if value and isinstance(value, str) and value.startswith('eyJ'):
                        token = value
                        token_key = key
                        break
            if token:
                return token
        except Exception:
            pass
        return None

    def _extract_token_from_network(self, page: Page) -> Optional[str]:
        try:
            captured_token = None

            def _scan_for_jwt_in(obj):
                if isinstance(obj, str) and obj.startswith('eyJ'):
                    return obj
                if isinstance(obj, dict):
                    for v in obj.values():
                        t = _scan_for_jwt_in(v)
                        if t:
                            return t
                if isinstance(obj, list):
                    for it in obj:
                        t = _scan_for_jwt_in(it)
                        if t:
                            return t
                return None

            def _handle_response_json(body, url):
                nonlocal captured_token
                t = _scan_for_jwt_in(body)
                if t:
                    captured_token = t

            def handle_request(request):
                nonlocal captured_token
                auth_header = request.headers.get('authorization', '')
                if auth_header.startswith('Bearer '):
                    captured_token = auth_header.replace('Bearer ', '')

            def handle_response(response):
                try:
                    auth_header = response.headers.get('authorization', '')
                    if auth_header.startswith('Bearer '):
                        captured_token = auth_header.replace('Bearer ', '')
                except Exception:
                    pass
                try:
                    ctype = (response.headers.get('content-type') or '').lower()
                    if 'application/json' in ctype or 'json' in ctype:
                        body = response.json()
                        _handle_response_json(body, response.url)
                        if not captured_token:
                            t = _scan_for_jwt_in(body)
                            if t:
                                captured_token = t
                    else:
                        text_body = response.text()
                        if text_body:
                            m = re.findall(r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', text_body)
                            if m:
                                captured_token = m[0]
                except Exception:
                    pass

            page.on('request', handle_request)
            page.on('response', handle_response)
            page.goto(f"{self.web_url}/orders", wait_until="load")
            time.sleep(5)
            try:
                cookies = page.context.cookies()
                for c in cookies:
                    name = str(c.get('name','')).lower()
                    val = c.get('value','')
                    if any(k in name for k in ['token','bearer','auth','access']) and val:
                        if val.startswith('eyJ'):
                            captured_token = val
                            break
            except Exception:
                pass
            if captured_token:
                return captured_token
            return None
        except Exception:
            pass
        return None

    def save_token_to_db(self, token: str) -> None:
        if not self.db:
            return
        try:
            token_queries = TokenQueries(self.db)
            token_queries.save_token(token, token_type='bearer_token')
        except Exception as e:
            raise

    def save_token_to_env(self, token: str) -> None:
        try:
            env_file = '.env'
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            token_found = False
            for i, line in enumerate(lines):
                if line.startswith('KEYCRM_BEARER_TOKEN='):
                    lines[i] = f'KEYCRM_BEARER_TOKEN={token}\n'
                    token_found = True
                    break
            if not token_found:
                lines.append(f'\nKEYCRM_BEARER_TOKEN={token}\n')
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            raise


def authenticate_and_save(db: Optional[DatabaseConnection] = None) -> str:
    auth = KeyCRMAuth(db=db)
    token = auth.extract_bearer_token()
    if db:
        auth.save_token_to_db(token)
        return token
    return token
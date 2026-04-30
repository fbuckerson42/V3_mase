import sys
import os
import argparse
from typing import Optional, Dict, Any
from config.settings import settings
from database.connection import DatabaseConnection
from database.queries import OrderQueries
from scraper.auth import authenticate_and_save
from scraper.api_client import KeyCRMClient, OrdersScraper
from scraper.parser import OrderParser
from scraper.url_parser import URLParser
from scraper.token_check import is_token_valid


def run_migration(db: DatabaseConnection) -> None:
    migrations = [
        'database/migrations/001_create_orders_table.sql',
        'database/migrations/002_create_tokens_table.sql',
    ]
    
    for migration_file in migrations:
        db.run_migration(migration_file)


def authenticate() -> str:
    with DatabaseConnection() as db:
        token = authenticate_and_save(db=db)
        return token


def scrape_orders(max_pages: Optional[int] = None, filters_url: Optional[str] = None, max_retries: int = 1) -> None:
    if not settings.validate():
        sys.exit(1)
    
    with DatabaseConnection() as db:
        from database.token_queries import TokenQueries
        token_queries = TokenQueries(db)
        stored_token = token_queries.get_token('bearer_token')
        
        should_authenticate = False
        
        if not stored_token:
            should_authenticate = True
        else:
            with KeyCRMClient(bearer_token=stored_token) as client:
                if not is_token_valid(client):
                    should_authenticate = True
        
        if should_authenticate:
            authenticate()
            stored_token = token_queries.get_token('bearer_token')
    
    filters_url = filters_url or os.getenv('KEYCRM_FILTERS_URL')
    
    if not filters_url:
        sys.exit(1)
    
    custom_filters = URLParser.parse_keycrm_url(filters_url)
    filter_summary = URLParser.get_filter_summary(filters_url)
    
    stats = {
        'total_fetched': 0,
        'inserted': 0,
        'updated': 0,
        'errors': 0
    }
    
    for attempt in range(max_retries + 1):
        try:
            with DatabaseConnection() as db:
                queries = OrderQueries(db)
                
                token_to_use = stored_token or settings.KEYCRM_BEARER_TOKEN
                with KeyCRMClient(bearer_token=token_to_use, db=db, auto_refresh=False) as client:
                    OrderParser.load_statuses_from_api(client)
                    
                    scraper = OrdersScraper(client)
                    
                    orders_json = scraper.scrape_all_orders(max_pages=max_pages, custom_filters=custom_filters)
                    stats['total_fetched'] = len(orders_json)
                    
                    if not orders_json:
                        return
                    
                    all_orders_data = []
                    for i, order_json in enumerate(orders_json, 1):
                        try:
                            order_data = OrderParser.parse_order(order_json)
                            all_orders_data.append(order_data)
                        except Exception:
                            stats['errors'] += 1
                            continue
                    
                    batch_stats = queries.batch_upsert_orders(all_orders_data)
                    stats['inserted'] = 0
                    stats['updated'] = batch_stats.get('updated', len(all_orders_data))
                    stats['errors'] += batch_stats.get('errors', 0)
                    
                    db.commit()
            
            return
            
        except Exception as e:
            error_str = str(e)
            is_401 = '401' in error_str or 'Unauthorized' in error_str
            
            if is_401 and attempt < max_retries:
                try:
                    with DatabaseConnection() as db:
                        token = authenticate_and_save(db=db)
                except Exception:
                    if attempt == max_retries:
                        raise
            else:
                raise


def show_statistics() -> None:
    try:
        with DatabaseConnection() as db:
            queries = OrderQueries(db)
            stats = queries.get_statistics()
            
    except Exception:
        raise


def main():
    parser = argparse.ArgumentParser(
        description='KeyCRM Scraper - Scrape orders from KeyCRM to PostgreSQL'
    )
    
    parser.add_argument(
        'command',
        choices=['scrape', 'auth', 'migrate', 'stats'],
        help='Command to execute'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='Maximum pages to scrape (default: all)'
    )
    
    parser.add_argument(
        '--url',
        type=str,
        default=None,
        help='KeyCRM URL with filters (e.g., "https://your-company.keycrm.app/orders?filters[manager_id]=120")'
    )
    
    args = parser.parse_args()
    
    try:
        if args.command == 'auth':
            authenticate()
            
        elif args.command == 'migrate':
            with DatabaseConnection() as db:
                run_migration(db)
        
        elif args.command == 'scrape':
            scrape_orders(max_pages=args.max_pages, filters_url=args.url)
        
        elif args.command == 'stats':
            show_statistics()
        
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        sys.exit(1)


if __name__ == '__main__':
    main()
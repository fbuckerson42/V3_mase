from typing import Optional, Dict, Any, List
from datetime import datetime, date
from config.settings import settings


class OrderParser:
    
    _status_cache: Optional[Dict[int, str]] = None
    
    @classmethod
    def load_statuses_from_api(cls, client) -> Dict[int, str]:
        if cls._status_cache is not None:
            return cls._status_cache
        
        try:
            response = client.get_statuses()
            statuses = response.get('data', [])
            cls._status_cache = {s['id']: s['name'] for s in statuses}
        except Exception:
            cls._status_cache = {}
        
        return cls._status_cache
    
    @classmethod
    def get_status_name(cls, status_id: int) -> str:
        if cls._status_cache is None:
            return 'Unknown'
        
        return cls._status_cache.get(status_id, 'Unknown')
    
    @classmethod
    def parse_date(cls, date_string: Optional[str]) -> Optional[date]:
        if not date_string:
            return None
        
        try:
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return dt.date()
        except (ValueError, AttributeError):
            return None
    
    @classmethod
    def extract_prp_date(cls, custom_fields: List[Dict[str, Any]]) -> Optional[date]:
        if not custom_fields:
            return None
        
        for field in custom_fields:
            if field.get('field_id') == settings.PRP_FIELD_ID:
                value = field.get('value')
                if value:
                    try:
                        return datetime.strptime(value, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        return None
        
        return None
    
    @classmethod
    def parse_order(cls, order_json: Dict[str, Any]) -> Dict[str, Any]:
        try:
            manager = order_json.get('manager', {})
            
            created_at = cls.parse_date(order_json.get('created_at'))
            closed_at = cls.parse_date(order_json.get('closed_at'))
            
            custom_fields = order_json.get('custom_field_values', [])
            prp_date = cls.extract_prp_date(custom_fields)
            
            status_id = order_json['status_id']
            status_name = cls.get_status_name(status_id)
            
            order_data = {
                'id': order_json['id'],
                'created_at': created_at,
                'closed_at': closed_at,
                
                'status_id': status_id,
                'status_name': status_name,
                
                'manager_id': order_json['manager_id'],
                'manager_name': manager.get('full_name', 'Unknown') if isinstance(manager, dict) else 'Unknown',
                
                'grand_total': float(order_json.get('grand_total', 0)),
                
                'prp_date': prp_date
            }
            
            return order_data
            
        except KeyError as e:
            raise
        except Exception as e:
            raise
    
    @staticmethod
    def parse_orders_response(response_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        orders_data = []
        
        data = response_json.get('data', [])
        if not data:
            return orders_data
        
        for order_json in data:
            try:
                order_data = OrderParser.parse_order(order_json)
                orders_data.append(order_data)
            except Exception:
                continue
        
        return orders_data
    
    @staticmethod
    def has_next_page(response_json: Dict[str, Any]) -> bool:
        links = response_json.get('links', {})
        return links.get('next') is not None
    
    @staticmethod
    def get_total_pages(response_json: Dict[str, Any]) -> Optional[int]:
        meta = response_json.get('meta', {})
        return meta.get('last_page')
    
    @staticmethod
    def get_current_page(response_json: Dict[str, Any]) -> int:
        meta = response_json.get('meta', {})
        return meta.get('current_page', 1)
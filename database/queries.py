from typing import Optional, Dict, Any, List
from datetime import datetime, date
import pytz
from database.connection import DatabaseConnection

KYIV_TZ = pytz.timezone('Europe/Kyiv')


def utc_to_kyiv(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            return dt.astimezone(KYIV_TZ)
        return pytz.UTC.localize(dt).astimezone(KYIV_TZ)
    if isinstance(dt, date):
        dt = datetime.combine(dt, datetime.min.time())
        return pytz.UTC.localize(dt).astimezone(KYIV_TZ)
    return dt


def now_kyiv() -> datetime:
    return datetime.now(KYIV_TZ)


class OrderQueries:
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
    
    def order_exists(self, order_id: int) -> bool:
        query = "SELECT id FROM orders WHERE id = %s"
        result = self.db.fetchone(query, (order_id,))
        return result is not None
    
    def insert_order(self, order_data: Dict[str, Any]) -> None:
        query = """
            INSERT INTO orders (
                id, created_at, closed_at,
                status_id, status_name,
                manager_id, manager_name,
                grand_total, prp_date,
                scraped_at, updated_at
            ) VALUES (
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s
            )
        """
        
        params = (
            order_data['id'],
            utc_to_kyiv(order_data['created_at']),
            utc_to_kyiv(order_data.get('closed_at')),
            order_data['status_id'],
            order_data['status_name'],
            order_data['manager_id'],
            order_data['manager_name'],
            order_data['grand_total'],
            order_data.get('prp_date'),
            now_kyiv(),
            now_kyiv()
        )
        
        try:
            self.db.execute(query, params)
            pass
        except Exception as e:
            raise
            raise
    
    def update_order(self, order_data: Dict[str, Any]) -> None:
        query = """
            UPDATE orders SET
                created_at = %s,
                closed_at = %s,
                status_id = %s,
                status_name = %s,
                manager_id = %s,
                manager_name = %s,
                grand_total = %s,
                prp_date = %s,
                updated_at = %s
            WHERE id = %s
        """
        
        params = (
            utc_to_kyiv(order_data['created_at']),
            utc_to_kyiv(order_data.get('closed_at')),
            order_data['status_id'],
            order_data['status_name'],
            order_data['manager_id'],
            order_data['manager_name'],
            order_data['grand_total'],
            order_data.get('prp_date'),
            now_kyiv(),
            order_data['id']
        )
        
        try:
            self.db.execute(query, params)
            pass
        except Exception as e:
            raise
            raise
    
    def upsert_order(self, order_data: Dict[str, Any]) -> str:
        if self.order_exists(order_data['id']):
            self.update_order(order_data)
            return 'updated'
        else:
            self.insert_order(order_data)
            return 'inserted'
    
    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM orders WHERE id = %s"
        return self.db.fetchone(query, (order_id,))
    
    def get_all_orders(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM orders ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        return self.db.fetchall(query)
    
    def get_orders_by_status(self, status_id: int) -> List[Dict[str, Any]]:
        query = "SELECT * FROM orders WHERE status_id = %s ORDER BY created_at DESC"
        return self.db.fetchall(query, (status_id,))
    
    def get_orders_by_manager(self, manager_id: int) -> List[Dict[str, Any]]:
        query = "SELECT * FROM orders WHERE manager_id = %s ORDER BY created_at DESC"
        return self.db.fetchall(query, (manager_id,))
    
    def get_orders_with_prp(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM orders WHERE prp_date IS NOT NULL ORDER BY prp_date DESC"
        return self.db.fetchall(query)
    
    def get_orders_without_prp(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM orders WHERE prp_date IS NULL ORDER BY created_at DESC"
        return self.db.fetchall(query)
    
    def get_statistics(self) -> Dict[str, Any]:
        stats = {}
        
        query = "SELECT COUNT(*) as total FROM orders"
        result = self.db.fetchone(query)
        stats['total_orders'] = result['total'] if result else 0
        
        query = "SELECT COUNT(*) as total FROM orders WHERE prp_date IS NOT NULL"
        result = self.db.fetchone(query)
        stats['orders_with_prp'] = result['total'] if result else 0
        
        query = "SELECT COUNT(*) as total FROM orders WHERE prp_date IS NULL"
        result = self.db.fetchone(query)
        stats['orders_without_prp'] = result['total'] if result else 0
        
        query = "SELECT SUM(grand_total) as total FROM orders"
        result = self.db.fetchone(query)
        stats['total_amount'] = float(result['total']) if result and result['total'] else 0.0
        
        query = "SELECT MAX(scraped_at) as last_scraped FROM orders"
        result = self.db.fetchone(query)
        stats['last_scraped'] = result['last_scraped'] if result else None
        
        return stats
    
    def delete_order(self, order_id: int) -> None:
        query = "DELETE FROM orders WHERE id = %s"
        self.db.execute(query, (order_id,))
        pass
    
    def truncate_table(self) -> None:
        query = "TRUNCATE TABLE orders"
        self.db.execute(query)
    
    def batch_upsert_orders(self, orders_data: List[Dict[str, Any]]) -> Dict[str, int]:
        if not orders_data:
            return {'inserted': 0, 'updated': 0, 'errors': 0}
        
        query = """
            INSERT INTO orders (
                id, created_at, closed_at,
                status_id, status_name,
                manager_id, manager_name,
                grand_total, prp_date,
                scraped_at, updated_at
            ) VALUES %s ON CONFLICT (id) DO UPDATE SET
                created_at = EXCLUDED.created_at,
                closed_at = EXCLUDED.closed_at,
                status_id = EXCLUDED.status_id,
                status_name = EXCLUDED.status_name,
                manager_id = EXCLUDED.manager_id,
                manager_name = EXCLUDED.manager_name,
                grand_total = EXCLUDED.grand_total,
                prp_date = EXCLUDED.prp_date,
                updated_at = EXCLUDED.updated_at
        """
        
        now = now_kyiv()
        params_list = []
        errors = 0
        
        for order_data in orders_data:
            try:
                params = (
                    order_data['id'],
                    utc_to_kyiv(order_data['created_at']),
                    utc_to_kyiv(order_data.get('closed_at')),
                    order_data['status_id'],
                    order_data['status_name'],
                    order_data['manager_id'],
                    order_data['manager_name'],
                    order_data['grand_total'],
                    order_data.get('prp_date'),
                    now,
                    now
                )
                params_list.append(params)
            except Exception as e:
                errors += 1
                pass
        
        if params_list:
            try:
                self.db.execute_batch(query, params_list)
                pass
            except Exception as e:
                errors += len(params_list)
                pass
        
        return {'inserted': 0, 'updated': len(params_list) - errors, 'errors': errors}


class MaketPushQueries:
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
    
    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM maket_push WHERE id = %s"
        return self.db.fetchone(query, (order_id,))
    
    def insert_maket_push(self, order_data: Dict[str, Any]) -> None:
        tg_push = True if order_data['status_id'] == 23 else None
        
        query = """
            INSERT INTO maket_push (
                id, created_at, closed_at,
                status_id, status_name,
                manager_id, manager_name,
                tg_push,
                scraped_at, updated_at
            ) VALUES (
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s
            )
        """
        
        params = (
            order_data['id'],
            utc_to_kyiv(order_data['created_at']),
            utc_to_kyiv(order_data.get('closed_at')),
            order_data['status_id'],
            order_data['status_name'],
            order_data['manager_id'],
            order_data['manager_name'],
            tg_push,
            now_kyiv(),
            now_kyiv()
        )
        
        try:
            self.db.execute(query, params)
        except Exception as e:
            raise
    
    def update_maket_push(self, order_data: Dict[str, Any]) -> None:
        existing = self.get_order_by_id(order_data['id'])
        
        if existing:
            old_status_id = existing.get('status_id')
            new_status_id = order_data['status_id']
            
            if old_status_id == new_status_id:
                return
            
            if new_status_id == 23:
                tg_push = True
            else:
                tg_push = existing.get('tg_push')
        else:
            tg_push = True if order_data['status_id'] == 23 else None
        
        query = """
            UPDATE maket_push SET
                created_at = %s,
                closed_at = %s,
                status_id = %s,
                status_name = %s,
                manager_id = %s,
                manager_name = %s,
                tg_push = %s,
                updated_at = %s
            WHERE id = %s
        """
        
        params = (
            utc_to_kyiv(order_data['created_at']),
            utc_to_kyiv(order_data.get('closed_at')),
            order_data['status_id'],
            order_data['status_name'],
            order_data['manager_id'],
            order_data['manager_name'],
            tg_push,
            now_kyiv(),
            order_data['id']
        )
        
        try:
            self.db.execute(query, params)
        except Exception as e:
            raise
    
    def upsert_maket_push(self, order_data: Dict[str, Any]) -> str:
        existing = self.get_order_by_id(order_data['id'])
        
        if existing:
            old_status_id = existing.get('status_id')
            new_status_id = order_data['status_id']
            
            if old_status_id == new_status_id:
                return 'skipped'
            
            self.update_maket_push(order_data)
            return 'updated'
        else:
            self.insert_maket_push(order_data)
            return 'inserted'
    
    def get_all_maket_push(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM maket_push ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        return self.db.fetchall(query)
    
    def get_maket_push_ready(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM maket_push WHERE tg_push = TRUE ORDER BY created_at DESC"
        return self.db.fetchall(query)
    
    def get_statistics(self) -> Dict[str, Any]:
        stats = {}
        
        query = "SELECT COUNT(*) as total FROM maket_push"
        result = self.db.fetchone(query)
        stats['total_maket_push'] = result['total'] if result else 0
        
        query = "SELECT COUNT(*) as total FROM maket_push WHERE tg_push = TRUE"
        result = self.db.fetchone(query)
        stats['tg_push_ready'] = result['total'] if result else 0
        
        query = "SELECT MAX(scraped_at) as last_scraped FROM maket_push"
        result = self.db.fetchone(query)
        stats['last_scraped'] = result['last_scraped'] if result else None
        
        return stats
    
    def batch_upsert_maket_push(self, orders_data: List[Dict[str, Any]]) -> Dict[str, int]:
        if not orders_data:
            return {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0
        
        for order_data in orders_data:
            try:
                result = self.upsert_maket_push(order_data)
                if result == 'inserted':
                    inserted += 1
                elif result == 'updated':
                    updated += 1
                elif result == 'skipped':
                    skipped += 1
            except Exception as e:
                errors += 1
        
        return {'inserted': inserted, 'updated': updated, 'skipped': skipped, 'errors': errors}
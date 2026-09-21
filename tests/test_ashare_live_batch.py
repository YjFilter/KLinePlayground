from __future__ import annotations
import unittest
from backend.app_enhanced import app

class AshareLiveBatchApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_batch_quotes_api(self):
        resp = self.client.get('/api/ashare/live/batch?symbols=600519,300750,000001')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 2)
        codes = [item['code'] for item in data]
        self.assertIn('600519', codes)
        for item in data:
            self.assertIn('name', item)
            self.assertIn('price', item)
            self.assertIn('change_percent', item)
            self.assertIn('symbol', item)
            self.assertGreater(item['price'], 0)

    def test_sh000001_vs_sz000001_distinction(self):
        """sh000001 must return Shanghai Composite Index, while sz000001 returns Ping An Bank."""
        from backend.services.ashare_live_service import get_secid, get_realtime_snapshot
        self.assertEqual(get_secid('sh000001'), '1.000001')
        self.assertEqual(get_secid('sz000001'), '0.000001')

        # Snapshot for Shanghai Index
        snap_sh = self.client.get('/api/ashare/live/snapshot?symbol=sh000001').get_json()
        self.assertEqual(snap_sh.get('symbol'), 'sh000001')
        self.assertIn('上证指数', snap_sh.get('name', ''))
        self.assertGreater(snap_sh.get('price', 0), 1000)

        # Snapshot for Ping An Bank
        snap_sz = self.client.get('/api/ashare/live/snapshot?symbol=sz000001').get_json()
        self.assertEqual(snap_sz.get('symbol'), 'sz000001')
        self.assertIn('平安银行', snap_sz.get('name', ''))
        self.assertLess(snap_sz.get('price', 0), 100)

    def test_batch_quotes_sh_and_sz_coexistence(self):
        """Batch quotes containing both sh000001 and sz000001 must return both without collision."""
        resp = self.client.get('/api/ashare/live/batch?symbols=sh000001,sz000001')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        sym_map = {item['symbol']: item for item in data}
        self.assertIn('sh000001', sym_map)
        self.assertIn('sz000001', sym_map)
        self.assertIn('上证指数', sym_map['sh000001']['name'])
        self.assertIn('平安银行', sym_map['sz000001']['name'])
        self.assertGreater(sym_map['sh000001']['price'], 1000)
        self.assertLess(sym_map['sz000001']['price'], 100)

    def test_empty_batch(self):
        resp = self.client.get('/api/ashare/live/batch?symbols=')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data, [])

if __name__ == '__main__':
    unittest.main()

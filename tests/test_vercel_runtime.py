import base64
import unittest
from unittest.mock import patch

import backend.app_enhanced as app_module


class VercelRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    @staticmethod
    def _authorization(username, password):
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def test_local_runtime_does_not_require_deployment_auth(self):
        with patch.object(app_module, "is_vercel_runtime", False), patch.object(
            app_module, "deployment_auth_password", "secret"
        ):
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)

    def test_vercel_runtime_rejects_missing_credentials(self):
        with patch.object(app_module, "is_vercel_runtime", True), patch.object(
            app_module, "deployment_auth_password", "secret"
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Basic", response.headers["WWW-Authenticate"])

    def test_health_remains_available_without_credentials(self):
        with patch.object(app_module, "is_vercel_runtime", True), patch.object(
            app_module, "deployment_auth_password", "secret"
        ):
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)

    def test_vercel_runtime_accepts_matching_credentials(self):
        with patch.object(app_module, "is_vercel_runtime", True), patch.object(
            app_module, "deployment_auth_user", "kline"
        ), patch.object(app_module, "deployment_auth_password", "secret"):
            response = self.client.get(
                "/api/health", headers=self._authorization("kline", "secret")
            )
        self.assertEqual(response.status_code, 200)

    def test_successful_user_creation_is_saved_to_cloud(self):
        fake_store = unittest.mock.Mock(enabled=True)
        fake_store.restore_user.return_value = False
        with patch.object(app_module, "cloud_user_store", fake_store), patch.object(
            app_module.user_manager, "user_exists", return_value=False
        ), patch.object(app_module.user_manager, "create_user", return_value=True):
            response = self.client.post("/api/users", json={"username": "cloud-user"})
        self.assertEqual(response.status_code, 200)
        fake_store.save_user.assert_called_once_with("cloud-user")

    def test_cloud_save_failure_turns_mutation_into_503(self):
        fake_store = unittest.mock.Mock(enabled=True)
        fake_store.restore_user.return_value = False
        fake_store.save_user.side_effect = app_module.CloudStateError("database down")
        with patch.object(app_module, "cloud_user_store", fake_store), patch.object(
            app_module.user_manager, "user_exists", return_value=False
        ), patch.object(app_module.user_manager, "create_user", return_value=True):
            response = self.client.post("/api/users", json={"username": "cloud-user"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "cloud_state_persist_failed")


if __name__ == "__main__":
    unittest.main()

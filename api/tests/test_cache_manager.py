import unittest
import os
import json
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from github.cache_manager import CacheManager

class TestCacheManager(unittest.TestCase):
    """Tests for the CacheManager class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock for BlobServiceClient
        self.blob_service_client_mock = MagicMock(spec=BlobServiceClient)
        self.container_client_mock = MagicMock(spec=ContainerClient)
        self.blob_client_mock = MagicMock(spec=BlobClient)
        
        # Set up the mocks chain
        self.blob_service_client_mock.get_container_client.return_value = self.container_client_mock
        self.blob_service_client_mock.get_blob_client.return_value = self.blob_client_mock
        self.container_client_mock.exists.return_value = True
        
        # Create cache manager with the mock
        self.cache_manager = CacheManager(container_name="test-cache")
        self.cache_manager.blob_service_client = self.blob_service_client_mock
    
    def test_init_cache(self):
        """Test initialization of cache."""
        with patch('os.getenv') as getenv_mock:
            # Test with connection string
            getenv_mock.return_value = "mock_connection_string"
            with patch('github.cache_manager.BlobServiceClient') as blob_service_client_class_mock:
                blob_service_client_mock = MagicMock()
                blob_service_client_class_mock.from_connection_string.return_value = blob_service_client_mock
                
                cache_manager = CacheManager()
                
                blob_service_client_class_mock.from_connection_string.assert_called_with("mock_connection_string")
                blob_service_client_mock.create_container.assert_called_once()
            
            # Test without connection string
            getenv_mock.return_value = None
            cache_manager = CacheManager()
            self.assertIsNone(cache_manager.blob_service_client)
    
    def test_get_cache_hit(self):
        """Test retrieving data from cache when it exists and is valid."""
        # Mock the blob client to simulate a cache hit
        self.blob_client_mock.exists.return_value = True
        
        # Set up properties mock
        properties_mock = MagicMock()
        properties_mock.metadata = {
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        properties_mock.last_modified = datetime.now()
        properties_mock.size = 1024
        self.blob_client_mock.get_blob_properties.return_value = properties_mock
        
        # Mock the downloaded data
        download_blob_mock = MagicMock()
        download_blob_mock.readall.return_value = json.dumps({
            'data': {'test': 'data'}
        })
        self.blob_client_mock.download_blob.return_value = download_blob_mock
        
        # Get from cache
        result = self.cache_manager.get("test_key")
        
        # Verify
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['data'], {'test': 'data'})
    
    
    def test_get_no_expiry(self):
        """Test retrieving data from cache that has no expiration."""
        # Mock the blob client for non-expiring cache
        self.blob_client_mock.exists.return_value = True
        
        # Set up properties mock
        properties_mock = MagicMock()
        properties_mock.metadata = {
            'no_expiry': 'True'
        }
        properties_mock.last_modified = datetime.now()
        properties_mock.size = 1024
        self.blob_client_mock.get_blob_properties.return_value = properties_mock
        
        # Mock the downloaded data
        download_blob_mock = MagicMock()
        download_blob_mock.readall.return_value = json.dumps({
            'data': {'test': 'data'}
        })
        self.blob_client_mock.download_blob.return_value = download_blob_mock
        
        # Get from cache
        result = self.cache_manager.get("test_key")
        
        # Verify
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['data'], {'test': 'data'})
        self.assertTrue(result.get('no_expiry'))
    
    
    def test_save_no_expiry(self):
        """Test saving data to cache with no expiration."""
        # Call save with None ttl
        success = self.cache_manager.save("test_key", {"test": "data"}, ttl=None)
        
        # Verify
        self.assertTrue(success)
        self.blob_client_mock.upload_blob.assert_called_once()
        
        # Verify the uploaded content
        args, kwargs = self.blob_client_mock.upload_blob.call_args
        self.assertIn('metadata', kwargs)
        self.assertIn('no_expiry', kwargs['metadata'])
        self.assertEqual(kwargs['metadata']['no_expiry'], 'True')
    
    def test_delete(self):
        """Test deleting data from cache."""
        # Mock blob exists
        self.blob_client_mock.exists.return_value = True
        
        # Call delete
        success = self.cache_manager.delete("test_key")
        
        # Verify
        self.assertTrue(success)
        self.blob_client_mock.delete_blob.assert_called_once()
    
    def test_cache_decorator(self):
        """Test the cache decorator."""
        # Set up the cache miss then hit scenario
        self.blob_client_mock.exists.side_effect = [False, True]
        
        # For the cache hit case
        properties_mock = MagicMock()
        properties_mock.metadata = {
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        properties_mock.last_modified = datetime.now()
        properties_mock.size = 1024
        self.blob_client_mock.get_blob_properties.return_value = properties_mock
        
        # Mock the downloaded data for the hit
        download_blob_mock = MagicMock()
        download_blob_mock.readall.return_value = json.dumps({
            'data': {'cached': True, 'value': 42}
        })
        self.blob_client_mock.download_blob.return_value = download_blob_mock
        
        # Define a test function and key generator
        def key_func(x):
            return f"test:{x}"
        
        function_called = [0]  # Use list for mutable counter
        
        @self.cache_manager.cache_decorator(cache_key_func=key_func, ttl=3600)
        def test_function(x):
            function_called[0] += 1
            return {'cached': False, 'value': x}
        
        # First call - should miss cache and call function
        result1 = test_function(42)
        self.assertEqual(result1, {'cached': False, 'value': 42})
        self.assertEqual(function_called[0], 1)
        
        # Second call - should hit cache and not call function
        result2 = test_function(42)
        self.assertEqual(result2, {'cached': True, 'value': 42})
        self.assertEqual(function_called[0], 1)  # Still 1, function not called again
    

if __name__ == "__main__":
    unittest.main()

"""
Service-level tests for Celery worker tasks.

Tests cover:
- Task function structure and signatures
- Task registration with Celery
- Basic parameter validation
"""
import pytest
from worker_service.tasks.prepopulate_db import pre_populate_keys
from worker_service.tasks.remove_expired_keys import remove_expired_keys
from worker_service.celery_app import celery_app


# ============================================
# Task Registration Tests
# ============================================

@pytest.mark.unit
def test_pre_populate_keys_task_registered():
    """Test that pre_populate_keys is registered with Celery"""
    assert "pre_populate_keys" in celery_app.tasks
    task = celery_app.tasks["pre_populate_keys"]
    assert task.name == "pre_populate_keys"


@pytest.mark.unit
def test_remove_expired_keys_callable():
    """Test that remove_expired_keys is callable"""
    assert callable(remove_expired_keys)


# ============================================
# Task Function Properties Tests
# ============================================

@pytest.mark.unit
def test_pre_populate_keys_has_task_decorators():
    """Test that pre_populate_keys has Celery task decorators"""
    # Check if it's a proper Celery Task object
    assert hasattr(pre_populate_keys, 'name')
    assert pre_populate_keys.name == "pre_populate_keys"
    assert hasattr(pre_populate_keys, 'max_retries')
    assert pre_populate_keys.max_retries == 3


@pytest.mark.unit
def test_remove_expired_keys_has_task_decorators():
    """Test that remove_expired_keys has Celery task decorators"""
    # Check if it's a proper Celery Task object
    assert hasattr(remove_expired_keys, 'name')
    assert remove_expired_keys.name == "remove_expired_keys"
    assert hasattr(remove_expired_keys, 'max_retries')
    assert remove_expired_keys.max_retries == 3


# ============================================
# Task Configuration Tests
# ============================================

@pytest.mark.unit
def test_celery_app_configuration():
    """Test Celery app configuration for async tasks"""
    assert celery_app.conf.task_serializer == 'json'
    assert celery_app.conf.accept_content == ['json']
    assert celery_app.conf.result_serializer == 'json'
    assert celery_app.conf.timezone == 'UTC'
    assert celery_app.conf.enable_utc is True
    assert celery_app.conf.worker_prefetch_multiplier == 1


@pytest.mark.unit
def test_periodic_task_schedule():
    """Test that periodic task is configured"""
    assert "populate-keys-periodic" in celery_app.conf.beat_schedule
    schedule = celery_app.conf.beat_schedule["populate-keys-periodic"]
    assert schedule["task"] == "pre_populate_keys"
    assert schedule["args"] == ()


@pytest.mark.unit
def test_task_retry_configuration():
    """Test that tasks have proper retry configuration"""
    # Check pre_populate_keys retry settings
    assert pre_populate_keys.autoretry_for == (Exception,)
    assert pre_populate_keys.retry_backoff is True
    assert pre_populate_keys.retry_jitter is True

    # Check remove_expired_keys retry settings
    assert remove_expired_keys.autoretry_for == (Exception,)
    assert remove_expired_keys.retry_backoff is True
    assert remove_expired_keys.retry_jitter is True
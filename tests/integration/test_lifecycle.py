from __future__ import annotations

import pytest

from wrenn import Capsule
from wrenn.models import Capsule as CapsuleModel, Status

pytestmark = pytest.mark.integration


class TestCapsuleLifecycle:
    """Each test manages its own capsule to test create/destroy paths."""

    def test_create_and_destroy(self):
        capsule = Capsule()
        capsule_id = capsule.capsule_id
        try:
            assert capsule_id
            assert capsule.info is not None
        finally:
            capsule.destroy()

        info = Capsule.get_info(capsule_id)
        assert info.status in (Status.stopped, Status.missing)

    def test_create_with_wait(self):
        capsule = Capsule(wait=True)
        try:
            assert capsule.info is not None
            assert capsule.info.status == Status.running
        finally:
            capsule.destroy()

    def test_context_manager_destroys(self):
        with Capsule(wait=True) as capsule:
            capsule_id = capsule.capsule_id
            assert capsule.is_running()

        info = Capsule.get_info(capsule_id)
        assert info.status in (Status.stopped, Status.missing)

    def test_get_info(self):
        capsule = Capsule(wait=True)
        try:
            info = capsule.get_info()
            assert isinstance(info, CapsuleModel)
            assert info.id == capsule.capsule_id
            assert info.status == Status.running
        finally:
            capsule.destroy()

    def test_pause_and_resume(self):
        capsule = Capsule(wait=True)
        try:
            paused = capsule.pause()
            assert paused.status == Status.paused
            assert not capsule.is_running()

            resumed = capsule.resume()
            assert resumed.status == Status.running
        finally:
            capsule.destroy()

    def test_static_destroy(self):
        capsule = Capsule(wait=True)
        capsule_id = capsule.capsule_id
        try:
            Capsule.destroy(capsule_id)
        except Exception:
            capsule.destroy()
            raise

        info = Capsule.get_info(capsule_id)
        assert info.status in (Status.stopped, Status.missing)

    def test_connect_to_existing(self):
        capsule = Capsule(wait=True)
        try:
            connected = Capsule.connect(capsule.capsule_id)
            assert connected.capsule_id == capsule.capsule_id
            assert connected.info is not None
            assert connected.info.status == Status.running
        finally:
            capsule.destroy()

    def test_connect_resumes_paused(self):
        capsule = Capsule(wait=True)
        try:
            capsule.pause()
            connected = Capsule.connect(capsule.capsule_id)
            assert connected.info is not None
            assert connected.info.status == Status.running
        finally:
            capsule.destroy()

    def test_list_capsules(self):
        capsule = Capsule(wait=True)
        try:
            capsules = Capsule.list()
            assert isinstance(capsules, list)
            ids = [c.id for c in capsules]
            assert capsule.capsule_id in ids
        finally:
            capsule.destroy()

    def test_wait_ready(self):
        capsule = Capsule()
        try:
            capsule.wait_ready(timeout=60)
            assert capsule.is_running()
        finally:
            capsule.destroy()

    def test_ping(self):
        capsule = Capsule(wait=True)
        try:
            capsule.ping()
        finally:
            capsule.destroy()
